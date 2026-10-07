"""Admin-only deployment bundle planning and staging."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import fnmatch
import os
from pathlib import Path
import threading
import uuid
import zipfile

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_login import current_user


deploy_bp = Blueprint("deployments", __name__)
_PLAN_LOCK = threading.Lock()
_DEPLOY_PLANS: dict[str, dict[str, object]] = {}
_PLAN_TTL = timedelta(minutes=10)
_SUPPORTED_TARGETS = {
    "local": "Local Windows/Linux",
    "wsl": "WSL",
    "wsl2": "WSL2",
    "usb": "USB drive",
}
_FUTURE_TARGETS = (
    "Remote server (SSH)",
    "Hyper-V",
    "Docker",
    "AKS",
    "Render",
    "PyPI",
    "WPF",
    "EXE",
)
_EXCLUDED_DIRECTORIES = {
    ".git", ".venv", "venv", "venv310", "__pycache__", "node_modules",
    "build", "dist", "data", "logs", "backup", "backups", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", "htmlcov",
}
_EXCLUDED_FILE_PATTERNS = (
    ".env",
    ".env.*",
    "*.log",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.tfstate",
    "*.tfstate.*",
    "*.pyc",
    "*.gguf",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.pypirc",
    ".pyirc*",
    "*backup*",
    "*credentials*.json",
    "service-account*.json",
)


def _is_admin() -> bool:
    try:
        return bool(
            current_user.is_authenticated
            and getattr(current_user, "provider", None) == "rbac"
            and str(getattr(current_user, "role", "") or "").casefold() == "admin"
            and "*" in (getattr(current_user, "permissions", None) or [])
        )
    except (AttributeError, RuntimeError):
        return False


def _admin_required():
    if not _is_admin():
        return jsonify({"ok": False, "error": "An authenticated RBAC admin account is required."}), 403
    return None


def _source_root() -> Path:
    root = Path(current_app.config.get("DEPLOY_SOURCE_ROOT", Path(__file__).resolve().parents[1]))
    return root.resolve()


def _safe_destination(raw_destination: object, source_root: Path) -> Path:
    if not isinstance(raw_destination, str) or not raw_destination.strip() or len(raw_destination) > 1000:
        raise ValueError("Choose an absolute destination directory.")
    destination = Path(raw_destination.strip()).expanduser()
    if not destination.is_absolute():
        raise ValueError("Destination must be an absolute path.")
    destination = destination.resolve()
    try:
        destination.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise ValueError("Choose a destination outside the MasterChief source directory.")

    existing_parent = destination
    while not existing_parent.exists() and existing_parent != existing_parent.parent:
        existing_parent = existing_parent.parent
    if not existing_parent.is_dir():
        raise ValueError("The destination or its nearest existing parent must be a directory.")
    if not os.access(existing_parent, os.W_OK):
        raise ValueError("The destination parent is not writable by the MasterChief process.")
    if destination.exists() and not destination.is_dir():
        raise ValueError("The destination path exists and is not a directory.")
    return destination


def _is_excluded(relative_path: Path) -> bool:
    if any(part.casefold() in _EXCLUDED_DIRECTORIES for part in relative_path.parts[:-1]):
        return True
    if tuple(part.casefold() for part in relative_path.parts[:2]) == ("config", "environments"):
        return True
    name = relative_path.name.casefold()
    return any(fnmatch.fnmatch(name, pattern.casefold()) for pattern in _EXCLUDED_FILE_PATTERNS)


def _collect_files(source_root: Path) -> list[tuple[Path, int, int]]:
    files = []
    for current, directories, filenames in os.walk(source_root, followlinks=False):
        current_path = Path(current)
        directories[:] = [
            name for name in directories
            if name.casefold() not in _EXCLUDED_DIRECTORIES
            and not (current_path / name).is_symlink()
            and not name.casefold().endswith(".egg-info")
        ]
        for filename in filenames:
            path = current_path / filename
            relative_path = path.relative_to(source_root)
            if _is_excluded(relative_path) or path.is_symlink():
                continue
            try:
                stat = path.stat(follow_symlinks=False)
            except OSError as exc:
                raise ValueError(f"Could not inspect source file {relative_path}: {exc}") from exc
            if not path.is_file():
                continue
            files.append((relative_path, stat.st_size, stat.st_mtime_ns))
    if not files:
        raise ValueError("No eligible application source files were found to bundle.")
    return files


def _purge_expired_plans() -> None:
    cutoff = datetime.now(timezone.utc) - _PLAN_TTL
    for plan_id, plan in list(_DEPLOY_PLANS.items()):
        if plan["created_at"] < cutoff:
            _DEPLOY_PLANS.pop(plan_id, None)


@deploy_bp.get("/deploy-center")
def deploy_center_page():
    denied = _admin_required()
    if denied:
        return denied
    return send_file(Path(__file__).resolve().parents[1] / "deploy_center.html")


@deploy_bp.get("/api/deployments/capabilities")
def deployment_capabilities():
    denied = _admin_required()
    if denied:
        return denied
    targets = [
        {"id": target_id, "name": name, "available": True, "operation": "Create a confirmed source bundle"}
        for target_id, name in _SUPPORTED_TARGETS.items()
    ]
    targets.extend(
        {"id": name.casefold().replace(" ", "-"), "name": name, "available": False, "operation": "Not executable yet"}
        for name in _FUTURE_TARGETS
    )
    return jsonify({"ok": True, "targets": targets})


@deploy_bp.post("/api/deployments/preview")
def deployment_preview():
    denied = _admin_required()
    if denied:
        return denied
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "Provide a JSON deployment plan."}), 400
    target = body.get("target")
    if target not in _SUPPORTED_TARGETS:
        return jsonify({"ok": False, "error": "Choose an available deployment target."}), 400

    source_root = _source_root()
    if not source_root.is_dir():
        current_app.logger.error("Deployment source directory is missing: %s", source_root)
        return jsonify({"ok": False, "error": "MasterChief source directory is unavailable."}), 500
    try:
        destination = _safe_destination(body.get("destination"), source_root)
        files = _collect_files(source_root)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    plan_id = uuid.uuid4().hex
    plan = {
        "id": plan_id,
        "target": target,
        "destination": str(destination),
        "files": files,
        "created_at": datetime.now(timezone.utc),
    }
    with _PLAN_LOCK:
        _purge_expired_plans()
        _DEPLOY_PLANS[plan_id] = plan

    return jsonify({
        "ok": True,
        "plan": {
            "id": plan_id,
            "target": _SUPPORTED_TARGETS[target],
            "destination": str(destination),
            "file_count": len(files),
            "size_bytes": sum(size for _, size, _ in files),
            "expires_in_seconds": int(_PLAN_TTL.total_seconds()),
            "exclusions": ["runtime data", "secrets", "virtual environments", "builds and caches"],
        },
    })


@deploy_bp.post("/api/deployments/execute")
def deployment_execute():
    denied = _admin_required()
    if denied:
        return denied
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or body.get("confirmed") is not True:
        return jsonify({"ok": False, "error": "Explicit confirmation is required before staging a bundle."}), 400
    plan_id = body.get("plan_id")
    if not isinstance(plan_id, str):
        return jsonify({"ok": False, "error": "A valid deployment preview is required."}), 400
    with _PLAN_LOCK:
        _purge_expired_plans()
        plan = _DEPLOY_PLANS.get(plan_id)
    if not plan:
        return jsonify({"ok": False, "error": "Deployment preview expired or was not found. Create a new preview."}), 404

    source_root = _source_root()
    destination = Path(str(plan["destination"]))
    files = plan["files"]
    try:
        for relative_path, expected_size, expected_mtime in files:
            source_file = source_root / relative_path
            stat = source_file.stat(follow_symlinks=False)
            if source_file.is_symlink() or not source_file.is_file():
                raise ValueError(f"Source file changed after preview: {relative_path}")
            if stat.st_size != expected_size or stat.st_mtime_ns != expected_mtime:
                raise ValueError(f"Source file changed after preview: {relative_path}")

        destination.mkdir(parents=True, exist_ok=True)
        filename = f"MasterChief-{plan['target']}-{plan_id[:8]}.zip"
        bundle_path = destination / filename
        with zipfile.ZipFile(bundle_path, mode="x", compression=zipfile.ZIP_DEFLATED) as bundle:
            for relative_path, _, _ in files:
                source_file = source_root / relative_path
                if source_file.is_symlink():
                    raise ValueError(f"Source file changed after preview: {relative_path}")
                bundle.write(source_file, arcname=relative_path.as_posix())
    except FileExistsError:
        return jsonify({"ok": False, "error": "A bundle with that name already exists; create a new preview."}), 409
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        if "bundle_path" in locals() and bundle_path.exists():
            bundle_path.unlink()
        current_app.logger.exception("Deployment bundle staging failed.")
        return jsonify({"ok": False, "error": f"Could not stage the deployment bundle: {exc}"}), 500

    with _PLAN_LOCK:
        _DEPLOY_PLANS.pop(plan_id, None)
    return jsonify({
        "ok": True,
        "result": {
            "target": _SUPPORTED_TARGETS[str(plan["target"])],
            "bundle": str(bundle_path),
            "file_count": len(files),
            "message": "Bundle staged only; no application was installed, started, or deployed to cloud infrastructure.",
        },
    })

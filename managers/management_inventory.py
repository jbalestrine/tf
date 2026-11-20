"""Read-only inventory of the platform's separate management systems."""
import json
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from managers import feature_loader
from managers.code_manager import CodeManager
from utils.feature_flags import DEFAULT_FEATURE_FLAGS


def build_inventory(app, root, feature_manager, modules, managers, startup_features):
    root = Path(root)
    rows = []
    if feature_manager is None:
        raise RuntimeError("The configured feature manager is unavailable.")

    for name, config in sorted(feature_manager.feature_configs.items()):
        startup = startup_features.get(name)
        rows.append({
            "kind": "Configured feature", "name": config.display_name, "key": name,
            "configured": "enabled" if config.enabled else "disabled",
            "runtime": ("not present at startup" if startup is None else
                        "enabled at startup" if startup else "disabled at startup"),
            "detail": "Handler registration is not verified. Changes require a restart.",
            "url": "/features",
        })

    flags_path = root / feature_loader.FLAGS_REL
    flags = json.loads(flags_path.read_text(encoding="utf-8")) if flags_path.exists() else {}
    if not isinstance(flags, dict) or any(not isinstance(value, bool) for value in flags.values()):
        raise ValueError("Feature flags must be a JSON object of boolean values.")
    features_dir = root / feature_loader.FEATURES_DIR
    if features_dir.is_dir():
        for directory in features_dir.iterdir():
            manifest = directory / "feature.json"
            if directory.is_dir() and manifest.is_file():
                data = json.loads(manifest.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError(f"Feature manifest for {directory.name} must be an object.")
    loaded = {item["slug"]: item for item in app.config.get("_features", [])}
    features = feature_loader.discover(root)
    for info in features:
        state = loaded.get(info["slug"])
        enabled = True if info["core"] else flags.get(info["slug"], info["enabled_default"])
        rows.append({
            "kind": "App feature", "name": info["title"], "key": info["slug"],
            "configured": "core" if info["core"] else ("enabled" if enabled else "disabled"),
            "runtime": state["state"] if state else "not loaded at startup",
            "detail": (state.get("error") if state and state.get("error") else
                       "Manage in Code Manager; changes require a restart."),
            "url": "/ext/code_manager/",
        })

    feature_slugs = {info["slug"] for info in features}
    for name in sorted(set(DEFAULT_FEATURE_FLAGS) | (set(flags) - feature_slugs)):
        enabled = flags.get(name, DEFAULT_FEATURE_FLAGS.get(name))
        rows.append({
            "kind": "Page flag" if name in DEFAULT_FEATURE_FLAGS else "Unclassified flag",
            "name": name, "key": name,
            "configured": "enabled" if enabled else "disabled",
            "runtime": "effect not verified",
            "detail": ("Used by the page/menu flag system where wired; this does not prove a component is loaded."
                       if name in DEFAULT_FEATURE_FLAGS else
                       "Stored flag is not recognized as a default page flag or discovered app feature."),
            "url": "/master-menu",
        })

    registry_path = root / "data" / "features.json"
    if registry_path.exists():
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if not isinstance(registry, dict):
            raise ValueError("Stored add-on feature registry must be an object.")
        for key, entry in sorted(registry.items()):
            if not isinstance(entry, dict):
                raise ValueError(f"Stored add-on feature {key} must be an object.")
            rows.append({
                "kind": "Stored add-on feature", "name": str(entry.get("label") or key),
                "key": key, "configured": "enabled" if entry.get("enabled") else "disabled",
                "runtime": "not verified",
                "detail": "Historical registry entry; its add-on or action may no longer be present.",
                "url": "/addons/modules",
            })

    for name, config in sorted(modules.items()):
        loaded_manager = managers.get(name)
        rows.append({
            "kind": "Built-in module", "name": name, "key": name,
            "configured": "enabled" if config.get("enabled") else "disabled",
            "runtime": "manager present" if loaded_manager is not None else "manager not present",
            "detail": "Configuration changes require a restart; registered routes may remain until then.",
            "url": "/modules",
        })

    linked_path = root / feature_loader.LINKED_REL
    if linked_path.exists():
        linked = json.loads(linked_path.read_text(encoding="utf-8"))
        if not isinstance(linked, dict) or not isinstance(linked.get("linked"), list):
            raise ValueError("Linked blueprint configuration must contain a list.")
    for item in CodeManager(app, root).blueprints():
        rows.append({
            "kind": "Blueprint", "name": item["module"], "key": item["module"],
            "configured": "linked" if item["linked"] else "not linked",
            "runtime": "registered" if item["registered"] else "not registered",
            "detail": item.get("error") or f"Source classification: {item['kind']}.",
            "url": "/ext/code_manager/",
        })

    addon_roots = [Path(app.config["UPLOAD_FOLDER"]) / "extracted",
                   root / ".claude" / "worktrees" / "cool-elbakyan" / "data" / "uploads" / "extracted"]
    services = app.config.get("running_services", {})
    for base in addon_roots:
        if not base.exists():
            continue
        for directory in sorted(base.iterdir(), key=lambda p: p.name.casefold()):
            if not directory.is_dir():
                continue
            service = services.get(directory.name) if base == addon_roots[0] else None
            if service and service.get("type") == "blueprint":
                runtime = "blueprint registered"
            elif service and service.get("process") and service["process"].poll() is None:
                runtime = "process running (readiness not checked)"
            else:
                runtime = "not tracked as running"
            rows.append({
                "kind": "Add-on folder", "name": directory.name, "key": directory.name,
                "configured": "discovered",
                "runtime": runtime,
                "detail": ("Primary add-on folder; launchability is not verified." if base == addon_roots[0]
                           else "Alternate worktree folder; launch support is not verified."),
                "url": "/addons/modules",
            })
    return rows


def register_inventory(app, root, feature_manager, modules, managers, admin_guard):
    startup_features = ({name: bool(config.enabled)
                         for name, config in feature_manager.feature_configs.items()}
                        if feature_manager is not None else {})
    bp = Blueprint("management_inventory", __name__)

    @bp.get("/api/management/inventory")
    def inventory():
        denied = admin_guard(True)
        if denied is not None:
            return denied
        try:
            rows = build_inventory(current_app, root, feature_manager, modules, managers, startup_features)
        except (OSError, ValueError, RuntimeError) as exc:
            current_app.logger.exception("Unable to build management inventory")
            return jsonify({"ok": False, "error": f"Unable to build inventory: {exc}"}), 500
        return jsonify({"ok": True, "items": rows})

    app.register_blueprint(bp)

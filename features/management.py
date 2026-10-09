"""Extra Feature Management API: detail, edit, delete, duplicate, export/import, health and activity log."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from importlib import metadata
from pathlib import Path

from flask import current_app, jsonify, request

NAME_RE = re.compile(r"[a-z][a-z0-9_-]{1,63}")
VERSION_RE = re.compile(r"^\d+(\.\d+){0,3}([.\-+][0-9A-Za-z.]+)?$")
MAX_CODE = 128 * 1024
MAX_ACTIVITY = 200
PIP_SPEC_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9,._-]+\])?((==|>=|<=|~=|!=|>|<)[A-Za-z0-9.*+!_-]+(,(==|>=|<=|~=|!=|>|<)[A-Za-z0-9.*+!_-]+)*)?$")
HANDLER_STUB = '''"""Handler for the {name} feature."""


def register_routes(app):
    pass
'''


def _dep_name(spec: str) -> str:
    return re.split(r"[<>=!~\[; ]", spec.strip(), maxsplit=1)[0]


def _dep_status(spec: str) -> dict:
    name = _dep_name(spec)
    try:
        return {"name": spec, "installed": True, "version": metadata.version(name)}
    except metadata.PackageNotFoundError:
        return {"name": spec, "installed": False, "version": ""}


class FeatureManagement:
    def __init__(self, manager):
        self.m = manager
        self.dir: Path = manager.features_dir
        self.trash = self.dir / "trash"
        self.activity_file = self.dir / "activity.json"

    # ---------- helpers ----------
    def _guard(self, mutating=True):
        if not mutating:
            return None
        if not self.m._is_admin_request():
            return jsonify({"success": False, "error": "RBAC platform admin permission required"}), 403
        if not self.m._is_same_origin_request():
            return jsonify({"success": False, "error": "same-origin request required"}), 403
        return None

    def _handler_path(self, name: str) -> Path:
        return self.dir / "handlers" / f"{name.replace('-', '_')}.py"

    def _log(self, action: str, name: str, detail: str = "") -> None:
        try:
            items = json.loads(self.activity_file.read_text(encoding="utf-8")) if self.activity_file.exists() else []
        except (OSError, ValueError):
            items = []
        try:
            from flask_login import current_user
            actor = str(getattr(current_user, "username", "") or getattr(current_user, "id", "") or "unknown")
        except Exception:
            actor = "unknown"
        items.append({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "action": action, "feature": name, "actor": actor, "detail": detail})
        self.activity_file.write_text(json.dumps(items[-MAX_ACTIVITY:], indent=2), encoding="utf-8")

    def _live_routes(self, cfg) -> list[dict]:
        live = {r.rule for r in self.m.app.url_map.iter_rules()}
        out = []
        for r in cfg.routes or []:
            path = r.get("path", "")
            pattern = re.sub(r"\{(\w+)\}", r"<\1>", path)
            norm = {re.sub(r"<[^>]+>", "<>", rule) for rule in live}
            out.append({**r, "live": re.sub(r"<[^>]+>", "<>", pattern) in norm})
        return out

    def _health(self, cfg) -> dict:
        handler = self._handler_path(cfg.name)
        deps = [_dep_status(d) for d in cfg.dependencies]
        routes = self._live_routes(cfg)
        loaded = cfg.name in self.m.features
        issues = []
        if not handler.exists():
            issues.append("Handler file is missing")
        missing = [d["name"] for d in deps if not d["installed"]]
        if missing:
            issues.append("Missing packages: " + ", ".join(missing))
        if cfg.enabled and not loaded:
            issues.append("Enabled but the handler is not loaded (restart may be required)")
        dead = [r["path"] for r in routes if cfg.enabled and not r["live"]]
        if dead:
            issues.append(f"{len(dead)} declared route(s) are not registered")
        status = "disabled" if not cfg.enabled else ("degraded" if issues else "healthy")
        return {"status": status, "issues": issues, "dependencies": deps, "routes": routes,
                "handler_exists": handler.exists(), "loaded": loaded}

    def _detail(self, cfg, with_code=False) -> dict:
        data = asdict(cfg)
        data["health"] = self._health(cfg)
        handler = self._handler_path(cfg.name)
        if handler.exists():
            data["handler_size"] = handler.stat().st_size
            data["handler_modified"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(handler.stat().st_mtime))
            if with_code:
                data["handler_code"] = handler.read_text(encoding="utf-8")
        return data

    @staticmethod
    def _check_code(name: str, code) -> str | None:
        if not isinstance(code, str) or len(code.encode("utf-8")) > MAX_CODE:
            return "Handler code must be text and no larger than 128 KiB"
        try:
            compile(code, f"<feature:{name}>", "exec")
        except SyntaxError as exc:
            return f"Handler code has a syntax error on line {exc.lineno}: {exc.msg}"
        return None

    @staticmethod
    def _check_meta(data: dict) -> str | None:
        display = str(data.get("display_name") or "").strip()
        if not display or len(display) > 100:
            return "Display name is required (max 100 characters)"
        if len(str(data.get("description") or "")) > 500:
            return "Description is limited to 500 characters"
        if not VERSION_RE.match(str(data.get("version") or "1.0.0")):
            return "Version must look like 1.2.3"
        deps = data.get("dependencies", [])
        if not isinstance(deps, list) or any(not isinstance(d, str) or not d.strip() or len(d) > 100 for d in deps):
            return "Dependencies must be a list of package names"
        return None

    def _backup_handler(self, name: str) -> None:
        handler = self._handler_path(name)
        if handler.exists():
            self.trash.mkdir(exist_ok=True)
            shutil.copy2(handler, self.trash / f"{time.strftime('%Y%m%d-%H%M%S')}__{handler.name}")

    # ---------- routes ----------
    def summary(self):
        cfgs = sorted(self.m.feature_configs.values(), key=lambda c: c.name)
        health = [self._health(c) for c in cfgs]
        return jsonify({"success": True, "summary": {
            "total": len(cfgs),
            "enabled": sum(c.enabled for c in cfgs),
            "disabled": sum(not c.enabled for c in cfgs),
            "healthy": sum(h["status"] == "healthy" for h in health),
            "degraded": sum(h["status"] == "degraded" for h in health),
            "missing_dependencies": sum(any(not d["installed"] for d in h["dependencies"]) for h in health),
        }, "features": {c.name: {"status": h["status"], "issues": h["issues"], "dependencies": h["dependencies"],
                                  "routes": h["routes"], "loaded": h["loaded"]} for c, h in zip(cfgs, health)}})

    def detail(self, feature_name):
        cfg = self.m.feature_configs.get(feature_name)
        if not cfg:
            return jsonify({"success": False, "error": "Feature not found"}), 404
        return jsonify({"success": True, "feature": self._detail(cfg, with_code=True)})

    def update(self, feature_name):
        denied = self._guard()
        if denied:
            return denied
        cfg = self.m.feature_configs.get(feature_name)
        if not cfg:
            return jsonify({"success": False, "error": "Feature not found"}), 404
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"success": False, "error": "No data provided"}), 400
        merged = {"display_name": data.get("display_name", cfg.display_name), "description": data.get("description", cfg.description),
                  "version": data.get("version", cfg.version), "dependencies": data.get("dependencies", cfg.dependencies)}
        error = self._check_meta(merged)
        if not error and "handler_code" in data:
            error = self._check_code(cfg.name, data["handler_code"])
        if error:
            return jsonify({"success": False, "error": error}), 400
        cfg.display_name = str(merged["display_name"]).strip()
        cfg.description = str(merged["description"] or "").strip()
        cfg.version = str(merged["version"]).strip()
        cfg.dependencies = [d.strip() for d in merged["dependencies"]]
        restart = False
        if "handler_code" in data:
            handler = self._handler_path(cfg.name)
            if not handler.exists() or handler.read_text(encoding="utf-8") != data["handler_code"]:
                self._backup_handler(cfg.name)
                handler.write_text(data["handler_code"], encoding="utf-8")
                restart = cfg.enabled
        self.m._save_feature_config(cfg)
        self._log("update", cfg.name, "handler changed" if restart else "")
        return jsonify({"success": True, "feature": self._detail(cfg), "restart_required": restart})

    def delete(self, feature_name):
        denied = self._guard()
        if denied:
            return denied
        cfg = self.m.feature_configs.get(feature_name)
        if not cfg:
            return jsonify({"success": False, "error": "Feature not found"}), 404
        was_loaded = feature_name in self.m.features
        if cfg.enabled:
            self.m.disable_feature(feature_name)
        self._backup_handler(feature_name)
        handler = self._handler_path(feature_name)
        if handler.exists():
            handler.unlink()
        config_file = self.dir / "configs" / f"{feature_name}.json"
        if config_file.exists():
            self.trash.mkdir(exist_ok=True)
            shutil.copy2(config_file, self.trash / f"{time.strftime('%Y%m%d-%H%M%S')}__{config_file.name}")
            config_file.unlink()
        self.m.feature_configs.pop(feature_name, None)
        self._log("delete", feature_name, "backup kept in features/trash")
        return jsonify({"success": True, "restart_required": was_loaded})

    def duplicate(self, feature_name):
        denied = self._guard()
        if denied:
            return denied
        cfg = self.m.feature_configs.get(feature_name)
        if not cfg:
            return jsonify({"success": False, "error": "Feature not found"}), 404
        data = request.get_json(silent=True) or {}
        new_name = str(data.get("name") or f"{cfg.name}-copy").strip().lower()
        if not NAME_RE.fullmatch(new_name):
            return jsonify({"success": False, "error": "Feature names must be 2-64 lowercase letters, numbers, underscores, or hyphens"}), 400
        if new_name in self.m.feature_configs or self._handler_path(new_name).exists():
            return jsonify({"success": False, "error": "A feature with that name already exists"}), 409
        src = self._handler_path(cfg.name)
        code = src.read_text(encoding="utf-8") if src.exists() else ""
        clone = type(cfg)(**{**asdict(cfg), "name": new_name, "display_name": f"{cfg.display_name} (copy)", "enabled": False})
        self._handler_path(new_name).write_text(code, encoding="utf-8")
        self.m._save_feature_config(clone)
        self.m.feature_configs[new_name] = clone
        self._log("duplicate", new_name, f"from {cfg.name}")
        return jsonify({"success": True, "feature": self._detail(clone)}), 201

    def export(self, feature_name):
        cfg = self.m.feature_configs.get(feature_name)
        if not cfg:
            return jsonify({"success": False, "error": "Feature not found"}), 404
        handler = self._handler_path(cfg.name)
        payload = {"format": "masterchief-feature", "version": 1, "config": {**asdict(cfg), "enabled": False},
                   "handler_code": handler.read_text(encoding="utf-8") if handler.exists() else ""}
        resp = jsonify(payload)
        resp.headers["Content-Disposition"] = f'attachment; filename="{cfg.name}.feature.json"'
        return resp

    def import_feature(self):
        denied = self._guard()
        if denied:
            return denied
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or data.get("format") != "masterchief-feature" or not isinstance(data.get("config"), dict):
            return jsonify({"success": False, "error": "Not a MasterChief feature export"}), 400
        conf = data["config"]
        name = str(conf.get("name") or "").strip().lower()
        if not NAME_RE.fullmatch(name):
            return jsonify({"success": False, "error": "Invalid feature name in file"}), 400
        error = self._check_meta(conf) or self._check_code(name, data.get("handler_code", ""))
        if error:
            return jsonify({"success": False, "error": error}), 400
        if name in self.m.feature_configs or self._handler_path(name).exists():
            return jsonify({"success": False, "error": f"A feature named {name} already exists"}), 409
        from features.manager import FeatureConfig
        cfg = FeatureConfig(name=name, display_name=str(conf["display_name"]).strip(), description=str(conf.get("description") or "").strip(),
                            version=str(conf.get("version") or "1.0.0"), dependencies=[d.strip() for d in conf.get("dependencies", [])],
                            routes=conf.get("routes") if isinstance(conf.get("routes"), list) else [],
                            ui_components=conf.get("ui_components") if isinstance(conf.get("ui_components"), list) else [])
        self._handler_path(name).write_text(data.get("handler_code", ""), encoding="utf-8")
        self.m._save_feature_config(cfg)
        self.m.feature_configs[name] = cfg
        self._log("import", name)
        return jsonify({"success": True, "feature": self._detail(cfg)}), 201

    def install_deps(self, feature_name):
        denied = self._guard()
        if denied:
            return denied
        cfg = self.m.feature_configs.get(feature_name)
        if not cfg:
            return jsonify({"success": False, "error": "Feature not found"}), 404
        todo = [d.strip() for d in cfg.dependencies if not _dep_status(d)["installed"]]
        bad = [d for d in todo if not PIP_SPEC_RE.match(d)]
        if bad:
            return jsonify({"success": False, "error": "Invalid package spec: " + ", ".join(bad)}), 400
        if not todo:
            return jsonify({"success": True, "installed": [], "message": "All packages already installed"})
        try:
            proc = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *todo],
                                  capture_output=True, text=True, timeout=600)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return jsonify({"success": False, "error": f"pip failed: {exc}"}), 500
        ok = proc.returncode == 0
        self._log("install-deps", feature_name, ", ".join(todo) + ("" if ok else " (failed)"))
        output = (proc.stdout + proc.stderr)[-2000:]
        status = 200 if ok else 500
        return jsonify({"success": ok, "installed": todo if ok else [], "output": output,
                        "error": None if ok else "pip install failed"}), status

    def generate_handler(self, feature_name):
        denied = self._guard()
        if denied:
            return denied
        cfg = self.m.feature_configs.get(feature_name)
        if not cfg:
            return jsonify({"success": False, "error": "Feature not found"}), 404
        path = self._handler_path(feature_name)
        if path.exists():
            return jsonify({"success": False, "error": "Handler already exists"}), 409
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(HANDLER_STUB.format(name=cfg.name), encoding="utf-8")
        self._log("generate-handler", feature_name)
        return jsonify({"success": True, "restart_required": cfg.enabled})

    def activity(self):
        try:
            items = json.loads(self.activity_file.read_text(encoding="utf-8")) if self.activity_file.exists() else []
        except (OSError, ValueError):
            items = []
        return jsonify({"success": True, "activity": list(reversed(items[-50:]))})


def register(manager) -> FeatureManagement:
    fm = FeatureManagement(manager)
    add = manager.app.add_url_rule
    add("/api/features/summary", "api_features_summary", fm.summary, methods=["GET"])
    add("/api/features/activity", "api_features_activity", fm.activity, methods=["GET"])
    add("/api/features/import", "api_features_import", fm.import_feature, methods=["POST"])
    add("/api/features/<feature_name>", "api_features_detail", fm.detail, methods=["GET"])
    add("/api/features/<feature_name>", "api_features_update", fm.update, methods=["PUT"])
    add("/api/features/<feature_name>", "api_features_delete", fm.delete, methods=["DELETE"])
    add("/api/features/<feature_name>/duplicate", "api_features_duplicate", fm.duplicate, methods=["POST"])
    add("/api/features/<feature_name>/install-deps", "api_features_install_deps", fm.install_deps, methods=["POST"])
    add("/api/features/<feature_name>/generate-handler", "api_features_generate_handler", fm.generate_handler, methods=["POST"])
    add("/api/features/<feature_name>/export", "api_features_export", fm.export, methods=["GET"])
    return fm

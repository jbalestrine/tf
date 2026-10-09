# Code Manager routes. Page markup: templates/index.html. Analysis logic: managers/code_manager.py.
from pathlib import Path

from flask import Blueprint, jsonify, request

from managers import feature_loader as fl
from managers.code_manager import CodeManager, CodeManagerError


def init(app, ctx):
    bp = Blueprint("feature_code_manager", __name__, url_prefix="/ext/code_manager")
    manager = CodeManager(app, ctx.root)

    def guarded(post=False):
        return ctx.admin_post() if post else ctx.admin_page(True)

    def body():
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    def failure(exc):
        return jsonify({"ok": False, "error": str(exc)}), 400

    @bp.route("/")
    def index():
        denied = ctx.admin_page(False)
        if denied is not None:
            return denied
        return ctx.render_page("index.html")

    @bp.route("/api/analysis")
    def analysis():
        denied = guarded()
        if denied is not None:
            return denied
        try:
            data = manager.analyze(force=request.args.get("refresh") == "1")
        except CodeManagerError as exc:
            return failure(exc)
        return jsonify({"ok": True, "analysis": data, "budget": manager.budget()})

    @bp.route("/api/blueprints")
    def blueprints():
        denied = guarded()
        if denied is not None:
            return denied
        return jsonify({"ok": True, "blueprints": manager.blueprints(),
                        "linked_status": app.config.get("_linked_blueprints", [])})

    @bp.route("/api/blueprints/probe", methods=["POST"])
    def probe():
        denied = guarded(True)
        if denied is not None:
            return denied
        try:
            return jsonify({"ok": True, "probe": fl.probe_blueprint(app, ctx.root, str(body().get("module", "")))})
        except fl.FeatureError as exc:
            return failure(exc)

    @bp.route("/api/blueprints/link", methods=["POST"])
    def link():
        denied = guarded(True)
        if denied is not None:
            return denied
        data = body()
        try:
            result = fl.probe_blueprint(app, ctx.root, str(data.get("module", "")))
            if not result["ok"]:
                return jsonify({"ok": False, "error": "Probe failed: " + result["error"]}), 400
            fl.link_blueprint(ctx.root, str(data["module"]), str(data.get("note", "")))
        except (fl.FeatureError, KeyError) as exc:
            return failure(exc)
        ctx.audit("link_blueprint", module=data.get("module"))
        return jsonify({"ok": True, "message": "Linked. Restart MasterChief to load it. Routes already served by main.py keep priority."})

    @bp.route("/api/blueprints/unlink", methods=["POST"])
    def unlink():
        denied = guarded(True)
        if denied is not None:
            return denied
        module = str(body().get("module", ""))
        fl.unlink_blueprint(ctx.root, module)
        ctx.audit("unlink_blueprint", module=module)
        return jsonify({"ok": True, "message": "Unlinked. Restart MasterChief for it to take effect."})

    @bp.route("/api/blueprints/retire", methods=["POST"])
    def retire():
        denied = guarded(True)
        if denied is not None:
            return denied
        data = body()
        try:
            report = manager.retire_module(str(data.get("module", "")), dry_run=not data.get("apply"))
        except CodeManagerError as exc:
            return failure(exc)
        if report.get("error"):
            return jsonify({"ok": False, "error": report["error"], "report": report}), 500
        if report["applied"]:
            ctx.audit("retire_main_routes", module=report["module"], lines=report["lines_removed"])
        return jsonify({"ok": True, "report": report})

    @bp.route("/api/pages")
    def pages():
        denied = guarded()
        if denied is not None:
            return denied
        live = [b["module"] for b in manager.blueprints() if b["registered"] and b["kind"] == "blueprint"]
        return jsonify({"ok": True, "pages": manager.pages(), "blueprints": live})

    @bp.route("/api/pages/isolate", methods=["POST"])
    def isolate():
        denied = guarded(True)
        if denied is not None:
            return denied
        data = body()
        try:
            report = manager.isolate_page(str(data.get("func", "")), str(data.get("module", "")), dry_run=not data.get("apply"))
        except CodeManagerError as exc:
            return failure(exc)
        if report.get("error"):
            return jsonify({"ok": False, "error": report["error"], "report": report}), 500
        if report["applied"]:
            ctx.audit("isolate_page", func=report["func"], module=report["module"])
        return jsonify({"ok": True, "report": report})

    @bp.route("/api/blueprints/create", methods=["POST"])
    def create_bp():
        denied = guarded(True)
        if denied is not None:
            return denied
        try:
            result = manager.create_blueprint(str(body().get("slug", "")))
        except CodeManagerError as exc:
            return failure(exc)
        ctx.audit("create_blueprint", module=result["module"])
        return jsonify({"ok": True, "blueprint": result, "message": "Created and linked. Restart MasterChief, then it appears as live and you can move pages into it."})

    @bp.route("/api/features")
    def features():
        denied = guarded()
        if denied is not None:
            return denied
        loaded = {s["slug"]: s for s in app.config.get("_features", [])}
        flags = fl.read_flags(ctx.root)
        rows = []
        for info in fl.discover(ctx.root):
            status = loaded.get(info["slug"], {})
            rows.append({
                "slug": info["slug"], "title": info["title"], "description": info["description"], "core": info["core"],
                "enabled": True if info["core"] else flags.get(info["slug"], info["enabled_default"]),
                "state": status.get("state", "not loaded yet (restart)"), "error": status.get("error", ""),
                "routes": status.get("routes", 0), "files": info["files"],
                "url": (info["nav"] or {}).get("href", ""),
            })
        return jsonify({"ok": True, "features": rows})

    @bp.route("/api/features/create", methods=["POST"])
    def create():
        denied = guarded(True)
        if denied is not None:
            return denied
        data = body()
        try:
            result = fl.create_feature(ctx.root, data.get("slug"), data.get("title"), data.get("description", ""),
                                       data.get("nav_label", ""), data.get("icon", ""))
        except fl.FeatureError as exc:
            return failure(exc)
        ctx.audit("create_feature", slug=result["slug"])
        return jsonify({"ok": True, "feature": result, "message": "Created. Restart MasterChief to load it."})

    @bp.route("/api/features/toggle", methods=["POST"])
    def toggle():
        denied = guarded(True)
        if denied is not None:
            return denied
        data = body()
        try:
            fl.set_flag(ctx.root, str(data.get("slug", "")), bool(data.get("enabled")))
        except fl.FeatureError as exc:
            return failure(exc)
        ctx.audit("toggle_feature", slug=data.get("slug"), enabled=bool(data.get("enabled")))
        return jsonify({"ok": True, "message": "Saved. Restart MasterChief for it to take effect."})

    @bp.route("/api/safety")
    def safety():
        denied = guarded()
        if denied is not None:
            return denied
        return jsonify({"ok": True, "baseline": manager.compare_baseline(), "budget": manager.budget()})

    @bp.route("/api/safety/baseline", methods=["POST"])
    def baseline():
        denied = guarded(True)
        if denied is not None:
            return denied
        ctx.audit("save_route_baseline")
        return jsonify({"ok": True, "saved": manager.save_baseline()})

    @bp.route("/api/safety/budget", methods=["POST"])
    def budget():
        denied = guarded(True)
        if denied is not None:
            return denied
        try:
            result = manager.set_budget(ratchet=True)
        except CodeManagerError as exc:
            return failure(exc)
        ctx.audit("ratchet_main_budget")
        return jsonify({"ok": True, "budget": result})

    return bp

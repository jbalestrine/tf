"""Independently loadable architecture whiteboard feature."""
from __future__ import annotations

import json
import io
import re
import tempfile
import zipfile
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file, send_from_directory

from .iac import build, terraform_json

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,79}$")
MAX_BYTES = 4 * 1024 * 1024


def init(app, ctx):
    bp = Blueprint("feature_archetype_studio", __name__, url_prefix="/ext/archetype_studio")
    storage = Path(ctx.root) / "data" / "archetype_studio"

    @bp.get("/")
    def index():
        denied = ctx.admin_page(False)
        if denied is not None:
            return denied
        return ctx.render_page("index.html")

    @bp.get("/assets/<path:name>")
    def asset(name):
        denied = ctx.admin_page(False)
        if denied is not None:
            return denied
        return send_from_directory(ctx.directory / "static", name)

    @bp.get("/api/diagrams")
    def list_diagrams():
        denied = ctx.admin_page(True)
        if denied is not None:
            return denied
        try:
            names = sorted((p.stem for p in storage.glob("*.json") if NAME.fullmatch(p.stem)), key=str.casefold)
        except OSError:
            app.logger.exception("Unable to list architecture diagrams")
            return jsonify(ok=False, error="Could not list server diagrams."), 500
        return jsonify(ok=True, diagrams=names)

    @bp.post("/api/iac/preview")
    def iac_preview():
        denied = ctx.admin_post()
        if denied is not None:
            return denied
        if request.content_length is None or request.content_length > MAX_BYTES:
            return jsonify(ok=False, error="Diagram exceeds the 4 MB limit."), 413
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(ok=False, error="A diagram and export mode are required."), 400
        try:
            result = build(payload.get("diagram"), payload.get("mode"))
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        return jsonify(ok=True, report=result)

    @bp.post("/api/iac/export")
    def iac_export():
        denied = ctx.admin_post()
        if denied is not None:
            return denied
        if request.content_length is None or request.content_length > MAX_BYTES:
            return jsonify(ok=False, error="Diagram exceeds the 4 MB limit."), 413
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(ok=False, error="A diagram and export mode are required."), 400
        try:
            report = build(payload.get("diagram"), payload.get("mode"))
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        if not report["can_export"]:
            return jsonify(ok=False, error="Export blocked; review the reported issues.", report=report), 422
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            name = "main.tf.json" if report["mode"] == "validated" else "draft-resources.json"
            archive.writestr(name, terraform_json(report))
            summary = {k: v for k, v in report.items() if k != "terraform"}
            archive.writestr("review-report.json", json.dumps(summary, indent=2, ensure_ascii=False))
            archive.writestr("README.txt", (
                "Generated Terraform configuration for review, not an automatic deployment.\n"
                "Read review-report.json for omissions and important limitations.\n"
                "Draft output is intentionally not named .tf.json; it is incomplete.\n"
                "Configure Azure authentication and ARM_SUBSCRIPTION_ID externally.\n"
                "Run terraform init, validate, and plan; review security and cost before apply.\n"
                "The exporter does not validate remote Azure policy, quotas, state or name availability.\n"
            ))
        output.seek(0)
        ctx.audit("export_iac", mode=report["mode"], count=len(report["resources"]))
        return send_file(output, mimetype="application/zip", as_attachment=True,
                         download_name=f"archetype-{report['mode']}-terraform.zip")

    @bp.route("/api/diagrams/<name>", methods=["GET", "PUT"])
    def diagram(name):
        denied = ctx.admin_post() if request.method == "PUT" else ctx.admin_page(True)
        if denied is not None:
            return denied
        if not NAME.fullmatch(name):
            return jsonify(ok=False, error="Use 1–80 letters, numbers, spaces, underscores or hyphens."), 400
        path = storage / (name + ".json")
        if request.method == "GET":
            try:
                if not path.is_file():
                    return jsonify(ok=False, error="Diagram not found."), 404
                if path.stat().st_size > MAX_BYTES:
                    return jsonify(ok=False, error="Stored diagram exceeds the size limit."), 413
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                app.logger.exception("Unable to read architecture diagram")
                return jsonify(ok=False, error="Could not read the saved diagram."), 500
            return jsonify(ok=True, diagram=document)

        if request.content_length is None or request.content_length > MAX_BYTES:
            return jsonify(ok=False, error="Diagram exceeds the 4 MB limit."), 413
        document = request.get_json(silent=True)
        if (not isinstance(document, dict) or document.get("version") != 1
                or not isinstance(document.get("nodes"), list)
                or not isinstance(document.get("edges"), list)):
            return jsonify(ok=False, error="Invalid whiteboard document."), 400
        if path.exists() and request.args.get("overwrite") != "1":
            return jsonify(ok=False, error="A diagram with this name already exists."), 409
        try:
            storage.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=storage, delete=False) as file:
                temporary = Path(file.name)
                json.dump(document, file, ensure_ascii=False)
            temporary.replace(path)
        except OSError:
            app.logger.exception("Unable to save architecture diagram")
            return jsonify(ok=False, error="Could not save the diagram on the server."), 500
        ctx.audit("save_diagram", name=name)
        return jsonify(ok=True)

    return bp

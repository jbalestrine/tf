from __future__ import annotations

import shutil
import subprocess
import sys

from flask import Blueprint, Response, current_app, jsonify, request

from auth_module import requires_permission
from core.iac_generator import generate_iac_zip

iac_bp = Blueprint("iac", __name__)


@iac_bp.route("/api/architecture/visio", methods=["POST"])
def api_architecture_visio():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON architecture diagram is required."}), 400
    try:
        from core.architecture_diagrams import normalize_diagram, render_vsdx

        title = str(payload.get("title") or "Architecture").strip()[:80]
        hub_label = str(payload.get("hub") or title).strip()[:80]
        components = payload.get("nodes")
        if not isinstance(components, list):
            raise ValueError("Diagram components must be a list.")
        nodes = [{"id": "architecture-hub", "label": hub_label, "kind": "system"}]
        component_ids: dict[str, str] = {}
        for index, component in enumerate(components):
            if isinstance(component, str):
                label = component.strip()
                node = {"id": f"component-{index + 1}", "label": label, "kind": "component"}
                original_id = ""
            elif isinstance(component, dict):
                label = str(component.get("label") or component.get("title") or "").strip()
                original_id = str(component.get("id") or "").strip()
                node = {
                    "id": f"component-{index + 1}",
                    "label": label,
                    "kind": str(component.get("kind") or "component"),
                }
            else:
                raise ValueError("Each diagram component must be a label or object.")
            if label in component_ids or label == hub_label:
                raise ValueError(f"Diagram component labels must be unique: {label!r}.")
            component_ids[label] = node["id"]
            if original_id:
                component_ids[original_id] = node["id"]
            nodes.append(node)

        edges = payload.get("edges") or []
        mapped_edges = []
        for edge in edges:
            if not isinstance(edge, dict):
                raise ValueError("Each connection must be an object.")
            source = str(edge.get("from") or "").strip()
            target = str(edge.get("to") or "").strip()
            mapped_edges.append({
                "from": component_ids.get(source, "architecture-hub" if source in {"hub", hub_label} else source),
                "to": component_ids.get(target, "architecture-hub" if target in {"hub", hub_label} else target),
                "label": str(edge.get("label") or ""),
            })
        if not mapped_edges:
            ordered_ids = [node["id"] for node in nodes[1:]]
            mapped_edges = [
                {"from": source, "to": target, "label": ""}
                for source, target in zip(ordered_ids, ordered_ids[1:])
            ]
        clean_nodes, clean_edges = normalize_diagram(nodes, mapped_edges)
        package = render_vsdx(title, clean_nodes, clean_edges)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Could not render Visio architecture diagram")
        return jsonify({"error": "Visio export failed. Check the server log for details."}), 500

    filename = "".join(character if character.isalnum() or character in "-_" else "_" for character in title).strip("_") or "architecture"
    return Response(
        package,
        mimetype="application/vnd.ms-visio.drawing",
        headers={"Content-Disposition": f'attachment; filename="{filename}.vsdx"'},
    )


@iac_bp.route("/api/iac/generate", methods=["POST"])
def api_iac_generate():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "A JSON IaC specification is required."}), 400
    try:
        artifact_format, package = generate_iac_zip(payload)
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Failed to generate IaC package")
        return jsonify({"ok": False, "error": "IaC generation failed. Check the server log for details."}), 500

    return Response(
        package,
        mimetype="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="iac-{artifact_format}.zip"',
            "X-IaC-Format": artifact_format,
        },
    )


@iac_bp.route("/api/terraform/status", methods=["GET"])
def api_terraform_status():
    executable = shutil.which("terraform")
    if not executable:
        return jsonify({"installed": False, "executable": None, "version": None})
    try:
        result = subprocess.run(
            [executable, "version", "-json"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        current_app.logger.exception("Could not query Terraform CLI")
        return jsonify({"installed": True, "executable": executable, "version": None, "error": str(exc)}), 500
    if result.returncode != 0:
        return jsonify({
            "installed": True,
            "executable": executable,
            "version": None,
            "error": (result.stderr or result.stdout or "Terraform version command failed").strip(),
        }), 500
    try:
        import json
        version = json.loads(result.stdout).get("terraform_version")
    except (json.JSONDecodeError, AttributeError):
        version = None
    return jsonify({"installed": True, "executable": executable, "version": version})


@iac_bp.route("/api/terraform/install", methods=["POST"])
@requires_permission("rbac")
def api_terraform_install():
    if sys.platform != "win32":
        return jsonify({
            "ok": False,
            "error": "One-click installation is currently supported only on Windows. Install Terraform using the official HashiCorp instructions for your operating system.",
        }), 501
    winget = shutil.which("winget")
    if not winget:
        return jsonify({
            "ok": False,
            "error": "Windows Package Manager (winget) was not found. Install winget or install Terraform from HashiCorp's official distribution.",
        }), 503
    try:
        result = subprocess.run(
            [
                winget,
                "install",
                "--id",
                "Hashicorp.Terraform",
                "--exact",
                "--accept-source-agreements",
                "--accept-package-agreements",
                "--silent",
            ],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired:
        current_app.logger.exception("Terraform installation timed out")
        return jsonify({"ok": False, "error": "Terraform installation timed out. Check winget and retry."}), 504
    except OSError as exc:
        current_app.logger.exception("Could not start Terraform installation")
        return jsonify({"ok": False, "error": str(exc)}), 500
    if result.returncode != 0:
        return jsonify({
            "ok": False,
            "error": (result.stderr or result.stdout or f"winget exited with code {result.returncode}").strip(),
        }), 500
    return jsonify({
        "ok": True,
        "message": "Terraform installation completed. Refresh the status check; restart the app if Terraform is not yet on PATH.",
        "output": result.stdout.strip()[-4000:],
    })

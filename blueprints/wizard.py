import ast
import difflib
import json
import re
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

wizard_bp = Blueprint("wizard", __name__)


def _root() -> Path:
    return Path(current_app.root_path).resolve()


def _main_path() -> Path:
    return _root() / "main.py"


def _feature_enabled(flag: str) -> bool:
    flags_path = _root() / "data" / "feature_flags.json"
    defaults = {"blueprint_wizard": True}
    try:
        if flags_path.exists():
            raw = json.loads(flags_path.read_text(encoding="utf-8") or "{}")
            if isinstance(raw, dict):
                defaults.update({str(k): bool(v) for k, v in raw.items()})
    except Exception:
        current_app.logger.exception("Failed reading feature flags in wizard")
    return bool(defaults.get(flag, True))


def _load_tree() -> tuple[str, ast.Module]:
    # Accept UTF-8 files with BOM so ast.parse does not fail.
    text = _main_path().read_text(encoding="utf-8-sig")
    return text, ast.parse(text)


def _template_names(text: str) -> list[str]:
    pat = re.compile(r"(?m)^([A-Z][A-Z0-9_]*_TEMPLATE)\s*=\s*(?:'''|\"\"\")")
    return sorted({m.group(1) for m in pat.finditer(text)})


def _function_rows(text: str, tree: ast.Module) -> list[dict]:
    rows = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        decorators = [ast.unparse(d) for d in node.decorator_list]
        has_route = any("route(" in d for d in decorators)
        rows.append(
            {
                "name": node.name,
                "start": node.lineno,
                "end": node.end_lineno,
                "lines": (node.end_lineno - node.lineno + 1),
                "decorators": decorators,
                "route": has_route,
                "extractable": not has_route,
                "preview": (ast.get_docstring(node) or "").split("\n")[0][:120],
            }
        )
    rows.sort(key=lambda r: r["lines"], reverse=True)
    return rows


@wizard_bp.route("/blueprint-wizard")
def blueprint_wizard_page():
    if not _feature_enabled("blueprint_wizard"):
        return (
            '<h2>Blueprint Wizard is disabled by feature flag.</h2><p>Enable it in <a href="/master-menu">Master Menu</a>.</p>',
            503,
        )
    return render_template("blueprint_wizard.html")


@wizard_bp.route("/api/blueprint/main/summary")
def api_blueprint_main_summary():
    try:
        text, tree = _load_tree()
        funcs = _function_rows(text, tree)
        templates = _template_names(text)
        return jsonify(
            {
                "ok": True,
                "file": "main.py",
                "updated_at": datetime.utcnow().isoformat(),
                "line_count": len(text.splitlines()),
                "function_count": len(funcs),
                "extractable_count": sum(1 for f in funcs if f["extractable"]),
                "route_function_count": sum(1 for f in funcs if f["route"]),
                "template_variable_count": len(templates),
                "largest_functions": funcs[:25],
                "template_variables": templates[:100],
            }
        )
    except Exception as exc:
        current_app.logger.exception("Blueprint summary failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@wizard_bp.route("/api/blueprint/main/extract", methods=["POST"])
def api_blueprint_main_extract():
    try:
        body = request.get_json(silent=True) or {}
        fn_name = (body.get("function_name") or "").strip()
        module_name = re.sub(r"[^a-zA-Z0-9_]", "_", (body.get("module_name") or "main_extracted").strip())
        apply_changes = bool(body.get("apply_changes", False))

        if not fn_name:
            return jsonify({"ok": False, "error": "function_name is required"}), 400

        text, tree = _load_tree()
        lines = text.splitlines()

        target = None
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == fn_name:
                target = node
                break

        if target is None:
            return jsonify({"ok": False, "error": f"Function not found: {fn_name}"}), 404
        if target.decorator_list:
            return jsonify({"ok": False, "error": "Decorated/route functions are not extractable in this operation"}), 400

        src_block = "\n".join(lines[target.lineno - 1 : target.end_lineno]) + "\n"
        pkg_dir = _root() / "core" / "extracted"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        target_file = pkg_dir / f"{module_name}.py"

        if not apply_changes:
            return jsonify(
                {
                    "ok": True,
                    "dry_run": True,
                    "function_name": fn_name,
                    "module_file": str(target_file.relative_to(_root())).replace("\\", "/"),
                    "source_preview": src_block[:5000],
                }
            )

        if target_file.exists():
            existing = target_file.read_text(encoding="utf-8")
        else:
            existing = "# Auto-generated by Blueprint Wizard\n\n"

        if f"def {fn_name}(" not in existing:
            if not existing.endswith("\n"):
                existing += "\n"
            existing += "\n" + src_block
            target_file.write_text(existing, encoding="utf-8")

        backup_dir = _root() / "data" / "blueprints" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / f"main.py.{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.bak"
        backup_file.write_text(text, encoding="utf-8")

        wrapper = [
            f"def {fn_name}(*args, **kwargs):",
            f"    from core.extracted.{module_name} import {fn_name} as _impl",
            "    return _impl(*args, **kwargs)",
        ]
        new_lines = lines[: target.lineno - 1] + wrapper + lines[target.end_lineno :]
        new_text = "\n".join(new_lines) + "\n"
        _main_path().write_text(new_text, encoding="utf-8")

        diff = "\n".join(
            difflib.unified_diff(
                text.splitlines(),
                new_text.splitlines(),
                fromfile="main.py",
                tofile="main.py",
                lineterm="",
            )
        )

        return jsonify(
            {
                "ok": True,
                "dry_run": False,
                "function_name": fn_name,
                "module_file": str(target_file.relative_to(_root())).replace("\\", "/"),
                "backup_file": str(backup_file.relative_to(_root())).replace("\\", "/"),
                "diff_preview": diff[:12000],
            }
        )
    except Exception as exc:
        current_app.logger.exception("Blueprint extraction failed")
        return jsonify({"ok": False, "error": str(exc)}), 500

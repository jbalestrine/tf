"""Feature loader: keeps new code out of main.py.

Two things are loaded after main.py has defined its own routes:

* ``app_features/<slug>/`` - self-contained features (blueprint + template + manifest).
* ``config/linked_blueprints.json`` - blueprint files in ``blueprints/`` that main.py never registered.

A feature or blueprint that fails to import is reported and skipped; it can never stop the app from starting.
"""
from __future__ import annotations

import importlib.util
import json
import keyword
import re
import sys
import time
from pathlib import Path

from flask import Blueprint, Flask, get_flashed_messages, render_template_string, request

FEATURES_DIR = "app_features"
FLAGS_REL = "data/feature_flags.json"
LINKED_REL = "config/linked_blueprints.json"
SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{2,30}$")
MODULE_RE = re.compile(r"^blueprints\.[a-z][a-z0-9_]{1,60}$")
RESERVED_SLUGS = {"test", "tests", "static", "templates", "api", "core", "main", "blueprints", "managers", "data"}
CONTENT_MARKER = "{% block content %}{% endblock %}"


class FeatureError(ValueError):
    pass


# ---------- small json helpers ----------
def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_flags(root: Path) -> dict:
    data = _read_json(Path(root) / FLAGS_REL, {})
    return {k: bool(v) for k, v in data.items()} if isinstance(data, dict) else {}


def set_flag(root: Path, slug: str, enabled: bool) -> None:
    root = Path(root)
    info = next((f for f in discover(root) if f["slug"] == slug), None)
    if info is None:
        raise FeatureError("Unknown feature.")
    if info["core"]:
        raise FeatureError("Core features cannot be turned off.")
    flags = read_flags(root)
    flags[slug] = bool(enabled)
    _write_json(root / FLAGS_REL, flags)


# ---------- discovery ----------
def discover(root: Path) -> list[dict]:
    base = Path(root) / FEATURES_DIR
    items = []
    if not base.is_dir():
        return items
    for directory in sorted(base.iterdir()):
        if not directory.is_dir() or not SLUG_RE.match(directory.name) or not (directory / "__init__.py").is_file():
            continue
        manifest = _read_json(directory / "feature.json", {})
        manifest = manifest if isinstance(manifest, dict) else {}
        nav = manifest.get("nav") if isinstance(manifest.get("nav"), dict) else None
        files = sorted(
            p.relative_to(root).as_posix() for p in directory.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        )
        items.append({
            "slug": directory.name,
            "title": str(manifest.get("title") or directory.name),
            "description": str(manifest.get("description") or ""),
            "version": str(manifest.get("version") or ""),
            "core": bool(manifest.get("core", False)),
            "enabled_default": bool(manifest.get("enabled", True)),
            "nav": nav,
            "files": files,
            "dir": directory,
        })
    return items


# ---------- context handed to each feature ----------
class FeatureContext:
    def __init__(self, app: Flask, root: Path, info: dict, layout: str, admin_page, post_guard, audit):
        self.app = app
        self.root = Path(root)
        self.slug = info["slug"]
        self.directory = info["dir"]
        self._layout = layout or ""
        self._admin_page = admin_page
        self._post_guard = post_guard
        self._audit = audit

    def admin_page(self, json_response: bool = False):
        """Return an error/redirect response unless the admin is signed in; None means allowed."""
        return self._admin_page(json_response)

    def admin_post(self):
        """Admin plus same-origin check for state-changing requests; None means allowed."""
        return self._post_guard()

    def audit(self, action: str, **details) -> None:
        if self._audit is None:
            return
        try:
            self._audit(f"feature_{self.slug}_{action}", **details)
        except Exception:
            self.app.logger.exception("Audit failed for feature %s", self.slug)

    def render_page(self, template_name: str, **context):
        base = (self.directory / "templates").resolve()
        path = (base / template_name).resolve()
        if base not in path.parents or not path.is_file():
            raise FeatureError(f"Template not found: {template_name}")
        content = render_template_string(path.read_text(encoding="utf-8"), **context)
        if CONTENT_MARKER not in self._layout:
            return content
        page = self._layout.replace(CONTENT_MARKER, "{{ feature_content__|safe }}")
        return render_template_string(
            page, feature_content__=content, request=request, get_flashed_messages=get_flashed_messages,
        )


# ---------- importing by path (works for any project root) ----------
def _load_module(name: str, path: Path, package_dir: Path | None = None):
    existing = sys.modules.get(name)
    if existing is not None and getattr(existing, "__file__", None) and Path(existing.__file__).resolve() == path.resolve():
        return existing
    kwargs = {"submodule_search_locations": [str(package_dir)]} if package_dir else {}
    spec = importlib.util.spec_from_file_location(name, str(path), **kwargs)
    if spec is None or spec.loader is None:
        raise FeatureError(f"Cannot load {path.name}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _load_feature_module(info: dict):
    return _load_module(f"{FEATURES_DIR}.{info['slug']}", info["dir"] / "__init__.py", info["dir"])


# ---------- linked blueprints ----------
def read_linked(root: Path) -> list[dict]:
    data = _read_json(Path(root) / LINKED_REL, {})
    rows = data.get("linked", []) if isinstance(data, dict) else []
    return [r for r in rows if isinstance(r, dict) and MODULE_RE.match(str(r.get("module", "")))]


def _blueprint_path(root: Path, module: str) -> Path:
    if not MODULE_RE.match(module or ""):
        raise FeatureError("Module must look like blueprints.some_name.")
    path = Path(root) / "blueprints" / (module.split(".", 1)[1] + ".py")
    if not path.is_file():
        raise FeatureError(f"{module} does not exist in blueprints/.")
    return path


def _blueprints_in(module) -> list[tuple[str, Blueprint]]:
    return [(n, v) for n, v in vars(module).items() if isinstance(v, Blueprint)]


def _method_set(rule) -> set[str]:
    return set(rule.methods or ()) - {"HEAD", "OPTIONS"}


def probe_blueprint(app: Flask, root: Path, module: str) -> dict:
    """Import a blueprint file and register it on a throwaway app. Nothing touches the live app."""
    root = Path(root)
    try:
        path = _blueprint_path(root, module)
        mod = _load_module(module, path)
        found = _blueprints_in(mod)
        if not found:
            return {"ok": False, "error": "This file defines no Blueprint object (it may use an init function instead).", "blueprints": []}
        live = {(r.rule, m) for r in app.url_map.iter_rules() for m in _method_set(r)}
        scratch = Flask("blueprint_probe")
        report = []
        for attr, bp in found:
            scratch.register_blueprint(bp)
        for attr, bp in found:
            routes = []
            for rule in scratch.url_map.iter_rules():
                if not rule.endpoint.startswith(bp.name + "."):
                    continue
                methods = sorted(_method_set(rule))
                collides = any((rule.rule, m) in live for m in methods)
                routes.append({"rule": rule.rule, "methods": methods, "status": "collides" if collides else "new"})
            report.append({
                "attr": attr, "name": bp.name, "routes": sorted(routes, key=lambda r: r["rule"]),
                "already_registered": bp.name in app.blueprints,
            })
        return {"ok": True, "error": "", "blueprints": report}
    except FeatureError:
        raise
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "blueprints": []}


def link_blueprint(root: Path, module: str, note: str = "") -> None:
    root = Path(root)
    _blueprint_path(root, module)
    rows = read_linked(root)
    if any(r["module"] == module for r in rows):
        return
    rows.append({"module": module, "note": str(note or "")[:200], "linked": time.strftime("%Y-%m-%d")})
    _write_json(root / LINKED_REL, {"linked": rows})


def unlink_blueprint(root: Path, module: str) -> None:
    root = Path(root)
    rows = [r for r in read_linked(root) if r["module"] != module]
    _write_json(root / LINKED_REL, {"linked": rows})


def _load_linked(app: Flask, root: Path) -> list[dict]:
    statuses = []
    for row in read_linked(root):
        status = {"module": row["module"], "note": row.get("note", ""), "state": "error", "error": "", "routes": 0}
        before = len(list(app.url_map.iter_rules()))
        try:
            mod = _load_module(row["module"], _blueprint_path(root, row["module"]))
            found = _blueprints_in(mod)
            if not found:
                raise FeatureError("No Blueprint object found.")
            for _, bp in found:
                if bp.name in app.blueprints:
                    continue
                app.register_blueprint(bp)
            status["state"] = "loaded"
        except Exception as exc:
            app.logger.exception("Linked blueprint %s failed", row["module"])
            status["error"] = f"{type(exc).__name__}: {exc}"
        status["routes"] = len(list(app.url_map.iter_rules())) - before
        statuses.append(status)
    return statuses


# ---------- loading ----------
def load_features(app: Flask, root, layout_template: str, admin_page, post_guard, audit=None) -> list[dict]:
    root = Path(root)
    app.config['_layout_template'] = layout_template
    flags = read_flags(root)
    statuses, nav = [], []
    for info in discover(root):
        enabled = True if info["core"] else flags.get(info["slug"], info["enabled_default"])
        status = {k: info[k] for k in ("slug", "title", "description", "version", "core", "nav", "files")}
        status.update(enabled=enabled, state="disabled", error="", routes=0)
        if enabled:
            before = len(list(app.url_map.iter_rules()))
            try:
                module = _load_feature_module(info)
                init = getattr(module, "init", None)
                if not callable(init):
                    raise FeatureError("Feature has no init(app, ctx) function.")
                bp = init(app, FeatureContext(app, root, info, layout_template, admin_page, post_guard, audit))
                if isinstance(bp, Blueprint):
                    app.register_blueprint(bp)
                status["state"] = "loaded"
                if info["nav"] and info["nav"].get("href") and info["nav"].get("label"):
                    nav.append({
                        "href": str(info["nav"]["href"]), "label": str(info["nav"]["label"]),
                        "icon": str(info["nav"].get("icon", "")),
                    })
            except Exception as exc:
                app.logger.exception("Feature %s failed to load", info["slug"])
                status.update(state="error", error=f"{type(exc).__name__}: {exc}")
            status["routes"] = len(list(app.url_map.iter_rules())) - before
        statuses.append(status)
    app.config["_features"] = statuses
    app.config["_feature_nav"] = nav
    app.config["_linked_blueprints"] = _load_linked(app, root)
    if not app.config.get("_feature_nav_registered"):
        app.config["_feature_nav_registered"] = True
        app.context_processor(lambda: {"feature_nav": app.config.get("_feature_nav", [])})
    app.context_processor(lambda: {"route_live": lambda path: any(r.rule == path for r in app.url_map.iter_rules())})
    return statuses


# ---------- scaffolding ----------
def _one_line(text: str, limit: int) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(text or "")).strip()
    return text[:limit]


def _page_file(slug: str, title: str, description: str) -> str:
    return f'''<div class="section">
    <h2>{{{{ title }}}}</h2>
    <p style="color:#9aa4b2;">{{{{ description }}}}</p>
    <p>This page is the starting point for <code>{slug}</code>. Edit this file to change what the page shows.</p>
    <button class="btn btn-info" id="{slug}-ping" type="button">Test the API</button>
    <pre id="{slug}-out" style="margin-top:8px;"></pre>
</div>
<script>
document.getElementById('{slug}-ping').addEventListener('click', async function () {{
    const r = await fetch('/ext/{slug}/api/ping', {{ credentials: 'same-origin' }});
    document.getElementById('{slug}-out').textContent = JSON.stringify(await r.json(), null, 2);
}});
</script>
'''


def create_feature(root, slug: str, title: str, description: str = "", nav_label: str = "", icon: str = "🧩") -> dict:
    root = Path(root)
    slug = str(slug or "").strip().lower()
    if not SLUG_RE.match(slug) or keyword.iskeyword(slug) or slug in RESERVED_SLUGS:
        raise FeatureError("Name must be 3-31 characters: lowercase letters, digits and underscores, starting with a letter (not a reserved word).")
    title = _one_line(title, 60)
    if not title:
        raise FeatureError("A title is required.")
    description = _one_line(description, 300)
    nav_label = _one_line(nav_label, 40) or title
    icon = _one_line(icon, 4) or "🧩"
    directory = root / FEATURES_DIR / slug
    if directory.exists():
        raise FeatureError(f"A feature named {slug} already exists.")
    package = root / FEATURES_DIR
    package.mkdir(exist_ok=True)
    if not (package / "__init__.py").exists():
        (package / "__init__.py").write_text('"""Self-contained features loaded by managers/feature_loader.py."""\n', encoding="utf-8")
    (directory / "templates").mkdir(parents=True)
    (directory / "__init__.py").write_text(f'''# {title}: {description}
# Edit this file for the feature's logic and routes.
# Page markup: templates/index.html.  Name, menu entry and on/off default: feature.json.
from flask import Blueprint, jsonify


def init(app, ctx):
    bp = Blueprint("feature_{slug}", __name__, url_prefix="/ext/{slug}")

    @bp.route("/")
    def index():
        denied = ctx.admin_page(False)
        if denied is not None:
            return denied
        return ctx.render_page("index.html", title={title!r}, description={description!r})

    @bp.route("/api/ping")
    def ping():
        denied = ctx.admin_page(True)
        if denied is not None:
            return denied
        return jsonify({{"ok": True, "feature": "{slug}"}})

    return bp
''', encoding="utf-8")
    (directory / "templates" / "index.html").write_text(_page_file(slug, title, description), encoding="utf-8")
    manifest = {
        "title": title, "description": description, "version": "0.1.0", "enabled": True, "core": False,
        "nav": {"label": nav_label, "href": f"/ext/{slug}/", "icon": icon}, "created": time.strftime("%Y-%m-%d"),
    }
    _write_json(directory / "feature.json", manifest)
    (directory / "README.md").write_text(f'''# {title}

{description}

Everything for this feature lives in this folder. Nothing here needs to be added to `main.py`.

| To change | Edit |
|-----------|------|
| What the page looks like | `templates/index.html` |
| Routes, API and logic | `__init__.py` |
| Name, menu entry, default on/off | `feature.json` |
| Turn it on or off | Code Manager -> Features (stored in `data/feature_flags.json`) |

URL: `/ext/{slug}/`. Restart the app after changing Python files or the on/off switch.
Remove it by deleting this folder; nothing else references it.
''', encoding="utf-8")
    test_path = root / "tests" / f"test_feature_{slug}.py"
    if (root / "tests").is_dir() and not test_path.exists():
        test_path.write_text(f'''from pathlib import Path

from flask import Flask

from managers.feature_loader import load_features

ROOT = Path(__file__).resolve().parent.parent


def test_{slug}_loads_and_answers():
    app = Flask(__name__)
    statuses = load_features(app, ROOT, "", lambda json_response: None, lambda: None)
    status = next(s for s in statuses if s["slug"] == "{slug}")
    assert status["state"] == "loaded", status["error"]
    assert app.test_client().get("/ext/{slug}/api/ping").get_json()["ok"] is True
''', encoding="utf-8")
    _register_in_source_map(root, slug, title, description)
    return {"slug": slug, "path": directory.relative_to(root).as_posix(), "url": f"/ext/{slug}/",
            "files": sorted(p.relative_to(root).as_posix() for p in directory.rglob("*") if p.is_file())}


def _register_in_source_map(root: Path, slug: str, title: str, description: str) -> None:
    path = root / "docs" / "source_map.json"
    doc = _read_json(path, None)
    if not isinstance(doc, dict) or not isinstance(doc.get("components"), list):
        return
    base = f"{FEATURES_DIR}/{slug}"
    doc["components"].append({
        "id": f"feature-{slug}", "title": title, "category": "Add-on features",
        "summary": description or "Isolated add-on feature.",
        "how_to_edit": f"Page: {base}/templates/index.html. Routes and logic: {base}/__init__.py. Name, menu entry, default on/off: {base}/feature.json.",
        "files": [
            {"path": f"{base}/__init__.py", "role": "Routes and logic"},
            {"path": f"{base}/templates/index.html", "role": "Page markup"},
            {"path": f"{base}/feature.json", "role": "Name, menu entry, default on/off"},
            {"path": f"{base}/README.md", "role": "Which file edits what"},
        ],
        "urls": [f"/ext/{slug}/"], "warning": "",
    })
    _write_json(path, doc)

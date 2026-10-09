import json
import shutil
from pathlib import Path

import pytest
from flask import Blueprint, Flask

from managers import feature_loader as fl
from managers.code_manager import CodeManager

ROOT = Path(__file__).resolve().parent.parent


def _app():
    return Flask(__name__)


def test_analysis_of_real_main_finds_routes_and_templates():
    a = CodeManager(_app(), ROOT).analyze()
    assert a["route_count"] > 100
    assert a["groups"] and a["templates"]
    assert all(g["difficulty"] in {"easy", "medium", "hard"} for g in a["groups"])


def test_analysis_of_small_file(tmp_path):
    (tmp_path / "main.py").write_text(
        "import os\nX = 1\n\ndef helper():\n    return X\n\n"
        "@app.route('/api/a/one')\ndef one():\n    return helper()\n\n"
        "@app.route('/api/a/one', methods=['POST'])\ndef one_b():\n    return os.name\n\n"
        "@app.route('/other')\ndef other():\n    return 1\n", encoding="utf-8")
    a = CodeManager(_app(), tmp_path).analyze()
    group = next(g for g in a["groups"] if g["prefix"] == "/api/a")
    assert group["needs_helpers"] == ["helper"] and group["needs_values"] == ["X"]
    assert group["uses_imports"] == ["os"] and group["difficulty"] == "easy"
    assert a["route_count"] == 3


def test_baseline_detects_missing_route(tmp_path):
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    app = _app()
    app.add_url_rule("/a", "a", lambda: "a")
    app.add_url_rule("/b", "b", lambda: "b")
    cm = CodeManager(app, tmp_path)
    assert cm.compare_baseline()["has_baseline"] is False
    cm.save_baseline()
    app2 = _app()
    app2.add_url_rule("/a", "a", lambda: "a")
    result = CodeManager(app2, tmp_path).compare_baseline()
    assert [r["rule"] for r in result["missing"]] == ["/b"]


def test_budget_ratchet_and_violation(tmp_path):
    (tmp_path / "main.py").write_text("@app.route('/a')\ndef a():\n    return 1\n", encoding="utf-8")
    cm = CodeManager(_app(), tmp_path)
    assert cm.set_budget(ratchet=True)["ok"]
    (tmp_path / "main.py").write_text("".join(f"@app.route('/r{i}')\ndef r{i}():\n    return 1\n" for i in range(3)), encoding="utf-8")
    assert not CodeManager(_app(), tmp_path).budget()["ok"]


def test_main_py_stays_within_budget():
    budget = CodeManager(_app(), ROOT).budget()
    assert budget["configured"], "docs/main_budget.json is missing"
    assert budget["ok"], " ".join(budget["problems"]) + " Put new features in app_features/<name>/."


def test_live_routes_match_baseline():
    """No route that existed at the last baseline may disappear."""
    import main
    result = CodeManager(main.app, ROOT).compare_baseline()
    assert result["has_baseline"], "docs/route_baseline.json is missing"
    assert not result["missing"], f"Routes lost: {result['missing'][:10]}"


def test_create_feature_loads_and_is_isolated(tmp_path):
    (tmp_path / "tests").mkdir()
    info = fl.create_feature(tmp_path, "bookmarks", "Bookmarks", "Save links")
    assert "app_features/bookmarks/__init__.py" in info["files"]
    with pytest.raises(fl.FeatureError):
        fl.create_feature(tmp_path, "bookmarks", "Again")
    for bad in ("Bad Name", "ab", "class", "../x", "api"):
        with pytest.raises(fl.FeatureError):
            fl.create_feature(tmp_path, bad, "T")
    app = _app()
    layout = "<html>{% block content %}{% endblock %}</html>"
    statuses = fl.load_features(app, tmp_path, layout, lambda j: None, lambda: None)
    assert statuses[0]["state"] == "loaded"
    client = app.test_client()
    assert client.get("/ext/bookmarks/api/ping").get_json()["ok"]
    page = client.get("/ext/bookmarks/").get_data(as_text=True)
    assert page.startswith("<html>") and "Bookmarks" in page
    assert app.config["_feature_nav"][0]["href"] == "/ext/bookmarks/"


def test_broken_feature_does_not_stop_others(tmp_path):
    fl.create_feature(tmp_path, "good_one", "Good")
    bad = tmp_path / "app_features" / "bad_one"
    bad.mkdir()
    (bad / "__init__.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    app = _app()
    states = {s["slug"]: s for s in fl.load_features(app, tmp_path, "", lambda j: None, lambda: None)}
    assert states["good_one"]["state"] == "loaded"
    assert states["bad_one"]["state"] == "error" and "boom" in states["bad_one"]["error"]


def test_flags_disable_feature_but_not_core(tmp_path):
    fl.create_feature(tmp_path, "toggled", "Toggled")
    fl.set_flag(tmp_path, "toggled", False)
    app = _app()
    states = fl.load_features(app, tmp_path, "", lambda j: None, lambda: None)
    assert states[0]["state"] == "disabled"
    assert app.test_client().get("/ext/toggled/api/ping").status_code == 404
    core = tmp_path / "app_features" / "toggled" / "feature.json"
    data = json.loads(core.read_text(encoding="utf-8"))
    data["core"] = True
    core.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(fl.FeatureError):
        fl.set_flag(tmp_path, "toggled", False)


def test_blueprint_probe_link_and_unlink(tmp_path):
    (tmp_path / "blueprints").mkdir()
    (tmp_path / "blueprints" / "demo_routes.py").write_text(
        "from flask import Blueprint\nbp = Blueprint('demo', __name__)\n\n@bp.route('/demo/hi')\ndef hi():\n    return 'hi'\n\n@bp.route('/taken')\ndef taken():\n    return 'x'\n",
        encoding="utf-8")
    (tmp_path / "blueprints" / "broken_routes.py").write_text("import not_a_real_module_xyz\n", encoding="utf-8")
    app = _app()
    app.add_url_rule("/taken", "taken_main", lambda: "main")
    probe = fl.probe_blueprint(app, tmp_path, "blueprints.demo_routes")
    status = {r["rule"]: r["status"] for r in probe["blueprints"][0]["routes"]}
    assert status == {"/demo/hi": "new", "/taken": "collides"}
    assert "demo" not in app.blueprints
    assert fl.probe_blueprint(app, tmp_path, "blueprints.broken_routes")["ok"] is False
    for bad in ("os", "blueprints.../x", "blueprints.missing"):
        with pytest.raises(fl.FeatureError):
            fl.probe_blueprint(app, tmp_path, bad)
    fl.link_blueprint(tmp_path, "blueprints.demo_routes")
    fl.load_features(app, tmp_path, "", lambda j: None, lambda: None)
    client = app.test_client()
    assert client.get("/demo/hi").data == b"hi"
    assert client.get("/taken").data == b"main"
    fl.unlink_blueprint(tmp_path, "blueprints.demo_routes")
    assert fl.read_linked(tmp_path) == []

MAIN_WITH_PAGE = (
    "from flask import render_template_string, request, get_flashed_messages\n"
    "HTML_TEMPLATE = '<html>{% block content %}{% endblock %}</html>'\n"
    "DEMO_TEMPLATE = \"\"\"\n<h1>Demo {{ 1 + 1 }}</h1>\n\"\"\"\n\n"
    "@app.route('/demo')\n@requires_permission('dashboard')\n"
    "def demo_page():\n    return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}', DEMO_TEMPLATE), request=request, get_flashed_messages=get_flashed_messages)\n\n"
    "@app.route('/keep')\ndef keep():\n    return 'k'\n"
)


def _page_project(tmp_path):
    (tmp_path / "main.py").write_text(MAIN_WITH_PAGE, encoding="utf-8")
    (tmp_path / "templates").mkdir()
    (tmp_path / "blueprints").mkdir()
    (tmp_path / "blueprints" / "demo_routes.py").write_text(
        "from flask import Blueprint\ndemo_bp = Blueprint('demo_routes', 'blueprints.demo_routes')\n", encoding="utf-8")
    app = _app()
    app.register_blueprint(Blueprint("demo_routes", "blueprints.demo_routes"))
    return app, CodeManager(app, tmp_path)


def test_pages_detects_movable_page(tmp_path):
    _, cm = _page_project(tmp_path)
    pages = cm.pages()
    assert [(p["func"], p["template"], p["eligible"]) for p in pages] == [("demo_page", "DEMO_TEMPLATE", True)]


def test_isolate_page_moves_and_rolls_back(tmp_path):
    app, cm = _page_project(tmp_path)
    assert cm.isolate_page("demo_page", "blueprints.demo_routes")["applied"] is False
    assert "DEMO_TEMPLATE" in (tmp_path / "main.py").read_text(encoding="utf-8")
    cm._verify_fresh_app = lambda timeout=240: "1 routes would go missing"
    result = cm.isolate_page("demo_page", "blueprints.demo_routes", dry_run=False)
    assert "restored" in result["error"].lower()
    assert (tmp_path / "main.py").read_text(encoding="utf-8") == MAIN_WITH_PAGE
    assert not (tmp_path / "templates" / "demo.html").exists()
    assert "demo_page" not in (tmp_path / "blueprints" / "demo_routes.py").read_text(encoding="utf-8")
    cm._verify_fresh_app = lambda timeout=240: ""
    result = cm.isolate_page("demo_page", "blueprints.demo_routes", dry_run=False)
    assert result["applied"]
    main_after = (tmp_path / "main.py").read_text(encoding="utf-8")
    assert "DEMO_TEMPLATE" not in main_after and "demo_page" not in main_after and "def keep" in main_after
    assert "Demo" in (tmp_path / "templates" / "demo.html").read_text(encoding="utf-8")
    bp_text = (tmp_path / "blueprints" / "demo_routes.py").read_text(encoding="utf-8")
    assert "def demo_page" in bp_text and "requires_permission" in bp_text


def test_create_blueprint(tmp_path):
    (tmp_path / "blueprints").mkdir()
    cm = CodeManager(_app(), tmp_path)
    info = cm.create_blueprint("okta")
    assert (tmp_path / info["file"]).is_file() and fl.read_linked(tmp_path)[0]["module"] == "blueprints.okta_routes"
    with pytest.raises(Exception):
        cm.create_blueprint("okta")
    with pytest.raises(Exception):
        cm.create_blueprint("../evil")

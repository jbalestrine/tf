import json
from types import SimpleNamespace

from flask import Flask, jsonify

from managers.management_inventory import build_inventory, register_inventory


def make_app(tmp_path, denied=False):
    app = Flask(__name__)
    app.config["UPLOAD_FOLDER"] = tmp_path / "uploads"
    feature = SimpleNamespace(display_name="Example", enabled=True)
    manager = SimpleNamespace(feature_configs={"example": feature})
    modules = {"rbac": {"enabled": True}, "script": {"enabled": False}}
    managers = {"rbac": object(), "script": None}
    register_inventory(app, tmp_path, manager, modules, managers,
                       lambda _: (jsonify({"error": "Admin required"}), 403) if denied else None)
    return app, feature, modules


def test_inventory_reports_distinct_configured_and_runtime_states(tmp_path):
    app, feature, modules = make_app(tmp_path)
    directory = tmp_path / "app_features" / "sample"
    directory.mkdir(parents=True)
    (directory / "__init__.py").write_text("", encoding="utf-8")
    (directory / "feature.json").write_text(json.dumps({"title": "Sample", "enabled": True}), encoding="utf-8")
    flags = tmp_path / "data" / "feature_flags.json"
    flags.parent.mkdir()
    flags.write_text('{"sample": false}', encoding="utf-8")
    addon = tmp_path / "uploads" / "extracted" / "example-addon"
    addon.mkdir(parents=True)
    (tmp_path / "data" / "features.json").write_text(
        '{"old.action": {"label": "Old action", "enabled": true}}', encoding="utf-8")
    feature.enabled = False
    modules["script"]["enabled"] = True
    app.config["_features"] = [{"slug": "sample", "state": "loaded", "error": ""}]

    result = app.test_client().get("/api/management/inventory")
    assert result.status_code == 200
    rows = {(item["kind"], item["key"]): item for item in result.get_json()["items"]}
    assert rows["Configured feature", "example"]["runtime"] == "enabled at startup"
    assert rows["Configured feature", "example"]["configured"] == "disabled"
    assert rows["App feature", "sample"]["configured"] == "disabled"
    assert rows["App feature", "sample"]["runtime"] == "loaded"
    assert rows["Built-in module", "script"]["runtime"] == "manager not present"
    assert rows["Built-in module", "script"]["configured"] == "enabled"
    assert rows["Add-on folder", "example-addon"]["runtime"] == "not tracked as running"
    assert rows["Page flag", "dashboard"]["configured"] == "enabled"
    assert rows["Stored add-on feature", "old.action"]["runtime"] == "not verified"


def test_inventory_requires_admin_and_reports_invalid_flags(tmp_path):
    app, _, _ = make_app(tmp_path, denied=True)
    assert app.test_client().get("/api/management/inventory").status_code == 403
    data = tmp_path / "data"
    data.mkdir()
    (data / "feature_flags.json").write_text("{invalid", encoding="utf-8")
    app, _, _ = make_app(tmp_path)
    result = app.test_client().get("/api/management/inventory")
    assert result.status_code == 500
    assert "Unable to build inventory" in result.get_json()["error"]


def test_module_toggle_requires_admin_preserves_core_and_saves_for_restart(tmp_path, monkeypatch):
    import main

    modules = {"rbac": {"enabled": True}, "script": {"enabled": True}}
    monkeypatch.setattr(main, "ENABLED_MODULES", modules)
    monkeypatch.setitem(main.app.config, "MODULES_CONFIG", tmp_path / "modules.json")
    endpoint = main.api_modules_toggle.__wrapped__
    monkeypatch.setattr(main, "_admin_post_guard", lambda: (jsonify({"error": "Admin required"}), 403))
    with main.app.test_request_context("/api/modules/toggle", method="POST", data={"module": "script"}):
        assert endpoint()[1] == 403
    assert modules["script"]["enabled"] is True
    monkeypatch.setattr(main, "_admin_post_guard", lambda: None)
    with main.app.test_request_context("/api/modules/toggle", method="POST", data={"module": "rbac"}):
        assert endpoint()[1] == 400
    with main.app.test_request_context("/api/modules/toggle", method="POST", data={"module": "script"}):
        response = endpoint().get_json()
    assert response["restart_required"] is True
    assert response["enabled"] is False
    assert json.loads((tmp_path / "modules.json").read_text())["script"]["enabled"] is False


def test_real_workspace_inventory_is_serializable():
    import main
    from features.manager import get_feature_manager

    manager = get_feature_manager()
    startup = {name: config.enabled for name, config in manager.feature_configs.items()}
    items = build_inventory(main.app, main.app.root_path, manager, main.ENABLED_MODULES, main.managers, startup)
    assert any(item["kind"] == "App feature" and item["key"] == "code_manager" for item in items)
    assert any(item["kind"] == "Built-in module" and item["key"] == "rbac" for item in items)
    json.dumps(items)


def test_three_management_pages_include_inventory(monkeypatch):
    import main

    monkeypatch.setattr(main, "ENABLED_MODULES", {"rbac": {"enabled": True}})
    monkeypatch.setattr(main, "managers", {"rbac": None})
    with main.app.test_request_context("/modules"):
        modules_html = main.modules_page.__wrapped__()
    with main.app.test_request_context("/addons/modules"):
        addons_html = main.render_addons_modules_page([])
    feature_html = main.app.test_client().get("/features").get_data(as_text=True)
    for html in (modules_html, addons_html, feature_html):
        assert 'id="management-inventory"' in html
        assert '/static/js/management-inventory.js' in html

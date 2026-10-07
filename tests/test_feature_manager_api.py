import features.manager as feature_manager_module
from features.manager import FeatureManager
from flask import Flask


class PlatformAdmin:
    is_authenticated = True
    provider = "rbac"
    role = "admin"
    permissions = ["*"]


class AnonymousUser:
    is_authenticated = False


def _make_feature_manager(tmp_path, monkeypatch, user):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(feature_manager_module, "current_user", user)
    app = Flask(__name__)
    manager = FeatureManager(app, str(tmp_path / "features"))
    return app, manager


def _post(client, path, payload):
    return client.post(
        path,
        json=payload,
        headers={"Origin": "http://localhost"},
    )


def test_feature_create_list_and_toggle_round_trip(tmp_path, monkeypatch):
    app, manager = _make_feature_manager(tmp_path, monkeypatch, PlatformAdmin())
    client = app.test_client()
    feature = {
        "name": "demo-feature",
        "display_name": "Demo Feature",
        "description": "A safe scaffold.",
        "dependencies": [],
        "handler_code": "def register_routes(app):\n    return None\n",
    }

    created = _post(client, "/api/features/create", feature)

    assert created.status_code == 201
    assert created.get_json()["success"] is True
    assert (tmp_path / "features" / "handlers" / "demo_feature.py").is_file()
    listed = client.get("/api/features").get_json()["features"]
    assert [item["name"] for item in listed] == ["demo-feature"]

    enabled = _post(client, "/api/features/demo-feature/toggle", {"enabled": True})
    assert enabled.status_code == 200
    assert enabled.get_json()["feature"]["enabled"] is True
    disabled = _post(client, "/api/features/demo-feature/toggle", {"enabled": False})
    assert disabled.status_code == 200
    assert disabled.get_json()["feature"]["enabled"] is False

    duplicate = _post(client, "/api/features/create", feature)
    assert duplicate.status_code == 409
    assert manager.feature_configs["demo-feature"].display_name == "Demo Feature"


def test_feature_create_rejects_invalid_names_code_and_non_admins(tmp_path, monkeypatch):
    app, _ = _make_feature_manager(tmp_path, monkeypatch, PlatformAdmin())
    client = app.test_client()
    base = {
        "display_name": "Example",
        "dependencies": [],
        "handler_code": "def register_routes(app):\n    return None\n",
    }

    traversal = _post(client, "/api/features/create", {**base, "name": "../escape"})
    assert traversal.status_code == 400
    invalid_code = _post(client, "/api/features/create", {**base, "name": "bad-code", "handler_code": "def broken("})
    assert invalid_code.status_code == 400

    monkeypatch.setattr(feature_manager_module, "current_user", AnonymousUser())
    denied = _post(client, "/api/features/create", {**base, "name": "denied-feature"})
    assert denied.status_code == 403


def test_feature_create_requires_same_origin(tmp_path, monkeypatch):
    app, _ = _make_feature_manager(tmp_path, monkeypatch, PlatformAdmin())
    response = app.test_client().post(
        "/api/features/create",
        json={
            "name": "demo-feature",
            "display_name": "Demo",
            "dependencies": [],
            "handler_code": "",
        },
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403

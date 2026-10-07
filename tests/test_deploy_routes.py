from pathlib import Path
from types import SimpleNamespace
import zipfile

from flask import Flask

from blueprints import deploy_routes


def _client(source_root, monkeypatch, *, is_admin=True):
    app = Flask(__name__)
    app.config["DEPLOY_SOURCE_ROOT"] = source_root
    app.register_blueprint(deploy_routes.deploy_bp)
    actor = SimpleNamespace(
        is_authenticated=is_admin,
        provider="rbac" if is_admin else None,
        role="admin" if is_admin else "user",
        permissions=["*"] if is_admin else [],
    )
    monkeypatch.setattr(deploy_routes, "current_user", actor)
    return app.test_client()


def test_deployment_center_and_apis_fail_closed_for_non_admin(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, is_admin=False)

    assert client.get("/deploy-center").status_code == 403
    assert client.get("/api/deployments/capabilities").status_code == 403
    assert client.post("/api/deployments/preview", json={}).status_code == 403
    assert client.post("/api/deployments/execute", json={}).status_code == 403


def test_bundle_requires_confirmation_and_excludes_runtime_and_secrets(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    destination = tmp_path / "new-bundles"
    (source_root / "blueprints").mkdir(parents=True)
    (source_root / "data").mkdir()
    (source_root / "config" / "environments").mkdir(parents=True)
    (source_root / "main.py").write_text("print('MasterChief')\n", encoding="utf-8")
    (source_root / "blueprints" / "routes.py").write_text("route = True\n", encoding="utf-8")
    (source_root / "main backup.py").write_text("password = 'old-secret'\n", encoding="utf-8")
    (source_root / ".env").write_text("API_TOKEN=not-for-bundle\n", encoding="utf-8")
    (source_root / "data" / "sessions.json").write_text('{"session": "private"}', encoding="utf-8")
    (source_root / "config" / "environments" / "prod.yaml").write_text(
        "database:\n  password: secret-value\n",
        encoding="utf-8",
    )
    client = _client(source_root, monkeypatch)

    preview = client.post(
        "/api/deployments/preview",
        json={"target": "local", "destination": str(destination)},
    )
    assert preview.status_code == 200
    plan = preview.get_json()["plan"]
    assert plan["file_count"] == 2
    assert not destination.exists()

    missing_confirmation = client.post(
        "/api/deployments/execute",
        json={"plan_id": plan["id"], "confirmed": False},
    )
    assert missing_confirmation.status_code == 400
    assert not destination.exists()

    staged = client.post(
        "/api/deployments/execute",
        json={"plan_id": plan["id"], "confirmed": True},
    )
    assert staged.status_code == 200
    bundle_path = Path(staged.get_json()["result"]["bundle"])
    assert bundle_path.is_file()
    with zipfile.ZipFile(bundle_path) as bundle:
        assert set(bundle.namelist()) == {"main.py", "blueprints/routes.py"}
    assert "staged only" in staged.get_json()["result"]["message"]


def test_deployment_preview_rejects_unsupported_or_relative_destination(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    unsupported = client.post(
        "/api/deployments/preview",
        json={"target": "docker", "destination": str(tmp_path / "bundle")},
    )
    relative = client.post(
        "/api/deployments/preview",
        json={"target": "usb", "destination": "relative/bundle"},
    )

    assert unsupported.status_code == 400
    assert relative.status_code == 400

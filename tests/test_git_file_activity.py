import subprocess

from flask import Flask, jsonify

from blueprints.scm_routes import scm_bp
from utils.git_file_activity import collect


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_activity_tracks_status_latest_commit_and_python_imports(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "base.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "consumer.py").write_text("from . import base\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.name=Test", "-c", "user.email=t@example.invalid",
        "commit", "-qm", "initial")
    (tmp_path / "pkg" / "base.py").write_text("value = 2\n", encoding="utf-8")
    (tmp_path / "new file.txt").write_text("new", encoding="utf-8")
    data = collect(tmp_path)
    paths = {f["path"]: f["sources"] for f in data["files"]}
    assert "new file.txt" in paths
    assert "latest commit" in paths["pkg/base.py"]
    assert any("working tree" in item for item in paths["pkg/base.py"])
    assert {"from": "pkg/consumer.py", "to": "pkg/base.py"} in data["edges"]
    assert data["coverage"]["python_scanned"] == 3


def test_activity_requires_admin_and_reports_failures(tmp_path, monkeypatch):
    app = Flask(__name__, root_path=str(tmp_path))
    app.register_blueprint(scm_bp)
    monkeypatch.setattr("blueprints.scm_routes._enabled", lambda: True)
    client = app.test_client()
    assert client.get("/sys/api/scm/activity").status_code == 503
    app.config["SCM_ADMIN_GET_GUARD"] = lambda: (jsonify(error="denied"), 403)
    assert client.get("/sys/api/scm/activity").status_code == 403
    app.config["SCM_ADMIN_GET_GUARD"] = lambda: None
    assert client.get("/sys/api/scm/activity").status_code == 500

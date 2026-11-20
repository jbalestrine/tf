import subprocess

from flask import Flask, jsonify

from blueprints.scm_routes import scm_bp


def test_activity_editor_permissions_conflicts_and_line_endings(tmp_path, monkeypatch):
    app = Flask(__name__, root_path=str(tmp_path))
    app.register_blueprint(scm_bp)
    monkeypatch.setattr("blueprints.scm_routes._enabled", lambda: True)
    client = app.test_client()
    path = tmp_path / "example.txt"
    path.write_bytes(b"first\r\nsecond\r\n")
    assert client.get("/sys/api/scm/activity-file?path=example.txt").status_code == 503
    app.config["SCM_ADMIN_GET_GUARD"] = lambda: None
    app.config["SCM_ADMIN_POST_GUARD"] = lambda: (jsonify(error="denied"), 403)
    loaded = client.get("/sys/api/scm/activity-file?path=example.txt").get_json()
    assert loaded["content"] == "first\nsecond\n"
    assert client.post("/sys/api/scm/activity-file", json={"path": "example.txt"}).status_code == 403
    app.config["SCM_ADMIN_POST_GUARD"] = lambda: None
    path.write_bytes(b"external\r\n")
    payload = {"path": "example.txt", "content": "new\n", "version": loaded["version"]}
    assert client.post("/sys/api/scm/activity-file", json=payload).status_code == 409
    assert path.read_bytes() == b"external\r\n"
    payload["version"] = client.get("/sys/api/scm/activity-file?path=example.txt").get_json()["version"]
    assert client.post("/sys/api/scm/activity-file", json=payload).status_code == 200
    assert path.read_bytes() == b"new\r\n"
    assert client.get("/sys/api/scm/activity-file?path=../example.txt").status_code == 400
    assert client.get("/sys/api/scm/activity-file?path=.git/config").status_code == 400
    assert client.get("/sys/api/scm/activity-file?path=missing.txt").status_code == 400
    path.write_bytes(b"binary\0data")
    assert client.get("/sys/api/scm/activity-file?path=example.txt").status_code == 400
    path.write_bytes(b"mixed\r\nlines\n")
    assert client.get("/sys/api/scm/activity-file?path=example.txt").status_code == 400


def test_edit_stage_review_and_commit_in_isolated_repository(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    (tmp_path / "a.txt").write_text("before\n", encoding="utf-8")
    (tmp_path / "other.txt").write_text("before\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "initial")
    (tmp_path / "other.txt").write_text("existing change\n", encoding="utf-8")
    git("add", "other.txt")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "note.txt").write_text("staged too\n", encoding="utf-8")
    git("add", "-f", ".claude/note.txt")
    app = Flask(__name__, root_path=str(tmp_path))
    app.register_blueprint(scm_bp)
    app.config["SCM_ADMIN_GET_GUARD"] = lambda: None
    app.config["SCM_ADMIN_POST_GUARD"] = lambda: None
    monkeypatch.setattr("blueprints.scm_routes._enabled", lambda: True)
    client = app.test_client()
    loaded = client.get("/sys/api/scm/activity-file?path=a.txt").get_json()
    assert client.post("/sys/api/scm/activity-file", json={
        "path": "a.txt", "content": "updated\n", "version": loaded["version"]
    }).status_code == 200
    assert client.post("/sys/api/scm/commands", json={
        "action": "stage", "values": {"path": "a.txt"}, "confirmation": "stage"
    }).get_json()["ok"]
    assert {item["file"] for item in client.get("/sys/api/scm/status").get_json()["staged"]} == {"a.txt", "other.txt", ".claude/note.txt"}
    diff = client.post("/sys/api/scm/commands", json={"action": "staged_diff", "values": {}}).get_json()
    assert "+updated" in diff["stdout"] and "+existing change" in diff["stdout"]
    assert client.post("/sys/api/scm/commands", json={
        "action": "commit", "values": {"message": "test edit"}, "confirmation": "commit"
    }).get_json()["ok"]
    assert set(git("show", "--format=", "--name-only", "HEAD").stdout.split()) == {"a.txt", "other.txt", ".claude/note.txt"}

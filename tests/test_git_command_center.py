import subprocess
from unittest import mock

import pytest
from flask import Flask, jsonify

from blueprints.scm_routes import scm_bp
from utils.git_command_center import build_command, execute


def test_command_vectors_validate_inputs():
    assert build_command("stage", {"path": "file name.txt"}) == [
        "git", "add", "--", "file name.txt"
    ]
    assert build_command("stage", {"path": " leading.txt"})[-1] == " leading.txt"
    assert build_command("stage_all", {}) == ["git", "add", "-A"]
    with pytest.raises(ValueError):
        build_command("push_upstream", {"branch": "--force"})
    with pytest.raises(ValueError):
        build_command("status", {"extra": "value"})
    with pytest.raises(ValueError):
        build_command("arbitrary", {})


def test_mutations_require_confirmation_and_do_not_use_shell(tmp_path):
    with mock.patch("utils.git_command_center.subprocess.run") as run:
        with pytest.raises(ValueError):
            execute(tmp_path, "reset_hard", {"ref": "HEAD"}, None)
        run.assert_not_called()
        run.return_value = subprocess.CompletedProcess([], 0, "ok", "")
        result = execute(tmp_path, "reset_hard", {"ref": "HEAD"}, "reset_hard")
        assert result["ok"]
        assert run.call_args.args[0] == ["git", "reset", "--hard", "HEAD"]
        assert not run.call_args.kwargs.get("shell", False)
        assert run.call_args.kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
        execute(tmp_path, "stage", {"path": ":(glob)*"}, "stage")
        assert run.call_args.kwargs["env"]["GIT_LITERAL_PATHSPECS"] == "1"


def test_routes_fail_closed_and_apply_post_guard(tmp_path, monkeypatch):
    app = Flask(__name__, root_path=str(tmp_path))
    app.register_blueprint(scm_bp)
    monkeypatch.setattr("blueprints.scm_routes._enabled", lambda: True)
    client = app.test_client()
    assert client.get("/sys/api/scm/commands").status_code == 503
    app.config["SCM_ADMIN_GET_GUARD"] = lambda: None
    app.config["SCM_ADMIN_POST_GUARD"] = lambda: (jsonify(error="denied"), 403)
    assert client.get("/sys/api/scm/commands").status_code == 200
    assert client.post("/sys/api/scm/commands", json={"action": "status", "values": {}}).status_code == 403
    assert client.post("/sys/api/scm/commit", json={"message": "test"}).status_code == 403
    app.config["SCM_ADMIN_POST_GUARD"] = lambda: None
    assert client.post("/sys/api/scm/commit", json={"message": "test"}).status_code == 400
    assert client.post("/sys/api/scm/commands", json={"action": "reset_hard", "values": {"ref": "HEAD"}}).status_code == 400


def test_read_only_command_in_isolated_repository(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    result = execute(tmp_path, "status", {}, None)
    assert result["ok"]
    assert "branch" in result["stdout"].lower()


def test_stage_all_stages_modified_deleted_and_new_files_with_confirmation(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "modified.txt").write_text("before", encoding="utf-8")
    (tmp_path / "deleted.txt").write_text("before", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Test",
                    "-c", "user.email=test@example.invalid", "commit", "-qm", "initial"], check=True)
    (tmp_path / "modified.txt").write_text("after", encoding="utf-8")
    (tmp_path / "deleted.txt").unlink()
    (tmp_path / "new.txt").write_text("new", encoding="utf-8")
    with pytest.raises(ValueError):
        execute(tmp_path, "stage_all", {}, None)
    assert execute(tmp_path, "stage_all", {}, "stage_all")["ok"]
    status = subprocess.run(["git", "-C", str(tmp_path), "status", "--short"],
                            check=True, capture_output=True, text=True).stdout
    assert "M  modified.txt" in status
    assert "D  deleted.txt" in status
    assert "A  new.txt" in status


def test_status_preserves_unstaged_paths_with_spaces(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Test",
                    "-c", "user.email=test@example.invalid", "commit", "--allow-empty",
                    "-qm", "initial"], check=True)
    path = tmp_path / "a file.txt"
    path.write_text("test", encoding="utf-8")
    app = Flask(__name__, root_path=str(tmp_path))
    app.register_blueprint(scm_bp)
    app.config["SCM_ADMIN_GET_GUARD"] = lambda: None
    monkeypatch.setattr("blueprints.scm_routes._enabled", lambda: True)
    result = app.test_client().get("/sys/api/scm/status").get_json()
    assert result["unstaged"] == [{"status": "?", "file": "a file.txt"}]

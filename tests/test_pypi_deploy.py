import subprocess
from unittest import mock

import pytest
from flask import Flask, jsonify

from blueprints.scm_routes import scm_bp
from utils.git_activity_editor import EditConflict
from utils.pypi_deploy import create_release_tag, deploy, release_preview, update_version, version_preview


COMMIT = "a" * 40


def test_validates_inputs_and_uses_fixed_script_with_vault(tmp_path, monkeypatch):
    (tmp_path / "PYPI_ONLY_DEPLOY.ps1").write_text("", encoding="utf-8")
    monkeypatch.setattr("utils.pypi_deploy.sys.platform", "win32")
    monkeypatch.setattr("utils.pypi_deploy.shutil.which", lambda _: "powershell.exe")
    monkeypatch.setenv("TWINE_PASSWORD", "private")
    with mock.patch("utils.pypi_deploy.subprocess.run") as run:
        for tag in ("v1.2.3;bad", "../bad", None):
            with pytest.raises(ValueError):
                deploy(tmp_path, tag, "dry_run")
        with pytest.raises(ValueError):
            deploy(tmp_path, "v1.2.3", "publish", "wrong", COMMIT)
        run.assert_not_called()
        run.side_effect = [
            subprocess.CompletedProcess([], 0, COMMIT + "\n", ""),
            subprocess.CompletedProcess([], 0, "success", ""),
        ]
        result = deploy(tmp_path, "v1.2.3", "publish", "v1.2.3", COMMIT)
        assert result["commit"] == COMMIT
        args = run.call_args.args[0]
        assert args[-1] == "-UseVault" and "-DryRun" not in args
        assert "TWINE_PASSWORD" not in run.call_args.kwargs["env"]
        assert not run.call_args.kwargs.get("shell", False)


def test_rejects_moved_tag_and_reports_redacted_failures(tmp_path, monkeypatch):
    (tmp_path / "PYPI_ONLY_DEPLOY.ps1").write_text("", encoding="utf-8")
    monkeypatch.setattr("utils.pypi_deploy.sys.platform", "win32")
    monkeypatch.setattr("utils.pypi_deploy.shutil.which", lambda _: "powershell.exe")
    with mock.patch("utils.pypi_deploy.subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess([], 0, COMMIT, "")
        with pytest.raises(ValueError, match="different commit"):
            deploy(tmp_path, "v1.2.3", "publish", "v1.2.3", "b" * 40)
        assert run.call_count == 1
        run.side_effect = [subprocess.CompletedProcess([], 0, COMMIT, ""),
                           subprocess.CompletedProcess([], 1, "secret text already exists", "")]
        with pytest.raises(RuntimeError, match="already exists") as error:
            deploy(tmp_path, "v1.2.3", "dry_run")
        assert "secret text" not in str(error.value)
        assert run.call_args.args[0][-1] == "-DryRun"


def test_endpoint_requires_post_guard_and_propagates_errors(tmp_path, monkeypatch):
    app = Flask(__name__, root_path=str(tmp_path))
    app.register_blueprint(scm_bp)
    monkeypatch.setattr("blueprints.scm_routes._enabled", lambda: True)
    client = app.test_client()
    assert client.post("/sys/api/scm/pypi-deploy", json={}).status_code == 503
    app.config["SCM_ADMIN_POST_GUARD"] = lambda: (jsonify(error="denied"), 403)
    assert client.post("/sys/api/scm/pypi-deploy", json={}).status_code == 403
    app.config["SCM_ADMIN_POST_GUARD"] = lambda: None
    with mock.patch("utils.pypi_deploy.deploy", side_effect=ValueError("Invalid tag")):
        response = client.post("/sys/api/scm/pypi-deploy", json={"tag": "bad"})
        assert response.status_code == 400
        assert response.get_json()["error"] == "Invalid tag"


def test_preview_and_tag_use_verified_merged_branch(tmp_path):
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    git("switch", "-c", "Masterchief4")
    (repo / "setup.py").write_text('setup(\n    version="1.2.3",\n)\n', encoding="utf-8")
    git("add", "setup.py")
    git("commit", "-m", "release")
    git("remote", "add", "origin", str(remote))
    git("push", "-u", "origin", "Masterchief4")
    git("switch", "-c", "different-work")
    (repo / "setup.py").write_text('setup(\n    version="9.9.9",\n)\n', encoding="utf-8")
    preview = release_preview(repo)
    assert preview["tag"] == "v1.2.3"
    assert preview["local_tag_commit"] is None
    assert preview["remote_tag_exists"] is False
    with pytest.raises(ValueError, match="match the merged"):
        create_release_tag(repo, "v9.9.9", preview["commit"], "v9.9.9")
    with pytest.raises(ValueError, match="Confirm"):
        create_release_tag(repo, preview["tag"], preview["commit"], "wrong")
    created = create_release_tag(repo, preview["tag"], preview["commit"], preview["tag"])
    assert created["commit"] == preview["commit"]
    assert git("ls-remote", "--refs", "origin", "refs/tags/v1.2.3").startswith(preview["commit"])
    updated = release_preview(repo)
    assert updated["local_tag_commit"] == preview["commit"]
    assert updated["remote_tag_exists"] is True
    with pytest.raises(ValueError, match="already exists"):
        create_release_tag(repo, preview["tag"], preview["commit"], preview["tag"])


def test_preview_and_tag_routes_obey_guards(tmp_path, monkeypatch):
    app = Flask(__name__, root_path=str(tmp_path))
    app.register_blueprint(scm_bp)
    monkeypatch.setattr("blueprints.scm_routes._enabled", lambda: True)
    client = app.test_client()
    assert client.get("/sys/api/scm/pypi-release-preview").status_code == 503
    app.config["SCM_ADMIN_GET_GUARD"] = lambda: None
    app.config["SCM_ADMIN_POST_GUARD"] = lambda: (jsonify(error="denied"), 403)
    assert client.post("/sys/api/scm/pypi-release-tag", json={}).status_code == 403
    with mock.patch("utils.pypi_deploy.release_preview", return_value={"ok": True, "tag": "v1.2.3"}):
        assert client.get("/sys/api/scm/pypi-release-preview").get_json()["tag"] == "v1.2.3"


def test_stale_preview_and_partial_push_are_reported(tmp_path):
    preview = {"ok": True, "commit": COMMIT, "tag": "v1.2.3"}
    with mock.patch("utils.pypi_deploy.release_preview", return_value=preview), \
         mock.patch("utils.pypi_deploy._git") as run:
        with pytest.raises(ValueError, match="branch has changed"):
            create_release_tag(tmp_path, "v1.2.3", "b" * 40, "v1.2.3")
        run.assert_not_called()
        run.side_effect = [
            subprocess.CompletedProcess([], 1, "", ""),
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "", ""),
            RuntimeError("push failed"),
        ]
        with pytest.raises(RuntimeError, match="Local tag v1.2.3 was created"):
            create_release_tag(tmp_path, "v1.2.3", COMMIT, "v1.2.3")


def test_version_editor_preserves_other_changes_and_detects_conflicts(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "switch", "-c", "feature"], check=True, capture_output=True)
    path = tmp_path / "setup.py"
    original = b'setup(\r\n    name="masterchief",\r\n    version="4.0.0",\r\n    other="keep",\r\n)\r\n'
    path.write_bytes(original)
    preview = version_preview(tmp_path)
    assert preview["current"] == "4.0.0" and preview["suggested"] == "4.0.1"
    assert preview["branch"] == "feature"
    with pytest.raises(ValueError, match="greater"):
        update_version(tmp_path, "4.0.0", preview["file_version"], "feature", "4.0.0")
    with pytest.raises(ValueError, match="three"):
        update_version(tmp_path, "4.0.01", preview["file_version"], "feature", "4.0.01")
    result = update_version(tmp_path, "4.0.1", preview["file_version"], "feature", "4.0.1")
    assert result["previous"] == "4.0.0"
    assert path.read_bytes() == original.replace(b'4.0.0', b'4.0.1')
    with pytest.raises(EditConflict, match="changed since preview"):
        update_version(tmp_path, "4.0.2", preview["file_version"], "feature", "4.0.2")
    with pytest.raises(EditConflict, match="branch changed"):
        update_version(tmp_path, "4.0.2", result["file_version"], "other", "4.0.2")


def test_version_editor_guards_and_rejects_base_branch(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "switch", "-c", "Masterchief4"], check=True, capture_output=True)
    (tmp_path / "setup.py").write_text('version="4.0.0",\n', encoding="utf-8")
    preview = version_preview(tmp_path)
    with pytest.raises(ValueError, match="feature branch"):
        update_version(tmp_path, "4.0.1", preview["file_version"], "Masterchief4", "4.0.1")
    app = Flask(__name__, root_path=str(tmp_path))
    app.register_blueprint(scm_bp)
    monkeypatch.setattr("blueprints.scm_routes._enabled", lambda: True)
    client = app.test_client()
    assert client.get("/sys/api/scm/pypi-version").status_code == 503
    app.config["SCM_ADMIN_GET_GUARD"] = lambda: None
    app.config["SCM_ADMIN_POST_GUARD"] = lambda: (jsonify(error="denied"), 403)
    assert client.get("/sys/api/scm/pypi-version").get_json()["current"] == "4.0.0"
    assert client.post("/sys/api/scm/pypi-version", json={}).status_code == 403

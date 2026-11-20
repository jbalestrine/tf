import json
import subprocess
from unittest import mock

from flask import Flask

from blueprints.scm_routes import scm_bp
from utils.git_update_check import check_update


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def test_update_check_reads_real_remote_and_reports_pr_states(tmp_path):
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "switch", "-c", "feature")
    (repo / "file.txt").write_text("first", encoding="utf-8")
    git(repo, "add", "file.txt")
    git(repo, "commit", "-qm", "initial")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "feature")
    head = git(repo, "rev-parse", "HEAD")
    real_run = subprocess.run
    prs = [{"number": 4, "state": "MERGED", "url": "https://github.com/o/r/pull/4",
            "headRefOid": head, "baseRefName": "main", "headRepository": {"name": "r"},
            "headRepositoryOwner": {"login": "o"}}]

    def run(args, **kwargs):
        if args[0] == "gh":
            if args[1] == "repo":
                output = "o/r"
            elif args[2] == "view":
                output = json.dumps({"mergedAt": "2026-01-01T00:00:00Z",
                                     "mergeCommit": {"oid": "merge123"},
                                     "commits": [{"oid": head}], "reviewDecision": "",
                                     "statusCheckRollup": [], "isDraft": False})
            else:
                output = json.dumps(prs)
            return subprocess.CompletedProcess(args, 0, output, "")
        return real_run(args, **kwargs)

    with mock.patch("utils.git_update_check.subprocess.run", side_effect=run):
        result = check_update(repo)
        assert result["worktree"] == "clean"
        assert result["upstream"]["state"] == "matches"
        assert result["pull_request"]["state"] == "merged"
        assert result["pull_request"]["head_matches"]
        assert result["pull_request"]["merged_head_matches"]
        assert result["pull_request"]["merge_commit"] == "merge123"
        (repo / "new.txt").write_text("new", encoding="utf-8")
        assert check_update(repo)["worktree"] == "changes"
        git(repo, "add", "new.txt")
        git(repo, "commit", "-qm", "next")
        result = check_update(repo)
        assert result["upstream"]["state"] == "different"
        assert not result["pull_request"]["head_matches"]
        assert not result["pull_request"]["merged_head_matches"]
        prs.clear()
        assert check_update(repo)["pull_request"]["state"] == "none"
        git(repo, "branch", "--unset-upstream")
        assert check_update(repo)["upstream"]["state"] == "not_configured"
        git(repo, "switch", "--detach")
        assert check_update(repo)["branch"] is None


def test_update_check_reports_remote_and_pr_failures(tmp_path):
    def run(root, args, allow_missing=False):
        if args[:2] == ["git", "branch"]:
            return "feature"
        if args[:2] == ["git", "rev-parse"]:
            return "abc"
        if args[:2] == ["git", "status"]:
            return ""
        if args[:2] == ["git", "config"]:
            return "origin" if args[-1].endswith(".remote") else "refs/heads/feature"
        raise RuntimeError("network unavailable")
    with mock.patch("utils.git_update_check._run", side_effect=run):
        result = check_update(tmp_path)
    assert result["upstream"]["state"] == "unknown"
    assert result["pull_request"]["state"] == "unknown"
    assert "network unavailable" in result["upstream"]["message"]


def test_update_check_route_requires_admin_and_surfaces_errors(tmp_path, monkeypatch):
    app = Flask(__name__, root_path=str(tmp_path))
    app.register_blueprint(scm_bp)
    monkeypatch.setattr("blueprints.scm_routes._enabled", lambda: True)
    client = app.test_client()
    assert client.get("/sys/api/scm/update-check").status_code == 503
    app.config["SCM_ADMIN_GET_GUARD"] = lambda: ({"error": "denied"}, 403)
    assert client.get("/sys/api/scm/update-check").status_code == 403
    app.config["SCM_ADMIN_GET_GUARD"] = lambda: None
    with mock.patch("utils.git_update_check.check_update", side_effect=RuntimeError("Git unavailable")):
        assert client.get("/sys/api/scm/update-check").status_code == 502

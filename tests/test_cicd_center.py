import pytest
from managers.cicd_center import CICDCenter, CICDError

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


def test_explain_branch_filters(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("name: CI\non:\n  push:\n    branches: [main]\njobs:\n  t:\n    runs-on: ubuntu-latest\n", encoding="utf-8")
    (wf / "pub.yml").write_text("name: Pub\non:\n  push:\n    tags: ['v*']\n  workflow_dispatch:\njobs:\n  p:\n    runs-on: ubuntu-latest\n", encoding="utf-8")
    c = CICDCenter(tmp_path)
    by = lambda ref: {r["file"]: r["runs"] for r in c.explain("push", ref)}
    assert by("main") == {"ci.yml": True, "pub.yml": False}
    assert by("Masterchief4") == {"ci.yml": False, "pub.yml": False}
    assert by("v4.0.0") == {"ci.yml": False, "pub.yml": True}
    targets = {t["id"]: t["available"] for t in c.targets()}
    assert targets["gh:pub.yml"] and not targets["gh:ci.yml"]


def test_real_workflows_parse():
    c = CICDCenter(ROOT)
    files = {w["file"] for w in c.workflows()}
    assert "ci.yml" in files


def test_plan_and_dry_run_validation(tmp_path):
    c = CICDCenter(tmp_path)
    with pytest.raises(CICDError):
        c.run(["bogus"], "main")
    with pytest.raises(CICDError):
        c.run(["render:deploy"], "--evil")
    out = c.run(["render:deploy"], "main", dry_run=True)
    assert out["dry_run"] and out["steps"][0]["status"] == "planned"


def test_config_validation(tmp_path):
    c = CICDCenter(tmp_path)
    with pytest.raises(CICDError):
        c.save_config({"repo": "not a repo"})
    with pytest.raises(CICDError):
        c.save_config({"selected": ["nope"]})
    cfg = c.save_config({"repo": "a/b", "selected": ["render:deploy"]})
    assert c.load_config()["selected"] == ["render:deploy"] and cfg["repo"] == "a/b"

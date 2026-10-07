import pytest

from managers.echo_change_approvals import EchoChangeApprovalManager, EchoChangeError


def test_proposal_does_not_edit_source_until_confirmed_and_keeps_backup(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    source = root / "feature.py"
    source.write_text("def value():\n    return 1\n", encoding="utf-8")
    manager = EchoChangeApprovalManager(root / "data" / "approvals.sqlite3", root)

    proposal = manager.create_pending(
        "chat-1",
        "admin-1",
        "Update feature value",
        [{"path": "feature.py", "content": "def value():\n    return 2\n"}],
    )
    assert source.read_text(encoding="utf-8") == "def value():\n    return 1\n"
    assert manager.get_pending("chat-1", "admin-1")["proposal_id"] == proposal["proposal_id"]

    applied = manager.confirm_pending("chat-1", "admin-1")

    assert source.read_text(encoding="utf-8") == "def value():\n    return 2\n"
    assert applied["files"] == ["feature.py"]
    assert (root / applied["backups"][0]).read_text(encoding="utf-8") == "def value():\n    return 1\n"
    with pytest.raises(EchoChangeError, match="no pending"):
        manager.confirm_pending("chat-1", "admin-1")


def test_proposal_rejects_unsafe_paths_invalid_source_and_stale_files(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    source = root / "feature.py"
    source.write_text("value = 1\n", encoding="utf-8")
    manager = EchoChangeApprovalManager(root / "data" / "approvals.sqlite3", root)

    for path in ("../outside.py", "data/config.json", "secrets.json", "/outside.py"):
        with pytest.raises(EchoChangeError):
            manager.create_pending("chat", "admin", "Change", [{"path": path, "content": "pass\n"}])

    with pytest.raises(EchoChangeError, match="syntax"):
        manager.create_pending("chat", "admin", "Change", [{"path": "feature.py", "content": "def broken(:\n"}])

    manager.create_pending("chat", "admin", "Change", [{"path": "feature.py", "content": "value = 2\n"}])
    source.write_text("value = 3\n", encoding="utf-8")
    with pytest.raises(EchoChangeError, match="changed since"):
        manager.confirm_pending("chat", "admin")
    assert source.read_text(encoding="utf-8") == "value = 3\n"


def test_pending_proposals_are_isolated_by_session_and_user_and_can_be_cancelled(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    manager = EchoChangeApprovalManager(root / "data" / "approvals.sqlite3", root)

    manager.create_pending("chat-a", "admin-a", "Add module", [{"path": "module.py", "content": "value = 1\n"}])
    assert manager.get_pending("chat-a", "admin-b") is None
    assert manager.get_pending("chat-b", "admin-a") is None
    proposal_id = manager.cancel_pending("chat-a", "admin-a")
    assert proposal_id
    assert manager.get_pending("chat-a", "admin-a") is None
    with pytest.raises(EchoChangeError, match="no pending"):
        manager.confirm_pending("chat-a", "admin-a")


def test_exact_edits_can_safely_update_large_files_without_replacing_the_whole_file(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    original = "# existing source\n" * 70_000 + "FEATURE_ENABLED = False\n"
    source = root / "main.py"
    source.write_text(original, encoding="utf-8")
    manager = EchoChangeApprovalManager(root / "data" / "approvals.sqlite3", root)

    manager.create_pending(
        "large-file-chat",
        "admin-1",
        "Enable the feature",
        [
            {
                "path": "main.py",
                "edits": [{"find": "FEATURE_ENABLED = False", "replace": "FEATURE_ENABLED = True"}],
            }
        ],
    )

    pending = manager.get_pending("large-file-chat", "admin-1")
    assert pending["files"][0]["content"] == original.replace(
        "FEATURE_ENABLED = False",
        "FEATURE_ENABLED = True",
    )
    assert source.read_text(encoding="utf-8") == original
    manager.confirm_pending("large-file-chat", "admin-1")
    assert source.read_text(encoding="utf-8").endswith("FEATURE_ENABLED = True\n")

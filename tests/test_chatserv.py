import sqlite3
from pathlib import Path

import pytest
from flask import Flask

from blueprints.chatserv_routes import init_chatserv
from managers.chatserv import ChatServError, ChatServManager


PASSWORD = "test-password-strong"


def test_accounts_store_password_hashes_and_authenticate_case_insensitively(tmp_path):
    manager = ChatServManager(tmp_path / "chatserv.sqlite3")

    user = manager.register("Alice", PASSWORD)
    assert manager.authenticate("alice", PASSWORD)["id"] == user["id"]
    with pytest.raises(ChatServError, match="incorrect"):
        manager.authenticate("Alice", "incorrect-password")

    with sqlite3.connect(manager.database_path) as db:
        saved_hash = db.execute(
            "SELECT password_hash FROM chatserv_users WHERE id = ?", (user["id"],)
        ).fetchone()[0]
    assert saved_hash != PASSWORD


def test_channel_roles_control_topic_and_op_changes(tmp_path):
    manager = ChatServManager(tmp_path / "chatserv.sqlite3")
    owner = manager.register("Alice", PASSWORD)
    member = manager.register("Bobby", PASSWORD)

    room = manager.create_channel("#engineering", owner["id"])
    assert room["role"] == "owner"
    manager.join_channel("#engineering", member["id"])

    with pytest.raises(ChatServError, match="permission"):
        manager.update_topic("#engineering", member["id"], "Unauthorized topic")

    manager.set_member_role("#engineering", owner["id"], "Bobby", "op")
    manager.update_topic("#engineering", member["id"], "Build and ship")
    assert manager.channel_info("#engineering", member["id"])["topic"] == "Build and ship"
    manager.set_member_role("#engineering", owner["id"], "Bobby", "member")

    with pytest.raises(ChatServError, match="owner"):
        manager.set_member_role("#engineering", member["id"], "Alice", "member", is_admin=True)


def test_bots_messages_and_page_transfers_are_persisted(tmp_path):
    manager = ChatServManager(tmp_path / "chatserv.sqlite3")
    owner = manager.register("Alice", PASSWORD)
    target = manager.register("Bobby", PASSWORD)
    manager.create_bot("#lobby", owner["id"], "helper", "Answer as a concise build assistant.")
    bot = manager.get_bot("#lobby", "HELPER")
    assert bot["persona"].startswith("Answer as")

    message = manager.add_message("#lobby", owner["id"], owner["nick"], "user", "hello")
    assert manager.list_messages("#lobby")[-1]["id"] == message["id"]
    transfer = manager.create_transfer("Bobby", "/about", "You were transferred to About by Alice.", "Alice")
    assert manager.consume_transfers(target["id"]) == [transfer]
    assert manager.consume_transfers(target["id"]) == []


def _make_app(tmp_path):
    template_dir = Path(__file__).resolve().parents[1] / "templates"
    app = Flask(__name__, template_folder=str(template_dir))
    app.config.update(SECRET_KEY="test-secret")
    app.config["CHAT_SERV_LLM_HANDLER"] = lambda prompt, session_id: {"response": "Echo reply"}
    app.config["CHAT_SERV_COMMAND_HANDLER"] = lambda command: "script ran"
    app.config["CHAT_SERV_MODEL_HANDLER"] = lambda model: {"ok": True, "model": model}
    init_chatserv(app, tmp_path)
    (tmp_path / "commands").mkdir(exist_ok=True)
    (tmp_path / "commands" / "MOTD.txt").write_text("Test MOTD", encoding="utf-8")
    return app


def _post(client, text, channel="#lobby"):
    return client.post(
        "/api/chatserv/message",
        json={"text": text, "channel": channel},
        headers={"Origin": "http://localhost"},
    )


def test_chatserv_register_room_join_and_topic_commands(tmp_path):
    app = _make_app(tmp_path)
    owner = app.test_client()
    guest = app.test_client()

    response = _post(owner, f"!register Alice {PASSWORD}")
    assert response.status_code == 200
    assert "Alice" in response.json["response"]
    assert PASSWORD not in response.get_data(as_text=True)
    assert _post(owner, "!register #engineering Alice").status_code == 200
    assert _post(owner, "!topic Build together", "#engineering").status_code == 200

    assert _post(guest, f"!register Bobby {PASSWORD}").status_code == 200
    assert _post(guest, "!join #engineering").status_code == 200
    response = _post(guest, "!topic Unauthorized", "#engineering")
    assert response.status_code == 403
    assert "permission" in response.json["error"]


def test_join_plus_creates_a_new_room_and_makes_first_user_owner(tmp_path):
    app = _make_app(tmp_path)
    client = app.test_client()
    assert _post(client, f"!register Alice {PASSWORD}").status_code == 200

    response = _post(client, "!join + #new-room")

    assert response.status_code == 200
    assert "Created and joined #new-room" in response.json["response"]
    state = client.get("/api/chatserv/state?channel=%23new-room").get_json()
    assert state["channel"]["role"] == "owner"


def test_chatserv_blocks_unapproved_script_and_model_commands_for_members(tmp_path):
    app = _make_app(tmp_path)
    app.config["CHAT_SERV_COMMAND_HANDLER"] = lambda command: pytest.fail("script callback must not run")
    app.config["CHAT_SERV_MODEL_HANDLER"] = lambda model: pytest.fail("model callback must not run")
    client = app.test_client()

    assert _post(client, f"!register Alice {PASSWORD}").status_code == 200
    response = _post(client, "!maintenance")
    assert response.status_code == 403
    assert "platform admins" in response.json["error"]

    response = _post(client, "!model load example.gguf")
    assert response.status_code == 403
    assert "admin" in response.json["error"]


def test_chatserv_requires_same_origin_for_post_commands(tmp_path):
    app = _make_app(tmp_path)
    response = app.test_client().post(
        "/api/chatserv/message",
        json={"text": f"!register Alice {PASSWORD}"},
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403

"""Web ChatServ routes for registered rooms, moderation, and Echo commands."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlencode

from flask import Blueprint, current_app, jsonify, render_template, request, session
from flask_login import current_user

from managers.chatserv import ChatServError, ChatServManager


chatserv_bp = Blueprint("chatserv", __name__)

PAGE_DESTINATIONS = {
    "home": ("Home", "/"),
    "echo-chat": ("Echo Chat", "/echo-chat"),
    "commands": ("Command Center", "/echo-commands"),
    "code": ("Project Code UI", "/masterchief_code_ui"),
    "pipelines": ("Pipeline Studio", "/pipelines"),
    "about": ("About", "/about"),
    "observability": ("Observability Center", "/observability"),
}
_REGISTER_RE = re.compile(r"^!(?:register|nickserv\s+register)\s+(\S+)\s+(.+)$", re.IGNORECASE)
_IDENTIFY_RE = re.compile(r"^!(?:identify|nickserv\s+identify)\s+(\S+)\s+(.+)$", re.IGNORECASE)


def init_chatserv(app, project_root: str | Path) -> None:
    root = Path(project_root).resolve()
    app.extensions["chatserv_manager"] = ChatServManager(root / "data" / "chatserv.sqlite3")
    app.config["CHAT_SERV_PROJECT_ROOT"] = root
    app.register_blueprint(chatserv_bp)


def _manager() -> ChatServManager:
    manager = current_app.extensions.get("chatserv_manager")
    if manager is None:
        raise RuntimeError("ChatServ manager was not initialized.")
    return manager


def _platform_admin() -> bool:
    try:
        return bool(
            current_user.is_authenticated
            and current_user.provider == "rbac"
            and str(current_user.role or "").casefold() == "admin"
            and "*" in (current_user.permissions or [])
        )
    except (AttributeError, RuntimeError):
        return False


def _same_origin() -> bool:
    from urllib.parse import urlparse

    source = request.headers.get("Origin") or request.headers.get("Referer")
    if not source:
        return False
    parsed = urlparse(source)
    return bool(parsed.netloc and parsed.netloc.casefold() == request.host.casefold())


def _active_user() -> dict | None:
    user = _manager().get_user(session.get("chatserv_user_id"))
    if user is None:
        session.pop("chatserv_user_id", None)
        return None
    return user


def _error(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def _llm_reply(prompt: str, channel: dict, user: dict, session_id: str) -> str:
    handler = current_app.config.get("CHAT_SERV_LLM_HANDLER")
    if not callable(handler):
        raise RuntimeError("Echo ChatServ model handler is not configured.")
    role_lines = [
        f"ChatServ room: {channel['name']}.",
        f"Current channel role for {user['nick']}: {channel['role'] or 'member'}.",
    ]
    if channel["topic"]:
        role_lines.append(f"Channel topic: {channel['topic']}")
    if channel["role_prompt"]:
        role_lines.append(f"Room conversation role: {channel['role_prompt']}")
    result = handler("\n".join(role_lines) + "\n\n" + prompt, session_id)
    response = result.get("response") if isinstance(result, dict) else result
    response_text = str(response or "").strip()
    if not response_text:
        raise RuntimeError("Echo returned an empty response.")
    return response_text[:4000]


def _require_user():
    user = _active_user()
    if user is None:
        raise ChatServError("Register or identify first with !register <nick> <password> or !identify <nick> <password>.")
    return user


def _system_reply(message: str, channel: str | None = None, status: int = 200):
    return jsonify({"ok": status < 400, "response": message, "channel": channel}), status


def _parse_page(value: str) -> tuple[str, str]:
    normalized = str(value or "").strip().casefold().lstrip("/")
    if normalized not in PAGE_DESTINATIONS:
        available = ", ".join(PAGE_DESTINATIONS)
        raise ChatServError(f"Unknown page. Allowed page names: {available}.")
    return PAGE_DESTINATIONS[normalized][0], PAGE_DESTINATIONS[normalized][1]


def _message_context(user: dict, channel_name: str) -> dict:
    info = _manager().require_member(channel_name, user["id"])
    return info


def _run_model(channel: dict, user: dict, prompt: str, session_id: str, kind: str = "echo") -> str:
    _manager().add_message(channel["name"], user["id"], user["nick"], "user", prompt)
    reply = _llm_reply(prompt, channel, user, session_id)
    _manager().add_message(channel["name"], None, "Echo", kind, reply)
    return reply


def _dispatch_chat_command(text: str, requested_channel: str | None):
    manager = _manager()
    command = text.strip()
    lowered = command.casefold()
    match = _REGISTER_RE.fullmatch(command)
    if match and not match.group(1).startswith("#"):
        user = manager.register(match.group(1), match.group(2))
        session["chatserv_user_id"] = user["id"]
        session["chatserv_channel"] = "#lobby"
        return _system_reply(
            f"Registered and signed in as {user['nick']}. Passwords are stored as one-way hashes.",
            "#lobby",
        )
    match = _IDENTIFY_RE.fullmatch(command)
    if match:
        user = manager.authenticate(match.group(1), match.group(2))
        session["chatserv_user_id"] = user["id"]
        session["chatserv_channel"] = "#lobby"
        return _system_reply(f"Identified as {user['nick']}.", "#lobby")

    if lowered == "!help":
        return _system_reply(
            "ChatServ commands: !register <nick> <password>, !identify <nick> <password>, "
            "!nickserv register|identify, !channels, !motd, !join [+] #channel, "
            "!register #channel <your-nick>, !part, !topic [text], !role <room instructions>, "
            "!op <nick>, !deop <nick>, !ask <prompt>, !bot create|list|say, "
            "!sendpage <nick> <page> [message], !page <page>, !model list|load <file>."
        )
    if lowered == "!motd":
        motd_path = Path(current_app.config["CHAT_SERV_PROJECT_ROOT"]) / "commands" / "MOTD.txt"
        return _system_reply(motd_path.read_text(encoding="utf-8").strip())
    if lowered == "!channels":
        channels = manager.list_channels()
        lines = [f"{item['name']} ({item['members']} members) — {item['topic']}" for item in channels]
        return _system_reply("\n".join(lines) or "There are no registered channels.")

    create_match = re.fullmatch(r"!register\s+(#[^\s]+)\s+(\S+)", command, re.IGNORECASE)
    if create_match:
        user = _require_user()
        if user["nick"].casefold() != create_match.group(2).casefold():
            raise ChatServError("Register a channel using your own identified nickname.")
        channel = manager.create_channel(create_match.group(1), user["id"])
        session["chatserv_channel"] = channel["name"]
        return _system_reply(f"Registered {channel['name']}; you are the channel owner.", channel["name"])
    if lowered.startswith("!chanserv register "):
        parts = command.split()
        if len(parts) != 4:
            raise ChatServError("Usage: !chanserv register #channel <your-nick>")
        user = _require_user()
        if user["nick"].casefold() != parts[3].casefold():
            raise ChatServError("Register a channel using your own identified nickname.")
        channel = manager.create_channel(parts[2], user["id"])
        session["chatserv_channel"] = channel["name"]
        return _system_reply(f"Registered {channel['name']}; you are the channel owner.", channel["name"])

    user = _require_user()
    channel_name = requested_channel or session.get("chatserv_channel") or "#lobby"

    if lowered == "!logout":
        session.pop("chatserv_user_id", None)
        session.pop("chatserv_channel", None)
        return _system_reply("Signed out of ChatServ.")
    if lowered.startswith("!join "):
        channel_args = command.split(maxsplit=1)[1].split()
        if len(channel_args) == 1:
            channel_name = channel_args[0]
        elif len(channel_args) == 2 and channel_args[0] == "+":
            channel_name = channel_args[1]
        else:
            raise ChatServError("Usage: !join #channel or !join + #new-channel")
        channel, created = manager.join_or_create_channel(channel_name, user["id"])
        session["chatserv_channel"] = channel["name"]
        verb = "Created and joined" if created else "Joined"
        return _system_reply(f"{verb} {channel['name']}.", channel["name"])
    if lowered == "!part" or lowered.startswith("!part "):
        manager.part_channel(command.split(maxsplit=1)[1] if " " in command else channel_name, user["id"])
        session["chatserv_channel"] = "#lobby"
        return _system_reply("Left the channel.", "#lobby")

    context = _message_context(user, channel_name)
    if lowered == "!topic":
        return _system_reply(context["topic"] or "No topic is set.", context["name"])
    if lowered == "!topic clear":
        manager.update_topic(context["name"], user["id"], "", _platform_admin())
        return _system_reply("Channel topic cleared.", context["name"])
    if lowered.startswith("!topic "):
        manager.update_topic(context["name"], user["id"], command.split(maxsplit=1)[1], _platform_admin())
        return _system_reply("Channel topic updated.", context["name"])
    if lowered.startswith("!role "):
        role_prompt = command.split(maxsplit=1)[1]
        if role_prompt.casefold() == "clear":
            role_prompt = ""
        manager.update_role_prompt(context["name"], user["id"], role_prompt, _platform_admin())
        return _system_reply("Room conversation role updated.", context["name"])
    if lowered.startswith("!op ") or lowered.startswith("!deop "):
        parts = command.split(maxsplit=1)
        if len(parts) != 2:
            raise ChatServError("Usage: !op <nick> or !deop <nick>")
        role = "op" if lowered.startswith("!op ") else "member"
        manager.set_member_role(context["name"], user["id"], parts[1], role, _platform_admin())
        return _system_reply(f"{parts[1]} is now {'OP' if role == 'op' else 'a member'}.", context["name"])
    if lowered.startswith("!ask "):
        prompt = command.split(maxsplit=1)[1].strip()
        if not prompt:
            raise ChatServError("Usage: !ask <message for Echo>")
        reply = _run_model(context, user, prompt, f"chatserv-{context['name']}")
        return _system_reply(reply, context["name"])
    if lowered.startswith("!bot "):
        parts = command.split(maxsplit=3)
        if len(parts) >= 3 and parts[1].casefold() in {"create", "add"}:
            if len(parts) != 4:
                raise ChatServError("Usage: !bot create <name> <persona>")
            bot = manager.create_bot(context["name"], user["id"], parts[2], parts[3])
            return _system_reply(f"Created @{bot['name']} using Echo's configured model.", context["name"])
        if len(parts) == 2 and parts[1].casefold() == "list":
            bots = manager.list_bots(context["name"])
            names = ", ".join("@" + bot["name"] for bot in bots)
            return _system_reply(names or "No room bots have been created.", context["name"])
        if len(parts) >= 4 and parts[1].casefold() == "say":
            bot = manager.get_bot(context["name"], parts[2])
            if bot is None:
                raise ChatServError("That room bot does not exist.")
            prompt = (
                f"Respond in the following persona: {bot['persona']}\n"
                f"Message from {user['nick']}: {parts[3]}"
            )
            reply = _llm_reply(prompt, context, user, f"chatserv-bot-{context['name']}-{bot['name']}")
            manager.add_message(context["name"], None, bot["name"], "bot", reply)
            return _system_reply(reply, context["name"])
        raise ChatServError("Usage: !bot create <name> <persona>, !bot list, or !bot say <name> <message>")
    if lowered.startswith("!sendpage "):
        if context["role"] not in {"owner", "op"} and not _platform_admin():
            raise ChatServError("Only the channel owner, an OP, or a platform admin can transfer pages.")
        parts = command.split(maxsplit=3)
        if len(parts) < 3:
            raise ChatServError("Usage: !sendpage <nick> <page> [message]")
        page_label, page_path = _parse_page(parts[2])
        transfer_message = f"You were transferred to {page_label} by {user['nick']}."
        if len(parts) == 4 and parts[3].strip():
            transfer_message += " " + parts[3].strip()[:180]
        transfer = manager.create_transfer(parts[1], page_path, transfer_message, user["nick"])
        return _system_reply(f"Page transfer queued for {parts[1]} (transfer {transfer['id']}).", context["name"])
    if lowered.startswith("!page "):
        page_label, page_path = _parse_page(command.split(maxsplit=1)[1])
        transfer_message = f"You were transferred to {page_label} by {user['nick']}."
        return jsonify({
            "ok": True,
            "redirect": page_path + "?" + urlencode({"chatserv_notice": transfer_message}),
            "response": transfer_message,
            "channel": context["name"],
        })
    if lowered.startswith("!model "):
        parts = command.split(maxsplit=2)
        if len(parts) < 2 or parts[1].casefold() == "list":
            root = Path(current_app.config["CHAT_SERV_PROJECT_ROOT"])
            models_dir = root / "models"
            names = sorted(path.name for path in models_dir.glob("*.gguf") if path.is_file()) if models_dir.is_dir() else []
            return _system_reply("\n".join(names) or "No GGUF files found in the models directory.", context["name"])
        if len(parts) != 3 or parts[1].casefold() != "load":
            raise ChatServError("Usage: !model list or !model load <gguf-filename>")
        if not _platform_admin():
            raise ChatServError("Loading a model requires a signed-in RBAC platform admin.")
        model_handler = current_app.config.get("CHAT_SERV_MODEL_HANDLER")
        if not callable(model_handler):
            raise RuntimeError("The secure Echo model loader is not configured.")
        result = model_handler(parts[2])
        if not isinstance(result, dict) or not result.get("ok"):
            raise ChatServError(str((result or {}).get("error", "Model load failed.")))
        return _system_reply(f"Echo will use {Path(result['model']).name} on the next response.", context["name"])

    if command.startswith("!"):
        safe_draft_commands = {"!help", "!commands", "!write", "!library"}
        if lowered.split(maxsplit=1)[0] in safe_draft_commands:
            handler = current_app.config.get("CHAT_SERV_COMMAND_HANDLER")
            if callable(handler):
                handled = handler(command)
                if handled is not None:
                    manager.add_message(context["name"], None, "Echo", "echo", str(handled))
                    return _system_reply(str(handled), context["name"])
            if lowered.startswith("!commands") or lowered == "!help":
                return _system_reply("Use !help for ChatServ commands, or open the Command Center for script add-ons.", context["name"])
            prompt = command
            reply = _run_model(context, user, prompt, f"chatserv-{context['name']}")
            return _system_reply(reply, context["name"])

        if not _platform_admin():
            raise ChatServError("Unrecognized command. Project script commands are restricted to platform admins.")
        if not _same_origin():
            raise ChatServError("Admin commands require a same-origin request.")
        handler = current_app.config.get("CHAT_SERV_COMMAND_HANDLER")
        if not callable(handler):
            raise RuntimeError("The secure Echo command handler is not configured.")
        handled = handler(command)
        if handled is None:
            raise ChatServError("Echo did not recognize that command.")
        manager.add_message(context["name"], None, "Echo", "echo", str(handled))
        return _system_reply(str(handled), context["name"])

    message = manager.add_message(context["name"], user["id"], user["nick"], "user", command)
    return jsonify({"ok": True, "response": "", "channel": context["name"], "message": message})


@chatserv_bp.get("/chatserv")
def chatserv_page():
    return render_template("chatserv.html")


@chatserv_bp.get("/api/chatserv/state")
def chatserv_state():
    try:
        manager = _manager()
        user = _active_user()
        channel_name = request.args.get("channel") or session.get("chatserv_channel") or "#lobby"
        channel = manager.channel_info(channel_name, user["id"] if user else None)
        messages = []
        members = []
        bots = []
        if user and channel["role"]:
            manager.touch_presence(channel["name"], user["id"])
            messages = manager.list_messages(channel["name"], request.args.get("after_id", 0))
            members = manager.list_members(channel["name"])
            bots = manager.list_bots(channel["name"])
        channels = manager.list_channels(user["id"] if user else None)
        return jsonify({
            "ok": True,
            "user": user,
            "platform_admin": _platform_admin(),
            "channels": channels,
            "joined_channels": [channel for channel in channels if channel["joined"]],
            "channel": channel,
            "messages": messages,
            "members": members,
            "bots": bots,
            "motd": (Path(current_app.config["CHAT_SERV_PROJECT_ROOT"]) / "commands" / "MOTD.txt").read_text(encoding="utf-8"),
        })
    except (ChatServError, ValueError) as exc:
        return _error(str(exc), 404)
    except OSError:
        current_app.logger.exception("Unable to load ChatServ state or MOTD")
        return _error("ChatServ state could not be loaded. Check the server log.", 500)


@chatserv_bp.post("/api/chatserv/message")
def chatserv_message():
    if not request.is_json or not _same_origin():
        return _error("A same-origin JSON request is required.", 403)
    data = request.get_json(silent=True) or {}
    text = str(data.get("text") or "").strip()
    if not text:
        return _error("Enter a message or command.")
    if len(text) > 2200:
        return _error("Messages and commands are limited to 2200 characters.")
    try:
        return _dispatch_chat_command(text, data.get("channel"))
    except ChatServError as exc:
        error_text = str(exc).casefold()
        if "register or identify first" in error_text:
            status = 401
        elif any(term in error_text for term in ("required", "permission", "requires a signed-in", "restricted to")):
            status = 403
        else:
            status = 400
        return _error(str(exc), status)
    except OSError:
        current_app.logger.exception("ChatServ command failed due to a filesystem error")
        return _error("ChatServ command failed. Check the server log.", 500)
    except Exception:
        current_app.logger.exception("ChatServ command failed")
        return _error("ChatServ command failed. Check the server log.", 500)


@chatserv_bp.post("/api/chatserv/transfers/consume")
def chatserv_consume_transfers():
    if not request.is_json or not _same_origin():
        return _error("A same-origin JSON request is required.", 403)
    user = _active_user()
    if user is None:
        return _error("Identify with ChatServ before receiving page transfers.", 401)
    try:
        transfers = _manager().consume_transfers(user["id"])
        for transfer in transfers:
            if transfer["page"] not in {value[1] for value in PAGE_DESTINATIONS.values()}:
                current_app.logger.error("Discarded invalid ChatServ page transfer %s", transfer["id"])
                continue
        safe_transfers = [
            transfer for transfer in transfers
            if transfer["page"] in {value[1] for value in PAGE_DESTINATIONS.values()}
        ]
        return jsonify({"ok": True, "transfers": safe_transfers})
    except Exception:
        current_app.logger.exception("Unable to read ChatServ page transfers")
        return _error("Page transfers could not be read. Check the server log.", 500)


@chatserv_bp.post("/api/chatserv/motd")
def chatserv_update_motd():
    if not _platform_admin():
        return _error("Signed-in RBAC platform admin required.", 403)
    if not request.is_json or not _same_origin():
        return _error("A same-origin JSON request is required.", 403)
    data = request.get_json(silent=True) or {}
    text = str(data.get("text") or "")
    if len(text) > 8000:
        return _error("MOTD is limited to 8000 characters.")
    motd_path = Path(current_app.config["CHAT_SERV_PROJECT_ROOT"]) / "commands" / "MOTD.txt"
    try:
        motd_path.parent.mkdir(parents=True, exist_ok=True)
        motd_path.write_text(text.rstrip() + "\n", encoding="utf-8")
        return jsonify({"ok": True})
    except OSError:
        current_app.logger.exception("Unable to save ChatServ MOTD")
        return _error("MOTD could not be saved. Check the server log.", 500)

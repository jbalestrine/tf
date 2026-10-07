"""Persistent accounts, rooms, moderation, and message storage for Echo ChatServ."""

from __future__ import annotations

import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from werkzeug.security import check_password_hash, generate_password_hash


_NICK_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,23}$")
_CHANNEL_RE = re.compile(r"^#[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
_BOT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,31}$")


class ChatServError(ValueError):
    """A user-facing ChatServ operation was invalid or not permitted."""


class ChatServManager:
    """SQLite-backed ChatServ state; passwords are stored as one-way hashes."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS chatserv_users (
                    id INTEGER PRIMARY KEY,
                    nick TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS chatserv_channels (
                    name TEXT PRIMARY KEY COLLATE NOCASE,
                    owner_id INTEGER REFERENCES chatserv_users(id),
                    topic TEXT NOT NULL DEFAULT '',
                    role_prompt TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS chatserv_members (
                    channel TEXT NOT NULL COLLATE NOCASE REFERENCES chatserv_channels(name) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES chatserv_users(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('owner', 'op', 'member')),
                    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(channel, user_id)
                );
                CREATE TABLE IF NOT EXISTS chatserv_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL COLLATE NOCASE REFERENCES chatserv_channels(name) ON DELETE CASCADE,
                    user_id INTEGER REFERENCES chatserv_users(id) ON DELETE SET NULL,
                    nick TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('user', 'echo', 'bot', 'system')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS chatserv_presence (
                    channel TEXT NOT NULL COLLATE NOCASE REFERENCES chatserv_channels(name) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES chatserv_users(id) ON DELETE CASCADE,
                    last_seen REAL NOT NULL,
                    PRIMARY KEY(channel, user_id)
                );
                CREATE TABLE IF NOT EXISTS chatserv_bots (
                    id INTEGER PRIMARY KEY,
                    channel TEXT NOT NULL COLLATE NOCASE REFERENCES chatserv_channels(name) ON DELETE CASCADE,
                    name TEXT NOT NULL COLLATE NOCASE,
                    owner_id INTEGER NOT NULL REFERENCES chatserv_users(id) ON DELETE CASCADE,
                    persona TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(channel, name)
                );
                CREATE TABLE IF NOT EXISTS chatserv_transfers (
                    id INTEGER PRIMARY KEY,
                    recipient_id INTEGER NOT NULL REFERENCES chatserv_users(id) ON DELETE CASCADE,
                    page TEXT NOT NULL,
                    message TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    consumed INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS chatserv_messages_channel_id
                    ON chatserv_messages(channel, id);
                CREATE INDEX IF NOT EXISTS chatserv_transfers_recipient
                    ON chatserv_transfers(recipient_id, consumed, id);
                """
            )
            db.execute("INSERT OR IGNORE INTO chatserv_channels(name) VALUES ('#lobby')")

    @staticmethod
    def normalize_channel(channel: str) -> str:
        value = str(channel or "").strip()
        if not value.startswith("#"):
            value = "#" + value
        if not _CHANNEL_RE.fullmatch(value):
            raise ChatServError("Channel names must look like #lobby and use letters, numbers, _ or -.")
        return value.lower()

    @staticmethod
    def _public_user(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        return {"id": row["id"], "nick": row["nick"], "created_at": row["created_at"]}

    @staticmethod
    def _public_message(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "nick": row["nick"],
            "kind": row["kind"],
            "content": row["content"],
            "created_at": row["created_at"],
        }

    def register(self, nick: str, password: str) -> dict:
        nick = str(nick or "").strip()
        password = str(password or "")
        if not _NICK_RE.fullmatch(nick):
            raise ChatServError("Nicknames must be 2-24 characters, start with a letter, and use letters, numbers, _ or -.")
        if len(password) < 12 or len(password) > 256:
            raise ChatServError("Passwords must be 12-256 characters.")
        password_hash = generate_password_hash(password)
        try:
            with self._connection() as db:
                cursor = db.execute(
                    "INSERT INTO chatserv_users(nick, password_hash) VALUES (?, ?)",
                    (nick, password_hash),
                )
                user_id = cursor.lastrowid
                db.execute(
                    "INSERT OR IGNORE INTO chatserv_members(channel, user_id, role) VALUES ('#lobby', ?, 'member')",
                    (user_id,),
                )
                row = db.execute("SELECT id, nick, created_at FROM chatserv_users WHERE id = ?", (user_id,)).fetchone()
            return self._public_user(row)
        except sqlite3.IntegrityError as exc:
            raise ChatServError("That nickname is already registered.") from exc

    def authenticate(self, nick: str, password: str) -> dict:
        with self._connection() as db:
            row = db.execute(
                "SELECT id, nick, password_hash, created_at FROM chatserv_users WHERE nick = ? COLLATE NOCASE",
                (str(nick or "").strip(),),
            ).fetchone()
        if row is None or not check_password_hash(row["password_hash"], str(password or "")):
            raise ChatServError("Nickname or password is incorrect.")
        return self._public_user(row)

    def get_user(self, user_id: int | str | None) -> dict | None:
        if user_id is None:
            return None
        with self._connection() as db:
            row = db.execute(
                "SELECT id, nick, created_at FROM chatserv_users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return self._public_user(row)

    def list_channels(self, user_id: int | None = None) -> list[dict]:
        with self._connection() as db:
            rows = db.execute(
                """
                SELECT c.name, c.topic, COUNT(m.user_id) AS members,
                       CASE WHEN mine.user_id IS NULL THEN 0 ELSE 1 END AS joined
                FROM chatserv_channels c
                LEFT JOIN chatserv_members m ON m.channel = c.name
                LEFT JOIN chatserv_members mine ON mine.channel = c.name AND mine.user_id = ?
                GROUP BY c.name
                ORDER BY c.name
                """,
                (user_id,),
            ).fetchall()
        return [
            {
                "name": row["name"],
                "topic": row["topic"],
                "members": row["members"],
                "joined": bool(row["joined"]),
            }
            for row in rows
        ]

    def create_channel(self, channel: str, user_id: int) -> dict:
        name = self.normalize_channel(channel)
        with self._connection() as db:
            exists = db.execute("SELECT 1 FROM chatserv_channels WHERE name = ?", (name,)).fetchone()
            if exists:
                raise ChatServError("That channel already exists.")
            db.execute(
                "INSERT INTO chatserv_channels(name, owner_id) VALUES (?, ?)",
                (name, user_id),
            )
            db.execute(
                "INSERT INTO chatserv_members(channel, user_id, role) VALUES (?, ?, 'owner')",
                (name, user_id),
            )
        return self.channel_info(name, user_id)

    def join_channel(self, channel: str, user_id: int) -> dict:
        name = self.normalize_channel(channel)
        with self._connection() as db:
            exists = db.execute("SELECT 1 FROM chatserv_channels WHERE name = ?", (name,)).fetchone()
            if not exists:
                raise ChatServError(f"Channel {name} does not exist. Create it with !register {name} <your-nick>.")
            db.execute(
                "INSERT OR IGNORE INTO chatserv_members(channel, user_id, role) VALUES (?, ?, 'member')",
                (name, user_id),
            )
        return self.channel_info(name, user_id)

    def join_or_create_channel(self, channel: str, user_id: int) -> tuple[dict, bool]:
        name = self.normalize_channel(channel)
        created = False
        try:
            with self._connection() as db:
                exists = db.execute("SELECT 1 FROM chatserv_channels WHERE name = ?", (name,)).fetchone()
                if exists:
                    db.execute(
                        "INSERT OR IGNORE INTO chatserv_members(channel, user_id, role) VALUES (?, ?, 'member')",
                        (name, user_id),
                    )
                else:
                    db.execute(
                        "INSERT INTO chatserv_channels(name, owner_id) VALUES (?, ?)",
                        (name, user_id),
                    )
                    db.execute(
                        "INSERT INTO chatserv_members(channel, user_id, role) VALUES (?, ?, 'owner')",
                        (name, user_id),
                    )
                    created = True
        except sqlite3.IntegrityError:
            # Another request may have created the room after the existence check.
            return self.join_channel(name, user_id), False
        return self.channel_info(name, user_id), created

    def part_channel(self, channel: str, user_id: int) -> None:
        name = self.normalize_channel(channel)
        with self._connection() as db:
            membership = db.execute(
                "SELECT role FROM chatserv_members WHERE channel = ? AND user_id = ?",
                (name, user_id),
            ).fetchone()
            if membership is None:
                raise ChatServError("You are not in that channel.")
            if membership["role"] == "owner":
                raise ChatServError("A channel owner cannot leave until ownership is transferred.")
            db.execute("DELETE FROM chatserv_members WHERE channel = ? AND user_id = ?", (name, user_id))

    def channel_info(self, channel: str, user_id: int | None = None) -> dict:
        name = self.normalize_channel(channel)
        with self._connection() as db:
            row = db.execute(
                """
                SELECT c.name, c.owner_id, c.topic, c.role_prompt, m.role
                FROM chatserv_channels c
                LEFT JOIN chatserv_members m ON m.channel = c.name AND m.user_id = ?
                WHERE c.name = ?
                """,
                (user_id, name),
            ).fetchone()
        if row is None:
            raise ChatServError(f"Channel {name} does not exist.")
        return {
            "name": row["name"],
            "owner_id": row["owner_id"],
            "topic": row["topic"],
            "role_prompt": row["role_prompt"],
            "role": row["role"],
        }

    def require_member(self, channel: str, user_id: int) -> dict:
        info = self.channel_info(channel, user_id)
        if info["role"] is None:
            raise ChatServError(f"Join {info['name']} first with !join {info['name']}.")
        return info

    def list_members(self, channel: str) -> list[dict]:
        name = self.normalize_channel(channel)
        with self._connection() as db:
            rows = db.execute(
                """
                SELECT u.nick, m.role, p.last_seen
                FROM chatserv_members m JOIN chatserv_users u ON u.id = m.user_id
                LEFT JOIN chatserv_presence p ON p.channel = m.channel AND p.user_id = m.user_id
                WHERE m.channel = ? ORDER BY
                  CASE m.role WHEN 'owner' THEN 0 WHEN 'op' THEN 1 ELSE 2 END, u.nick COLLATE NOCASE
                """,
                (name,),
            ).fetchall()
        now = time.time()
        return [
            {"nick": row["nick"], "role": row["role"], "online": bool(row["last_seen"] and now - row["last_seen"] <= 15)}
            for row in rows
        ]

    def touch_presence(self, channel: str, user_id: int) -> None:
        name = self.normalize_channel(channel)
        with self._connection() as db:
            membership = db.execute(
                "SELECT 1 FROM chatserv_members WHERE channel = ? AND user_id = ?",
                (name, user_id),
            ).fetchone()
            if membership is None:
                raise ChatServError(f"Join {name} before sending presence.")
            db.execute(
                """
                INSERT INTO chatserv_presence(channel, user_id, last_seen) VALUES (?, ?, ?)
                ON CONFLICT(channel, user_id) DO UPDATE SET last_seen = excluded.last_seen
                """,
                (name, user_id, time.time()),
            )

    def update_topic(self, channel: str, user_id: int, topic: str, is_admin: bool = False) -> None:
        name = self.normalize_channel(channel)
        topic = str(topic or "").strip()
        if len(topic) > 240:
            raise ChatServError("Channel topics are limited to 240 characters.")
        self._require_operator(name, user_id, is_admin)
        with self._connection() as db:
            db.execute("UPDATE chatserv_channels SET topic = ? WHERE name = ?", (topic, name))

    def update_role_prompt(self, channel: str, user_id: int, prompt: str, is_admin: bool = False) -> None:
        name = self.normalize_channel(channel)
        prompt = str(prompt or "").strip()
        if len(prompt) > 600:
            raise ChatServError("Room role instructions are limited to 600 characters.")
        self._require_operator(name, user_id, is_admin)
        with self._connection() as db:
            db.execute("UPDATE chatserv_channels SET role_prompt = ? WHERE name = ?", (prompt, name))

    def _require_operator(self, channel: str, user_id: int, is_admin: bool) -> dict:
        info = self.require_member(channel, user_id)
        if info["role"] not in {"owner", "op"} and not is_admin:
            raise ChatServError("Channel owner or OP permission is required.")
        return info

    def set_member_role(
        self,
        channel: str,
        actor_id: int,
        target_nick: str,
        role: str,
        is_admin: bool = False,
    ) -> None:
        name = self.normalize_channel(channel)
        if role not in {"op", "member"}:
            raise ChatServError("Only OP and member roles can be assigned.")
        self._require_operator(name, actor_id, is_admin)
        with self._connection() as db:
            target = db.execute(
                """
                SELECT u.id, m.role FROM chatserv_members m
                JOIN chatserv_users u ON u.id = m.user_id
                WHERE m.channel = ? AND u.nick = ? COLLATE NOCASE
                """,
                (name, str(target_nick or "").strip()),
            ).fetchone()
            if target is None:
                raise ChatServError("That nickname is not in the channel.")
            if target["role"] == "owner":
                raise ChatServError("The channel owner cannot be deopped.")
            db.execute(
                "UPDATE chatserv_members SET role = ? WHERE channel = ? AND user_id = ?",
                (role, name, target["id"]),
            )

    def add_message(self, channel: str, user_id: int | None, nick: str, kind: str, content: str) -> dict:
        name = self.normalize_channel(channel)
        if kind not in {"user", "echo", "bot", "system"}:
            raise ChatServError("Invalid message type.")
        text = str(content or "").strip()
        if not text or len(text) > 2000:
            raise ChatServError("Messages must contain 1-2000 characters.")
        with self._connection() as db:
            cursor = db.execute(
                "INSERT INTO chatserv_messages(channel, user_id, nick, kind, content) VALUES (?, ?, ?, ?, ?)",
                (name, user_id, str(nick)[:32], kind, text),
            )
            row = db.execute("SELECT * FROM chatserv_messages WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._public_message(row)

    def list_messages(self, channel: str, after_id: int = 0, limit: int = 100) -> list[dict]:
        name = self.normalize_channel(channel)
        safe_after = max(0, int(after_id))
        safe_limit = min(200, max(1, int(limit)))
        with self._connection() as db:
            if safe_after:
                rows = db.execute(
                    """
                    SELECT id, nick, kind, content, created_at FROM chatserv_messages
                    WHERE channel = ? AND id > ? ORDER BY id LIMIT ?
                    """,
                    (name, safe_after, safe_limit),
                ).fetchall()
            else:
                rows = db.execute(
                    """
                    SELECT id, nick, kind, content, created_at FROM chatserv_messages
                    WHERE channel = ? ORDER BY id DESC LIMIT ?
                    """,
                    (name, safe_limit),
                ).fetchall()
                rows.reverse()
        return [self._public_message(row) for row in rows]

    def create_bot(self, channel: str, user_id: int, name: str, persona: str) -> dict:
        info = self.require_member(channel, user_id)
        if not _BOT_RE.fullmatch(str(name or "").strip()):
            raise ChatServError("Bot names must be 2-32 characters and use letters, numbers, _ or -.")
        persona = str(persona or "").strip()
        if not persona or len(persona) > 500:
            raise ChatServError("A bot persona of 1-500 characters is required.")
        try:
            with self._connection() as db:
                cursor = db.execute(
                    "INSERT INTO chatserv_bots(channel, name, owner_id, persona) VALUES (?, ?, ?, ?)",
                    (info["name"], name, user_id, persona),
                )
                row = db.execute(
                    "SELECT name, persona, owner_id FROM chatserv_bots WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ChatServError("A bot with that name already exists in this channel.") from exc
        return {"name": row["name"], "persona": row["persona"], "owner_id": row["owner_id"]}

    def list_bots(self, channel: str) -> list[dict]:
        name = self.normalize_channel(channel)
        with self._connection() as db:
            rows = db.execute(
                "SELECT name, persona, owner_id FROM chatserv_bots WHERE channel = ? ORDER BY name COLLATE NOCASE",
                (name,),
            ).fetchall()
        return [{"name": row["name"], "persona": row["persona"], "owner_id": row["owner_id"]} for row in rows]

    def get_bot(self, channel: str, name: str) -> dict | None:
        normalized = self.normalize_channel(channel)
        with self._connection() as db:
            row = db.execute(
                "SELECT name, persona, owner_id FROM chatserv_bots WHERE channel = ? AND name = ? COLLATE NOCASE",
                (normalized, str(name or "").strip()),
            ).fetchone()
        if row is None:
            return None
        return {"name": row["name"], "persona": row["persona"], "owner_id": row["owner_id"]}

    def create_transfer(self, recipient_nick: str, page: str, message: str, sender: str) -> dict:
        with self._connection() as db:
            recipient = db.execute(
                "SELECT id FROM chatserv_users WHERE nick = ? COLLATE NOCASE",
                (str(recipient_nick or "").strip(),),
            ).fetchone()
            if recipient is None:
                raise ChatServError("No registered ChatServ user has that nickname.")
            cursor = db.execute(
                """
                INSERT INTO chatserv_transfers(recipient_id, page, message, sender)
                VALUES (?, ?, ?, ?)
                """,
                (recipient["id"], page, message[:300], str(sender)[:32]),
            )
            return {"id": cursor.lastrowid, "page": page, "message": message[:300], "sender": str(sender)[:32]}

    def consume_transfers(self, user_id: int, limit: int = 1) -> list[dict]:
        safe_limit = min(20, max(1, int(limit)))
        with self._connection() as db:
            rows = db.execute(
                """
                SELECT id, page, message, sender FROM chatserv_transfers
                WHERE recipient_id = ? AND consumed = 0 ORDER BY id LIMIT ?
                """,
                (user_id, safe_limit),
            ).fetchall()
            db.executemany(
                "UPDATE chatserv_transfers SET consumed = 1 WHERE id = ?",
                [(row["id"],) for row in rows],
            )
        return [
            {"id": row["id"], "page": row["page"], "message": row["message"], "sender": row["sender"]}
            for row in rows
        ]

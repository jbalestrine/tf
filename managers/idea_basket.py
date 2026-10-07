"""Persistent, non-destructive parking list for disconnected project scripts."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class IdeaBasketError(ValueError):
    """An invalid idea-basket entry or operation."""


class IdeaBasketManager:
    """Store script ideas without moving, changing, or deleting their source files."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
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
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS script_ideas (
                    path TEXT PRIMARY KEY,
                    note TEXT NOT NULL DEFAULT '',
                    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    @staticmethod
    def _normalize_path(path: str) -> str:
        normalized = str(path or "").strip().replace("\\", "/")
        parts = normalized.split("/")
        if (
            not normalized
            or normalized.startswith("/")
            or any(part in {"", ".", ".."} for part in parts)
            or "\x00" in normalized
        ):
            raise IdeaBasketError("Use a project-relative file path.")
        return normalized

    def add(self, path: str, note: str = "") -> dict:
        normalized = self._normalize_path(path)
        note = str(note or "").strip()
        if len(note) > 500:
            raise IdeaBasketError("Idea notes must be 500 characters or fewer.")
        with self._connection() as db:
            db.execute(
                """
                INSERT INTO script_ideas(path, note)
                VALUES (?, ?)
                ON CONFLICT(path) DO UPDATE SET note = excluded.note
                """,
                (normalized, note),
            )
            row = db.execute(
                "SELECT path, note, added_at FROM script_ideas WHERE path = ?",
                (normalized,),
            ).fetchone()
        return dict(row)

    def list_ideas(self) -> list[dict]:
        with self._connection() as db:
            rows = db.execute(
                "SELECT path, note, added_at FROM script_ideas ORDER BY added_at DESC, path"
            ).fetchall()
        return [dict(row) for row in rows]

    def remove(self, path: str) -> bool:
        normalized = self._normalize_path(path)
        with self._connection() as db:
            cursor = db.execute("DELETE FROM script_ideas WHERE path = ?", (normalized,))
        return cursor.rowcount > 0

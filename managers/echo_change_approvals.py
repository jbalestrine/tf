"""Store and apply Echo-generated app changes only after explicit approval."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class EchoChangeError(ValueError):
    """An invalid, stale, or unappliable Echo change proposal."""


class EchoChangeApprovalManager:
    """Persist source proposals and apply them transactionally after confirmation."""

    _ALLOWED_EXTENSIONS = {
        ".py", ".html", ".css", ".js", ".php", ".xml", ".json",
        ".tf", ".ps1", ".psm1", ".sh", ".bash",
    }
    _BLOCKED_PARTS = {
        ".git", "data", "venv", ".venv", "env", "node_modules",
        "__pycache__", "site-packages",
    }
    _BLOCKED_FILENAMES = {".env", "secrets.json", "credentials.json"}
    _MAX_FILES = 8
    _MAX_TOTAL_BYTES = 500_000

    def __init__(self, database_path: str | Path, project_root: str | Path):
        self.database_path = Path(database_path)
        self.project_root = Path(project_root).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.database_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 10000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self) -> None:
        with self._connection() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS echo_change_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    files_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    applied_at TEXT,
                    backup_paths_json TEXT
                )
                """
            )
            db.execute(
                """
                CREATE INDEX IF NOT EXISTS echo_change_pending_owner
                ON echo_change_proposals(session_id, user_id, status)
                """
            )

    def _resolve_target(self, relative_path: str) -> Path:
        normalized = str(relative_path or "").strip().replace("\\", "/")
        parts = normalized.split("/")
        if (
            not normalized
            or normalized.startswith("/")
            or any(part in {"", ".", ".."} for part in parts)
            or "\x00" in normalized
            or Path(normalized).is_absolute()
        ):
            raise EchoChangeError("Each change must use a clean project-relative path.")
        if any(part.casefold() in self._BLOCKED_PARTS for part in parts):
            raise EchoChangeError(f"Changes to protected runtime/storage paths are not allowed: {normalized}")
        if parts[-1].casefold() in self._BLOCKED_FILENAMES:
            raise EchoChangeError(f"Changes to protected local files are not allowed: {normalized}")

        target = self.project_root.joinpath(*parts)
        if target.suffix.casefold() not in self._ALLOWED_EXTENSIONS:
            raise EchoChangeError(f"Unsupported app source file type: {target.suffix or '(none)'}")
        try:
            target.resolve(strict=False).relative_to(self.project_root)
        except ValueError as exc:
            raise EchoChangeError(f"Target path escapes the project: {normalized}") from exc
        if any(parent.is_symlink() for parent in (target, *target.parents) if parent != self.project_root.parent):
            raise EchoChangeError(f"Symbolic-link targets are not allowed: {normalized}")
        return target

    @staticmethod
    def _validate_content(target: Path, content: str) -> None:
        if target.suffix.casefold() == ".py":
            try:
                ast.parse(content, filename=str(target))
            except SyntaxError as exc:
                raise EchoChangeError(f"Python syntax check failed for {target.name}: {exc}") from exc
        elif target.suffix.casefold() == ".json":
            try:
                json.loads(content)
            except json.JSONDecodeError as exc:
                raise EchoChangeError(f"JSON validation failed for {target.name}: {exc}") from exc

    @staticmethod
    def _apply_edits(relative_path: str, source: str, edits: list[dict]) -> str:
        content = source
        for edit in edits:
            if not isinstance(edit, dict):
                raise EchoChangeError(f"Each exact-match edit must have find and replace text: {relative_path}")
            find = edit.get("find")
            replacement = edit.get("replace")
            if not isinstance(find, str) or not find or not isinstance(replacement, str):
                raise EchoChangeError(
                    f"Each exact-match edit must have non-empty find text and replacement text: {relative_path}"
                )
            occurrences = content.count(find)
            if occurrences != 1:
                raise EchoChangeError(
                    f"Exact edit for {relative_path} matched {occurrences} times; "
                    "it must match exactly once to avoid changing the wrong code."
                )
            content = content.replace(find, replacement, 1)
        return content

    def _normalize_files(self, files: list[dict]) -> list[dict]:
        if not isinstance(files, list) or not files or len(files) > self._MAX_FILES:
            raise EchoChangeError(f"A proposal must contain between 1 and {self._MAX_FILES} files.")

        normalized = []
        seen = set()
        total_bytes = 0
        for item in files:
            if not isinstance(item, dict):
                raise EchoChangeError("Each proposed file must be an object with path and content.")
            relative_path = str(item.get("path") or "").strip().replace("\\", "/")
            if relative_path.casefold() in seen:
                raise EchoChangeError(f"A path appears more than once in the proposal: {relative_path}")
            seen.add(relative_path.casefold())
            target = self._resolve_target(relative_path)
            content = item.get("content")
            edits = item.get("edits")
            if edits is not None:
                if not target.is_file() or not isinstance(edits, list) or not edits:
                    raise EchoChangeError(f"Exact-match edits require an existing file and a non-empty edits list: {relative_path}")
                try:
                    original_content = target.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    raise EchoChangeError(f"Cannot read current source file {relative_path}: {exc}") from exc
                content = self._apply_edits(relative_path, original_content, edits)
                stored_edits = edits
                total_bytes += sum(
                    len(str(edit.get("find", "")).encode("utf-8"))
                    + len(str(edit.get("replace", "")).encode("utf-8"))
                    for edit in edits if isinstance(edit, dict)
                )
            elif not isinstance(content, str):
                raise EchoChangeError(f"Proposed content must be text: {relative_path}")
            else:
                stored_edits = None
                total_bytes += len(content.encode("utf-8"))
            if total_bytes > self._MAX_TOTAL_BYTES:
                raise EchoChangeError("The proposed change exceeds the 500 KB safety limit.")
            self._validate_content(target, content)

            if target.exists() and not target.is_file():
                raise EchoChangeError(f"Target is not a regular file: {relative_path}")
            original_hash = None
            if target.exists():
                try:
                    original_hash = hashlib.sha256(target.read_bytes()).hexdigest()
                except OSError as exc:
                    raise EchoChangeError(f"Cannot read current file {relative_path}: {exc}") from exc
            normalized_item = {
                "path": relative_path,
                "before_sha256": original_hash,
                "is_new": original_hash is None,
            }
            if stored_edits is None:
                normalized_item["content"] = content
            else:
                normalized_item["edits"] = stored_edits
            normalized.append(normalized_item)
        return normalized

    def create_pending(
        self,
        session_id: str,
        user_id: str,
        summary: str,
        files: list[dict],
    ) -> dict:
        session_id = str(session_id or "").strip()
        user_id = str(user_id or "").strip()
        summary = str(summary or "").strip()
        if not session_id or not user_id or not summary:
            raise EchoChangeError("A session, authenticated user, and change summary are required.")
        if len(summary) > 1000:
            raise EchoChangeError("The change summary is too long.")

        normalized_files = self._normalize_files(files)
        with self._connection() as db:
            existing = db.execute(
                """
                SELECT proposal_id FROM echo_change_proposals
                WHERE session_id = ? AND user_id = ? AND status = 'pending'
                LIMIT 1
                """,
                (session_id, user_id),
            ).fetchone()
            if existing:
                raise EchoChangeError(
                    "There is already an unconfirmed proposal for this chat. "
                    "Use !confirmed or !cancelchange before drafting another."
                )

            proposal_id = uuid.uuid4().hex
            db.execute(
                """
                INSERT INTO echo_change_proposals
                    (proposal_id, session_id, user_id, summary, files_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (proposal_id, session_id, user_id, summary, json.dumps(normalized_files)),
            )
        return {
            "proposal_id": proposal_id,
            "summary": summary,
            "files": [
                {"path": item["path"], "is_new": item["is_new"]}
                for item in normalized_files
            ],
        }

    def get_pending(self, session_id: str, user_id: str) -> dict | None:
        with self._connection() as db:
            row = db.execute(
                """
                SELECT proposal_id, summary, files_json, created_at
                FROM echo_change_proposals
                WHERE session_id = ? AND user_id = ? AND status = 'pending'
                ORDER BY created_at DESC LIMIT 1
                """,
                (str(session_id), str(user_id)),
            ).fetchone()
        if row is None:
            return None
        files = json.loads(row["files_json"])
        for item in files:
            if item.get("edits") is None:
                continue
            target = self._resolve_target(item["path"])
            try:
                original = target.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise EchoChangeError(f"Cannot preview {item['path']}: {exc}") from exc
            current_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            if current_hash != item["before_sha256"]:
                raise EchoChangeError(f"{item['path']} changed after drafting. Ask Echo to create a fresh proposal.")
            item["content"] = self._apply_edits(item["path"], original, item["edits"])
        return {
            "proposal_id": row["proposal_id"],
            "summary": row["summary"],
            "files": files,
            "created_at": row["created_at"],
        }

    def cancel_pending(self, session_id: str, user_id: str) -> str | None:
        with self._connection() as db:
            row = db.execute(
                """
                SELECT proposal_id FROM echo_change_proposals
                WHERE session_id = ? AND user_id = ? AND status = 'pending'
                ORDER BY created_at DESC LIMIT 1
                """,
                (str(session_id), str(user_id)),
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE echo_change_proposals SET status = 'cancelled' WHERE proposal_id = ?",
                (row["proposal_id"],),
            )
        return row["proposal_id"]

    def confirm_pending(self, session_id: str, user_id: str) -> dict:
        backups: list[str] = []
        replaced: list[tuple[Path, Path | None]] = []
        temporary_paths: list[Path] = []
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT proposal_id, summary, files_json
                FROM echo_change_proposals
                WHERE session_id = ? AND user_id = ? AND status = 'pending'
                ORDER BY created_at DESC LIMIT 1
                """,
                (str(session_id), str(user_id)),
            ).fetchone()
            if row is None:
                raise EchoChangeError("There is no pending app-change proposal to confirm.")

            proposal_id = row["proposal_id"]
            files = json.loads(row["files_json"])
            targets = []
            for item in files:
                target = self._resolve_target(item["path"])
                if target.exists() != (item["before_sha256"] is not None):
                    raise EchoChangeError(
                        f"{item['path']} changed since the proposal was shown. Ask Echo to draft it again."
                    )
                if target.exists():
                    current_hash = hashlib.sha256(target.read_bytes()).hexdigest()
                    if current_hash != item["before_sha256"]:
                        raise EchoChangeError(
                            f"{item['path']} changed since the proposal was shown. Ask Echo to draft it again."
                        )
                if item.get("edits") is not None:
                    try:
                        original = target.read_text(encoding="utf-8")
                    except (OSError, UnicodeError) as exc:
                        raise EchoChangeError(f"Cannot apply exact edits to {item['path']}: {exc}") from exc
                    content = self._apply_edits(item["path"], original, item["edits"])
                else:
                    content = item["content"]
                self._validate_content(target, content)
                targets.append((item, target, content))

            backup_root = self.project_root / "data" / "echo_change_backups" / proposal_id
            try:
                staged = []
                for item, target, content in targets:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    backup = None
                    if target.exists():
                        backup = backup_root / item["path"]
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(target, backup)
                        backups.append(backup.relative_to(self.project_root).as_posix())

                    temporary = target.with_name(f".{target.name}.{proposal_id}.tmp")
                    with temporary.open("xb") as stream:
                        stream.write(content.encode("utf-8"))
                        stream.flush()
                        os.fsync(stream.fileno())
                    if target.exists():
                        os.chmod(temporary, target.stat().st_mode)
                    temporary_paths.append(temporary)
                    staged.append((target, temporary, backup))

                for target, temporary, backup in staged:
                    os.replace(temporary, target)
                    temporary_paths.remove(temporary)
                    replaced.append((target, backup))

                db.execute(
                    """
                    UPDATE echo_change_proposals
                    SET status = 'applied', applied_at = ?, backup_paths_json = ?
                    WHERE proposal_id = ? AND status = 'pending'
                    """,
                    (
                        datetime.now(timezone.utc).isoformat(),
                        json.dumps(backups),
                        proposal_id,
                    ),
                )
            except Exception as exc:
                rollback_errors = []
                for target, backup in reversed(replaced):
                    try:
                        if backup is None:
                            target.unlink()
                        else:
                            rollback_tmp = target.with_name(f".{target.name}.{proposal_id}.rollback")
                            shutil.copy2(backup, rollback_tmp)
                            os.replace(rollback_tmp, target)
                    except OSError as rollback_exc:
                        rollback_errors.append(f"{target}: {rollback_exc}")
                for temporary in temporary_paths:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError as cleanup_exc:
                        rollback_errors.append(f"{temporary}: {cleanup_exc}")
                if rollback_errors:
                    raise EchoChangeError(
                        f"Applying the proposal failed ({exc}); rollback also reported: "
                        + "; ".join(rollback_errors)
                    ) from exc
                raise EchoChangeError(f"Applying the proposal failed; no partial change was retained: {exc}") from exc

        return {
            "proposal_id": proposal_id,
            "summary": row["summary"],
            "files": [item["path"] for item in files],
            "backups": backups,
        }

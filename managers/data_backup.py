"""Create and list zip backups of the MasterChief data directory."""

from __future__ import annotations

import re
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

BACKUP_NAME_PATTERN = re.compile(r"^data-backup-\d{8}-\d{6}\.zip$")
_SQLITE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
_SKIP_DIR_NAMES = {"backups", "__pycache__"}


class DataBackupError(ValueError):
    """An invalid backup request."""


class DataBackupManager:
    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.data_dir = self.project_root / "data"
        self.backup_dir = self.data_dir / "backups"

    def _iter_files(self):
        for path in sorted(self.data_dir.rglob("*")):
            relative = path.relative_to(self.data_dir)
            if any(part in _SKIP_DIR_NAMES for part in relative.parts) or not path.is_file():
                continue
            yield path, relative

    @staticmethod
    def _consistent_sqlite_copy(source: Path, destination: Path) -> bool:
        """Copy a live SQLite database safely; return False if it is not a readable database."""
        try:
            src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True, timeout=10)
        except sqlite3.Error:
            return False
        try:
            dst = sqlite3.connect(destination)
            try:
                src.backup(dst)
            finally:
                dst.close()
            return True
        except sqlite3.Error:
            return False
        finally:
            src.close()

    def create_backup(self) -> dict:
        if not self.data_dir.is_dir():
            raise DataBackupError("The data directory does not exist.")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        name = f"data-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
        target = self.backup_dir / name
        partial = target.with_suffix(".zip.partial")
        file_count = 0
        skipped: list[str] = []
        try:
            with tempfile.TemporaryDirectory() as scratch, zipfile.ZipFile(
                partial, "w", zipfile.ZIP_DEFLATED
            ) as archive:
                for path, relative in self._iter_files():
                    source = path
                    if path.suffix.lower() in _SQLITE_SUFFIXES:
                        copy = Path(scratch) / f"{file_count}.db"
                        if self._consistent_sqlite_copy(path, copy):
                            source = copy
                    try:
                        archive.write(source, Path("data", relative).as_posix())
                        file_count += 1
                    except OSError:
                        skipped.append(relative.as_posix())
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        return {
            "name": name,
            "files": file_count,
            "skipped": skipped,
            "size": target.stat().st_size,
        }

    def list_backups(self) -> list[dict]:
        if not self.backup_dir.is_dir():
            return []
        backups = []
        for path in self.backup_dir.iterdir():
            if path.is_file() and BACKUP_NAME_PATTERN.match(path.name):
                stat = path.stat()
                backups.append(
                    {
                        "name": path.name,
                        "size": stat.st_size,
                        "created": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    }
                )
        return sorted(backups, key=lambda item: item["name"], reverse=True)

    def backup_path(self, name: str) -> Path:
        if not BACKUP_NAME_PATTERN.match(name or ""):
            raise DataBackupError("Invalid backup name.")
        path = self.backup_dir / name
        if not path.is_file():
            raise DataBackupError("Backup not found.")
        return path

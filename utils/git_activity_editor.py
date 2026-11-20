"""Read and update existing UTF-8 project files for the activity editor."""

import hashlib
import re
from pathlib import Path

from utils.ide_files import resolve_project_file

MAX_BYTES = 1_000_000


class EditConflict(ValueError):
    pass


def _file(root, name):
    if not isinstance(name, str) or not name or name != name.strip() or "\0" in name:
        raise ValueError("A valid file path is required.")
    parts = name.replace("\\", "/").split("/")
    if any(part in ("", ".", "..") or part.lower() == ".git" for part in parts):
        raise ValueError("Invalid project file path.")
    root = Path(root).resolve()
    path = resolve_project_file(root, name)
    if any((root.joinpath(*parts[:index])).is_symlink() for index in range(1, len(parts) + 1)):
        raise ValueError("Symbolic links cannot be edited here.")
    if not path.is_file():
        raise ValueError("File does not exist or is not a regular file.")
    return path


def _read(path):
    with path.open("rb") as source:
        data = source.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("File is too large to edit here (limit: 1 MB).")
    if b"\0" in data:
        raise ValueError("Binary files cannot be edited here.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Only UTF-8 text files can be edited here.") from exc
    endings = set(re.findall(r"\r\n|\r|\n", text))
    if len(endings) > 1:
        raise ValueError("Mixed line endings cannot be safely edited here; use Code UI or another editor.")
    return text, hashlib.sha256(data).hexdigest(), next(iter(endings), "\n")


def load(root, name):
    text, version, ending = _read(_file(root, name))
    return {"content": text.replace("\r\n", "\n").replace("\r", "\n"),
            "version": version, "line_ending": ending}


def save(root, name, content, version):
    if not isinstance(content, str) or "\0" in content or not isinstance(version, str):
        raise ValueError("Valid text content and a file version are required.")
    path = _file(root, name)
    _, current_version, ending = _read(path)
    if current_version != version:
        raise EditConflict("The file changed on disk since it was opened. Copy your edits before reloading.")
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    encoded = normalized.replace("\n", ending).encode("utf-8")
    if len(encoded) > MAX_BYTES:
        raise ValueError("File is too large to save here (limit: 1 MB).")
    path.write_bytes(encoded)
    return {"version": hashlib.sha256(encoded).hexdigest()}

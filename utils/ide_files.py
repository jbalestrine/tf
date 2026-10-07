"""Path helpers for the project-wide Code UI."""

from pathlib import Path


def resolve_project_file(project_root: Path, relative_path: str) -> Path:
    """Resolve a relative IDE path without allowing it to escape the project."""
    raw_path = str(relative_path or '').strip()
    if not raw_path:
        return Path(project_root).resolve()

    normalized = raw_path.replace('\\', '/')
    candidate_path = Path(normalized)
    if candidate_path.is_absolute() or candidate_path.drive:
        raise ValueError('absolute paths are not allowed')

    root = Path(project_root).resolve()
    target = (root / normalized).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError('path must stay inside the project directory') from exc
    return target

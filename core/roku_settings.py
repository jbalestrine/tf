"""Persistent private-feature settings for the Roku builder."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_FILE = PROJECT_ROOT / "data" / "roku_settings.json"


def get_roku_settings(path: Path = SETTINGS_FILE) -> dict:
    if not path.exists():
        return {"enabled": True}
    settings = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(settings, dict) or not isinstance(settings.get("enabled"), bool):
        raise ValueError("Roku settings must contain a boolean enabled value.")
    return {"enabled": settings["enabled"]}


def set_roku_enabled(enabled: bool, path: Path = SETTINGS_FILE) -> dict:
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a boolean.")
    settings = {"enabled": enabled}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return settings

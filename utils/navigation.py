"""Helpers for keeping pinned add-on navigation safe and useful."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any


_HIDDEN_MODULE_NAMES = {
    "create_a_new_module_when_i_say_module_cr",
}


def visible_pinned_modules(value: Any, upload_folder: Path) -> dict[str, dict[str, str]]:
    """Return valid, installed, same-origin add-ons suitable for the main menu."""
    if not isinstance(value, Mapping):
        return {}

    extracted_root = (Path(upload_folder) / "extracted").resolve()
    visible: dict[str, dict[str, str]] = {}
    for raw_name, raw_module in value.items():
        if not isinstance(raw_name, str) or not raw_name.strip():
            continue
        name = raw_name.strip()
        if name.casefold() in _HIDDEN_MODULE_NAMES or not isinstance(raw_module, Mapping):
            continue

        module_dir = (extracted_root / name).resolve()
        try:
            module_dir.relative_to(extracted_root)
        except ValueError:
            continue
        if not module_dir.is_dir():
            continue

        url = raw_module.get("url")
        if not isinstance(url, str):
            continue
        parsed = urlsplit(url)
        if (
            parsed.scheme
            or parsed.netloc
            or not parsed.path.startswith("/addons/modules/")
            or "\\" in parsed.path
            or any(part == ".." for part in parsed.path.split("/"))
        ):
            continue

        icon = raw_module.get("icon")
        visible[name] = {
            "url": url,
            "icon": icon if isinstance(icon, str) and len(icon) <= 12 else "🧩",
        }
    return visible

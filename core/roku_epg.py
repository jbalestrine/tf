"""Small XMLTV helpers for matching live listings to playlist channel IDs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import secrets
from xml.etree import ElementTree


MAX_XMLTV_BYTES = 50 * 1024 * 1024
MAX_XMLTV_PROGRAMMES = 500_000
_XMLTV_TIME = re.compile(r"^(\d{14})(?:\s*([+-]\d{4}|Z))?")


def _parse_xmltv_time(value: str) -> datetime | None:
    match = _XMLTV_TIME.match(value or "")
    if not match:
        return None
    try:
        parsed = datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    zone = match.group(2) or "Z"
    if zone == "Z":
        return parsed.replace(tzinfo=timezone.utc)
    sign = 1 if zone[0] == "+" else -1
    minutes = int(zone[1:3]) * 60 + int(zone[3:5])
    return parsed.replace(tzinfo=timezone(sign * timedelta(minutes=minutes)))


def parse_xmltv_listings(
    content: bytes | str,
    now: datetime | None = None,
) -> dict[str, dict[str, dict[str, str]]]:
    """Return current and next programmes keyed by XMLTV channel ID."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    if len(content) > MAX_XMLTV_BYTES:
        raise ValueError("XMLTV guide files must be 50 MiB or smaller.")
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", content, re.IGNORECASE):
        raise ValueError("XMLTV guide cannot contain document type or entity declarations.")
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    instant = instant.astimezone(timezone.utc)
    candidates: dict[str, list[tuple[datetime, datetime, str, str]]] = {}
    count = 0
    element_stack = []
    try:
        for event, element in ElementTree.iterparse(BytesIO(content), events=("start", "end")):
            if event == "start":
                element_stack.append(element)
                continue

            tag = element.tag.rsplit("}", 1)[-1]
            if tag == "programme":
                count += 1
                if count > MAX_XMLTV_PROGRAMMES:
                    raise ValueError("XMLTV guide exceeds the 500,000-programme processing limit.")
                channel_id = (element.get("channel") or "").strip()
                start = _parse_xmltv_time(element.get("start") or "")
                stop = _parse_xmltv_time(element.get("stop") or "")
                title_element = next(
                    (child for child in element if child.tag.rsplit("}", 1)[-1] == "title"),
                    None,
                )
                title = " ".join("".join(title_element.itertext()).split()) if title_element is not None else ""
                desc_element = next(
                    (child for child in element if child.tag.rsplit("}", 1)[-1] == "desc"),
                    None,
                )
                description = " ".join("".join(desc_element.itertext()).split()) if desc_element is not None else ""
                if channel_id and start and stop and start < stop and title and stop > instant:
                    candidates.setdefault(channel_id, []).append((start, stop, title[:300], description[:1000]))
                element.clear()
            elif tag == "channel":
                element.clear()
            elif len(element_stack) == 2:
                element.clear()
            element_stack.pop()
    except ElementTree.ParseError as exc:
        raise ValueError(f"XMLTV guide is not valid XML: {exc}") from exc

    result = {}
    for channel_id, programmes in candidates.items():
        programmes.sort(key=lambda item: item[0])
        current = next((item for item in programmes if item[0] <= instant < item[1]), None)
        upcoming = next((item for item in programmes if item[0] > instant), None)
        channel_listings = {}
        if current:
            channel_listings["now"] = _listing_payload(current)
        if upcoming:
            channel_listings["next"] = _listing_payload(upcoming)
        if channel_listings:
            result[channel_id] = channel_listings
    return result


def _listing_payload(
    programme: tuple[datetime, datetime, str, str],
) -> dict[str, str]:
    start, stop, title, description = programme
    return {
        "title": title,
        "start": start.isoformat(),
        "stop": stop.isoformat(),
        "description": description,
    }


def apply_xmltv_listings(entries: list[dict], guide: dict[str, dict]) -> int:
    """Attach guide listings to channels using the M3U tvg_id."""
    matched = 0
    for entry in entries:
        channel_id = str(entry.get("tvg_id") or "").strip()
        listings = guide.get(channel_id)
        if not listings:
            continue
        entry["program_now"] = listings.get("now")
        entry["program_next"] = listings.get("next")
        matched += 1
    return matched


def create_guide_token() -> str:
    return secrets.token_urlsafe(32)


def save_guide_source(guide_dir: Path, token: str, guide_url: str) -> None:
    """Store a Roku guide URL outside the public tree, keyed by a token hash."""
    guide_dir = Path(guide_dir)
    guide_dir.mkdir(parents=True, exist_ok=True)
    target = guide_dir / f"{hashlib.sha256(token.encode('utf-8')).hexdigest()}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps({"url": guide_url}), encoding="utf-8")
    temporary.replace(target)


def load_guide_source(guide_dir: Path, token: str) -> str | None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,64}", token or ""):
        return None
    root = Path(guide_dir).resolve()
    source = root / f"{hashlib.sha256(token.encode('utf-8')).hexdigest()}.json"
    if source.is_symlink() or not source.is_file() or source.resolve().parent != root:
        return None
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    url = payload.get("url") if isinstance(payload, dict) else None
    return url if isinstance(url, str) and url else None

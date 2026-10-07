"""Robust playlist parsing and normalization for the Roku builder."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import parse_qs, urljoin, urlsplit
import json


MAX_PLAYLIST_ENTRIES = 100_000
PLAYABLE_SCHEMES = {"http", "https", "rtsp", "rtmp", "udp", "mms"}


def normalize_group_key(value: Optional[str]) -> str:
    text = (value or "").strip().lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "live"


def _path_category(url: str) -> Optional[str]:
    try:
        segments = {segment.casefold() for segment in urlsplit(url or "").path.split("/") if segment}
    except ValueError:
        return None
    route_categories = (
        ({"movie", "movies", "film", "films", "vod"}, "movies"),
        ({"series", "show", "shows", "episode", "episodes"}, "series"),
        ({"live", "livetv", "live-tv"}, "live"),
        ({"sport", "sports"}, "sports"),
        ({"news"}, "news"),
        ({"kids", "children"}, "kids"),
        ({"music", "radio"}, "music"),
    )
    for route_names, category in route_categories:
        if segments.intersection(route_names):
            return category
    return None


def classify_entry(title: str, group: Optional[str] = None, url: str = "") -> str:
    text = f"{title or ''} {group or ''} {url or ''}".casefold()
    route_category = _path_category(url)
    if route_category:
        return route_category
    categories = (
        ("series", r"\b(series|tv shows?|episodes?|season\s*\d+|s\d{1,2}e\d{1,2})\b"),
        ("movies", r"\b(movies?|films?|cinema|vod)\b"),
        ("sports", r"\b(sports?|football|soccer|nba|nfl|mma|boxing|premier league)\b"),
        ("news", r"\b(news|breaking news|cnn|bbc|fox news|sky news)\b"),
        ("kids", r"\b(kids?|cartoons?|animation|family)\b"),
        ("music", r"\b(music|radio|concerts?)\b"),
    )
    for category, pattern in categories:
        if re.search(pattern, text):
            return category
    if re.search(r"\b(live(?:\s+tv)?|live channels?)\b", text):
        return "live"
    return "uncategorized"


def infer_stream_format(url: str, declared: Optional[str] = None) -> str:
    """Return the Roku Video streamFormat value without changing the source URL."""
    aliases = {
        "m3u8": "hls",
        "hls": "hls",
        "ts": "mp2ts",
        "mp2ts": "mp2ts",
        "mpegts": "mp2ts",
        "mpeg-ts": "mp2ts",
        "mp4": "mp4",
        "m4v": "mp4",
        "mkv": "mkv",
        "mov": "mov",
        "mp3": "mp3",
        "mpd": "dash",
        "dash": "dash",
        "ism": "ism",
    }
    value = str(declared or "").strip().lower().lstrip(".")
    if value in aliases:
        return aliases[value]
    try:
        parsed_url = urlsplit(url or "")
        path = parsed_url.path.lower()
        query = parse_qs(parsed_url.query)
    except ValueError:
        path = ""
        query = {}
    for key in ("output", "format", "container", "stream_format"):
        for value in query.get(key, []):
            normalized = aliases.get(value.strip().lower().lstrip("."))
            if normalized:
                return normalized
    for suffix, stream_format in (
        (".m3u8", "hls"),
        (".ts", "mp2ts"),
        (".mp4", "mp4"),
        (".m4v", "mp4"),
        (".mkv", "mkv"),
        (".mov", "mov"),
        (".mp3", "mp3"),
        (".mpd", "dash"),
        (".ism", "ism"),
    ):
        if path.endswith(suffix):
            return stream_format
    if path.endswith(".avi") or path.endswith(".m3u"):
        return "unsupported"
    return "hls"


def _category_group(title: str, raw_group: str, url: str) -> str:
    group = re.sub(r"\s+", " ", str(raw_group or "")).strip(" \t|-/")
    if not _is_placeholder_group(group):
        canonical = {
            "movie": "Movies",
            "movies": "Movies",
            "film": "Movies",
            "films": "Movies",
            "series": "Series",
            "live": "Live TV",
            "live tv": "Live TV",
            "live television": "Live TV",
        }.get(group.casefold())
        return canonical or group[:120]
    inferred = classify_entry(title, group, url)
    if inferred == "live":
        return "Live TV"
    return inferred.title() if inferred != "uncategorized" else "Uncategorized"


def _split_title_category(title: str) -> tuple[str, str]:
    match = re.match(r"^\s*(\d+\s*/\s*\d+)\s+(?:[-:|]\s*)?(.+?)\s*$", str(title or ""))
    if not match:
        return str(title or "").strip(), ""
    return match.group(2).strip(), re.sub(r"\s+", "", match.group(1))


def _is_placeholder_group(group: str) -> bool:
    return str(group or "").strip().casefold() in {
        "",
        "uncategorized",
        "unknown",
        "none",
        "null",
        "default",
        "other",
    }


def _organize_entries(entries: list[dict]) -> list[dict]:
    unique = {}
    for entry in entries:
        url = entry["url"]
        unique.setdefault(url, entry)
    return sorted(
        unique.values(),
        key=lambda entry: (
            str(entry.get("group") or "Uncategorized").casefold(),
            str(entry.get("title") or "").casefold(),
            str(entry.get("url") or ""),
        ),
    )


def _split_extinf(line: str) -> tuple[dict[str, str], str, str]:
    content = line[len("#EXTINF:"):]
    quoted = None
    comma_at = -1
    for index, char in enumerate(content):
        if char in {'"', "'"} and (index == 0 or content[index - 1] != "\\"):
            quoted = None if quoted == char else (char if quoted is None else quoted)
        elif char == "," and quoted is None:
            comma_at = index
            break
    metadata = content if comma_at < 0 else content[:comma_at]
    title = "" if comma_at < 0 else content[comma_at + 1:].strip()
    duration_match = re.match(r"\s*(-?\d+(?:\.\d+)?)", metadata)
    duration = duration_match.group(1) if duration_match else "-1"
    attrs = {}
    attr_pattern = re.compile(
        r"""([A-Za-z0-9_-]+)\s*=\s*(?:"((?:\\.|[^"])*)"|'((?:\\.|[^'])*)'|([^\s,]+))"""
    )
    for match in attr_pattern.finditer(metadata):
        value = next((part for part in match.groups()[1:] if part is not None), "")
        attrs[match.group(1).lower().replace("-", "_")] = value.replace('\\"', '"').replace("\\'", "'")
    return attrs, title, duration


def _playable_url(value: str, base_url: Optional[str]) -> Optional[str]:
    url = (value or "").strip()
    if not url or url.startswith("#"):
        return None
    if base_url:
        url = urljoin(base_url, url)
    try:
        scheme = urlsplit(url).scheme.lower()
    except ValueError:
        return None
    return url if scheme in PLAYABLE_SCHEMES else None


def parse_m3u_playlist(text: str, base_url: Optional[str] = None) -> list[dict]:
    entries = []
    pending = {}
    pending_group = ""
    stream_headers = {}
    lines = str(text or "").lstrip("\ufeff").splitlines()
    upper_lines = [line.strip().upper() for line in lines]
    hls_media_tags = (
        "#EXT-X-TARGETDURATION:",
        "#EXT-X-MEDIA-SEQUENCE:",
        "#EXT-X-PLAYLIST-TYPE:",
        "#EXT-X-ENDLIST",
        "#EXT-X-KEY:",
    )
    if base_url and any(line.startswith(hls_media_tags) for line in upper_lines):
        title = urlsplit(base_url).path.rstrip("/").rsplit("/", 1)[-1] or "Live stream"
        title = re.sub(r"\.(m3u8?|ts)$", "", title, flags=re.IGNORECASE)
        return [{
            "title": title[:300],
            "url": base_url,
            "group": _category_group(title, "", base_url),
            "category": classify_entry(title, url=base_url),
            "logo": "",
            "tvg_id": "",
            "duration": "-1",
            "metadata": {},
            "http_headers": {},
            "stream_format": "hls",
        }]

    pending_variant = ""
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.upper().startswith("#EXTGRP:"):
            pending_group = line.split(":", 1)[1].strip()
            continue
        if line.upper().startswith("#EXTINF:"):
            attrs, title, duration = _split_extinf(line)
            group = attrs.get("group_title") or attrs.get("tvg_group") or attrs.get("group") or pending_group
            pending = {
                "title": title or attrs.get("tvg_name") or f"Channel {len(entries) + 1}",
                "group": group or "",
                "category": attrs.get("category") or (normalize_group_key(group) if group else ""),
                "stream_format": attrs.get("stream_format") or attrs.get("format") or attrs.get("tvg_type") or "",
                "logo": attrs.get("tvg_logo") or attrs.get("logo") or "",
                "tvg_id": attrs.get("tvg_id") or "",
                "duration": duration,
                "metadata": attrs,
            }
            stream_headers = {}
            continue
        if line.upper().startswith("#EXT-X-STREAM-INF:"):
            resolution = re.search(r"(?:^|,)RESOLUTION=(\d+x\d+)", line, re.IGNORECASE)
            pending_variant = resolution.group(1) if resolution else "Adaptive"
            continue
        if line.upper().startswith("#EXTVLCOPT:"):
            setting = line.split(":", 1)[1]
            if "=" in setting:
                key, value = setting.split("=", 1)
                header_names = {
                    "http-user-agent": "User-Agent",
                    "http-referrer": "Referer",
                    "http-referer": "Referer",
                }
                header_name = header_names.get(key.strip().lower())
                if header_name:
                    stream_headers[header_name] = value.strip()
            continue
        if line.upper().startswith("#EXTHTTP:"):
            try:
                header_values = json.loads(line.split(":", 1)[1])
            except (ValueError, json.JSONDecodeError):
                header_values = {}
            if isinstance(header_values, dict):
                for key, value in header_values.items():
                    if isinstance(value, (str, int, float)):
                        stream_headers[str(key)[:100]] = str(value)[:2048]
            continue
        if line.startswith("#"):
            continue
        url = _playable_url(line, base_url)
        if not url:
            continue
        if len(entries) >= MAX_PLAYLIST_ENTRIES:
            break
        group = pending.get("group") or pending_group
        title = pending.get("title") or f"Channel {len(entries) + 1}"
        inferred_title, title_group = _split_title_category(title)
        title_category_applied = _is_placeholder_group(group) and bool(title_group)
        if title_category_applied:
            title = inferred_title
            group = title_group
        if pending_variant:
            title = f"{title} ({pending_variant})"
        display_group = _category_group(title, group, url)
        category = str(pending.get("category") or "").strip()
        if _is_placeholder_group(category):
            if title_category_applied:
                category = normalize_group_key(group)
            elif _is_placeholder_group(group):
                category = classify_entry(title, "", url)
            else:
                category = normalize_group_key(group)
        entries.append({
            "title": title[:300],
            "url": url,
            "group": display_group,
            "category": category,
            "logo": urljoin(base_url, pending.get("logo") or "") if base_url and pending.get("logo") else pending.get("logo") or "",
            "tvg_id": pending.get("tvg_id") or "",
            "duration": pending.get("duration") or "-1",
            "metadata": pending.get("metadata") or {},
            "http_headers": dict(stream_headers),
            "stream_format": infer_stream_format(url, pending.get("stream_format")),
        })
        pending = {}
        pending_group = ""
        stream_headers = {}
        pending_variant = ""
    return _organize_entries(entries)


def parse_json_playlist(value, base_url: Optional[str] = None) -> list[dict]:
    import json

    import_value = json.loads(value) if isinstance(value, str) else value
    if isinstance(import_value, list):
        raw_entries = import_value
    elif isinstance(import_value, dict):
        raw_entries = next(
            (import_value[key] for key in ("channels", "items", "streams", "entries") if isinstance(import_value.get(key), list)),
            None,
        )
        if raw_entries is None:
            raise ValueError("JSON playlist must be a list or contain a channels/items/streams/entries list.")
    else:
        raise ValueError("JSON playlist must be a list or object.")

    entries = []
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        url = _playable_url(str(item.get("url") or item.get("stream_url") or item.get("stream") or ""), base_url)
        if not url:
            continue
        title = str(item.get("title") or item.get("name") or f"Channel {len(entries) + 1}").strip()
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        group = str(
            item.get("group")
            or item.get("group-title")
            or item.get("group_title")
            or item.get("tvg_group")
            or metadata.get("group_title")
            or item.get("category")
            or ""
        ).strip()
        inferred_title, title_group = _split_title_category(title)
        title_category_applied = _is_placeholder_group(group) and bool(title_group)
        if title_category_applied:
            title = inferred_title
            group = title_group
        display_group = _category_group(title, group, url)
        category = str(item.get("category") or "").strip()
        if _is_placeholder_group(category):
            if title_category_applied:
                category = normalize_group_key(group)
            elif _is_placeholder_group(group):
                category = classify_entry(title, "", url)
            else:
                category = normalize_group_key(group)
        entries.append({
            "title": title[:300] or f"Channel {len(entries) + 1}",
            "url": url,
            "group": display_group,
            "category": category,
            "logo": urljoin(base_url, str(item.get("logo") or item.get("tvg_logo") or "").strip())
            if base_url and (item.get("logo") or item.get("tvg_logo"))
            else str(item.get("logo") or item.get("tvg_logo") or "").strip(),
            "tvg_id": str(item.get("tvg_id") or "").strip(),
            "duration": str(item.get("duration") or "-1"),
            "metadata": metadata,
            "http_headers": item.get("http_headers") if isinstance(item.get("http_headers"), dict) else {},
            "stream_format": infer_stream_format(
                url,
                item.get("stream_format") or item.get("streamFormat") or item.get("format"),
            ),
        })
        if len(entries) >= MAX_PLAYLIST_ENTRIES:
            break
    return _organize_entries(entries)


def group_entries(entries: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        category = str(entry.get("group") or entry.get("raw_group") or entry.get("category") or "Uncategorized")
        grouped.setdefault(category, []).append(entry)
    return dict(sorted(grouped.items(), key=lambda item: item[0].casefold()))

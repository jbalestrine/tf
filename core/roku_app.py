"""Package a complete SceneGraph Roku app from normalized playlist entries."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
import re
import shutil
import zipfile

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROKU_ROOT = PROJECT_ROOT / "roku"
ROKU_PLAYLIST_SHARD_SIZE = 500
ROKU_COLLECTIONS = (
    "XXX",
    "Sports",
    "UFC",
    "WWE",
    "Boxing",
    "NFL",
    "NBA",
    "MLB",
    "NHL",
    "Soccer",
    "Motorsports",
    "Tennis",
    "Cricket",
    "Rugby",
    "Golf",
    "Olympics",
    "Jackie Chan Films",
    "Transporter",
    "Two and a Half Men",
    "Lord of the Rings",
    "Batman",
    "The Big Bang Theory",
    "Curb Your Enthusiasm",
    "BBC Earth",
    "24/7 Channels",
    "HBO",
    "CINEMAX",
    "SHOWTIME",
    "STARZ",
    "NETFLIX",
    "NEWS CHANNELS",
    "Series",
)
ROKU_LOGO_COLORS = {
    "green": (35, 134, 54, 255),
    "blue": (31, 111, 235, 255),
    "red": (218, 54, 51, 255),
    "purple": (137, 87, 229, 255),
    "gold": (187, 128, 9, 255),
}


def project_slug(channel_name: str, build_id: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", channel_name.casefold()).strip("-") or "masterchief-roku"
    return f"{base[:45]}-{build_id[:8]}"


def _safe_manifest_text(value: str, field: str, limit: int = 80) -> str:
    value = re.sub(r"[\r\n=]", " ", str(value or "")).strip()
    if not value or len(value) > limit:
        raise ValueError(f"{field} must be between 1 and {limit} characters.")
    return value


def _validate_render_url(value: str) -> str:
    value = str(value or "").strip().rstrip("/")
    if not value:
        return ""
    from urllib.parse import urlsplit

    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Render app URL must be an HTTPS base URL without credentials, query, or fragment.")
    return value


def _validate_web_app_url(value: str) -> str:
    value = str(value or "").strip().rstrip("/")
    if not value:
        return ""
    from urllib.parse import urlsplit

    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or parsed.hostname.casefold() in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError(
            "Web app URL must be an HTTP(S) base URL reachable from the Roku, "
            "without credentials, path, query, or fragment. Use the computer's "
            "LAN address instead of localhost for a local server."
        )
    return value


def _logo_font(size: int) -> ImageFont.ImageFont:
    font_candidates = (
        Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    )
    for font_path in font_candidates:
        if font_path.is_file():
            return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default(size=size)


def _write_roku_logo(path: Path, size: tuple[int, int], text: str, color: tuple[int, int, int, int]) -> None:
    width, height = size
    image = Image.new("RGBA", size, (13, 17, 23, 255))
    draw = ImageDraw.Draw(image)
    inset_x = max(4, round(width * 0.04))
    inset_y = max(4, round(height * 0.08))
    draw.rounded_rectangle(
        (inset_x, inset_y, width - inset_x - 1, height - inset_y - 1),
        radius=round(height * 0.2),
        fill=color,
    )

    font_size = max(8, round(height * 0.46))
    font = _logo_font(font_size)
    bounds = draw.textbbox((0, 0), text, font=font)
    available_width = width - inset_x * 4
    while bounds[2] - bounds[0] > available_width and font_size > 8:
        font_size -= 1
        font = _logo_font(font_size)
        bounds = draw.textbbox((0, 0), text, font=font)
    text_width = bounds[2] - bounds[0]
    text_height = bounds[3] - bounds[1]
    x = (width - text_width) / 2 - bounds[0]
    y = (height - text_height) / 2 - bounds[1]
    draw.text((x, y), text, font=font, fill=(230, 237, 243, 255))
    image.save(path, format="PNG", optimize=True)


def _write_custom_logo(path: Path, content: bytes) -> None:
    if len(content) > 5 * 1024 * 1024:
        raise ValueError("Custom logo images must be 5 MiB or smaller.")
    try:
        with Image.open(BytesIO(content)) as source:
            if source.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Custom logo must be a PNG, JPEG, or WebP image.")
            if source.width * source.height > 16_000_000:
                raise ValueError("Custom logo image dimensions are too large.")
            image = source.convert("RGBA")
            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            image.save(path, format="PNG", optimize=True)
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Custom logo image could not be read.") from exc


def load_latest_saved_playlist(build_root: Path) -> list[dict]:
    """Load the most recently built non-empty playlist for one-click rebuilds."""
    root = Path(build_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError("No saved Roku playlist is available. Load a playlist in the Builder first.")

    candidates = []
    for project_dir in root.iterdir():
        if project_dir.is_symlink() or not project_dir.is_dir():
            continue
        data_dir = project_dir / "data"
        if data_dir.is_symlink():
            continue
        playlist_path = data_dir / "channels.json"
        index_path = data_dir / "channels_index.json"
        if index_path.is_symlink() or (not index_path.is_file() and playlist_path.is_symlink()):
            continue
        resolved_data_dir = data_dir.resolve()
        if project_dir.resolve().parent != root or resolved_data_dir.parent != project_dir.resolve():
            continue
        source_path = index_path if index_path.is_file() else playlist_path
        if source_path.is_file() and source_path.stat().st_size:
            candidates.append((source_path.stat().st_mtime_ns, project_dir, source_path))

    for _, project_dir, source_path in sorted(candidates, reverse=True):
        try:
            playlist_data = json.loads(source_path.read_text(encoding="utf-8"))
            if source_path.name == "channels_index.json":
                shard_names = playlist_data.get("shards") if isinstance(playlist_data, dict) else None
                if not isinstance(shard_names, list) or not shard_names:
                    continue
                playlist_data = []
                for shard_name in shard_names:
                    if not isinstance(shard_name, str) or not re.fullmatch(r"channels_[0-9]{4}\.json", shard_name):
                        playlist_data = []
                        break
                    shard_path = project_dir / "data" / shard_name
                    if shard_path.is_symlink() or shard_path.resolve().parent != (project_dir / "data").resolve():
                        playlist_data = []
                        break
                    shard_items = json.loads(shard_path.read_text(encoding="utf-8"))
                    if not isinstance(shard_items, list):
                        playlist_data = []
                        break
                    playlist_data.extend(shard_items)
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(playlist_data, list):
            continue
        from core.roku_playlist import parse_json_playlist

        entries = parse_json_playlist(playlist_data)
        if entries:
            return entries
    raise FileNotFoundError(
        "No non-empty saved Roku playlist was found. Load a playlist and build it once before using this button."
    )


def build_roku_project(project_dir: Path, config: dict, entries: list[dict]) -> Path:
    name = _safe_manifest_text(config.get("channel_name"), "Channel name")
    logo_text = str(config.get("logo_text") or "JBTV").strip().upper()
    if not re.fullmatch(r"[A-Z0-9-]{1,8}", logo_text):
        raise ValueError("Logo text must contain 1 to 8 letters, numbers, or hyphens.")
    logo_color_name = str(config.get("logo_color") or "green").strip().lower()
    if logo_color_name not in ROKU_LOGO_COLORS:
        raise ValueError("Choose one of the supported Roku logo colors.")
    collection_order = config.get("collection_order")
    if collection_order is not None:
        if not isinstance(collection_order, (list, tuple)):
            raise ValueError("Collection order must be a list of Roku smart collections.")
        if any(item not in ROKU_COLLECTIONS for item in collection_order):
            raise ValueError("Collection order contains an unsupported Roku collection.")
        collection_order = list(dict.fromkeys(collection_order))
    bundle_id = str(config.get("bundle_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9]+(?:\.[A-Za-z0-9_-]+){1,4}", bundle_id):
        raise ValueError("Bundle ID must use reverse-domain style, such as com.example.channel.")
    render_url = _validate_render_url(config.get("render_url", ""))
    web_app_url = _validate_web_app_url(config.get("web_app_url", ""))
    guide_api_url = str(config.get("guide_api_url") or "").strip()
    if guide_api_url and not guide_api_url.startswith(("http://", "https://")):
        raise ValueError("Live guide API URL must start with HTTP or HTTPS.")
    custom_logo = config.get("logo_image_bytes")
    theme = str(config.get("theme") or "dark").lower()
    if theme not in {"dark", "light", "sport"}:
        raise ValueError("Choose one of the supported Roku themes.")
    if not isinstance(entries, list) or not any(
        isinstance(entry, dict) and isinstance(entry.get("url"), str) and entry["url"].strip()
        for entry in entries
    ):
        raise ValueError("Roku package requires at least one playable playlist channel.")

    project_dir.mkdir(parents=True, exist_ok=False)
    for directory in ("source", "components", "images"):
        source = ROKU_ROOT / directory
        if not source.is_dir():
            raise FileNotFoundError(f"Required Roku app template directory is missing: {source}")
        shutil.copytree(source, project_dir / directory)
    _write_roku_logo(
        project_dir / "images" / "icon_focus_hd.png",
        (336, 210),
        logo_text,
        ROKU_LOGO_COLORS[logo_color_name],
    )
    _write_roku_logo(
        project_dir / "images" / "icon_side_hd.png",
        (108, 69),
        logo_text,
        ROKU_LOGO_COLORS[logo_color_name],
    )
    if custom_logo:
        if not isinstance(custom_logo, bytes):
            raise ValueError("Custom logo image data must be bytes.")
        _write_custom_logo(project_dir / "images" / "custom_logo.png", custom_logo)

    data_dir = project_dir / "data"
    data_dir.mkdir()
    shard_names = []
    for shard_index, offset in enumerate(range(0, len(entries), ROKU_PLAYLIST_SHARD_SIZE)):
        shard_name = f"channels_{shard_index:04d}.json"
        shard_entries = entries[offset:offset + ROKU_PLAYLIST_SHARD_SIZE]
        (data_dir / shard_name).write_text(
            json.dumps(shard_entries, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        shard_names.append(shard_name)
    (data_dir / "channels_index.json").write_text(
        json.dumps({"shards": shard_names, "count": len(entries)}, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (data_dir / "app_config.json").write_text(
        json.dumps({
            "channel_name": name,
            "bundle_id": bundle_id,
            "theme": theme,
            "render_url": render_url,
            "web_app_url": web_app_url,
            "guide_api_url": guide_api_url,
            "custom_logo": bool(custom_logo),
            "logo_text": logo_text,
            "logo_color": logo_color_name,
            "collection_order": collection_order,
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    (project_dir / "manifest").write_text(
        "\n".join([
            f"title={name}",
            "major_version=1",
            "minor_version=0",
            "build_version=00001",
            "mm_icon_focus_hd=pkg:/images/icon_focus_hd.png",
            "mm_icon_side_hd=pkg:/images/icon_side_hd.png",
            "splash_screen_hd=pkg:/images/splash_hd.png",
            "splash_color=#0d1117",
            "splash_min_time=1000",
            "ui_resolutions=hd",
            "requires_audiometadata=0",
            "",
        ]),
        encoding="utf-8",
    )
    (project_dir / "README.md").write_text(
        f"# {name} Roku app\n\n"
        f"- Playlist entries: {len(entries):,}\n"
        f"- Categories: {len({item.get('group') for item in entries}):,}\n"
        f"- Theme: {theme}\n"
        f"- MasterChief Render connection: {'configured' if render_url else 'not configured'}\n\n"
        "The package contains a native Roku SceneGraph player and the complete normalized playlist split into small JSON shards for reliable loading on Roku devices.\n"
        "The channel icon text and accent color are configurable in the Builder; curated sidebar collections can be reordered or hidden without removing the provider playlist categories.\n"
        "The Roku browser caches searchable metadata and per-category channel indexes at load time so searches and category counts avoid reprocessing the full playlist.\n"
        "Search also uses a three-character title/metadata prefix index to narrow typical queries; the left sidebar includes Web Tools Links, sports collections, XXX, Jackie Chan Films, Transporter, Two and a Half Men, Batman, The Big Bang Theory, Curb Your Enthusiasm, BBC Earth, 24/7 Channels, HBO, CINEMAX, SHOWTIME, STARZ, NETFLIX, News Channels, and Series.\n"
        "Roku cannot run HTML or JavaScript pages. Web Tools Links lists the MasterChief pages to open in a browser on another device; configure a URL reachable from the Roku to show complete links.\n"
        "The About Me screen identifies the Roku edition and notes that server-backed features remain in the MasterChief web app; JOEY BALLZ appears at the bottom of that screen.\n"
        "Original non-empty provider group-title labels are kept as separate Roku categories rather than merged into generic genres.\n"
        "When EXTINF does not provide a group-title, categories are inferred from provider path folders such as movie, series, and live.\n"
        "Leading numeric labels such as '24/7 X-MEN' are displayed as category '24/7' and title 'X-MEN' when no explicit group-title is supplied.\n"
        "The Roku browser opens on All Channels, with About Me, Search, Favorites, and the configured smart collections in the sidebar.\n"
        "Choose Search channels in the category list to open Roku's on-screen keyboard. Press OK on a category to play its first channel, or press Right to browse individual channels.\n"
        "Press * for search, All Channels, Favorites, favorite management, and the dashboard; press Play to toggle a channel favorite.\n"
        "Favorites are saved in Roku storage. Channel details include available EXTINF metadata.\n"
        "HLS/M3U8 and MPEG-TS (mp2ts) are detected and the player retries the alternate HLS/TS format after a playback error. A recognized container does not guarantee its audio/video codecs are supported by every Roku model.\n"
        "Enable Roku Developer Mode, upload this ZIP through the Roku Developer web page, and install it.\n"
        "The channel loads only streams you supplied; confirm you have rights to use each stream.\n",
        encoding="utf-8",
    )
    archive_path = project_dir / f"{project_dir.name}.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(project_dir.rglob("*")):
            if path.is_file() and path != archive_path:
                archive.write(path, arcname=str(path.relative_to(project_dir)))
    return archive_path

from __future__ import annotations

import ipaddress
import hashlib
import re
from pathlib import Path
import time
from urllib.parse import urlsplit

import requests
from flask import Blueprint, current_app, jsonify, request, send_file
from werkzeug.utils import secure_filename

from core.roku_settings import get_roku_settings, set_roku_enabled
from core.roku_epg import MAX_XMLTV_BYTES, load_guide_source, parse_xmltv_listings


roku_bp = Blueprint("roku_tools", __name__)
_GUIDE_CACHE = {}
_GUIDE_CACHE_TTL_SECONDS = 15 * 60


def _admin_response():
    if getattr(current_app, "login_manager", None) is None:
        return jsonify({
            "ok": False,
            "error": "RBAC authentication is unavailable; Roku administration is disabled.",
        }), 503

    from flask_login import current_user

    if not current_user.is_authenticated:
        return jsonify({"ok": False, "error": "Sign in is required."}), 401
    permissions = getattr(current_user, "permissions", [])
    if "*" not in permissions and "rbac" not in permissions:
        return jsonify({"ok": False, "error": "Roku administration requires RBAC administrator permission."}), 403
    return None


@roku_bp.route("/api/roku/settings", methods=["GET", "POST"])
def api_roku_settings():
    denied = _admin_response()
    if denied:
        return denied
    if request.method == "GET":
        try:
            return jsonify({"ok": True, "settings": get_roku_settings()})
        except (OSError, ValueError) as exc:
            current_app.logger.exception("Could not load Roku feature settings")
            return jsonify({"ok": False, "error": str(exc)}), 500

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("enabled"), bool):
        return jsonify({"ok": False, "error": "Provide enabled as a boolean."}), 400
    try:
        settings = set_roku_enabled(payload["enabled"])
    except OSError as exc:
        current_app.logger.exception("Could not save Roku feature settings")
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True, "settings": settings})


@roku_bp.route("/api/roku/download/<slug>", methods=["GET"])
def api_roku_download(slug):
    denied = _admin_response()
    if denied:
        return denied
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        return jsonify({"ok": False, "error": "Invalid project name."}), 400
    root = Path(current_app.root_path).resolve() / "data" / "roku_builds"
    package = (root / slug / f"{slug}.zip").resolve()
    if root not in package.parents or not package.is_file():
        return jsonify({"ok": False, "error": "Roku project package was not found."}), 404
    return send_file(package, as_attachment=True, download_name=f"{slug}.zip", mimetype="application/zip")


@roku_bp.route("/api/roku/guide/<token>", methods=["GET"])
def api_roku_guide(token):
    """Return current/next listings to the packaged Roku app using its private token."""
    source = load_guide_source(Path(current_app.root_path) / "data" / "roku_guides", token)
    if source is None:
        return jsonify({"ok": False, "error": "Roku guide token is invalid or expired."}), 404
    cache_key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    cached = _GUIDE_CACHE.get(cache_key)
    if cached and cached[0] > time.monotonic():
        return jsonify({"ok": True, "updated_at": cached[1], "programmes": cached[2]})

    try:
        parsed = urlsplit(source)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return jsonify({"ok": False, "error": "The configured XMLTV guide URL is invalid."}), 400
        with requests.get(
            source,
            headers={"User-Agent": "MasterChief-Roku/1.0", "Accept": "application/xml,text/xml,*/*"},
            timeout=(5, 45),
            allow_redirects=True,
            stream=True,
            verify=True,
        ) as response:
            response.raise_for_status()
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_XMLTV_BYTES:
                return jsonify({"ok": False, "error": "XMLTV guide exceeds the 50 MiB limit."}), 413
            chunks = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_XMLTV_BYTES:
                    return jsonify({"ok": False, "error": "XMLTV guide exceeds the 50 MiB limit."}), 413
                chunks.append(chunk)
        programmes = parse_xmltv_listings(b"".join(chunks))
    except requests.RequestException as exc:
        current_app.logger.warning("Could not fetch Roku XMLTV guide (%s)", type(exc).__name__)
        return jsonify({"ok": False, "error": "Could not refresh the XMLTV guide. Check its URL and server connection."}), 502
    except (ValueError, OSError) as exc:
        current_app.logger.warning("Could not parse Roku XMLTV guide (%s)", type(exc).__name__)
        return jsonify({"ok": False, "error": str(exc)}), 502

    updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _GUIDE_CACHE[cache_key] = (
        time.monotonic() + _GUIDE_CACHE_TTL_SECONDS,
        updated_at,
        programmes,
    )
    return jsonify({"ok": True, "updated_at": updated_at, "programmes": programmes})


@roku_bp.route("/api/roku/deploy", methods=["POST"])
def api_roku_deploy():
    denied = _admin_response()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "A deployment request object is required."}), 400
    try:
        if not get_roku_settings()["enabled"]:
            return jsonify({"ok": False, "error": "The private Roku feature is switched off."}), 409
    except (OSError, ValueError) as exc:
        current_app.logger.exception("Could not read Roku feature settings")
        return jsonify({"ok": False, "error": str(exc)}), 500

    slug = str(payload.get("slug") or "")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        return jsonify({"ok": False, "error": "Invalid project name."}), 400
    password = payload.get("password")
    if not isinstance(password, str) or not password:
        return jsonify({"ok": False, "error": "Enter the Roku Developer Mode password for this install."}), 400

    host = str(payload.get("device") or "").strip()
    parsed = urlsplit(host if "://" in host else f"http://{host}")
    if parsed.scheme != "http" or parsed.path not in ("", "/") or parsed.username or parsed.password:
        return jsonify({"ok": False, "error": "Enter the Roku device's private IPv4 address, optionally followed by a port."}), 400
    try:
        address = ipaddress.ip_address(parsed.hostname or "")
        port = parsed.port or 80
    except ValueError:
        return jsonify({"ok": False, "error": "Roku address or port is invalid."}), 400
    if address.version != 4 or not address.is_private or address.is_loopback or address.is_link_local or not 1 <= port <= 65535:
        return jsonify({"ok": False, "error": "Deployment is restricted to a private IPv4 Roku device on your LAN."}), 400

    root = Path(current_app.root_path).resolve() / "data" / "roku_builds"
    package = (root / slug / f"{slug}.zip").resolve()
    if root not in package.parents or not package.is_file():
        return jsonify({"ok": False, "error": "Build the Roku app package before deploying."}), 404
    try:
        with package.open("rb") as archive:
            with requests.Session() as session:
                session.trust_env = False
                response = session.post(
                    f"http://{address}:{port}/plugin_install",
                    auth=("rokudev", password),
                    files={"archive": (package.name, archive, "application/zip")},
                    timeout=(5, 90),
                    allow_redirects=False,
                )
    except requests.Timeout as exc:
        current_app.logger.warning("Roku install timed out for device %s:%s (%s)", address, port, type(exc).__name__)
        return jsonify({
            "ok": False,
            "error": "The Roku install timed out while waiting for the device. Confirm the Roku is awake on the same LAN and try again.",
        }), 504
    except requests.ConnectionError as exc:
        current_app.logger.warning("Could not connect to Roku device %s:%s (%s)", address, port, type(exc).__name__)
        detail = re.sub(r"\s+", " ", str(exc)).strip()[:240]
        return jsonify({
            "ok": False,
            "error": "Could not reach Roku Developer Mode. Confirm the device IP, same Wi-Fi/LAN, Developer Mode, and that the server is not isolated from the Roku."
                    + (f" Network detail: {detail}" if detail else ""),
        }), 502
    except requests.RequestException as exc:
        current_app.logger.exception("Roku device deployment request failed")
        detail = re.sub(r"\s+", " ", str(exc)).strip()[:240]
        return jsonify({
            "ok": False,
            "error": "Roku Developer Mode request failed."
                    + (f" Request detail: {detail}" if detail else ""),
        }), 502
    if response.status_code in (401, 403):
        return jsonify({
            "ok": False,
            "error": "Roku rejected the Developer Mode credentials. Recheck the device IP and the Developer Mode password.",
        }), 502
    if response.status_code not in (200, 201, 302, 303):
        detail = re.sub(r"\s+", " ", response.text or "").strip()[:240]
        return jsonify({
            "ok": False,
            "error": f"Roku Developer Mode rejected the package (HTTP {response.status_code})."
                    + (f" Roku response: {detail}" if detail else " Check the package size, device storage, and Developer Mode status."),
        }), 502
    return jsonify({
        "ok": True,
        "message": "Package uploaded to the Roku device. Check the TV for the install confirmation.",
        "http_status": response.status_code,
    })

"""Mail & Calendar: read-only IMAP inbox and ICS calendar feeds (Gmail, Yahoo, any IMAP provider)."""

from __future__ import annotations

import email
import imaplib
import ipaddress
import json
import re
import socket
import uuid
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit

import requests
from flask import Blueprint, abort, jsonify, request

mailcal_bp = Blueprint("mailcal", __name__)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "mailcal_accounts.json"
PAGE_FILE = Path(__file__).resolve().parent.parent / "mail_calendar.html"
PROVIDERS = {
    "gmail": "imap.gmail.com",
    "yahoo": "imap.mail.yahoo.com",
    "outlook": "outlook.office365.com",
    "icloud": "imap.mail.me.com",
    "custom": "",
}
HOST_RE = re.compile(r"^[A-Za-z0-9.-]{1,253}$")
TIMEOUT = 20

try:
    from auth_module import requires_permission
except ImportError:
    from functools import wraps

    def requires_permission(_permission):
        def decorator(func):
            @wraps(func)
            def unavailable(*args, **kwargs):
                abort(503, description="Authentication is unavailable.")
            return unavailable
        return decorator


def _load() -> list[dict]:
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save(accounts: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(accounts, indent=2), encoding="utf-8")


def _public(acct: dict) -> dict:
    return {k: v for k, v in acct.items() if k != "password"}


def _find(account_id: str) -> dict:
    for acct in _load():
        if acct["id"] == account_id:
            return acct
    abort(404, description="Account not found")


def _safe_https_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Calendar URL must be an https URL without credentials")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve {parts.hostname}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("Calendar URL must point to a public host")
    return url.strip()


def _dh(value) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def _imap(acct: dict) -> imaplib.IMAP4_SSL:
    conn = imaplib.IMAP4_SSL(acct["imap_host"], 993, timeout=TIMEOUT)
    conn.login(acct["email"], acct["password"])
    return conn


def _body(msg) -> str:
    plain, html = "", ""
    for part in msg.walk():
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True) or b""
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if ctype == "text/plain" and not plain:
            plain = text
        elif ctype == "text/html" and not html:
            html = text
    if plain:
        return plain
    html = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    return unescape(re.sub(r"<[^>]+>", " ", html))


@mailcal_bp.get("/mail-calendar")
@requires_permission("scripts")
def page():
    return PAGE_FILE.read_text(encoding="utf-8")


@mailcal_bp.get("/api/mailcal/accounts")
@requires_permission("scripts")
def list_accounts():
    return jsonify({"accounts": [_public(a) for a in _load()], "providers": PROVIDERS})


@mailcal_bp.post("/api/mailcal/accounts")
@requires_permission("scripts")
def add_account():
    data = request.get_json(silent=True) or {}
    provider = data.get("provider", "custom")
    addr = str(data.get("email", "")).strip()
    password = str(data.get("password", ""))
    host = str(data.get("imap_host") or PROVIDERS.get(provider, "")).strip()
    if provider not in PROVIDERS or not re.match(r"^[^@\s]+@[^@\s]+$", addr) or not password or not HOST_RE.match(host):
        return jsonify({"error": "Provider, a valid email, an app password and an IMAP host are required"}), 400
    calendars = []
    for item in data.get("calendars") or []:
        url = str(item.get("url", "")).strip()
        if not url:
            continue
        try:
            calendars.append({"name": str(item.get("name") or "Calendar")[:60], "url": _safe_https_url(url)})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    acct = {"id": uuid.uuid4().hex[:10], "label": str(data.get("label") or addr)[:60], "provider": provider,
            "email": addr, "password": password, "imap_host": host, "calendars": calendars}
    try:
        conn = _imap(acct)
        conn.logout()
    except (imaplib.IMAP4.error, OSError) as exc:
        return jsonify({"error": f"Login failed: {exc}. Use an app password, not your normal password."}), 400
    accounts = _load()
    accounts.append(acct)
    _save(accounts)
    return jsonify({"account": _public(acct)}), 201


@mailcal_bp.delete("/api/mailcal/accounts/<account_id>")
@requires_permission("scripts")
def delete_account(account_id: str):
    accounts = _load()
    kept = [a for a in accounts if a["id"] != account_id]
    if len(kept) == len(accounts):
        abort(404)
    _save(kept)
    return jsonify({"success": True})


@mailcal_bp.get("/api/mailcal/accounts/<account_id>/inbox")
@requires_permission("scripts")
def inbox(account_id: str):
    acct = _find(account_id)
    limit = min(max(request.args.get("limit", 25, type=int), 1), 100)
    try:
        conn = _imap(acct)
        conn.select("INBOX", readonly=True)
        _, data = conn.uid("search", None, "ALL")
        uids = data[0].split()[-limit:][::-1]
        items = []
        for uid in uids:
            _, parts = conn.uid("fetch", uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            raw = next((p[1] for p in parts if isinstance(p, tuple)), b"")
            flags = next((p[0] for p in parts if isinstance(p, tuple)), b"")
            msg = email.message_from_bytes(raw)
            items.append({"uid": uid.decode(), "from": _dh(msg["From"]), "subject": _dh(msg["Subject"]) or "(no subject)",
                          "date": _dh(msg["Date"]), "unread": b"\\Seen" not in flags})
        conn.logout()
    except (imaplib.IMAP4.error, OSError) as exc:
        return jsonify({"error": f"Mailbox error: {exc}"}), 502
    return jsonify({"messages": items})


@mailcal_bp.get("/api/mailcal/accounts/<account_id>/message/<uid>")
@requires_permission("scripts")
def message(account_id: str, uid: str):
    if not uid.isdigit():
        abort(400)
    acct = _find(account_id)
    try:
        conn = _imap(acct)
        conn.select("INBOX", readonly=True)
        _, parts = conn.uid("fetch", uid, "(BODY.PEEK[])")
        raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
        conn.logout()
    except (imaplib.IMAP4.error, OSError) as exc:
        return jsonify({"error": f"Mailbox error: {exc}"}), 502
    if raw is None:
        abort(404)
    msg = email.message_from_bytes(raw)
    return jsonify({"from": _dh(msg["From"]), "to": _dh(msg["To"]), "subject": _dh(msg["Subject"]),
                    "date": _dh(msg["Date"]), "body": _body(msg)[:20000]})


def _unfold(text: str) -> list[str]:
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def _parse_dt(value: str, params: str):
    value = value.strip()
    if "VALUE=DATE" in params or re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value[:8], "%Y%m%d").replace(tzinfo=timezone.utc), True
    dt = datetime.strptime(value.rstrip("Z"), "%Y%m%dT%H%M%S")
    return dt.replace(tzinfo=timezone.utc), False


def _events(ics: str, start: datetime, end: datetime, calendar: str) -> list[dict]:
    try:
        from dateutil.rrule import rrulestr
    except ImportError:
        rrulestr = None
    out, cur = [], None
    for line in _unfold(ics):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT" and cur is not None:
            cur_event, cur = cur, None
            if "DTSTART" not in cur_event:
                continue
            try:
                s, all_day = _parse_dt(*cur_event["DTSTART"])
                e = _parse_dt(*cur_event["DTEND"])[0] if "DTEND" in cur_event else s
            except ValueError:
                continue
            length = e - s
            starts = [s]
            if "RRULE" in cur_event and rrulestr:
                try:
                    rule = rrulestr(cur_event["RRULE"][0], dtstart=s.replace(tzinfo=None))
                    starts = [d.replace(tzinfo=timezone.utc) for d in rule.between(start.replace(tzinfo=None) - length, end.replace(tzinfo=None), inc=True)]
                except (ValueError, TypeError):
                    pass
            for st in starts:
                if st + length >= start and st <= end:
                    out.append({"title": cur_event.get("SUMMARY", ("", ""))[0].replace("\\,", ",").replace("\\n", " ") or "(untitled)",
                                "start": st.isoformat(), "end": (st + length).isoformat(), "all_day": all_day,
                                "location": cur_event.get("LOCATION", ("", ""))[0].replace("\\,", ","), "calendar": calendar})
        elif cur is not None and ":" in line:
            key, _, val = line.partition(":")
            name, _, params = key.partition(";")
            cur[name.upper()] = (val, params.upper())
    return out


@mailcal_bp.get("/api/mailcal/calendar")
@requires_permission("scripts")
def calendar():
    days = min(max(request.args.get("days", 14, type=int), 1), 90)
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = now + timedelta(days=days)
    events, errors = [], []
    for acct in _load():
        for cal in acct.get("calendars", []):
            label = f"{acct['label']}: {cal['name']}"
            try:
                url = _safe_https_url(cal["url"])
                resp = requests.get(url, timeout=TIMEOUT, allow_redirects=False)
                resp.raise_for_status()
                events.extend(_events(resp.text, now, end, label))
            except (requests.RequestException, ValueError) as exc:
                errors.append(f"{label}: {exc}")
    events.sort(key=lambda ev: ev["start"])
    return jsonify({"events": events, "errors": errors})

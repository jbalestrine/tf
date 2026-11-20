"""Local, review-first Gmail recruiter response queue."""

import hashlib
import imaplib
import io
import json
import os
import re
import smtplib
import ssl
import threading
import uuid
from datetime import datetime, timedelta, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, make_msgid, parseaddr
from html.parser import HTMLParser
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import build_resumes
import profile_store
import studio_tools

BASE = Path(__file__).resolve().parent
STATE = BASE / "processed_emails.json"
LOCK = threading.RLock()
router = APIRouter(prefix="/api/email")
DEFAULT_KEYWORDS = "architect,devops,cloud architect,platform engineer,sre"
EXEC = "Joseph_Balestrine_Executive_2Page.docx"
PDF = "Joseph_Balestrine_Architect_Portfolio.pdf"
MASTER = "Joseph_Balestrine_DevOps_Architect_Master.docx"


class Approval(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    role_title: str = Field(min_length=1, max_length=200)


class AutoMode(BaseModel):
    enabled: bool


class ScanOptions(BaseModel):
    keywords: str | None = Field(default=None, max_length=1000)
    all_unread: bool = False


class ManualReply(BaseModel):
    body: str = Field(min_length=1, max_length=20000)
    attachments: list[str] = Field(default_factory=list, max_length=20)


class ReplyTemplate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=20000)
    attachments: list[str] = Field(default_factory=list, max_length=20)


def configuration():
    settings = {}
    path = BASE / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                settings[key.strip()] = value.strip().strip("\"'")
    for key in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "EMAIL_KEYWORDS", "EMAIL_AUTO_SEND"):
        if key in os.environ:
            settings[key] = os.environ[key]
    return settings


def state_read():
    if not STATE.exists():
        return {"messages": [], "auto_send": None}
    state = json.loads(STATE.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or not isinstance(state.get("messages"), list):
        raise ValueError("Invalid email agent state.")
    return state


def state_write(state):
    tmp = STATE.with_name(f".{STATE.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("x", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=2)
        tmp.replace(STATE)
    finally:
        if tmp.exists():
            tmp.unlink()


def auto_enabled(state, config):
    if state.get("auto_send") is not None:
        return state["auto_send"] is True
    return config.get("EMAIL_AUTO_SEND", "false").strip().lower() == "true"


def credentials(config):
    address = config.get("GMAIL_ADDRESS", "").strip()
    password = config.get("GMAIL_APP_PASSWORD", "").strip()
    if not address or not password or parseaddr(address)[1] != address or "@" not in address:
        raise ValueError("Configure GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env or the environment.")
    return address, password


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chunks = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.hidden += 1
        elif tag in ("p", "div", "br", "li", "tr"):
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self.hidden:
            self.hidden -= 1
        elif tag in ("p", "div", "li", "tr"):
            self.chunks.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.chunks.append(data)


def plain_body(message):
    parts = message.walk() if message.is_multipart() else (message,)
    chunks, html_chunks = [], []
    for part in parts:
        if part.get_content_type() in ("text/plain", "text/html") and part.get_content_disposition() != "attachment":
            try:
                text = part.get_content()
            except (LookupError, UnicodeError):
                text = part.get_payload(decode=True).decode("utf-8", errors="replace")
            if isinstance(text, str):
                if part.get_content_type() == "text/plain":
                    chunks.append(text)
                else:
                    parser = TextExtractor()
                    parser.feed(text)
                    html_chunks.append("".join(parser.chunks))
    if not chunks:
        chunks = html_chunks
    return "\n".join(chunks)[:100000]


def candidate(message, address, keywords, all_unread=False):
    sender_name, sender = parseaddr(message.get("From", ""))
    sender = sender.strip().lower()
    if (not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", sender)
            or sender == address.lower() or re.search(r"no[-_.]?reply|mailer[-_.]?daemon", sender, re.I)
            or message.get("List-Unsubscribe")
            or message.get("Auto-Submitted", "no").strip().lower() != "no"
            or message.get("Precedence", "").strip().lower() in ("bulk", "list", "junk")
            or len(getaddresses(message.get_all("From", []))) != 1):
        return None
    message_id = str(message.get("Message-ID", "")).strip()
    if not re.fullmatch(r"<[^<>\s@]+@[^<>\s@]+>", message_id):
        return None
    subject = str(message.get("Subject", ""))[:500]
    body = plain_body(message)
    if not all_unread and not any(word in (subject + "\n" + body).casefold() for word in keywords):
        return None
    company_match = re.search(r"(?im)^\s*company\s*:\s*([^\r\n]{1,120})", body)
    role_match = re.search(r"(?im)^\s*(?:role|position|job title)\s*:\s*([^\r\n]{1,150})", body)
    return {"id": hashlib.sha256(message_id.encode()).hexdigest(), "message_id": message_id,
            "sender": sender, "sender_name": sender_name[:200], "subject": subject,
            "company": company_match.group(1).strip() if company_match else "",
            "role_title": role_match.group(1).strip() if role_match else "",
            "snippet": re.sub(r"\s+", " ", body).strip()[:600], "status": "queued",
            "received_at": datetime.now(timezone.utc).isoformat()}


def within_cooldown(state, sender, current_id=None):
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    for item in state["messages"]:
        if item.get("sender") == sender and item.get("id") != current_id and item.get("status") in ("sending", "sent", "uncertain"):
            if datetime.fromisoformat(item["attempted_at"]) >= cutoff:
                return True
    return False


def load_item(state, item_id):
    item = next((entry for entry in state["messages"] if entry["id"] == item_id), None)
    if item is None:
        raise HTTPException(404, "Email not found.")
    return item


def send(item_id, company, role, auto=False):
    company, role = company.strip(), role.strip()
    if not company or not role or "\n" in company + role or "\r" in company + role:
        raise ValueError("Company and role are required and must be single-line text.")
    with LOCK:
        state = state_read()
        item = load_item(state, item_id)
        if item["status"] != "queued":
            raise ValueError("This message is no longer awaiting approval.")
        if within_cooldown(state, item["sender"], item_id):
            raise ValueError("A reply to this sender was sent or attempted within 30 days.")
        config = configuration()
        address, password = credentials(config)
        if auto and not auto_enabled(state, config):
            raise ValueError("Auto-send is disabled.")
        if "architect" in role.casefold():
            files = [EXEC, PDF]
        elif re.search(r"\b(devops|sre|platform engineer)\b", role, re.I):
            files = [MASTER]
        else:
            raise ValueError("Role must identify an architect, DevOps, SRE, or platform engineer to select attachments.")
        with profile_store.LOCK:
            data = yaml.safe_load(profile_store.RESUME.read_text(encoding="utf-8"))
            profile_store.validate(yaml.safe_dump(data, allow_unicode=True))
        contents = []
        for filename in files:
            output = io.BytesIO()
            if filename == PDF:
                build_resumes.build_pdf(data, BASE / "template_v2.html", output)
            else:
                build_resumes.build_docx(data, "exec" if filename == EXEC else "master", output)
            contents.append((filename, output.getvalue()))
        cover = io.BytesIO()
        build_resumes.build_cover_letter(data, company, role, cover)
        outgoing = EmailMessage()
        outgoing["From"] = address
        outgoing["To"] = item["sender"]
        outgoing["Subject"] = "Re: " + re.sub(r"(?i)^re:\s*", "", item["subject"])
        outgoing["In-Reply-To"] = item["message_id"]
        outgoing["References"] = item["message_id"]
        outgoing["Message-ID"] = make_msgid()
        outgoing.set_content(f"Hello {item['sender_name'] or 'there'},\n\nThank you for reaching out. "
                             f"Please find my resume and cover letter attached for the {role} opportunity at {company}.\n\n"
                             f"Best regards,\n{data['profile']['name']}")
        for filename, content in contents:
            subtype = "pdf" if filename.endswith(".pdf") else "vnd.openxmlformats-officedocument.wordprocessingml.document"
            outgoing.add_attachment(content, maintype="application", subtype=subtype, filename=filename)
        outgoing.add_attachment(cover.getvalue(), maintype="application",
                                subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
                                filename="Cover_Letter.docx")
        item.update(status="sending", attempted_at=datetime.now(timezone.utc).isoformat(),
                    company=company, role_title=role, automatic=auto, attachments=files,
                    outgoing_message_id=outgoing["Message-ID"])
        state_write(state)
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(address, password)
                smtp.send_message(outgoing)
        except (OSError, smtplib.SMTPException):
            item["status"] = "uncertain"
            state_write(state)
            raise ValueError("Delivery could not be confirmed. Check Gmail Sent before taking further action; automatic retry is disabled.")
        item["status"] = "sent"
        item["sent_at"] = datetime.now(timezone.utc).isoformat()
        item["crm_status"] = "pending"
        state_write(state)
        try:
            studio_tools.add_submission(studio_tools.Submission(
                company=company, role_title=role, recruiter_name=item["sender_name"],
                resume_version=", ".join(files), date=datetime.now().date(), status="Submitted",
                notes=f"Email reply to {item['sender']} (message {item['message_id']})."))
        except (OSError, ValueError):
            raise ValueError("Email was sent, but CRM logging failed. Add it to the CRM manually; do not resend.")
        item["crm_status"] = "logged"
        state_write(state)
        return item


@router.get("")
def status():
    with LOCK:
        state = state_read()
        config = configuration()
        try:
            attachments = available_attachments()
        except OSError as exc:
            raise HTTPException(500, "Could not read the Generated Artifacts directory.") from exc
        return {"auto_send": auto_enabled(state, config), "messages": state["messages"],
                "default_keywords": config.get("EMAIL_KEYWORDS", DEFAULT_KEYWORDS),
                "templates": state.get("reply_templates", []), "attachments": attachments}


def available_attachments():
    dist = BASE / "dist"
    if not dist.exists():
        return []
    return sorted(path.name for path in dist.iterdir()
                  if path.is_file() and not path.is_symlink() and path.suffix.lower() in (".pdf", ".docx"))


def attachment_contents(names):
    if len(set(names)) != len(names):
        raise ValueError("Duplicate attachments are not allowed.")
    try:
        return _attachment_contents(names)
    except OSError as exc:
        raise ValueError("Could not read a selected attachment. Check Generated Artifacts and try again.") from exc


def _attachment_contents(names):
    available = set(available_attachments())
    contents = []
    total = 0
    for name in names:
        if name not in available or Path(name).name != name or "/" in name or "\\" in name:
            raise ValueError(f"Attachment is unavailable: {name}")
        original = BASE / "dist" / name
        if original.is_symlink():
            raise ValueError(f"Attachment is unavailable: {name}")
        path = original.resolve()
        if path.parent != (BASE / "dist").resolve():
            raise ValueError("Invalid attachment path.")
        if path.stat().st_size > 15 * 1024 * 1024 - total:
            raise ValueError("Attachments exceed the 15 MB total limit.")
        data = path.read_bytes()
        total += len(data)
        if total > 15 * 1024 * 1024:
            raise ValueError("Attachments exceed the 15 MB total limit.")
        contents.append((name, data))
    return contents


@router.post("/templates")
def save_template(payload: ReplyTemplate):
    name, body = payload.name.strip(), payload.body.strip()
    if not name or not body or any(ch in name for ch in "/\\\r\n"):
        raise HTTPException(400, "Template name and message are required; names cannot contain slashes or line breaks.")
    try:
        attachment_contents(payload.attachments)
        with LOCK:
            state = state_read()
            templates = state.setdefault("reply_templates", [])
            if any(t["name"].casefold() == name.casefold() for t in templates):
                raise ValueError("A template with that name already exists.")
            if len(templates) >= 50:
                raise ValueError("At most 50 templates can be saved.")
            templates.append({"name": name, "body": body, "attachments": payload.attachments})
            state_write(state)
        return {"name": name}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/templates/{name}")
def delete_template(name: str):
    with LOCK:
        state = state_read()
        templates = state.get("reply_templates", [])
        remaining = [entry for entry in templates if entry["name"] != name]
        if len(remaining) == len(templates):
            raise HTTPException(404, "Template not found.")
        state["reply_templates"] = remaining
        state_write(state)
    return {"deleted": name}


@router.post("/reply/{item_id}")
def manual_reply(item_id: str, payload: ManualReply):
    body = payload.body.strip()
    if not body:
        raise HTTPException(400, "Reply text is required.")
    try:
        with LOCK:
            state = state_read()
            item = load_item(state, item_id)
            if item["status"] != "queued":
                raise ValueError("This message is no longer awaiting approval.")
            address, password = credentials(configuration())
            contents = attachment_contents(payload.attachments)
            outgoing = EmailMessage()
            outgoing["From"] = address
            outgoing["To"] = item["sender"]
            outgoing["Subject"] = "Re: " + re.sub(r"(?i)^re:\s*", "", item["subject"])
            outgoing["In-Reply-To"] = item["message_id"]
            outgoing["References"] = item["message_id"]
            outgoing["Message-ID"] = make_msgid()
            outgoing.set_content(body)
            for name, content in contents:
                maintype, subtype = ("application", "pdf") if name.lower().endswith(".pdf") else (
                    "application", "vnd.openxmlformats-officedocument.wordprocessingml.document")
                outgoing.add_attachment(content, maintype=maintype, subtype=subtype, filename=name)
            item.update(status="sending", attempted_at=datetime.now(timezone.utc).isoformat(),
                        automatic=False, attachments=payload.attachments,
                        outgoing_message_id=outgoing["Message-ID"])
            state_write(state)
            try:
                with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
                    smtp.ehlo()
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                    smtp.login(address, password)
                    smtp.send_message(outgoing)
            except (OSError, smtplib.SMTPException):
                item["status"] = "uncertain"
                state_write(state)
                raise ValueError("Delivery could not be confirmed. Check Gmail Sent before taking further action; automatic retry is disabled.")
            item.update(status="sent", sent_at=datetime.now(timezone.utc).isoformat(), crm_status="not logged")
            state_write(state)
            return item
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/mode")
def set_mode(payload: AutoMode):
    with LOCK:
        state = state_read()
        state["auto_send"] = payload.enabled
        state_write(state)
        return {"auto_send": payload.enabled}


def scan_inbox(options=None):
    with LOCK:
        options = options or ScanOptions()
        config = configuration()
        address, password = credentials(config)
        source = options.keywords if options.keywords is not None else config.get("EMAIL_KEYWORDS", DEFAULT_KEYWORDS)
        keywords = [k.strip().casefold() for k in source.split(",") if k.strip()]
        if not keywords and not options.all_unread:
            raise ValueError("EMAIL_KEYWORDS must contain at least one keyword.")
        state = state_read()
        known = {item["id"] for item in state["messages"]}
        added = []
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ssl.create_default_context(), timeout=30) as client:
                client.login(address, password)
                result, _ = client.select("INBOX", readonly=True)
                if result != "OK":
                    raise ValueError("Could not open Gmail INBOX.")
                result, uids = client.uid("search", None, "UNSEEN")
                if result != "OK":
                    raise ValueError("Could not search Gmail INBOX.")
                for uid in uids[0].split()[-200:]:
                    result, fetched = client.uid("fetch", uid, "(BODY.PEEK[])")
                    if result != "OK":
                        raise ValueError("Failed to fetch an unread Gmail message.")
                    raw = next((entry[1] for entry in fetched if isinstance(entry, tuple)), None)
                    if raw is None:
                        raise ValueError("Gmail returned an incomplete message.")
                    if len(raw) > 5 * 1024 * 1024:
                        continue
                    item = candidate(BytesParser(policy=policy.default).parsebytes(raw), address, keywords, options.all_unread)
                    if item and item["id"] not in known:
                        state["messages"].append(item)
                        known.add(item["id"])
                        added.append(item)
            state_write(state)
        except (OSError, imaplib.IMAP4.error) as exc:
            raise ValueError("Gmail scan failed. Check connection and app-password configuration.") from exc
        failures = []
        if options.keywords is None and not options.all_unread and auto_enabled(state, config):
            for item in added:
                if item["company"] and item["role_title"]:
                    try:
                        send(item["id"], item["company"], item["role_title"], auto=True)
                    except ValueError as exc:
                        failures.append({"id": item["id"], "detail": str(exc)})
        return {"added": len(added), "auto_send_errors": failures, "scan_limit": 200}


@router.post("/scan")
def scan(options: ScanOptions | None = None):
    try:
        return scan_inbox(options)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/approve/{item_id}")
def approve(item_id: str, payload: Approval):
    try:
        return send(item_id, payload.company, payload.role_title)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/dismiss/{item_id}")
def dismiss(item_id: str):
    with LOCK:
        state = state_read()
        item = load_item(state, item_id)
        if item["status"] != "queued":
            raise HTTPException(409, "Only queued messages can be dismissed.")
        item["status"] = "dismissed"
        state_write(state)
        return item

"""Profile persistence and conservative resume import."""

import io
import json
import re
import threading
import uuid
import zipfile
from pathlib import Path

import yaml
from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pydantic import BaseModel, ConfigDict, ValidationError

from techlearn_router import local_json_request

BASE = Path(__file__).resolve().parent
RESUME = BASE / "resume.yaml"
PROFILES = BASE / "profiles"
ACTIVE = PROFILES / ".active"
LOCK = threading.RLock()
TIERS = ["master", "exec", "slideedition", "pdf"]
MAX_UPLOAD = 5 * 1024 * 1024


class ExtraModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class Profile(ExtraModel):
    name: str
    titles: list[str]
    email: str
    phone: str
    linkedin: str
    location: str
    summary: str


class Bullet(ExtraModel):
    category: str
    text: str
    tiers: list[str]


class Skill(ExtraModel):
    category: str
    items: list[str]
    tiers: list[str]


class Experience(ExtraModel):
    role: str
    company: str
    location: str
    dates: str
    tiers: list[str]
    bullets: list[Bullet]


class MicrosoftBlock(ExtraModel):
    company: str
    location: str
    dates: str
    roles: list[str]
    bullets: list[Bullet]


class Metric(ExtraModel):
    value: str
    label: str


class Education(ExtraModel):
    credential: str
    institution: str
    year: str | int | None


class Earlier(ExtraModel):
    company: str
    dates: str
    text: str
    tiers: list[str]


class Cover(ExtraModel):
    opening: str
    body_1: str
    body_2: str
    closing: str


class Interview(ExtraModel):
    headlines: list[str]
    fabric_igca: list[str]
    questions: list[str]


class Resume(ExtraModel):
    profile: Profile
    skills: list[Skill]
    metrics: list[Metric]
    experience: list[Experience]
    microsoft_block: MicrosoftBlock
    earlier_experience: list[Earlier]
    education: list[Education]
    cover_letter: Cover
    interview_prep: Interview


def validate(raw):
    try:
        data = yaml.safe_load(raw)
        Resume.model_validate(data)
    except (yaml.YAMLError, ValidationError) as exc:
        raise ValueError(f"Resume does not match the builder schema: {exc}") from exc
    return data


def name_path(name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise ValueError("Profile names must contain only letters, digits, underscores, or hyphens.")
    if name.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise ValueError("This profile name is reserved.")
    path = PROFILES / f"{name}.yaml"
    if path.is_symlink() or path.resolve().parent != PROFILES.resolve():
        raise ValueError("Invalid profile path.")
    return path


def atomic_write(path, content):
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as file:
            file.write(content)
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def initialize():
    with LOCK:
        PROFILES.mkdir(exist_ok=True)
        if not ACTIVE.exists():
            default = name_path("default")
            if default.exists():
                raise ValueError("Profile state is missing but default.yaml already exists; restore .active manually.")
            current = RESUME.read_text(encoding="utf-8")
            validate(current)
            with default.open("x", encoding="utf-8") as file:
                file.write(current)
            atomic_write(ACTIVE, "default\n")
        active = ACTIVE.read_text(encoding="utf-8").strip()
        if not name_path(active).is_file():
            raise ValueError("Active profile is missing.")
        return active


def list_profiles():
    with LOCK:
        active = initialize()
        names = sorted((p.stem for p in PROFILES.glob("*.yaml") if p.is_file() and not p.is_symlink()), key=str.casefold)
        return {"active": active, "profiles": names}


def save_current(raw, expected=None):
    validate(raw)
    with LOCK:
        active = initialize()
        if expected is not None and active != expected:
            raise ValueError("Active profile changed in another session; reload before saving.")
        old = RESUME.read_text(encoding="utf-8")
        atomic_write(RESUME, raw)
        try:
            atomic_write(name_path(active), raw)
        except OSError:
            atomic_write(RESUME, old)
            raise


def switch(name, expected=None):
    with LOCK:
        active = initialize()
        if expected is not None and active != expected:
            raise ValueError("Active profile changed in another session; reload before switching.")
        target = name_path(name)
        if not target.is_file():
            raise FileNotFoundError("Profile not found.")
        new = target.read_text(encoding="utf-8")
        validate(new)
        old = RESUME.read_text(encoding="utf-8")
        validate(old)
        if name != active:
            atomic_write(name_path(active), old)
            atomic_write(RESUME, new)
            try:
                atomic_write(ACTIVE, name + "\n")
            except OSError:
                atomic_write(RESUME, old)
                raise
        return name


def create(name, raw, activate=False, expected=None):
    validate(raw)
    with LOCK:
        active = initialize()
        if expected is not None and active != expected:
            raise ValueError("Active profile changed in another session; reload first.")
        path = name_path(name)
        if any(p.stem.casefold() == name.casefold() for p in PROFILES.glob("*.yaml")):
            raise FileExistsError("A profile with that name already exists.")
        with path.open("x", encoding="utf-8") as file:
            file.write(raw)
        if activate:
            try:
                switch(name)
            except (OSError, ValueError):
                path.unlink()
                raise
        return name


def blank_resume():
    return {
        "profile": {k: "" for k in ("name", "email", "phone", "linkedin", "location", "summary", "eyebrow", "headline", "github")} | {"titles": []},
        "skills": [], "metrics": [], "experience": [],
        "microsoft_block": {"company": "", "location": "", "dates": "", "roles": [], "bullets": []},
        "earlier_experience": [], "education": [],
        "cover_letter": {k: "" for k in ("opening", "body_1", "body_2", "closing")},
        "interview_prep": {"headlines": [], "fabric_igca": [], "questions": []},
    }


def extract_text(filename, content):
    suffix = Path(filename).suffix.lower()
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if sum(info.file_size for info in archive.infolist()) > 25 * 1024 * 1024:
                    raise ValueError("DOCX contents exceed the size limit.")
            doc = Document(io.BytesIO(content))
            lines = []
            for block in doc.iter_inner_content():
                if hasattr(block, "text"):
                    lines.append(block.text)
                elif hasattr(block, "rows"):
                    lines.extend(" | ".join(cell.text for cell in row.cells) for row in block.rows)
            text = "\n".join(lines)
        except (zipfile.BadZipFile, PackageNotFoundError, KeyError) as exc:
            raise ValueError("Invalid DOCX file.") from exc
    elif suffix == ".pdf":
        try:
            pdf = PdfReader(io.BytesIO(content))
            if pdf.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported.")
            if len(pdf.pages) > 100:
                raise ValueError("PDF exceeds the 100-page limit.")
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except PdfReadError as exc:
            raise ValueError("Invalid PDF file.") from exc
    else:
        raise ValueError("Unsupported document type.")
    if not text.strip():
        raise ValueError("No text could be extracted. Scanned PDFs require OCR, which is not supported.")
    if len(text) > 500000:
        raise ValueError("Extracted text exceeds the size limit.")
    return text


def parse_document(text):
    data = blank_resume()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    data["profile"]["name"] = lines[0][:200] if lines else ""
    email = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    if email:
        data["profile"]["email"] = email.group()
    sections = {"summary": [], "skills": [], "experience": [], "education": []}
    section = None
    for line in lines[1:]:
        heading = re.sub(r"[^a-z ]", "", line.lower()).strip()
        mapping = {"summary": "summary", "professional summary": "summary", "executive summary": "summary",
                   "skills": "skills", "technical skills": "skills", "core competencies": "skills",
                   "experience": "experience", "professional experience": "experience", "work experience": "experience",
                   "education": "education", "education certifications": "education"}
        if heading in mapping:
            section = mapping[heading]
        elif section:
            sections[section].append(line)
    data["profile"]["summary"] = " ".join(sections["summary"])
    if sections["skills"]:
        data["skills"] = [{"category": "Imported skills", "items": sections["skills"], "tiers": TIERS.copy()}]
    jobs = []
    for line in sections["experience"]:
        pieces = [part.strip() for part in line.split("|")]
        if len(pieces) >= 3 and re.search(r"\b(?:19|20)\d{2}\b", pieces[-1]):
            jobs.append({"role": pieces[0], "company": pieces[1], "location": "",
                         "dates": pieces[-1], "tiers": TIERS.copy(), "bullets": []})
        else:
            if not jobs:
                jobs.append({"role": "", "company": "", "location": "", "dates": "",
                             "tiers": TIERS.copy(), "bullets": []})
            jobs[-1]["bullets"].append({"category": "Experience", "text": line, "tiers": TIERS.copy()})
    data["experience"] = jobs
    data["import_source_text"] = text
    return data


def import_file(filename, content):
    suffix = Path(filename).suffix.lower()
    if suffix in (".yaml", ".yml", ".json"):
        try:
            raw = content.decode("utf-8-sig")
            data = json.loads(raw) if suffix == ".json" else yaml.safe_load(raw)
            Resume.model_validate(data)
        except (UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError, ValidationError) as exc:
            raise ValueError(f"Invalid or incomplete resume schema: {exc}") from exc
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True), []
    text = extract_text(filename, content)
    data = parse_document(text)
    prompt = ("Extract only exact verbatim phrases from this resume. Return JSON with keys name, summary, "
              "skills (array of strings), and experience (array of objects with role, company, location, "
              "dates strings and bullets array of strings). Use empty strings or arrays when uncertain; "
              "do not infer. Resume:\n" + text[:16000])
    model, warning = local_json_request(prompt)
    notices = ["Review imported fields against the source; extracted text is retained under import_source_text."]
    if model is not None:
        valid = (isinstance(model.get("name"), str) and isinstance(model.get("summary"), str)
                 and isinstance(model.get("skills"), list) and all(isinstance(s, str) for s in model["skills"])
                 and isinstance(model.get("experience"), list)
                 and all(isinstance(job, dict)
                         and all(isinstance(job.get(key), str) for key in ("role", "company", "location", "dates"))
                         and isinstance(job.get("bullets"), list)
                         and all(isinstance(b, str) for b in job["bullets"]) for job in model["experience"]))
        values = [model.get("name", ""), model.get("summary", "")] + (model.get("skills", []) if valid else [])
        if valid:
            for job in model["experience"]:
                values.extend([job[key] for key in ("role", "company", "location", "dates")] + job["bullets"])
        if valid and all(not value or value.casefold() in text.casefold() for value in values):
            data["profile"]["name"] = model["name"]
            data["profile"]["summary"] = model["summary"]
            if model["skills"]:
                data["skills"] = [{"category": "Imported skills", "items": model["skills"], "tiers": TIERS.copy()}]
            if model["experience"]:
                data["experience"] = [
                    {key: job[key] for key in ("role", "company", "location", "dates")} |
                    {"tiers": TIERS.copy(), "bullets": [
                        {"category": "Experience", "text": b, "tiers": TIERS.copy()} for b in job["bullets"]
                    ]} for job in model["experience"]]
            notices.append("A local model extracted verbatim text; verify its classifications.")
        else:
            notices.append("Local model output was invalid or not verbatim; heuristic extraction was used.")
    if warning:
        notices.append(warning)
    raw = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    validate(raw)
    return raw, notices

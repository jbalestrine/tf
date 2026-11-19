"""Job matching, application tracking and read-only portfolio routes."""

import json
import re
import threading
import uuid
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import quote

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent
SUBMISSIONS = BASE / "submissions.json"
lock = threading.Lock()
router = APIRouter()
APPROVED = (
    "Joseph_Balestrine_DevOps_Architect_Master.docx",
    "Joseph_Balestrine_Executive_2Page.docx",
    "Joseph_Balestrine_Slide_Edition.docx",
    "Joseph_Balestrine_Architect_Portfolio.pdf",
)


class JDRequest(BaseModel):
    job_description: str = Field(min_length=1, max_length=30000)


class Submission(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    role_title: str = Field(min_length=1, max_length=200)
    recruiter_name: str = Field(default="", max_length=200)
    agency: str = Field(default="", max_length=200)
    resume_version: str = Field(default="", max_length=200)
    date: date
    status: Literal["Submitted", "Shortlisted", "Tech Screen", "Final Panel", "Offer"]
    notes: str = Field(default="", max_length=10000)


def load_resume():
    return yaml.safe_load((BASE / "resume.yaml").read_text(encoding="utf-8"))


@router.post("/api/analyze-jd")
def analyze(payload: JDRequest):
    data = load_resume()
    resume_text = yaml.safe_dump(data, allow_unicode=True).lower()
    candidates = []
    for group in data["skills"]:
        for item in group["items"]:
            candidates.extend(re.split(r"\s*/\s*|\s*\([^)]*\)", item))
    for module in json.loads((BASE / "techlearn_knowledge.json").read_text(encoding="utf-8")):
        candidates.extend(module["aliases"])
    candidates.extend(("ArgoCD", "Ansible", "Pulumi", "Helm", "Istio", "OpenShift", "Datadog",
                       "Elasticsearch", "Kafka", "Snowflake", "Databricks", "Java", "Rust"))
    unique = {}
    for candidate in candidates:
        candidate = candidate.strip()
        if len(candidate) >= 2:
            unique.setdefault(candidate.lower(), candidate)
    candidates = list(unique.values())
    mentioned = [x for x in candidates if re.search(r"(?<!\w)" + re.escape(x) + r"(?!\w)", payload.job_description, re.I)]
    matched = [x for x in mentioned if x.lower() in resume_text]
    missing = [x for x in mentioned if x not in matched]
    return {"score": round(100 * len(matched) / len(mentioned)) if mentioned else None,
            "matched": matched, "missing": missing, "identified": mentioned,
            "notice": "Heuristic overlap with known resume skills, not an ATS score. Unrecognized requirements need manual review."}


def read_submissions():
    if not SUBMISSIONS.exists():
        return []
    value = json.loads(SUBMISSIONS.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("Invalid submissions.json: expected a list.")
    return value


@router.get("/api/submissions")
def list_submissions():
    with lock:
        return read_submissions()


@router.post("/api/submissions")
def add_submission(payload: Submission):
    with lock:
        entries = read_submissions()
        item = payload.model_dump(mode="json")
        item["id"] = uuid.uuid4().hex
        entries.append(item)
        tmp = SUBMISSIONS.with_name(f".{SUBMISSIONS.name}.{uuid.uuid4().hex}.tmp")
        try:
            tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(SUBMISSIONS)
        finally:
            if tmp.exists():
                tmp.unlink()
    return item


@router.put("/api/submissions/{item_id}")
def update_submission(item_id: str, payload: Submission):
    with lock:
        entries = read_submissions()
        for index, item in enumerate(entries):
            if item.get("id") == item_id:
                updated = payload.model_dump(mode="json")
                updated["id"] = item_id
                entries[index] = updated
                tmp = SUBMISSIONS.with_name(f".{SUBMISSIONS.name}.{uuid.uuid4().hex}.tmp")
                try:
                    tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
                    tmp.replace(SUBMISSIONS)
                finally:
                    if tmp.exists():
                        tmp.unlink()
                return updated
    raise HTTPException(404, "Submission not found.")


@router.get("/portfolio")
def portfolio():
    return FileResponse(BASE / "portfolio.html")


@router.get("/api/portfolio/data")
def portfolio_data():
    data = load_resume()
    return {"name": data["profile"]["name"], "titles": data["profile"]["titles"],
            "metrics": data["metrics"], "skills": data["skills"],
            "files": [{"name": name, "preview": "/api/portfolio/preview/" + quote(name),
                       "download": "/api/portfolio/download/" + quote(name)}
                      for name in APPROVED if (BASE / "dist" / name).is_file()
                      and (BASE / "dist" / name).resolve().parent == (BASE / "dist").resolve()]}


@router.get("/api/portfolio/download/{filename}")
def portfolio_download(filename: str):
    if filename not in APPROVED:
        raise HTTPException(404, "File not available.")
    root = (BASE / "dist").resolve()
    path = (root / filename).resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(404, "File not available.")
    return FileResponse(path, filename=filename)

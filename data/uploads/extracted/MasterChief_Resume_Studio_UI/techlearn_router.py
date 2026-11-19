"""Local study library and optional loopback-only model integration."""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from requests.exceptions import RequestException
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import YouTubeTranscriptApiException

BASE = Path(__file__).resolve().parent
WIKI = BASE / "techlearn_wiki"
router = APIRouter()


class StudyRequest(BaseModel):
    technology: str = Field(default="", max_length=300)
    job_description: str = Field(default="", max_length=30000)


class VideoRequest(BaseModel):
    url: str = Field(max_length=2048)


def video_id(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in (
        "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"
    ) or parsed.username or parsed.password:
        raise ValueError("Provide a valid YouTube URL.")
    if parsed.hostname.endswith("youtu.be"):
        candidate = parsed.path.strip("/")
    elif parsed.path == "/watch":
        candidate = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
    elif parsed.path.startswith(("/shorts/", "/embed/")):
        candidate = parsed.path.split("/")[2]
    else:
        candidate = ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
        raise ValueError("Could not identify a valid YouTube video ID.")
    return candidate


def settings():
    import os
    result = {}
    env_file = BASE / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                result[key.strip()] = value.strip().strip("\"'")
    for key in ("LLM_ENDPOINT_URL", "LLM_API_KEY", "LLM_MODEL"):
        if key in os.environ:
            result[key] = os.environ[key]
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def local_json_request(prompt):
    config = settings()
    endpoint = config.get("LLM_ENDPOINT_URL", "")
    if not endpoint:
        return None, None
    parsed = urllib.parse.urlsplit(endpoint)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "::1")
            or parsed.username or parsed.password or parsed.path not in
            ("/v1/chat/completions", "/api/generate")):
        return None, "LLM endpoint must be a loopback HTTP chat-completions or Ollama endpoint."
    model = config.get("LLM_MODEL", "")
    if not model:
        return None, "LLM_MODEL is required; local study content was used."
    ollama = parsed.path == "/api/generate"
    payload = ({"model": model, "prompt": prompt, "stream": False, "format": "json"} if ollama
               else {"model": model, "messages": [{"role": "user", "content": prompt}],
                     "response_format": {"type": "json_object"}})
    headers = {"Content-Type": "application/json"}
    if config.get("LLM_API_KEY"):
        headers["Authorization"] = "Bearer " + config["LLM_API_KEY"]
    request = urllib.request.Request(endpoint, json.dumps(payload).encode(), headers, method="POST")
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect).open(request, timeout=15) as response:
            raw = response.read(200001)
        if len(raw) > 200000:
            raise ValueError("Model response exceeds the size limit.")
        data = json.loads(raw)
        result = json.loads(data["response"] if ollama else data["choices"][0]["message"]["content"])
        if not isinstance(result, dict):
            raise ValueError("Invalid model response format.")
        return result, None
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        return None, f"Local model unavailable or returned invalid output ({type(exc).__name__}); local content was used."


def local_llm(source):
    prompt = ("Produce concise JSON with headline, rules, failures, snippet, and flashcards "
              "(question and answer objects). Do not invent evidence. Input:\n" + source[:16000])
    result, warning = local_json_request(prompt)
    if result is not None and (
        not isinstance(result.get("headline"), str)
        or not isinstance(result.get("rules"), list) or not isinstance(result.get("failures"), list)
        or not isinstance(result.get("snippet"), str) or not isinstance(result.get("flashcards"), list)
        or not all(isinstance(x, str) for x in result["rules"] + result["failures"])
        or not all(isinstance(x, dict) and isinstance(x.get("question"), str)
                   and isinstance(x.get("answer"), str) for x in result["flashcards"])
    ):
        return None, "Local model returned invalid output; local content was used."
    return result, warning


def create_study(title, source, kind):
    bank = json.loads((BASE / "techlearn_knowledge.json").read_text(encoding="utf-8"))
    matches = [item for item in bank if any(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", source, re.I)
                                          for alias in item["aliases"])]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", source) if len(s.strip()) >= 25][:8]
    words = re.findall(r"\b(?:[A-Z][A-Z0-9+#/-]{1,14}|[A-Za-z][A-Za-z0-9+#/-]{3,})\b", source)
    terms = list(dict.fromkeys(w for w in words if w.lower() not in {
        "with", "that", "this", "from", "your", "their", "will", "have", "experience", "using", "and", "the"
    }))[:20]
    study = {
        "id": uuid.uuid4().hex, "title": title, "kind": kind,
        "created": datetime.now(timezone.utc).isoformat(),
        "tags": [m["title"] for m in matches], "terms": terms,
        "headline": matches[0]["headline"] if matches else "Study notes extracted from the supplied source.",
        "rules": [x for m in matches for x in m["rules"]],
        "failures": [x for m in matches for x in m["failures"]],
        "snippet": "\n\n".join(m["snippet"] for m in matches),
        "flashcards": [x for m in matches for x in m["flashcards"]],
        "takeaways": sentences, "source_mode": "local",
        "notice": "Extracts are not summaries; verify source context. Review any example commands before use.",
    }
    if kind == "youtube" and sentences:
        study["flashcards"].extend(
            {"question": f"Recall source takeaway {index + 1}.", "answer": sentence}
            for index, sentence in enumerate(sentences[:5])
        )
    for question, answer in zip(sentences, sentences[1:]):
        if question.endswith("?"):
            study["flashcards"].append({"question": question, "answer": answer})
    if not matches:
        study["notice"] += " No curated module matched; architecture rules and examples require review."
    llm, warning = local_llm(source)
    if llm:
        study.update({key: llm[key] for key in ("headline", "rules", "failures", "snippet", "flashcards")})
        study["source_mode"] = "local model"
        study["notice"] += " Model-generated content may be inaccurate."
    if warning:
        study["warning"] = warning
    WIKI.mkdir(exist_ok=True)
    path = WIKI / (study["id"] + ".json")
    with path.open("x", encoding="utf-8") as file:
        json.dump(study, file, ensure_ascii=False, indent=2)
    return study


@router.get("/techlearn")
def techlearn_page():
    return FileResponse(BASE / "techlearn.html")


@router.get("/api/techlearn/technologies")
def technologies():
    data = yaml.safe_load((BASE / "resume.yaml").read_text(encoding="utf-8"))
    return [item for group in data["skills"] for item in group["items"]]


@router.post("/api/techlearn/cheatsheet")
def cheatsheet(payload: StudyRequest):
    source = (payload.technology + "\n" + payload.job_description).strip()
    if not source:
        raise HTTPException(422, "Provide a technology or job description.")
    return create_study(payload.technology or "Job description study", source, "cheatsheet")


@router.post("/api/techlearn/youtube")
def youtube(payload: VideoRequest):
    try:
        identifier = video_id(payload.url)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        transcript = YouTubeTranscriptApi().fetch(identifier)
    except (YouTubeTranscriptApiException, RequestException) as exc:
        raise HTTPException(502, "Transcript unavailable: captions may be disabled or YouTube could not be reached.") from exc
    text = " ".join(entry.text for entry in transcript)
    if not text.strip():
        raise HTTPException(422, "The transcript is empty.")
    return create_study(f"YouTube {identifier}", text, "youtube")


@router.get("/api/techlearn/wiki")
def wiki(q: str = Query(default="", max_length=300), tag: str = Query(default="", max_length=300)):
    if not WIKI.exists():
        return []
    records = []
    for path in WIKI.glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        if q.lower() in json.dumps(record, ensure_ascii=False).lower() and (
                not tag or any(tag.lower() in t.lower() for t in record["tags"])):
            records.append(record)
    return sorted(records, key=lambda x: x["created"], reverse=True)


@router.delete("/api/techlearn/wiki/{item_id}")
def delete_wiki(item_id: str):
    if not re.fullmatch(r"[0-9a-f]{32}", item_id):
        raise HTTPException(404, "Study not found.")
    path = WIKI / (item_id + ".json")
    if not path.is_file() or path.is_symlink():
        raise HTTPException(404, "Study not found.")
    path.unlink()
    return {"deleted": item_id}

import os
import sys
import shutil
import subprocess
import ipaddress
from urllib.parse import urlsplit
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, Optional

if __name__ == "__main__" and "PORT" in os.environ:
    import run as studio_launcher

    if Path(sys.prefix).resolve() != studio_launcher.ENV_DIR.resolve():
        try:
            python = studio_launcher.prepare_environment()
            env = os.environ.copy()
            env["MASTERCHIEF_ADDON_PARENT_PIPE"] = "1"
            with subprocess.Popen([str(python), str(Path(__file__).resolve())],
                                  stdin=subprocess.PIPE, env=env) as process:
                try:
                    sys.exit(process.wait())
                except KeyboardInterrupt:
                    process.terminate()
                    sys.exit(process.wait())
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"Add-on startup failed: {exc}", file=sys.stderr, flush=True)
            sys.exit(1)
    if os.environ.get("MASTERCHIEF_ADDON_PARENT_PIPE") == "1":
        import threading

        def watch_addon_parent():
            sys.stdin.buffer.read(1)
            os._exit(1)

        threading.Thread(target=watch_addon_parent, daemon=True).start()

import jinja2
import mammoth
import yaml
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
import studio_tools
import techlearn_router
import profile_store
import email_agent
import visual_resume

BASE_DIR = Path(__file__).resolve().parent
RESUME_YAML = BASE_DIR / "resume.yaml"
DIST_DIR = BASE_DIR / "dist"
BACKUP_DIR = BASE_DIR / "backups"
INDEX_HTML = BASE_DIR / "index.html"
TEMPLATE_HTML = BASE_DIR / "template_v2.html"
PREVIEW_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:; sandbox",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
}
DOCX_PREVIEW_STYLES = """
p[style-name='Resume Banner Eyebrow'] => div.resume-banner > p.banner-eyebrow:fresh
p[style-name='Resume Banner Name'] => div.resume-banner > p.banner-name:fresh
p[style-name='Resume Banner Title'] => div.resume-banner > p.banner-title:fresh
p[style-name='Resume Banner Contact'] => div.resume-banner > p.banner-contact:fresh
p[style-name='Resume Job Header'] => div.resume-timeline > p.resume-job:fresh
p[style-name='Resume Tech Thread'] => div.resume-timeline > p.resume-thread:fresh
p[style-name='Resume Timeline Bullet'] => div.resume-timeline > ul > li:fresh
p[style-name='Resume Microsoft Header'] => p.resume-job:fresh
p[style-name='Resume Microsoft Thread'] => p.resume-thread:fresh
table[style-name='Resume Microsoft Block'] => div.resume-timeline > table.resume-microsoft:fresh
table[style-name='Resume KPI Strip'] => table.resume-kpis:fresh
table[style-name='Resume Skills Matrix'] => table.resume-skills:fresh
"""

DIST_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

app = FastAPI(title="MasterChief Resume Studio API", version="1.0.0")
app.include_router(studio_tools.router)
app.include_router(techlearn_router.router)
app.include_router(email_agent.router)


@app.middleware("http")
async def public_mode_guard(request: Request, call_next):
    if os.environ.get("MASTERCHIEF_PUBLIC_ONLY", "").lower() in ("1", "true", "yes"):
        path = request.url.path
        allowed = path in ("/portfolio", "/api/portfolio/data") or (
            path.startswith(("/api/portfolio/preview/", "/api/portfolio/download/"))
            and path.rsplit("/", 1)[-1] in studio_tools.APPROVED
        )
        if request.method != "GET" or not allowed:
            return Response(status_code=404)
    if request.url.path == "/api/email" or request.url.path.startswith("/api/email/"):
        try:
            local = request.client is not None and ipaddress.ip_address(request.client.host).is_loopback
        except ValueError:
            local = False
        hostname = request.url.hostname
        origin = request.headers.get("origin")
        allowed_host = hostname in ("localhost", "127.0.0.1", "::1")
        if origin:
            parsed = urlsplit(origin)
            valid_origin = parsed.scheme == request.url.scheme and parsed.netloc == request.url.netloc
        else:
            valid_origin = request.method == "GET"
        forwarded = any(name in request.headers for name in ("forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto"))
        if not local or not allowed_host or not valid_origin or forwarded:
            return JSONResponse({"detail": "Email agent access requires a direct, same-origin localhost connection."}, status_code=403)
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResumePayload(BaseModel):
    data: Optional[Dict[str, Any]] = None
    raw_yaml: Optional[str] = None
    active_profile: Optional[str] = None


class ProfileName(BaseModel):
    name: str
    active_profile: Optional[str] = None


class BuildRequest(BaseModel):
    target: str = "all"
    company_name: str = "[Company Name]"
    role_title: str = "Senior DevOps Engineer / Enterprise Cloud Architect"


class VisualResumePayload(BaseModel):
    html: str


def create_backup() -> None:
    if RESUME_YAML.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(RESUME_YAML, BACKUP_DIR / f"resume_{ts}.yaml")


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    if not INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return INDEX_HTML.read_text(encoding="utf-8")


@app.get("/visual-resume.js")
def visual_resume_script():
    return FileResponse(BASE_DIR / "visual-resume.js", media_type="application/javascript")


@app.post("/api/visual-resume/import")
async def visual_resume_import(file: UploadFile = File(...)):
    content = await file.read(profile_store.MAX_UPLOAD + 1)
    if len(content) > profile_store.MAX_UPLOAD:
        raise HTTPException(413, "File exceeds the 5 MB upload limit.")
    try:
        text = await run_in_threadpool(profile_store.extract_text, file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    html = "".join(f"<p>{escape(line) or '<br>'}</p>" for line in text.splitlines())
    return {"html": html, "warning": "Imported as text only. Layout, images, tables and formatting may change. The original is unchanged."}


@app.post("/api/visual-resume/export/{format}")
def visual_resume_export(format: str, payload: VisualResumePayload):
    if format not in {"docx", "pdf"}:
        raise HTTPException(400, "Choose DOCX or PDF.")
    try:
        result = visual_resume.docx_bytes(payload.html) if format == "docx" else visual_resume.pdf_bytes(payload.html)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if format == "docx" else "application/pdf"
    return Response(result, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="resume-edited.{format}"',
                                                              "Cache-Control": "no-store"})


@app.get("/api/resume")
def get_resume():
    if not RESUME_YAML.exists():
        raise HTTPException(status_code=404, detail="resume.yaml not found")
    with profile_store.LOCK:
        active = profile_store.initialize()
        raw_text = RESUME_YAML.read_text(encoding="utf-8")
        parsed = yaml.safe_load(raw_text)
    return {"data": parsed, "raw_yaml": raw_text, "active_profile": active}


@app.post("/api/resume")
def save_resume(payload: ResumePayload):
    try:
        if payload.raw_yaml is not None:
            raw = payload.raw_yaml
        elif payload.data is not None:
            raw = yaml.safe_dump(payload.data, sort_keys=False, allow_unicode=True)
        else:
            raise ValueError("Must supply either data or raw_yaml")
        with profile_store.LOCK:
            profile_store.validate(raw)
            create_backup()
            profile_store.save_current(raw, payload.active_profile)
    except (ValueError, yaml.YAMLError) as exc:
        raise HTTPException(status_code=400, detail=f"Failed to save YAML: {exc}")

    return {"status": "saved", "timestamp": datetime.now().isoformat()}


@app.get("/api/profiles")
def profiles():
    try:
        return profile_store.list_profiles()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/profiles/switch")
def switch_profile(payload: ProfileName):
    try:
        return {"active": profile_store.switch(payload.name, payload.active_profile)}
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/profiles/clone")
def clone_profile(payload: ProfileName):
    try:
        with profile_store.LOCK:
            profile_store.initialize()
            raw = profile_store.RESUME.read_text(encoding="utf-8")
            return {"name": profile_store.create(payload.name, raw, expected=payload.active_profile)}
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/profiles/import")
async def import_profile(file: UploadFile = File(...), name: str = Form(...), active_profile: Optional[str] = Form(None)):
    try:
        content = await file.read(profile_store.MAX_UPLOAD + 1)
        if len(content) > profile_store.MAX_UPLOAD:
            raise HTTPException(413, "File exceeds the 5 MB upload limit.")
        raw, warnings = await run_in_threadpool(profile_store.import_file, file.filename or "", content)
        await run_in_threadpool(profile_store.create, name, raw, True, active_profile)
        return {"active": name, "warnings": warnings}
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(500, "Could not update the active profile. Ensure resume.yaml is not open or locked, then retry.") from exc
    finally:
        await file.close()


@app.post("/api/build")
def trigger_build(req: BuildRequest):
    valid_targets = {"all", "master", "exec", "slideedition", "coverletter", "pdf", "interviewprep"}
    if req.target not in valid_targets:
        raise HTTPException(status_code=400, detail=f"Invalid target: {req.target}")

    cmd = [
        sys.executable,
        str(BASE_DIR / "build_resumes.py"),
        "--target",
        req.target,
        "--company",
        req.company_name,
        "--role",
        req.role_title,
    ]
    with profile_store.LOCK:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"Build failed: {result.stderr or result.stdout}",
        )

    files = sorted(
        [f.name for f in DIST_DIR.iterdir() if f.is_file()],
        key=lambda x: (DIST_DIR / x).stat().st_mtime,
        reverse=True,
    )
    return {
        "status": "success",
        "target": req.target,
        "logs": result.stdout,
        "files": files,
    }


@app.get("/api/files")
def list_files():
    files = sorted(
        [f.name for f in DIST_DIR.iterdir() if f.is_file()],
        key=lambda x: (DIST_DIR / x).stat().st_mtime,
        reverse=True,
    )
    return {"files": files}


@app.get("/api/preview-template", response_class=HTMLResponse)
def preview_template():
    if not RESUME_YAML.is_file() or not TEMPLATE_HTML.is_file():
        raise HTTPException(status_code=404, detail="Resume or template not found")
    with RESUME_YAML.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Invalid YAML root structure")
    template = jinja2.Environment(autoescape=True).from_string(
        TEMPLATE_HTML.read_text(encoding="utf-8")
    )
    return HTMLResponse(template.render(**data), headers=PREVIEW_HEADERS)


@app.get("/api/preview/{filename}")
def preview_file(filename: str):
    if not filename or filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = (DIST_DIR / filename).resolve()
    if path.parent != DIST_DIR.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    extension = path.suffix.lower()
    if extension == ".pdf":
        return FileResponse(
            path, media_type="application/pdf", filename=filename,
            content_disposition_type="inline", headers={"Cache-Control": "no-store"},
        )
    if extension == ".html":
        return FileResponse(path, media_type="text/html", headers=PREVIEW_HEADERS)
    if extension != ".docx":
        raise HTTPException(status_code=415, detail="Unsupported preview format")

    with path.open("rb") as file:
        result = mammoth.convert_to_html(file, style_map=DOCX_PREVIEW_STYLES)
    document = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(filename)}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 32px 16px; background-color: #e8f2fd;
          background-image: linear-gradient(#b4d6fa55 1px, transparent 1px),
                            linear-gradient(90deg, #b4d6fa55 1px, transparent 1px);
          background-size: 24px 24px;
          color: #1e293b; font: 15px/1.6 Calibri, Arial, sans-serif; }}
  main {{ max-width: 850px; min-height: 100vh; margin: auto; padding: 48px 56px;
          background: #fff; box-shadow: 0 12px 40px #0f172a26; overflow-wrap: anywhere; }}
  h1, h2, h3 {{ color: #002050; line-height: 1.25; }}
  h1 {{ border-bottom: 2px solid #0078d4; padding-bottom: 10px; }}
  p {{ margin: 0 0 0.8em; }}
  ul, ol {{ padding-left: 1.5em; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1em 0; }}
  td, th {{ padding: 8px; border: 1px solid #cbd5e1; vertical-align: top; }}
  .resume-banner {{ margin: -16px -16px 18px; padding: 22px 24px 18px;
                   background: #002050; color: #fff; border-bottom: 4px solid #50e6ff; }}
  .resume-banner p {{ margin: 0 0 5px; }}
  .resume-banner .banner-eyebrow {{ color: #50e6ff; font-size: .72rem; font-weight: 700; letter-spacing: .04em; }}
  .resume-banner .banner-name {{ font-size: 1.8rem; font-weight: 700; line-height: 1.15; }}
  .resume-banner .banner-title {{ font-weight: 600; color: #b7eeff; }}
  .resume-banner .banner-contact {{ font-size: .85rem; overflow-wrap: anywhere; }}
  table.resume-kpis {{ table-layout: fixed; border-collapse: separate; border-spacing: 5px 0; margin: 12px -5px 18px; width: calc(100% + 10px); }}
  .resume-kpis td {{ width: 25%; background: #f0f6ff; border: 1px solid #b4d6fa; border-top: 4px solid #50e6ff; }}
  .resume-kpis p {{ margin: 0; }}
  .resume-kpis p:first-child {{ color: #0078d4; font-size: 1.15rem; font-weight: 700; }}
  .resume-kpis p + p {{ color: #475569; font-size: .8rem; }}
  table.resume-skills {{ margin: 12px 0 18px; }}
  .resume-skills tr:nth-child(odd) {{ background: #f0f6ff; }}
  .resume-skills tr:nth-child(even) {{ background: #deecf9; }}
  .resume-skills td:first-child {{ width: 30%; color: #002050; }}
  .resume-skills p {{ margin: 0; }}
  .resume-timeline {{ position: relative; margin-left: 8px; padding-left: 16px; }}
  .resume-timeline::before {{ content: ""; position: absolute; top: 0; bottom: 0; left: 0; border-left: 2px dotted #0078d4; }}
  p.resume-job {{ position: relative; margin: 16px 0 0; padding: 8px 12px; background: #f0f6ff;
                  border: 1px solid #b4d6fa; border-left: 4px solid #0078d4; color: #002050; }}
  .resume-timeline > p.resume-job::before {{ content: ""; position: absolute; left: -23px; top: 14px;
                                             width: 7px; height: 7px; background: #0078d4; transform: rotate(45deg); }}
  p.resume-thread {{ margin: 0 0 5px; padding: 3px 10px; background: #deecf9; color: #0078d4; font-size: .84rem; }}
  .resume-timeline > ul {{ margin: 6px 0 14px; }}
  table.resume-microsoft {{ background: #f0f6ff; border: 1px solid #b4d6fa; border-left: 4px solid #0078d4; }}
  .resume-microsoft > tbody > tr > td {{ border: 0; }}
  .resume-microsoft p.resume-job {{ margin-top: 0; }}
  img {{ max-width: 100%; height: auto; }}
  a {{ color: #0078d4; }}
  @media (max-width: 600px) {{ main {{ padding: 24px; }} body {{ padding: 8px; }} }}
</style></head><body><main>{result.value}</main></body></html>"""
    return HTMLResponse(document, headers=PREVIEW_HEADERS)


@app.get("/api/portfolio/preview/{filename}")
def portfolio_preview(filename: str):
    if filename not in studio_tools.APPROVED:
        raise HTTPException(status_code=404, detail="File not available")
    return preview_file(filename)


@app.get("/api/download/{filename}")
def download_file(filename: str):
    safe_name = os.path.basename(filename)
    file_path = DIST_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=safe_name)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    print(f"[MC] Running on http://127.0.0.1:{port}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, proxy_headers=False, access_log=False)

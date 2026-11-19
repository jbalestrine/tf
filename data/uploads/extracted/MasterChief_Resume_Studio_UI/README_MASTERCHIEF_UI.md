# MasterChief Resume-as-Code Studio (Web UI + FastAPI)

## Directory Structure
Place these files in the same folder as `resume.yaml`, `build_resumes.py`, and `template_v2.html`:
- `app.py` — FastAPI backend serving the dashboard, reading/writing `resume.yaml` with automatic backups, and triggering `build_resumes.py`.
- `index.html` — Dark-mode MasterChief UI with tabs for Profile & KPIs, Cover Letter, Experience & Tier checkboxes, and Raw YAML.
- `requirements.txt` — Python dependencies.
- `run.py` — Creates the local environment, installs dependencies, and starts the server.

## Quick Start
```bash
python run.py
```
Python 3 with `venv` and `pip` is required. The first run downloads and installs
the dependencies into `.venv`; an internet connection or configured package mirror
is needed. The launcher opens `http://127.0.0.1:8080/` after the server starts.
Run `python` with the full path to `run.py` when starting from another directory.
The launcher reinstalls dependencies if `requirements.txt` changes. Virtual
environments are not portable across machines or operating systems: when moving the
folder, recreate `.venv` on the destination machine. A writable application folder
is required for `.venv`, `dist`, and backups.

The launcher listens on `0.0.0.0:8080` and the app has **no authentication**.
Anyone with network access can read and modify resume data and trigger builds. Use
only on a trusted network, or configure authentication and network restrictions at
your web host. For hosting, the app may also be run directly with
`uvicorn app:app` after installing the requirements.

Use **Preview** beside a generated PDF, HTML, or DOCX artifact to view it in the
dashboard. DOCX previews are converted to HTML, so some Word formatting may differ.
Newly built master and executive documents use named styles for the navy banner,
KPI cards, skills matrix, and job headers so these colors appear in the preview.
Rebuild existing artifacts to apply the updated styling.
**Live Architect Preview** renders the current saved `resume.yaml` without a build;
save dashboard edits before opening the preview. Use **Refresh** in the
preview to reload the latest saved data or artifact.

## Resume profiles and imports

The toolbar switches, clones, and imports profiles. The first use creates
`profiles/default.yaml` from the saved `resume.yaml`. Saves update both the
active profile and `resume.yaml`; switching preserves the currently saved
profile. Unsaved editor changes require confirmation before they are discarded,
and cloning copies the last saved version. Profile names use letters, numbers,
underscores and hyphens; existing names are never overwritten by import or clone.

YAML/JSON uploads must have the complete resume builder schema. DOCX and
text-based PDF imports use conservative heuristic section extraction; the full
extracted text is retained in `import_source_text` in the Raw YAML tab. Missing
metrics, cover-letter content and other facts are left empty, not copied from
another profile. Scanned PDFs require OCR and are rejected; encrypted PDFs and
files over 5 MB are not supported. Review the raw import and correct sections,
dates and tier selections before building. If the optional loopback LLM is
configured, it may classify verbatim excerpts; invalid or non-verbatim output
falls back to the heuristic parser with a warning.

Profiles are stored unencrypted and may contain private information. The builder
still writes shared artifact filenames in `dist/`; building another profile
overwrites those generated files. The portfolio displays the active resume data
and approved files, so review both before publishing. Use one server process per
workspace: concurrent multi-process profile writes are not coordinated.

## TechLearn, job matching and CRM

TechLearn uses the local `techlearn_knowledge.json` modules and source excerpts;
review the material and examples before relying on them. Studies are stored in
`techlearn_wiki/` as JSON. Fetching YouTube captions requires network access;
videos without accessible captions cannot be processed.

Optionally set `LLM_ENDPOINT_URL`, `LLM_MODEL`, and `LLM_API_KEY` in a local
`.env` or environment. The URL must use HTTP and a loopback IP (`127.0.0.1`
or `::1`) with `/v1/chat/completions` or `/api/generate`; remote endpoints and
redirects are rejected. The supplied study text is sent to that local service.
If it is unavailable or returns invalid JSON, the app reports the fallback to
local content. Do not share `.env`, the wiki, or `submissions.json`.
Copy `.env.example` to `.env` to start with blank placeholders; `.env` is
ignored by Git. Git ignore rules do not untrack files that were already committed.

The JD analyzer is a limited vocabulary-based overlap estimate, **not an ATS
score**. Missing terms are suggestions for review, not evidence of experience.
The CRM stores applications in `submissions.json`; it is not encrypted and is
intended for a trusted private environment.

## Gmail recruiter agent

Copy `.env.example` to `.env` and set `GMAIL_ADDRESS` and a Google app
password in `GMAIL_APP_PASSWORD` (Google account two-step verification and
Gmail IMAP access are required). Never use your normal Google password.
`EMAIL_KEYWORDS` is a comma-separated filter. The Email Agent is disabled in
public-only mode and accepts only direct loopback, same-origin browser requests;
it does not work through a reverse proxy. These restrictions do not protect the
rest of the unauthenticated dashboard: run it on a trusted network, preferably
bound to `127.0.0.1`, not exposed to the internet.

Scanning is manual: **Scan Inbox Now** reads up to 200 unread messages without
marking them read. It checks subjects and plain-text bodies (or extracts text
from HTML when no plain-text body is present), ignores messages
over 5 MB, and skips mailing lists, automatic senders, messages without valid
Message-IDs and messages already processed. Review company and role before
approving. Replies are limited to one sent or attempted message per sender in
30 days. Architect roles receive executive DOCX and portfolio PDF; DevOps,
SRE and platform engineer roles receive the master DOCX. Other roles require
manual correction. Documents and the tailored cover letter are generated in
memory from the currently saved active profile, not from shared `dist` files.
Unsaved edits are not included.

Auto-send defaults off. Enabling it sends real emails during subsequent scans
without individual approval whenever a message has explicit `Company:` and
`Role:` fields and a supported role. Email contents and sender identities can
be forged; use this mode only if that risk is acceptable. The toggle overrides
`EMAIL_AUTO_SEND` and persists in `processed_emails.json`. Disable it from the
UI to return to approval mode. This file contains unencrypted personal email
data and is ignored by Git; protect it and `submissions.json`. Use one server
process per workspace.

If delivery is shown as `sending` or `uncertain`, check Gmail Sent before
taking any action; the agent deliberately does not retry, because delivery may
have succeeded. If CRM status remains `pending`, add the application to the
CRM manually and do not resend. Network tests should use mocks, not real mail.

## Public portfolio mode

The dashboard and its APIs have no login. Do not expose the normal server to the
internet. To run a separate read-only portfolio instance, set the environment
variable `MASTERCHIEF_PUBLIC_ONLY=1` before starting `run.py` or Uvicorn, then
open `/portfolio`. This mode denies all non-portfolio routes, including API
documentation and write APIs. It does not authenticate visitors or provide
multi-user RBAC. Only the three named resume DOCX files and Architect Portfolio
PDF are available through the public routes; these files may contain personal
contact information. Review the files and data before publishing. Protect the
private instance separately with network restrictions.

## MasterChief add-on

On the host machine, use **Start** in Addons Modules, then **Open App** or
the pinned Resume Studio link. The add-on creates its own `.venv` and installs
its requirements on first start, then binds to the dynamically assigned port
on `127.0.0.1`. The static add-on page redirects to the running service; it
does not provide an API itself. An internet connection or package mirror is
needed for first-time setup. The add-on is accessible only on the host machine.

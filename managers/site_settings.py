"""Site settings wizard: change logo, title, version, About text and menu entries.

Every change is a small, line-ranged edit applied through PageEditor, so it gets the same
validation, stale-edit check, backup and restore as the Page Editor.
"""
from __future__ import annotations

import html
import re
import time
from pathlib import Path

from managers.page_editor import PageEditor, PageEditorError, _sha

LAYOUT_FILE = "templates/layout.html"
LAYOUT_FILES = (LAYOUT_FILE,)
NAV_OPEN = '<nav aria-label="Main navigation">'
HREF_RE = re.compile(r"^/[A-Za-z0-9_\-./#?=&%]*$")
VERSION_RE = re.compile(r"^\d+(\.\d+){1,3}([.\-+][0-9A-Za-z.]+)?$")
NAV_LINK_RE = re.compile(r'^(\s*)<a href="(/[^"]*)"(?: class="(.*?)")?>(.*?)</a>\s*$')
NAV_SUMMARY_RE = re.compile(r'^(\s*<summary[^>]*>)(.*?)(</summary>\s*)$')
LOGO_TYPES = {".svg", ".png", ".jpg", ".jpeg", ".webp"}
MAX_LOGO_BYTES = 1_000_000
LOGO_BASE = "static/masterchief-logo"


class SiteSettingsError(ValueError):
    pass


def _b(file, pattern, flags=0, after=None, optional=False, nth=0):
    return {"file": file, "pattern": pattern, "flags": flags, "after": after, "optional": optional, "nth": nth}


FIELDS = [
    {"id": "site_title", "group": "Site", "label": "Browser tab title", "kind": "text",
     "help": "Text in the browser tab on every page that uses the shared layout.",
     "bindings": [_b(LAYOUT_FILE, r"<title>(?P<v>[^<{]*)</title>")]},
    {"id": "logo_alt", "group": "Site", "label": "Logo alt text", "kind": "text", "attr": True,
     "help": "Description read by screen readers and shown if the logo cannot load.",
     "bindings": [_b(LAYOUT_FILE, r'masterchief-site-brand.*?<img[^>]*?alt="(?P<v>[^"]*)"', re.S)]},
    {"id": "logo_width", "group": "Site", "label": "Logo max width (px)", "kind": "int", "min": 40, "max": 1200,
     "help": "Largest width of the logo in the header.",
     "bindings": [_b(LAYOUT_FILE, r"masterchief-site-brand.*?width:min\((?P<v>\d+)px", re.S)]},
    {"id": "version", "group": "Version", "label": "App version", "kind": "version",
     "help": "Updates the package version in setup.py and masterchief/__init__.py. The About page also shows the latest GitHub release, which is read from GitHub.",
     "bindings": [_b("setup.py", r'^\s*version="(?P<v>[^"]+)"', re.M),
                  _b("masterchief/__init__.py", r'^__version__\s*=\s*"(?P<v>[^"]+)"', re.M)]},
    {"id": "about_title", "group": "About page", "label": "Page title (browser tab)", "kind": "text",
     "bindings": [_b("about.html", r"<title>(?P<v>.*?)</title>", re.S)]},
    {"id": "about_heading", "group": "About page", "label": "Header title", "kind": "text",
     "bindings": [_b("about.html", r"<h1>(?P<v>.*?)</h1>", re.S)]},
    {"id": "about_subtitle", "group": "About page", "label": "Header subtitle", "kind": "text",
     "bindings": [_b("about.html", r'<p class="subtitle">(?P<v>.*?)</p>', re.S)]},
    {"id": "about_hero_title", "group": "About page", "label": "Hero title", "kind": "text",
     "bindings": [_b("about.html", r'<div class="hero-title">(?P<v>.*?)</div>', re.S)]},
    {"id": "about_hero_subtitle", "group": "About page", "label": "Hero subtitle", "kind": "text",
     "bindings": [_b("about.html", r'<div class="hero-subtitle">(?P<v>.*?)</div>', re.S)]},
    {"id": "about_release_note", "group": "About page", "label": "Release note line", "kind": "text",
     "bindings": [_b("about.html", r'<p class="version-source">(?P<v>[^<]*)</p>', re.S)]},
    {"id": "about_description", "group": "About page", "label": "Hero description", "kind": "textarea",
     "bindings": [_b("about.html", r'<p class="hero-description">(?P<v>.*?)</p>', re.S)]},
]
_CARD = r'<div class="feature-card[^>]*>\s*<span class="feature-icon">.*?</span>\s*'
_CARD_COUNT = 18
for _n in range(_CARD_COUNT):
    FIELDS.append({"id": f"about_card_{_n + 1}_title", "group": "About page cards", "label": f"Card {_n + 1} title", "kind": "text",
                   "bindings": [_b("about.html", _CARD + r"<h3>(?P<v>.*?)</h3>", re.S, optional=True, nth=_n)]})
    FIELDS.append({"id": f"about_card_{_n + 1}_text", "group": "About page cards", "label": f"Card {_n + 1} text", "kind": "textarea",
                   "bindings": [_b("about.html", _CARD + r"<h3>.*?</h3>\s*<p>(?P<v>.*?)</p>", re.S, optional=True, nth=_n)]})
for _n, _name in enumerate(("Current Features", "Updates Made", "Coming Soon", "Tech Stack")):
    FIELDS.append({"id": f"about_section_{_n + 1}_title", "group": "About page sections", "label": f"Section {_n + 1} heading ({_name})", "kind": "text",
                   "bindings": [_b("about.html", r'<h2 class="section-title">(?P<v>.*?)</h2>', re.S, optional=True, nth=_n)]})
    FIELDS.append({"id": f"about_section_{_n + 1}_subtitle", "group": "About page sections", "label": f"Section {_n + 1} subtitle ({_name})", "kind": "text",
                   "bindings": [_b("about.html", r'<p class="section-subtitle">(?P<v>.*?)</p>', re.S, optional=True, nth=_n)]})
FIELD_BY_ID = {f["id"]: f for f in FIELDS}


class SiteSettings:
    def __init__(self, editor: PageEditor):
        self.editor = editor
        self.root = editor.root

    # ---------- reading ----------
    def _read(self, rel: str) -> tuple[bytes, str]:
        raw = self.editor._safe(rel).read_bytes()
        return raw, raw.decode("utf-8").replace("\r\n", "\n")

    @staticmethod
    def _find(text: str, binding: dict):
        base = 0
        if binding["after"]:
            base = text.find(binding["after"])
            if base < 0:
                return None
        found = list(re.compile(binding["pattern"], binding["flags"]).finditer(text, base))
        nth = binding.get("nth", 0)
        return found[nth] if len(found) > nth else None

    @staticmethod
    def _to_plain(value: str) -> str:
        return html.unescape(re.sub(r"\s+", " ", value)).strip()

    def _current(self, field: dict) -> tuple[str, list[dict]]:
        value, files = "", []
        for binding in field["bindings"]:
            try:
                _, text = self._read(binding["file"])
            except PageEditorError:
                files.append({"path": binding["file"], "found": False, "optional": binding["optional"]})
                continue
            match = self._find(text, binding)
            found = match is not None
            files.append({"path": binding["file"], "found": found, "optional": binding["optional"]})
            if found and not value:
                value = self._to_plain(match.group("v")) if field["kind"] in ("text", "textarea") else match.group("v")
        return value, files

    def overview(self) -> dict:
        groups: dict[str, list] = {}
        for field in FIELDS:
            value, files = self._current(field)
            for item in files:
                item["ide"] = f"/masterchief_code_ui?open={item['path']}"
            groups.setdefault(field["group"], []).append({
                "id": field["id"], "label": field["label"], "kind": field["kind"], "help": field.get("help", ""),
                "value": value, "files": files,
            })
        return {"groups": [{"name": k, "fields": v} for k, v in groups.items()], "nav": self.nav(), "logo": self.logo_info()}

    # ---------- field edits ----------
    def _clean(self, field: dict, value) -> str:
        value = "" if value is None else str(value)
        if field["kind"] == "int":
            if not value.strip().isdigit() or not field["min"] <= int(value) <= field["max"]:
                raise SiteSettingsError(f"{field['label']} must be a number from {field['min']} to {field['max']}.")
            return str(int(value))
        if field["kind"] == "version":
            value = value.strip()
            if not VERSION_RE.match(value):
                raise SiteSettingsError("Version must look like 4.0.1 (digits and dots, optional suffix).")
            return value
        value = re.sub(r"\s+", " ", value).strip()
        if not value or len(value) > 1500:
            raise SiteSettingsError(f"{field['label']} cannot be empty or longer than 1500 characters.")
        if "{{" in value or "{%" in value or "{#" in value:
            raise SiteSettingsError(f"{field['label']} cannot contain template tags.")
        if field["kind"] == "text" and len(value) > 300:
            raise SiteSettingsError(f"{field['label']} is too long.")
        return value

    def _encode(self, field: dict, value: str) -> str:
        if field["kind"] in ("int", "version"):
            return value
        return html.escape(value, quote=bool(field.get("attr")))

    def _plan(self, binding: dict, field: dict, new_value: str) -> dict | None:
        try:
            raw, text = self._read(binding["file"])
        except PageEditorError:
            if binding["optional"]:
                return None
            raise SiteSettingsError(f"{binding['file']} is not available for editing.")
        match = self._find(text, binding)
        if not match:
            if binding["optional"]:
                return None
            raise SiteSettingsError(f"Could not find {field['label']} in {binding['file']}.")
        encoded = self._encode(field, new_value)
        if field["kind"] == "textarea":
            encoded = "\n            " + encoded + "\n        "
        return self._span_change(binding["file"], raw, text, match.start("v"), match.end("v"), encoded)

    def _span_change(self, rel: str, raw: bytes, text: str, a: int, b: int, replacement: str) -> dict | None:
        if text[a:b] == replacement:
            return None
        lines = text.splitlines(keepends=True)
        offsets, pos = [], 0
        for ln in lines:
            offsets.append(pos)
            pos += len(ln)
        first = max(i for i, off in enumerate(offsets) if off <= a)
        last = max(i for i, off in enumerate(offsets) if off <= max(a, b - 1))
        seg_start, seg_end = offsets[first], offsets[last] + len(lines[last])
        new_seg = text[seg_start:a] + replacement + text[b:seg_end]
        return {"path": rel, "start": first + 1, "end": last + 1, "text": new_seg.rstrip("\n"), "sha": _sha(raw)}

    def _plans_for(self, values: dict) -> list[tuple[dict, dict]]:
        plans = []
        for fid, value in (values or {}).items():
            field = FIELD_BY_ID.get(fid)
            if not field:
                raise SiteSettingsError(f"Unknown setting: {fid}")
            cleaned = self._clean(field, value)
            for binding in field["bindings"]:
                change = self._plan(binding, field, cleaned)
                if change:
                    plans.append((field, change))
        return plans

    def preview(self, values: dict) -> dict:
        diffs, problems = [], []
        for field, change in self._plans_for(values):
            result = self.editor.preview(change["path"], change["start"], change["end"], change["text"], change["sha"])
            diffs.append(result["diff"])
            problems += [f"{change['path']}: {p}" for p in result["problems"]]
        return {"diff": "\n".join(diffs), "changed": bool(diffs), "problems": problems, "ok": not problems}

    def save(self, values: dict) -> dict:
        if not self.preview(values)["ok"]:
            raise SiteSettingsError("Not saved: validation failed.")
        saved, restart = [], False
        for fid, value in (values or {}).items():
            field = FIELD_BY_ID[fid]
            cleaned = self._clean(field, value)
            for binding in field["bindings"]:
                change = self._plan(binding, field, cleaned)  # re-read: an earlier save may have changed the file
                if change:
                    r = self.editor.save(change["path"], change["start"], change["end"], change["text"], change["sha"])
                    saved.append({"path": change["path"], "backup": r["backup"]})
                    restart = restart or r["needs_restart"]
        if not saved:
            raise SiteSettingsError("Nothing changed.")
        return {"saved": saved, "needs_restart": restart}

    # ---------- menu ----------
    def _nav_range(self, text: str) -> tuple[list[str], int, int]:
        lines = text.splitlines()
        try:
            open_i = next(i for i, l in enumerate(lines) if NAV_OPEN in l)
            close_i = next(i for i in range(open_i, len(lines)) if "</nav>" in lines[i])
        except StopIteration as exc:
            raise SiteSettingsError("Menu markup not found.") from exc
        return lines, open_i, close_i

    def nav(self) -> dict:
        _, text = self._read(LAYOUT_FILE)
        lines, open_i, close_i = self._nav_range(text)
        groups, current = [{"label": "Top bar", "line": None, "links": []}], None
        for i in range(open_i + 1, close_i):
            s = NAV_SUMMARY_RE.match(lines[i])
            if s:
                current = {"label": html.unescape(s.group(2)), "line": i + 1, "links": []}
                groups.append(current)
                continue
            m = NAV_LINK_RE.match(lines[i])
            if m:
                (current or groups[0])["links"].append({"line": i + 1, "href": m.group(2), "label": html.unescape(m.group(4))})
        return {"groups": groups}

    @staticmethod
    def _check_label(label: str) -> str:
        label = re.sub(r"\s+", " ", str(label or "")).strip()
        if not label or len(label) > 80 or any(t in label for t in ("{{", "{%", "{#")) or "\n" in label:
            raise SiteSettingsError("Label must be 1-80 characters and cannot contain template tags.")
        return html.escape(html.unescape(label), quote=False)

    def _nav_plans(self, op: dict) -> list[dict]:
        kind = op.get("type")
        changes = []
        for rel in LAYOUT_FILES:
            try:
                raw, text = self._read(rel)
                lines, open_i, close_i = self._nav_range(text)
            except PageEditorError as exc:
                raise SiteSettingsError(f"{rel} is not available for editing.") from exc
            try:
                line_no = int(op.get("line"))
            except (TypeError, ValueError) as exc:
                raise SiteSettingsError("A menu line is required.") from exc
            idx = line_no - 1
            if not (open_i < idx < close_i):
                raise SiteSettingsError("That line is not part of the menu.")
            old = lines[idx]
            sha = _sha(raw)
            if kind == "rename_group":
                m = NAV_SUMMARY_RE.match(old)
                if not m:
                    raise SiteSettingsError("That line is not a menu group.")
                new = m.group(1) + self._check_label(op.get("label")) + m.group(3).rstrip()
                changes.append({"path": rel, "start": idx + 1, "end": idx + 1, "text": new, "sha": sha, "old": old})
            elif kind in ("rename_link", "remove_link", "add_link"):
                m = NAV_LINK_RE.match(old)
                if not m:
                    raise SiteSettingsError("That line is not a menu link.")
                if kind == "rename_link":
                    requested = op.get("href") or m.group(2)
                    href = requested if requested == m.group(2) else self._check_href(requested)
                    cls = f' class="{m.group(3)}"' if m.group(3) is not None else ""
                    new = f'{m.group(1)}<a href="{href}"{cls}>{self._check_label(op.get("label"))}</a>'
                    changes.append({"path": rel, "start": idx + 1, "end": idx + 1, "text": new, "sha": sha, "old": old})
                elif kind == "add_link":
                    href = self._check_href(op.get("href"))
                    cls = "{{ 'active' if '" + href.split("#")[0].split("?")[0] + "' in request.path else '' }}"
                    new_line = f'{m.group(1)}<a href="{href}" class="{cls}">{self._check_label(op.get("label"))}</a>'
                    changes.append({"path": rel, "start": idx + 1, "end": idx + 1, "text": old + "\n" + new_line, "sha": sha, "old": old})
                else:
                    if m.group(2) != op.get("href"):
                        raise SiteSettingsError("The menu changed. Reload and try again.")
                    if idx - 1 <= open_i:
                        raise SiteSettingsError("Cannot remove the first menu line.")
                    changes.append({"path": rel, "start": idx, "end": idx + 1, "text": lines[idx - 1], "sha": sha, "old": old})
            else:
                raise SiteSettingsError("Unknown menu action.")
        return changes

    @staticmethod
    def _check_href(href) -> str:
        href = str(href or "").strip()
        if not HREF_RE.match(href):
            raise SiteSettingsError("Link must start with / and use only URL characters, e.g. /my-page.")
        return href

    def _prepare_nav(self) -> None:
        self._read(LAYOUT_FILE)

    def nav_preview(self, op: dict) -> dict:
        self._prepare_nav()
        diffs, problems = [], []
        for c in self._nav_plans(op):
            r = self.editor.preview(c["path"], c["start"], c["end"], c["text"], c["sha"])
            diffs.append(r["diff"])
            problems += r["problems"]
        return {"diff": "\n".join(diffs), "changed": bool(diffs), "problems": problems, "ok": not problems}

    def nav_save(self, op: dict) -> dict:
        if not self.nav_preview(op)["ok"]:
            raise SiteSettingsError("Not saved: validation failed.")
        saved = []
        self._prepare_nav()
        plans = self._nav_plans(op)
        for c in plans:  # one change per file, so shas stay valid
            r = self.editor.save(c["path"], c["start"], c["end"], c["text"], c["sha"])
            saved.append({"path": c["path"], "backup": r["backup"]})
        if not saved:
            raise SiteSettingsError("Nothing changed.")
        return {"saved": saved, "needs_restart": True}

    # ---------- logo ----------
    def logo_info(self) -> dict:
        _, text = self._read(LAYOUT_FILE)
        m = re.compile(r'masterchief-site-brand.*?<img src="(/static/[^"]+)"', re.S).search(text)
        return {"src": m.group(1) if m else "", "max_bytes": MAX_LOGO_BYTES, "types": sorted(LOGO_TYPES)}

    @staticmethod
    def _sniff_logo(name: str, data: bytes) -> str:
        ext = Path(name or "").suffix.lower()
        if ext not in LOGO_TYPES:
            raise SiteSettingsError("Logo must be SVG, PNG, JPG or WebP.")
        if not data or len(data) > MAX_LOGO_BYTES:
            raise SiteSettingsError("Logo must be between 1 byte and 1 MB.")
        head = data[:16]
        if ext == ".svg":
            text = data.decode("utf-8", errors="strict").lower()
            if "<svg" not in text or re.search(r"<script|\son\w+\s*=|javascript:|<foreignobject", text):
                raise SiteSettingsError("SVG must contain <svg> and no scripts or event handlers.")
        elif ext == ".png" and not head.startswith(b"\x89PNG\r\n\x1a\n"):
            raise SiteSettingsError("File is not a valid PNG.")
        elif ext in (".jpg", ".jpeg") and not head.startswith(b"\xff\xd8\xff"):
            raise SiteSettingsError("File is not a valid JPEG.")
        elif ext == ".webp" and not (head.startswith(b"RIFF") and head[8:12] == b"WEBP"):
            raise SiteSettingsError("File is not a valid WebP.")
        return ".jpg" if ext == ".jpeg" else ext

    def set_logo(self, name: str, data: bytes) -> dict:
        ext = self._sniff_logo(name, data)
        rel = f"{LOGO_BASE}{ext}"
        target = self.root / rel
        self.editor.backup_dir.mkdir(parents=True, exist_ok=True)
        current = self.logo_info()["src"]
        old_file = self.root / current.lstrip("/") if current.startswith("/static/") else None
        backup = ""
        if old_file and old_file.is_file():
            backup = f"{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1000000:06d}__{old_file.relative_to(self.root).as_posix().replace('/', '__')}"
            (self.editor.backup_dir / backup).write_bytes(old_file.read_bytes())
        tmp = target.with_name(target.name + ".pe-tmp")
        tmp.write_bytes(data)
        tmp.replace(target)
        changed = []
        new_src = f"/{rel}"
        if current != new_src:
            for r in LAYOUT_FILES:
                try:
                    raw, text = self._read(r)
                except PageEditorError:
                    continue
                m = re.compile(r'masterchief-site-brand.*?<img src="(?P<v>/static/[^"]+)"', re.S).search(text)
                if not m:
                    continue
                c = self._span_change(r, raw, text, m.start("v"), m.end("v"), new_src)
                if c:
                    self.editor.save(c["path"], c["start"], c["end"], c["text"], c["sha"])
                    changed.append(r)
        return {"logo": new_src, "backup": backup, "updated_layouts": changed, "needs_restart": bool(changed)}

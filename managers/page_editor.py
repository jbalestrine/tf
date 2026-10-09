"""Page Editor backend: find and safely edit the source behind any page.

Pages come from the live nav menu. For a page URL we locate the Flask view,
the template constants/files it renders, the shared layout and static assets,
then expose each one as an editable "segment" (a line range of a file).
Writes require a matching file hash, validate syntax, and keep a backup.
"""

from __future__ import annotations

import ast
import difflib
import html
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from managers.source_map import SourceMap

EDITABLE_EXT = {".py", ".html", ".js", ".css", ".json", ".md", ".txt", ".yml", ".yaml", ".svg"}
BLOCKED_PARTS = {"venv", ".venv", ".git", "node_modules", "__pycache__", "data", "models", "dist", "build"}
MAX_FILE_BYTES = 2_000_000
MAX_SEGMENT_CHARS = 400_000
IDENT_RE = re.compile(r"\b[A-Z][A-Z0-9_]{3,}\b")
STATIC_RE = re.compile(r"""/static/([\w./\-]+\.(?:js|css|svg|png|json))""")
NAV_GROUP_RE = re.compile(r'<summary[^>]*>(.*?)</summary>(.*?)</details>', re.S)
NAV_LINK_RE = re.compile(r'<a\s+href="(/[^"#]*)"[^>]*>(.*?)</a>', re.S)
SCAN_DIRS = ["", "templates", "blueprints", "core", "managers", "echo"]


class PageEditorError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PageEditor:
    def __init__(self, app, project_root: str | Path, layout_template: str = ""):
        self.app = app
        self.root = Path(project_root).resolve()
        self.layout_template = layout_template
        self.backup_dir = self.root / "data" / "page_editor_backups"
        self.source_map = SourceMap(app, self.root)
        self._ast_cache: dict[str, tuple[float, dict]] = {}

    # ---------- path safety ----------
    def _safe(self, rel: str) -> Path:
        rel = str(rel or "").replace("\\", "/").lstrip("/")
        if not rel:
            raise PageEditorError("A file path is required.")
        path = (self.root / rel).resolve()
        try:
            parts = path.relative_to(self.root).parts
        except ValueError as exc:
            raise PageEditorError("Path is outside the project.") from exc
        if any(part in BLOCKED_PARTS for part in parts[:-1]) or path.name.startswith("."):
            raise PageEditorError("This location is not editable from the browser.")
        if path.suffix.lower() not in EDITABLE_EXT:
            raise PageEditorError("This file type is not editable here.")
        if not path.is_file():
            raise PageEditorError("File not found.")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise PageEditorError("File is too large to edit in the browser.")
        return path

    def _rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    # ---------- pages from the nav ----------
    def pages(self) -> list[dict]:
        groups = []
        seen_top = []
        for match in NAV_GROUP_RE.finditer(self.layout_template):
            title = html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
            links = []
            for href, label in NAV_LINK_RE.findall(match.group(2)):
                label = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", label))).strip()
                if label and "{{" not in href:
                    links.append({"url": href, "label": label})
            if links:
                groups.append({"group": title, "pages": links})
        top = [{"url": "/", "label": "Dashboard"}]
        for url in ("/about", "/site-map"):
            if not any(p["url"] == url for g in groups for p in g["pages"]):
                seen_top.append(url)
        return [{"group": "Home", "pages": top}] + groups

    # ---------- definition lookup ----------
    def _defs(self, path: Path) -> dict:
        key = str(path)
        mtime = path.stat().st_mtime
        cached = self._ast_cache.get(key)
        if cached and cached[0] == mtime:
            return cached[1]
        defs: dict[str, dict] = {}
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            tree = None
        if tree:
            for node in tree.body:
                end = getattr(node, "end_lineno", node.lineno)
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    defs[node.targets[0].id] = {"start": node.lineno, "end": end, "kind": "constant"}
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
                    defs[node.name] = {"start": start, "end": end, "kind": "function"}
        self._ast_cache[key] = (mtime, defs)
        return defs

    def _find_definitions(self, name: str) -> list[dict]:
        pattern = re.compile(rf"^{re.escape(name)}\s*=", re.M)
        found = []
        for folder in SCAN_DIRS:
            base = self.root / folder if folder else self.root
            if not base.is_dir():
                continue
            for path in sorted(base.glob("*.py")):
                try:
                    if path.stat().st_size > MAX_FILE_BYTES:
                        continue
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if pattern.search(text):
                    info = self._defs(path).get(name)
                    if info and info["kind"] == "constant":
                        found.append({"path": self._rel(path), **info})
        return found

    def _imported_modules(self, rel: str) -> dict[str, str]:
        """Map imported names in a file to the project file they come from."""
        mapping: dict[str, str] = {}
        try:
            tree = ast.parse((self.root / rel).read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            return mapping
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and not node.level:
                candidate = node.module.replace(".", "/") + ".py"
                if (self.root / candidate).is_file():
                    for alias in node.names:
                        mapping[alias.asname or alias.name] = candidate
        return mapping

    # ---------- segments for a page ----------
    def _segment(self, path: str, start: int, end: int, label: str, role: str, note: str = "") -> dict:
        return {
            "id": f"{path}:{start}-{end}", "path": path, "start": start, "end": end,
            "label": label, "role": role, "note": note,
        }

    def _whole_file(self, rel: str, label: str, role: str) -> dict | None:
        try:
            path = self._safe(rel)
        except PageEditorError:
            return None
        lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines()) or 1
        return self._segment(rel, 1, lines, label, role)

    def page_segments(self, url: str) -> dict:
        url = str(url or "").split("?", 1)[0].split("#", 1)[0]
        if not url.startswith("/") or len(url) > 200:
            raise PageEditorError("Enter a page path such as / or /about.")
        adapter = self.app.url_map.bind("localhost")
        try:
            endpoint, _ = adapter.match(url, method="GET")
        except Exception as exc:
            raise PageEditorError("No page is registered at that URL.") from exc
        rows = [r for r in self.source_map.routes() if r["endpoint"] == endpoint and "GET" in r["methods"]]
        if not rows:
            raise PageEditorError("That URL has no GET page.")
        row = rows[0]
        segments: list[dict] = []
        seen: set[str] = set()

        def add(seg: dict | None) -> None:
            if seg and seg["id"] not in seen:
                seen.add(seg["id"])
                segments.append(seg)

        route_text = ""
        if row["file"] and not row["file"].startswith(("<", "/")):
            try:
                path = self._safe(row["file"])
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                start = row["line"] or 1
                func = next((n for n, i in self._defs(path).items() if i["kind"] == "function" and i["start"] == start), None)
                end = self._defs(path)[func]["end"] if func else min(len(lines), start + 40)
                route_text = "\n".join(lines[start - 1:end])
                add(self._segment(row["file"], start, end, f"Route: {url}", "route", "Python that decides what this page shows"))
            except PageEditorError:
                pass

        texts = [route_text]
        imports = self._imported_modules(row["file"]) if row["file"] and not row["file"].startswith(("<", "/")) else {}
        for ident in sorted(set(IDENT_RE.findall(route_text))):
            if ident == "HTML_TEMPLATE":
                continue
            defs = self._find_definitions(ident)
            if len(defs) > 1:
                preferred = imports.get(ident) or row["file"]
                chosen = [d for d in defs if d["path"] == preferred]
                if chosen:
                    defs = chosen + [d for d in defs if d["path"] != preferred]
            for index, d in enumerate(defs):
                if len(defs) == 1:
                    role, note, label = "template", "Page markup (template string)", ident
                elif index == 0:
                    role, note, label = "template", "Page markup (template string) - the copy this page imports", ident
                else:
                    role, note, label = "shadowed", "Another copy with the same name that this page does not use; editing it changes nothing.", ident + " (unused copy)"
                add(self._segment(d["path"], d["start"], d["end"], label, role, note))
                if index == 0:
                    texts.append(self._read_lines(d["path"], d["start"], d["end"]))

        for rel in row["files"]:
            add(self._whole_file(rel, rel, "file"))
            try:
                texts.append(self._safe(rel).read_text(encoding="utf-8", errors="replace"))
            except PageEditorError:
                pass

        layout_defs = [d for d in self._find_definitions("HTML_TEMPLATE")]
        live = next((d for d in layout_defs if d["path"] == "main.py"), layout_defs[0] if layout_defs else None)
        for d in layout_defs:
            is_live = live is not None and d is live
            add(self._segment(
                d["path"], d["start"], d["end"],
                "Layout: header, logo and menu" + ("" if is_live else " (unused copy)"),
                "layout" if is_live else "shadowed",
                "Shared by every page. This is the copy that is actually rendered." if is_live else "Overridden by main.py; editing it changes nothing.",
            ))
            if is_live:
                texts.append(self._read_lines(d["path"], d["start"], d["end"]))

        static_refs = sorted({m for t in texts for m in STATIC_RE.findall(t)})
        for ref in static_refs:
            add(self._whole_file("static/" + ref, "static/" + ref, "asset"))

        return {"url": url, "endpoint": endpoint, "segments": segments, "restart_note": "Python and template-string edits take effect after the app restarts."}

    def _read_lines(self, rel: str, start: int, end: int) -> str:
        try:
            lines = self._safe(rel).read_text(encoding="utf-8", errors="replace").splitlines()
        except PageEditorError:
            return ""
        return "\n".join(lines[start - 1:end])

    # ---------- element lookup ----------
    def find(self, url: str, needle: str) -> list[dict]:
        needle = str(needle or "").strip()
        if len(needle) < 2 or len(needle) > 200:
            raise PageEditorError("Search text must be 2-200 characters.")
        hits = []
        for seg in self.page_segments(url)["segments"]:
            lines = self._read_lines(seg["path"], seg["start"], seg["end"]).splitlines()
            matches = [seg["start"] + i for i, line in enumerate(lines) if needle in line]
            if matches:
                hits.append({**seg, "lines": matches[:8], "count": len(matches)})
        return hits

    # ---------- read / preview / save ----------
    def read_segment(self, rel: str, start: int, end: int) -> dict:
        path = self._safe(rel)
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        start, end = self._range(start, end, len(lines))
        chunk = "\n".join(lines[start - 1:end])
        if len(chunk) > MAX_SEGMENT_CHARS:
            raise PageEditorError("Segment is too large to edit in the browser.")
        return {
            "path": rel, "start": start, "end": end, "text": chunk, "sha": _sha(raw),
            "eol": "crlf" if b"\r\n" in raw else "lf", "total_lines": len(lines),
        }

    @staticmethod
    def _range(start: Any, end: Any, total: int) -> tuple[int, int]:
        try:
            start, end = int(start), int(end)
        except (TypeError, ValueError) as exc:
            raise PageEditorError("Invalid line range.") from exc
        if start < 1 or end < start or end > max(total, 1):
            raise PageEditorError("Line range is outside the file.")
        return start, end

    def _build(self, rel: str, start: int, end: int, new_text: str, sha: str) -> tuple[Path, bytes, bytes, str]:
        if not isinstance(new_text, str) or len(new_text) > MAX_SEGMENT_CHARS:
            raise PageEditorError("Replacement text is missing or too large.")
        path = self._safe(rel)
        raw = path.read_bytes()
        if _sha(raw) != sha:
            raise PageEditorError("The file changed since you opened it. Reload the segment and try again.")
        eol = "\r\n" if b"\r\n" in raw else "\n"
        text = raw.decode("utf-8")
        had_final_newline = text.endswith(("\n", "\r\n"))
        lines = text.splitlines()
        start, end = self._range(start, end, len(lines))
        replacement = new_text.replace("\r\n", "\n").split("\n")
        if replacement and replacement[-1] == "" and len(replacement) > 1:
            replacement = replacement[:-1]
        merged = lines[:start - 1] + replacement + lines[end:]
        result = eol.join(merged) + (eol if had_final_newline else "")
        return path, raw, result.encode("utf-8"), eol

    def _validate(self, rel: str, data: bytes) -> list[str]:
        problems = []
        suffix = Path(rel).suffix.lower()
        text = data.decode("utf-8")
        try:
            if suffix == ".py":
                compile(text, rel, "exec")
            elif suffix == ".json":
                json.loads(text)
            elif suffix == ".html":
                from jinja2 import Environment
                Environment().parse(text)
        except SyntaxError as exc:
            problems.append(f"Python syntax error on line {exc.lineno}: {exc.msg}")
        except ValueError as exc:
            problems.append(f"Invalid JSON: {exc}")
        except Exception as exc:  # jinja2 TemplateSyntaxError and friends
            problems.append(f"Template error: {exc}")
        return problems

    def preview(self, rel: str, start: int, end: int, new_text: str, sha: str) -> dict:
        path, old, new, _ = self._build(rel, start, end, new_text, sha)
        diff = "".join(difflib.unified_diff(
            old.decode("utf-8").splitlines(True), new.decode("utf-8").splitlines(True),
            fromfile=rel, tofile=rel + " (edited)", n=2,
        ))
        problems = self._validate(rel, new)
        return {"diff": diff[:200_000], "changed": old != new, "problems": problems, "ok": not problems}

    def save(self, rel: str, start: int, end: int, new_text: str, sha: str) -> dict:
        path, old, new, _ = self._build(rel, start, end, new_text, sha)
        if old == new:
            raise PageEditorError("Nothing changed.")
        problems = self._validate(rel, new)
        if problems:
            raise PageEditorError("Not saved: " + "; ".join(problems))
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        name = f"{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1000000:06d}__{rel.replace('/', '__')}"
        (self.backup_dir / name).write_bytes(old)
        tmp = path.with_name(path.name + ".pe-tmp")
        tmp.write_bytes(new)
        tmp.replace(path)
        self._ast_cache.pop(str(path), None)
        return {"backup": name, "sha": _sha(new), "needs_restart": path.suffix.lower() in {".py", ".html"}}

    # ---------- backups ----------
    def backups(self, rel: str) -> list[dict]:
        self._safe(rel)
        suffix = "__" + rel.replace("/", "__")
        if not self.backup_dir.is_dir():
            return []
        items = [p for p in self.backup_dir.iterdir() if p.name.endswith(suffix)]
        items.sort(key=lambda p: p.name, reverse=True)
        return [{"name": p.name, "size": p.stat().st_size} for p in items[:30]]

    def restore(self, rel: str, backup_name: str, sha: str) -> dict:
        path = self._safe(rel)
        if backup_name not in {b["name"] for b in self.backups(rel)}:
            raise PageEditorError("Unknown backup.")
        current = path.read_bytes()
        if _sha(current) != sha:
            raise PageEditorError("The file changed since you opened it. Reload and try again.")
        data = (self.backup_dir / backup_name).read_bytes()
        problems = self._validate(rel, data)
        if problems:
            raise PageEditorError("Backup is not valid: " + "; ".join(problems))
        (self.backup_dir / (time.strftime("%Y%m%d-%H%M%S") + f"-{time.time_ns() % 1000000:06d}__" + rel.replace("/", "__"))).write_bytes(current)
        tmp = path.with_name(path.name + ".pe-tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        self._ast_cache.pop(str(path), None)
        return {"sha": _sha(data), "needs_restart": path.suffix.lower() in {".py", ".html"}}

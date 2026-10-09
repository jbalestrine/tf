"""Source map: answers "which file controls what I see on screen?".

Two sources are combined:
  * an automatic scan of the Flask route table (view function file/line and the
    templates/static files it names), and
  * a hand-edited registry in docs/source_map.json for things routes cannot show
    (logo, nav menu, version, ...).
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any

FILE_REF_RE = re.compile(r"""['"]([\w./\\-]+\.(?:html|py|js|css|svg|json|md))['"]""")
SKIP_ENDPOINTS = {"static"}


class SourceMapError(ValueError):
    pass


class SourceMap:
    def __init__(self, app, project_root: str | Path):
        self.app = app
        self.root = Path(project_root).resolve()
        self.registry_path = self.root / "docs" / "source_map.json"

    # ---------- helpers ----------
    def _rel(self, path: str | Path | None) -> str:
        if not path:
            return ""
        try:
            return Path(path).resolve().relative_to(self.root).as_posix()
        except (ValueError, OSError):
            return str(path)

    def _safe_file(self, rel: str) -> Path:
        candidate = (self.root / rel).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise SourceMapError("Path is outside the project.") from exc
        return candidate

    def _find_line(self, path: Path, anchor: str | None) -> int | None:
        if not anchor or not path.is_file() or path.stat().st_size > 5_000_000:
            return None
        try:
            pattern = re.compile(anchor)
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if pattern.search(line):
                    return number
        except (re.error, OSError):
            return None
        return None

    def _vscode_link(self, rel: str, line: int | None) -> str:
        absolute = (self.root / rel).as_posix()
        return f"vscode://file/{absolute}" + (f":{line}" if line else "")

    # ---------- automatic route scan ----------
    def routes(self) -> list[dict]:
        rows = []
        for rule in self.app.url_map.iter_rules():
            if rule.endpoint in SKIP_ENDPOINTS:
                continue
            view = self.app.view_functions.get(rule.endpoint)
            if view is None:
                continue
            target = inspect.unwrap(view)
            try:
                source_file = inspect.getsourcefile(target)
                lines, start = inspect.getsourcelines(target)
            except (OSError, TypeError):
                source_file, lines, start = None, [], None
            rel = self._rel(source_file)
            referenced = sorted({m.replace("\\", "/") for m in FILE_REF_RE.findall("".join(lines))})
            files = []
            for ref in referenced:
                hit = self._locate(ref)
                if hit:
                    files.append(hit)
            rows.append({
                "url": rule.rule,
                "methods": sorted(rule.methods - {"HEAD", "OPTIONS"}),
                "endpoint": rule.endpoint,
                "file": rel,
                "line": start,
                "link": self._vscode_link(rel, start) if rel and not rel.startswith(("<", "/")) else "",
                "files": files,
                "blueprint": rule.endpoint.split(".")[0] if "." in rule.endpoint else "",
            })
        rows.sort(key=lambda r: (r["url"], r["methods"]))
        seen: dict[tuple, int] = {}
        for row in rows:
            key = (row["url"], tuple(row["methods"]))
            seen[key] = seen.get(key, 0) + 1
        for row in rows:
            row["duplicate"] = seen[(row["url"], tuple(row["methods"]))] > 1
        return rows

    def _locate(self, ref: str) -> str | None:
        for base in (self.root, self.root / "templates", self.root / "static"):
            candidate = base / ref
            if candidate.is_file():
                return self._rel(candidate)
        return None

    def lookup(self, query: str) -> dict:
        """Find the file(s) behind a URL path or a keyword."""
        query = (query or "").strip()
        if not query or len(query) > 200:
            raise SourceMapError("Enter a URL path (e.g. /echo-chat) or a keyword.")
        path = query
        if "://" in path:
            path = "/" + path.split("://", 1)[1].split("/", 1)[-1]
        path = path.split("?", 1)[0].split("#", 1)[0]
        matches = []
        adapter = self.app.url_map.bind("localhost")
        try:
            endpoint, _ = adapter.match(path, method="GET")
            matches = [r for r in self.routes() if r["endpoint"] == endpoint]
        except Exception:  # NotFound / MethodNotAllowed / redirect
            needle = path.lower()
            matches = [r for r in self.routes() if needle in r["url"].lower()][:25]
        needle = query.lower().lstrip("/")
        components = [c for c in self.components() if needle in json.dumps(c).lower()][:10]
        return {"routes": matches, "components": components}

    # ---------- curated registry ----------
    def _load_registry(self) -> dict:
        try:
            doc = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"components": [], "notes": []}
        return doc if isinstance(doc, dict) else {"components": [], "notes": []}

    def components(self) -> list[dict]:
        resolved = []
        for comp in self._load_registry().get("components", []):
            files = []
            for item in comp.get("files", []):
                rel = str(item.get("path", ""))
                try:
                    full = self._safe_file(rel)
                except SourceMapError:
                    continue
                line = self._find_line(full, item.get("anchor"))
                files.append({
                    "path": rel,
                    "role": item.get("role", ""),
                    "exists": full.exists(),
                    "line": line,
                    "link": self._vscode_link(rel, line),
                })
            resolved.append({
                "id": comp.get("id", ""),
                "title": comp.get("title", ""),
                "category": comp.get("category", "Other"),
                "summary": comp.get("summary", ""),
                "how_to_edit": comp.get("how_to_edit", ""),
                "urls": comp.get("urls", []),
                "files": files,
                "warning": comp.get("warning", ""),
            })
        return resolved

    def notes(self) -> list[str]:
        return [str(n) for n in self._load_registry().get("notes", [])]

    def health(self) -> dict:
        missing = [
            {"component": c["id"], "path": f["path"]}
            for c in self.components() for f in c["files"] if not f["exists"]
        ]
        duplicates = sorted({f"{r['url']} {','.join(r['methods'])}" for r in self.routes() if r["duplicate"]})
        return {"missing_files": missing, "duplicate_routes": duplicates}

    def overview(self) -> dict:
        return {
            "components": self.components(),
            "routes": self.routes(),
            "notes": self.notes(),
            "health": self.health(),
        }

    # ---------- markdown export ----------
    def markdown(self) -> str:
        lines = [
            "# MasterChief Source Map",
            "",
            "Generated from `docs/source_map.json` plus the live route table. Edit the JSON (or use /source-map) and regenerate with `python tools/gen_source_map.py`.",
            "",
        ]
        for note in self.notes():
            lines.append(f"> {note}")
        lines.append("")
        by_cat: dict[str, list[dict]] = {}
        for comp in self.components():
            by_cat.setdefault(comp["category"], []).append(comp)
        for category in sorted(by_cat):
            lines += [f"## {category}", ""]
            for comp in by_cat[category]:
                lines += [f"### {comp['title']}", "", comp["summary"], ""]
                if comp["warning"]:
                    lines += [f"**Warning:** {comp['warning']}", ""]
                if comp["how_to_edit"]:
                    lines += [f"**How to edit:** {comp['how_to_edit']}", ""]
                for f in comp["files"]:
                    where = f"`{f['path']}`" + (f" (line {f['line']})" if f["line"] else "")
                    lines.append(f"- {where} - {f['role']}" + ("" if f["exists"] else " **(missing)**"))
                if comp["urls"]:
                    lines.append("- URLs: " + ", ".join(f"`{u}`" for u in comp["urls"]))
                lines.append("")
        lines += ["## All routes", "", "| URL | Methods | File | Line |", "|---|---|---|---|"]
        for r in self.routes():
            lines.append(f"| `{r['url']}` | {','.join(r['methods'])} | `{r['file']}` | {r['line'] or ''} |")
        return "\n".join(lines) + "\n"

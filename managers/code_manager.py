"""Code Manager: read-only analysis of main.py plus blueprint, baseline and size-budget tools.

Nothing in here edits main.py. It reports what is in the file, what each part depends on,
what could move to a template or blueprint, and guards against silently losing routes.
"""
from __future__ import annotations

import ast
import builtins
import inspect
import json
import re
import time
from pathlib import Path

BASELINE_REL = "docs/route_baseline.json"
BUDGET_REL = "docs/main_budget.json"
TEMPLATE_MIN_LINES = 40
BUILTIN_NAMES = set(dir(builtins))
ROUTE_ATTRS = {"route", "get", "post", "put", "delete", "patch"}
MODULE_RE = re.compile(r"^blueprints\.[a-z][a-z0-9_]{1,60}$")


class CodeManagerError(ValueError):
    pass


def _route_info(dec: ast.expr):
    """Return (url, methods) for an @app.route(...) style decorator, else None."""
    if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
            and dec.func.attr in ROUTE_ATTRS and isinstance(dec.func.value, ast.Name)
            and dec.func.value.id == "app"):
        return None
    if not dec.args or not isinstance(dec.args[0], ast.Constant) or not isinstance(dec.args[0].value, str):
        return None
    methods = ["GET"] if dec.func.attr == "route" else [dec.func.attr.upper()]
    for kw in dec.keywords:
        if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple, ast.Set)):
            methods = [e.value.upper() for e in kw.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return dec.args[0].value, sorted(methods)


def _group_of(url: str) -> str:
    parts = [p for p in url.strip("/").split("/") if p]
    if not parts:
        return "/"
    if parts[0] == "api" and len(parts) > 1:
        return f"/api/{parts[1]}"
    return f"/{parts[0]}"


def _local_names(fn: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not fn:
            names.add(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
    return names


def _suggest_file(prefix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", prefix.lower().strip("/")).strip("_") or "home"
    return f"blueprints/{slug}_routes.py"


class CodeManager:
    def __init__(self, app, root: Path):
        self.app = app
        self.root = Path(root)
        self.main_path = self.root / "main.py"
        self._cache: tuple[float, dict] | None = None

    # ---------- main.py analysis ----------
    def analyze(self, force: bool = False) -> dict:
        try:
            mtime = self.main_path.stat().st_mtime
        except OSError as exc:
            raise CodeManagerError(f"Cannot read main.py: {exc}") from exc
        if not force and self._cache and self._cache[0] == mtime:
            return self._cache[1]
        text = self.main_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
        result = self._analyze_tree(tree, text)
        self._cache = (mtime, result)
        return result

    def _analyze_tree(self, tree: ast.Module, text: str) -> dict:
        total_lines = text.count("\n") + 1
        imports: set[str] = set()
        helpers: dict[str, dict] = {}
        values: dict[str, dict] = {}
        templates: dict[str, dict] = {}
        route_funcs: list[ast.FunctionDef] = []
        helper_nodes: dict[str, ast.AST] = {}
        blueprint_regs = []

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    imports.add((alias.asname or alias.name).split(".")[0])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(_route_info(d) for d in node.decorator_list):
                    route_funcs.append(node)
                else:
                    helpers[node.name] = {"line": node.lineno, "lines": node.end_lineno - node.lineno + 1, "kind": "function"}
                    helper_nodes[node.name] = node
            elif isinstance(node, ast.ClassDef):
                helpers[node.name] = {"line": node.lineno, "lines": node.end_lineno - node.lineno + 1, "kind": "class"}
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names = [t.id for t in targets if isinstance(t, ast.Name)]
                span = node.end_lineno - node.lineno + 1
                value = node.value
                for name in names:
                    if span >= TEMPLATE_MIN_LINES and value is not None:
                        plain = isinstance(value, ast.Constant) and isinstance(value.value, str)
                        kind = "plain" if plain else ("f-string" if isinstance(value, ast.JoinedStr) else "computed")
                        templates[name] = {"line": node.lineno, "lines": span, "kind": kind,
                                           "has_jinja": plain and "{%" in value.value or plain and "{{" in value.value}
                    else:
                        values[name] = {"line": node.lineno, "lines": span}
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Attribute) and func.attr == "register_blueprint":
                    blueprint_regs.append(node.lineno)

        def loads(fn_node):
            local = _local_names(fn_node)
            return {n.id for n in ast.walk(fn_node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)} - local - BUILTIN_NAMES

        helper_deps = {name: loads(node) for name, node in helper_nodes.items()}

        def closure(names):
            seen, stack = set(), list(names)
            while stack:
                n = stack.pop()
                if n in seen:
                    continue
                seen.add(n)
                stack.extend(helper_deps.get(n, ()))
            return seen
        groups: dict[str, dict] = {}
        seen_routes: dict[tuple, list[str]] = {}
        for fn in route_funcs:
            local = _local_names(fn)
            used = closure(loads(fn))
            globals_written = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
                               } & {g for stmt in ast.walk(fn) if isinstance(stmt, ast.Global) for g in stmt.names}
            needs_helpers = sorted(used & set(helpers))
            needs_values = sorted(used & set(values))
            needs_templates = sorted(used & set(templates))
            for dec in fn.decorator_list:
                info = _route_info(dec)
                if not info:
                    continue
                url, methods = info
                group = groups.setdefault(_group_of(url), {
                    "prefix": _group_of(url), "routes": [], "helpers": set(), "values": set(), "templates": set(),
                    "imports": set(), "writes_globals": set(), "lines": 0,
                })
                lines = fn.end_lineno - (fn.decorator_list[0].lineno) + 1
                group["routes"].append({"url": url, "methods": methods, "func": fn.name, "line": fn.decorator_list[0].lineno,
                                        "end": fn.end_lineno, "lines": lines})
                group["lines"] += lines
                group["helpers"].update(needs_helpers)
                group["values"].update(needs_values)
                group["templates"].update(needs_templates)
                group["imports"].update(used & imports)
                group["writes_globals"].update(globals_written)
                for m in methods:
                    seen_routes.setdefault((url, m), []).append(fn.name)

        hub_users: dict[str, set] = {}
        for g in groups.values():
            for name in g["helpers"] | g["values"]:
                hub_users.setdefault(name, set()).add(g["prefix"])
        hubs = [{"name": n, "used_by": sorted(u), "kind": "helper" if n in helpers else "value",
                 **(helpers.get(n) or values.get(n))} for n, u in hub_users.items() if len(u) >= 2]
        hubs.sort(key=lambda h: (-len(h["used_by"]), h["name"]))

        template_users: dict[str, set] = {}
        out_groups = []
        for g in groups.values():
            needs = len(g["helpers"]) + len(g["values"])
            difficulty = "easy" if needs <= 3 else "medium" if needs <= 10 else "hard"
            if g["writes_globals"]:
                difficulty = "hard"
            for t in g["templates"]:
                template_users.setdefault(t, set()).add(g["prefix"])
            routes = sorted(g["routes"], key=lambda r: r["line"])
            out_groups.append({
                "prefix": g["prefix"], "route_count": len(routes), "lines": g["lines"],
                "first_line": routes[0]["line"], "last_line": max(r["end"] for r in routes),
                "needs_helpers": sorted(g["helpers"]), "needs_values": sorted(g["values"]),
                "needs_templates": sorted(g["templates"]), "uses_imports": sorted(g["imports"]),
                "writes_globals": sorted(g["writes_globals"]), "difficulty": difficulty,
                "suggested_file": _suggest_file(g["prefix"]),
                "routes": routes,
            })
        out_groups.sort(key=lambda g: (-g["route_count"], g["prefix"]))

        out_templates = []
        for name, t in templates.items():
            safe = t["kind"] == "plain"
            out_templates.append({
                "name": name, **t, "used_by": sorted(template_users.get(name, [])),
                "safe_to_extract": safe,
                "suggested_file": f"templates/{name.lower().removesuffix('_template').removesuffix('_html')}.html" if safe else "",
                "note": "" if safe else "Built with an f-string or expression; needs hand conversion before it can become a file.",
            })
        out_templates.sort(key=lambda t: -t["lines"])

        dupes = []
        for (url, method), funcs in sorted(seen_routes.items()):
            if len(funcs) > 1:
                dupes.append({"url": url, "method": method, "functions": funcs})

        return {
            "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_lines": total_lines, "route_count": sum(g["route_count"] for g in out_groups),
            "helper_count": len(helpers), "template_lines": sum(t["lines"] for t in out_templates),
            "blueprint_registration_lines": blueprint_regs,
            "groups": out_groups, "templates": out_templates, "hubs": hubs[:40],
            "duplicates_within_main": dupes,
            "biggest_functions": sorted(
                ({"name": n, **h} for n, h in helpers.items() if h["kind"] == "function"),
                key=lambda h: -h["lines"])[:10] + [],
            "biggest_routes": sorted(
                ({"func": r["func"], "url": r["url"], "line": r["line"], "lines": r["lines"]}
                 for g in out_groups for r in g["routes"]), key=lambda r: -r["lines"])[:10],
        }

    # ---------- blueprint inventory ----------
    def blueprints(self) -> list[dict]:
        live_by_module = {}
        for name, bp in self.app.blueprints.items():
            live_by_module[getattr(bp, "import_name", "")] = name
        linked = {r["module"] for r in self._linked()}
        live_urls = {(r.rule, m): r for r in self.app.url_map.iter_rules() for m in (r.methods or ()) - {"HEAD", "OPTIONS"}}
        rows = []
        for path in sorted((self.root / "blueprints").glob("*.py")):
            if path.name == "__init__.py":
                continue
            module = f"blueprints.{path.stem}"
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError as exc:
                rows.append({"module": module, "file": f"blueprints/{path.name}", "kind": "error", "error": f"Syntax error line {exc.lineno}",
                             "registered": False, "linked": module in linked, "routes": [], "lines": 0})
                continue
            registered = module in live_by_module
            bp_vars, routes, has_init = {}, [], False
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                    f = node.value.func
                    if (isinstance(f, ast.Name) and f.id == "Blueprint") or (isinstance(f, ast.Attribute) and f.attr == "Blueprint"):
                        prefix = ""
                        for kw in node.value.keywords:
                            if kw.arg == "url_prefix" and isinstance(kw.value, ast.Constant):
                                prefix = str(kw.value.value)
                        for t in node.targets:
                            if isinstance(t, ast.Name):
                                bp_vars[t.id] = prefix
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.name.startswith(("init_", "register_")):
                        has_init = True
                    for dec in node.decorator_list:
                        if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in ROUTE_ATTRS
                                and isinstance(dec.func.value, ast.Name) and dec.func.value.id in bp_vars
                                and dec.args and isinstance(dec.args[0], ast.Constant)):
                            methods = ["GET"]
                            for kw in dec.keywords:
                                if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                                    methods = [e.value.upper() for e in kw.value.elts if isinstance(e, ast.Constant)]
                            full = bp_vars[dec.func.value.id].rstrip("/") + str(dec.args[0].value)
                            existing = (not registered) and any((full, m) in live_urls for m in methods)
                            routes.append({"rule": full, "methods": sorted(methods), "func": node.name, "line": node.lineno,
                                           "url_exists_live": existing})
            kind = "blueprint" if bp_vars else ("init-function" if has_init else "helper")
            rows.append({
                "module": module, "file": f"blueprints/{path.name}", "kind": kind, "registered": registered,
                "linked": module in linked, "prefixes": sorted(set(bp_vars.values())), "routes": sorted(routes, key=lambda r: r["rule"]),
                "colliding": sum(1 for r in routes if r["url_exists_live"]), "lines": len(path.read_text(encoding="utf-8", errors="replace").splitlines()),
                "error": "",
            })
        return rows

    def _linked(self) -> list[dict]:
        from managers.feature_loader import read_linked
        return read_linked(self.root)

    # ---------- move main.py routes into a live blueprint ----------
    def retire_module(self, module: str, dry_run: bool = True, timeout: int = 240) -> dict:
        """Remove main.py route functions that a live blueprint already serves.

        Removed code is archived (never deleted), main.py is backed up first, and the change is
        rolled back automatically if any baseline route goes missing.
        """
        import shutil
        import subprocess
        import sys
        if not MODULE_RE.match(module or ""):
            raise CodeManagerError("Module must look like blueprints.some_name.")
        names = [n for n, b in self.app.blueprints.items() if getattr(b, "import_name", "") == module]
        if not names:
            raise CodeManagerError("That blueprint is not live yet. Link it, restart, then try again.")
        prefixes = tuple(n + "." for n in names)
        served = set()
        for rule in self.app.url_map.iter_rules():
            if rule.endpoint.startswith(prefixes):
                for m in (rule.methods or set()) - {"HEAD", "OPTIONS"}:
                    served.add((rule.rule, m))

        raw = self.main_path.read_bytes().decode("utf-8")
        tree = ast.parse(raw)
        lines = re.findall(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+", raw)
        movable, skipped = [], []
        for fn in tree.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            infos = [i for i in (_route_info(d) for d in fn.decorator_list) if i]
            if not infos:
                continue
            pairs = {(u, m) for u, ms in infos for m in ms}
            if not any(p in served for p in pairs):
                continue
            first = min(d.lineno for d in fn.decorator_list)
            row = {"func": fn.name, "start": first, "end": fn.end_lineno, "lines": fn.end_lineno - first + 1,
                   "routes": sorted(f"{m} {u}" for u, m in pairs)}
            if len(infos) != len(fn.decorator_list):
                skipped.append({**row, "reason": "has other decorators (kept in main.py)"})
            elif not pairs <= served:
                skipped.append({**row, "reason": "blueprint does not serve every URL/method of this function (kept)"})
            else:
                movable.append(row)

        def mentions(name: str) -> bool:
            pattern = re.compile(r"\b" + re.escape(name) + r"\b")
            outside = "".join(l for i, l in enumerate(lines, 1) if not any(r["start"] <= i <= r["end"] for r in movable if r["func"] == name))
            if pattern.search(outside):
                return True
            for folder in ("templates",):
                for f in (self.root / folder).rglob("*"):
                    if f.suffix in {".html", ".py", ".js"} and f.is_file() and pattern.search(f.read_text(encoding="utf-8", errors="ignore")):
                        return True
            return False

        keep = []
        for row in movable:
            if mentions(row["func"]):
                skipped.append({**row, "reason": "name is referenced elsewhere (url_for or a call), kept in main.py"})
            else:
                keep.append(row)
        movable = keep
        report = {"module": module, "dry_run": dry_run, "move": movable, "skipped": skipped,
                  "lines_removed": sum(r["lines"] for r in movable), "applied": False, "backup": "", "archive": ""}
        if dry_run or not movable:
            return report

        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup_dir = self.root / "data" / "main_py_backups"
        archive_dir = self.root / "data" / "retired_code"
        backup_dir.mkdir(parents=True, exist_ok=True)
        archive_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"main.py.{stamp}.before-{module.split('.')[1]}"
        shutil.copy2(self.main_path, backup)
        drop = set()
        for r in movable:
            drop.update(range(r["start"], r["end"] + 1))
        archive = archive_dir / f"{module.split('.')[1]}.{stamp}.py"
        chunks = ["".join(lines[r["start"] - 1:r["end"]]) for r in sorted(movable, key=lambda r: r["start"])]
        archive.write_text(f"# Retired from main.py on {stamp}; now served by {module}.\n# Kept for reference - restore by pasting back into main.py.\n\n" + "\n\n".join(chunks), encoding="utf-8")
        new_text = "".join(l for i, l in enumerate(lines, 1) if i not in drop)
        new_text = re.sub(r"(\r?\n){4,}", "\n\n\n", new_text)
        try:
            ast.parse(new_text)
        except SyntaxError as exc:
            raise CodeManagerError(f"Edit would break main.py ({exc}); nothing was changed.") from exc
        self.main_path.write_bytes(new_text.encode("utf-8"))
        script = ("import json,sys;from pathlib import Path;import main;"
                  "from managers.code_manager import CodeManager;"
                  "r=CodeManager(main.app,Path('.').resolve()).compare_baseline();"
                  "print('RESULT:'+json.dumps({'missing':r['missing']}))")
        failure = ""
        try:
            proc = subprocess.run([sys.executable, "-c", script], cwd=self.root, capture_output=True, text=True, timeout=timeout)
            line = next((l for l in proc.stdout.splitlines() if l.startswith("RESULT:")), "")
            missing = json.loads(line[7:])["missing"] if line else None
            if missing is None:
                failure = "main.py failed to import: " + (proc.stderr or proc.stdout)[-400:]
            elif missing:
                failure = f"{len(missing)} routes would go missing, e.g. {missing[0]['rule']}"
        except Exception as exc:
            failure = f"verification failed: {exc}"
        if failure:
            shutil.copy2(backup, self.main_path)
            report.update(error=failure + " main.py was restored from backup.")
            return report
        self._cache = None
        report.update(applied=True, backup=backup.relative_to(self.root).as_posix(), archive=archive.relative_to(self.root).as_posix())
        return report

    # ---------- move whole pages (route + template) into a blueprint ----------
    PAGE_MARKER = "{% block content %}{% endblock %}"
    STRIPS = {('{% extends "base.html" %}', ""), ("{% block content %}", ""), ("{% endblock %}", "")}

    def _page_candidates(self) -> list[dict]:
        text = self.main_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
        consts = {}
        for n in tree.body:
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                for tg in n.targets:
                    if isinstance(tg, ast.Name):
                        consts[tg.id] = n
        rows = []
        for fn in tree.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            infos = [i for i in (_route_info(d) for d in fn.decorator_list) if i]
            if not infos:
                continue
            others = [d for d in fn.decorator_list if not _route_info(d)]
            found = self._page_template_name(fn)
            if not found or found[0] not in consts:
                continue
            name, chain = found
            perm = None
            ok = True
            for d in others:
                if (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "requires_permission"
                        and len(d.args) == 1 and isinstance(d.args[0], ast.Constant)):
                    perm = d.args[0].value
                else:
                    ok = False
            node = consts[name]
            rows.append({
                "func": fn.name, "url": infos[0][0], "template": name, "template_lines": node.end_lineno - node.lineno + 1,
                "permission": perm, "eligible": ok, "reason": "" if ok else "has decorators other than requires_permission",
                "start": min(d.lineno for d in fn.decorator_list), "end": fn.end_lineno,
                "tpl_start": node.lineno, "tpl_end": node.end_lineno, "tpl_value": node.value.value,
                "routes": [(u, m) for u, ms in infos for m in ms],
                "chain": chain,
            })
        return rows

    @staticmethod
    def _page_template_name(fn: ast.FunctionDef) -> tuple[str, bool] | None:
        """Matches: return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}', NAME), request=request, get_flashed_messages=get_flashed_messages)"""
        body = [s for s in fn.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
        if len(body) != 1 or not isinstance(body[0], ast.Return) or not isinstance(body[0].value, ast.Call):
            return None
        call = body[0].value
        if not (isinstance(call.func, ast.Name) and call.func.id == "render_template_string" and len(call.args) == 1):
            return None
        if {k.arg for k in call.keywords} - {"request", "get_flashed_messages"}:
            return None
        rep = call.args[0]
        if not (isinstance(rep, ast.Call) and isinstance(rep.func, ast.Attribute) and rep.func.attr == "replace"
                and isinstance(rep.func.value, ast.Name) and rep.func.value.id == "HTML_TEMPLATE" and len(rep.args) == 2):
            return None
        first, second = rep.args
        if not (isinstance(first, ast.Constant) and first.value == CodeManager.PAGE_MARKER):
            return None
        chain = False
        while isinstance(second, ast.Call) and isinstance(second.func, ast.Attribute) and second.func.attr == "replace":
            if len(second.args) != 2 or not all(isinstance(a, ast.Constant) for a in second.args):
                return None
            if (second.args[0].value, second.args[1].value) not in CodeManager.STRIPS:
                return None
            second = second.func.value
            chain = True
        return (second.id, chain) if isinstance(second, ast.Name) else None

    def pages(self) -> list[dict]:
        """Pages still defined in main.py that can be moved whole into a blueprint."""
        out = []
        for r in self._page_candidates():
            out.append({k: r[k] for k in ("func", "url", "template", "template_lines", "permission", "eligible", "reason")})
        return sorted(out, key=lambda r: -r["template_lines"])

    def _verify_fresh_app(self, timeout: int = 240) -> str:
        """Start a fresh interpreter, import main and compare against the baseline. Returns '' when OK."""
        import subprocess
        import sys
        script = ("import json;from pathlib import Path;import main;"
                  "from managers.code_manager import CodeManager;"
                  "r=CodeManager(main.app,Path('.').resolve()).compare_baseline();"
                  "print('RESULT:'+json.dumps({'missing':r['missing']}))")
        try:
            proc = subprocess.run([sys.executable, "-c", script], cwd=self.root, capture_output=True, text=True, timeout=timeout)
            line = next((l for l in proc.stdout.splitlines() if l.startswith("RESULT:")), "")
            missing = json.loads(line[7:])["missing"] if line else None
        except Exception as exc:
            return f"verification failed: {exc}"
        if missing is None:
            return "the app failed to start: " + (proc.stderr or proc.stdout)[-400:]
        if missing:
            return f"{len(missing)} routes would go missing, e.g. {missing[0]['rule']}"
        return ""

    def isolate_page(self, func: str, module: str, dry_run: bool = True) -> dict:
        """Move a page route and its HTML template out of main.py into a blueprint and templates/<name>.html."""
        import shutil
        if not MODULE_RE.match(module or ""):
            raise CodeManagerError("Choose a blueprint from the list.")
        bp_path = self.root / "blueprints" / (module.split(".", 1)[1] + ".py")
        if not bp_path.is_file():
            raise CodeManagerError("That blueprint file does not exist.")
        if not any(getattr(b, "import_name", "") == module for b in self.app.blueprints.values()):
            raise CodeManagerError("That blueprint is not live yet. Link it and restart first.")
        cand = next((c for c in self._page_candidates() if c["func"] == func), None)
        if cand is None:
            raise CodeManagerError("That page is not in main.py in a movable form.")
        if not cand["eligible"]:
            raise CodeManagerError("Not moved: " + cand["reason"] + ".")
        raw = self.main_path.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        main_text = raw.replace("\r\n", "\n")
        lines = main_text.split("\n")
        outside = "\n".join(l for i, l in enumerate(lines, 1)
                           if not (cand["start"] <= i <= cand["end"] or cand["tpl_start"] <= i <= cand["tpl_end"]))
        for name in (cand["func"], cand["template"]):
            if re.search(r"\b" + re.escape(name) + r"\b", outside):
                raise CodeManagerError(f"Not moved: {name} is still referenced elsewhere in main.py.")
        slug = re.sub(r"(_template|_html|_page)$", "", cand["template"].lower())
        tpl_rel = f"templates/{slug}.html"
        tpl_path = self.root / tpl_rel
        bp_text = bp_path.read_text(encoding="utf-8")
        bp_tree = ast.parse(bp_text)
        bp_var = next((tg.id for n in bp_tree.body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                       and getattr(n.value.func, "id", getattr(n.value.func, "attr", "")) == "Blueprint"
                       for tg in n.targets if isinstance(tg, ast.Name)), None)
        if not bp_var:
            raise CodeManagerError("Could not find the Blueprint object in that file.")
        if tpl_path.exists():
            raise CodeManagerError(f"{tpl_rel} already exists; nothing was changed.")
        if any(isinstance(n, ast.FunctionDef) and n.name == cand["func"] for n in ast.walk(bp_tree)):
            raise CodeManagerError(f"{cand['func']} already exists in {module}.")
        report = {"func": func, "url": cand["url"], "module": module, "template_file": tpl_rel, "template_lines": cand["template_lines"],
                  "lines_removed": (cand["end"] - cand["start"] + 1) + (cand["tpl_end"] - cand["tpl_start"] + 1),
                  "dry_run": dry_run, "applied": False, "backup": ""}
        if dry_run:
            return report
        perm_dec = f"@requires_permission({cand['permission']!r})\n" if cand["permission"] else ""
        block = (f"\n\n# Moved from main.py by Code Manager. Markup: {tpl_rel}\n"
                 f"@{bp_var}.route({cand['url']!r})\n{perm_dec}def {cand['func']}():\n"
                 "    from pathlib import Path as _P\n"
                 "    from flask import current_app as _app, get_flashed_messages as _flash, render_template_string as _render, request as _req\n"
                 f"    content = (_P(_app.root_path) / {tpl_rel!r}).read_text(encoding='utf-8')\n"
                 "    marker = '{% block content %}{% endblock %}'\n"
                 "    layout = _app.config.get('_layout_template', marker)\n"
                 "    return _render(layout.replace(marker, content), request=_req, get_flashed_messages=_flash)\n")
        header = "from auth_module import requires_permission\n" if cand["permission"] and "requires_permission" not in bp_text else ""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup_dir = self.root / "data" / "main_py_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"main.py.{stamp}.before-page-{cand['func']}"
        bp_backup = backup_dir / f"{bp_path.name}.{stamp}.before-page-{cand['func']}"
        shutil.copy2(self.main_path, backup)
        shutil.copy2(bp_path, bp_backup)
        drop = set(range(cand["start"], cand["end"] + 1)) | set(range(cand["tpl_start"], cand["tpl_end"] + 1))
        new_main = re.sub(r"\n{4,}", "\n\n\n", "\n".join(l for i, l in enumerate(lines, 1) if i not in drop))
        new_bp = bp_text.rstrip("\n") + "\n" + block
        if header:
            new_bp = header + new_bp
        try:
            ast.parse(new_main)
            ast.parse(new_bp)
        except SyntaxError as exc:
            raise CodeManagerError(f"Edit would produce invalid code ({exc}); nothing was changed.") from exc
        tpl_text = cand["tpl_value"]
        if cand["chain"]:
            for old, new_ in sorted(self.STRIPS):
                tpl_text = tpl_text.replace(old, new_)
        tpl_path.write_text(tpl_text, encoding="utf-8", newline="\n")
        bp_path.write_text(new_bp, encoding="utf-8")
        self.main_path.write_bytes((new_main.replace("\n", "\r\n") if crlf else new_main).encode("utf-8"))
        failure = self._verify_fresh_app()
        if failure:
            shutil.copy2(backup, self.main_path)
            shutil.copy2(bp_backup, bp_path)
            tpl_path.unlink(missing_ok=True)
            report["error"] = failure + ". Everything was restored from backup."
            return report
        self._cache = None
        report.update(applied=True, backup=backup.relative_to(self.root).as_posix())
        return report

    def create_blueprint(self, slug: str) -> dict:
        """Create an empty blueprint file and link it so pages and routes can be moved into it."""
        from managers.feature_loader import link_blueprint
        slug = str(slug or "").strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", slug):
            raise CodeManagerError("Use lowercase letters, digits and underscores (e.g. okta).")
        path = self.root / "blueprints" / f"{slug}_routes.py"
        if path.exists():
            raise CodeManagerError(f"blueprints/{slug}_routes.py already exists.")
        path.write_text(f"from flask import Blueprint\n\n{slug}_bp = Blueprint('{slug}_routes', __name__)\n", encoding="utf-8")
        link_blueprint(self.root, f"blueprints.{slug}_routes", "created by Code Manager")
        return {"module": f"blueprints.{slug}_routes", "file": f"blueprints/{slug}_routes.py"}

    # ---------- route baseline (loss guard) ----------
    def current_routes(self) -> list[dict]:
        rows = []
        for rule in self.app.url_map.iter_rules():
            if rule.endpoint == "static":
                continue
            view = self.app.view_functions.get(rule.endpoint)
            try:
                src = self._rel(inspect.getsourcefile(inspect.unwrap(view))) if view else ""
            except (OSError, TypeError):
                src = ""
            for m in sorted((rule.methods or set()) - {"HEAD", "OPTIONS"}):
                rows.append({"rule": rule.rule, "method": m, "endpoint": rule.endpoint, "file": src})
        rows.sort(key=lambda r: (r["rule"], r["method"], r["endpoint"]))
        return rows

    def _rel(self, path) -> str:
        if not path:
            return ""
        try:
            return Path(path).resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return Path(path).name

    def save_baseline(self) -> dict:
        rows = self.current_routes()
        path = self.root / BASELINE_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        doc = {"saved": time.strftime("%Y-%m-%d %H:%M:%S"), "count": len(rows), "routes": rows}
        path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
        return {"saved": doc["saved"], "count": len(rows)}

    def compare_baseline(self) -> dict:
        try:
            doc = json.loads((self.root / BASELINE_REL).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"has_baseline": False, "missing": [], "new": [], "moved": [], "saved": "", "count": 0}
        old = {(r["rule"], r["method"]): r for r in doc.get("routes", [])}
        now = {(r["rule"], r["method"]): r for r in self.current_routes()}
        missing = [{"rule": k[0], "method": k[1], "file": old[k]["file"]} for k in sorted(old.keys() - now.keys())]
        new = [{"rule": k[0], "method": k[1], "file": now[k]["file"]} for k in sorted(now.keys() - old.keys())]
        moved = [{"rule": k[0], "method": k[1], "from": old[k]["file"], "to": now[k]["file"]}
                 for k in sorted(old.keys() & now.keys()) if old[k]["file"] != now[k]["file"]]
        return {"has_baseline": True, "saved": doc.get("saved", ""), "count": doc.get("count", 0),
                "missing": missing, "new": new, "moved": moved}

    # ---------- size budget ----------
    def budget(self) -> dict:
        analysis = self.analyze()
        try:
            doc = json.loads((self.root / BUDGET_REL).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            doc = {}
        max_lines, max_routes = doc.get("max_lines"), doc.get("max_routes")
        lines, routes = analysis["total_lines"], analysis["route_count"]
        over = []
        if isinstance(max_lines, int) and lines > max_lines:
            over.append(f"main.py has {lines} lines; the limit is {max_lines}.")
        if isinstance(max_routes, int) and routes > max_routes:
            over.append(f"main.py defines {routes} routes; the limit is {max_routes}.")
        return {"lines": lines, "routes": routes, "max_lines": max_lines, "max_routes": max_routes,
                "ok": not over, "problems": over, "configured": bool(doc)}

    def set_budget(self, ratchet: bool = False, max_lines: int | None = None, max_routes: int | None = None) -> dict:
        analysis = self.analyze(force=True)
        path = self.root / BUDGET_REL
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            doc = {}
        if ratchet:
            max_lines = min(doc.get("max_lines", 10 ** 9), analysis["total_lines"] + 50)
            max_routes = min(doc.get("max_routes", 10 ** 9), analysis["route_count"])
        for key, val in (("max_lines", max_lines), ("max_routes", max_routes)):
            if not isinstance(val, int) or val < 1:
                raise CodeManagerError(f"{key} must be a positive whole number.")
        doc.update(max_lines=max_lines, max_routes=max_routes,
                   note="New features go in app_features/<name>/. Lower these numbers as main.py shrinks.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        return self.budget()

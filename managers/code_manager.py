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

"""
MasterChief System Diagnostics Engine
======================================
AST-based full-repo scanner that powers the /sys/diagnostics admin page.
Extracts routes, function call graphs, imports, orphans, and issues.
"""

import ast
import os
import re
import time
import json
from pathlib import Path
from typing import Dict, List, Set, Any, Optional

WORKSPACE = Path(__file__).parent

SKIP_DIRS: Set[str] = {
    '.git', '__pycache__', 'venv', '.venv', 'env', '.env',
    'node_modules', '.claude', 'dist', 'build', '.pytest_cache',
    'eggs', '.eggs', '.tox', 'htmlcov', '.mypy_cache', '.ruff_cache',
    'site-packages', 'lib', 'lib64', 'Lib', 'Scripts', 'bin',
    'include', 'Include', 'share',
    # noise: uploaded addon archives, backups, old experiments
    'data', 'backups', 'platform.bak', 'webapp', 'irc_flask_superapp_final', 'mc_platform',
}

PYTHON_EXT   = '.py'
TEMPLATE_EXT = {'.html', '.htm', '.jinja', '.jinja2'}
STATIC_EXT   = {'.css', '.js', '.ts', '.jsx', '.tsx'}
DATA_EXT     = {'.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.env', '.txt', '.md'}
IMAGE_EXT    = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf'}


# ─────────────────────────────────────────────────────────────
#  AST Visitor
# ─────────────────────────────────────────────────────────────

class _Visitor(ast.NodeVisitor):
    """Single-pass AST visitor: extracts routes, functions, calls, imports."""

    def __init__(self, rel_path: str):
        self.rel_path = rel_path
        self.routes:    List[Dict] = []
        self.functions: List[Dict] = []
        self.imports:   List[Dict] = []
        self._fn_stack: List[Dict] = []   # nested function support
        self._route_handlers: Set[str] = set()
        self._used_names: Set[str] = set()   # all names referenced anywhere

    # ── imports ──────────────────────────────────────────────

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append({
                'type': 'import',
                'module': alias.name,
                'alias': alias.asname,
                'line': node.lineno,
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        self.imports.append({
            'type': 'from',
            'module': node.module or '',
            'names': [a.name for a in node.names],
            'line': node.lineno,
        })
        self.generic_visit(node)

    # ── functions / routes ───────────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef):
        route_info: Optional[Dict] = None
        dec_strings: List[str] = []

        for dec in node.decorator_list:
            try:
                ds = ast.unparse(dec)
            except Exception:
                ds = ''
            dec_strings.append(ds)

            # Match @app.route / @bp.route / @login_required etc.
            m = re.search(
                r'(?:\w+\.)?route\(\s*[\'"]([^\'"]+)[\'"]'
                r'(?:.*?methods\s*=\s*(\[[^\]]*\]))?',
                ds,
            )
            if m:
                try:
                    methods = ast.literal_eval(m.group(2)) if m.group(2) else ['GET']
                except Exception:
                    methods = ['GET']
                route_info = {
                    'path': m.group(1),
                    'methods': methods,
                    'handler': node.name,
                    'line': node.lineno,
                    'file': self.rel_path,
                }
                self._route_handlers.add(node.name)

        # Push a call-collection frame
        frame: Dict = {'name': node.name, 'calls': [], 'line': node.lineno}
        self._fn_stack.append(frame)
        self.generic_visit(node)
        self._fn_stack.pop()

        fn_calls = list(dict.fromkeys(frame['calls']))  # dedup, preserve order
        docstring = ast.get_docstring(node)

        fn_info: Dict = {
            'name': node.name,
            'line': node.lineno,
            'end_line': getattr(node, 'end_lineno', node.lineno),
            'calls': fn_calls,
            'decorators': dec_strings,
            'is_route_handler': bool(route_info),
            'docstring': docstring or '',
            'file': self.rel_path,
        }
        self.functions.append(fn_info)

        if route_info:
            route_info['end_line']  = fn_info['end_line']
            route_info['calls']     = fn_calls
            route_info['docstring'] = docstring or ''
            route_info['decorators'] = dec_strings
            self.routes.append(route_info)

    visit_AsyncFunctionDef = visit_FunctionDef

    # ── call tracking ────────────────────────────────────────

    def visit_Call(self, node: ast.Call):
        if self._fn_stack:
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name:
                self._fn_stack[-1]['calls'].append(name)
                self._used_names.add(name)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load):
            self._used_names.add(node.id)
        self.generic_visit(node)


# ─────────────────────────────────────────────────────────────
#  File collection
# ─────────────────────────────────────────────────────────────

def _rel(path: Path, root: Path = WORKSPACE) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


# Paths that indicate we've entered an installed-package tree
_PACKAGE_MARKERS = {'pyvenv.cfg', 'pip', 'setuptools'}


def _is_ignored_directory(name: str) -> bool:
    normalized = name.casefold()
    if normalized in {entry.casefold() for entry in SKIP_DIRS}:
        return True
    return bool(re.fullmatch(r'\.?venv(?:[-_.]?[a-z0-9]+)?', normalized))


def _collect_files(root: Path = WORKSPACE) -> List[Dict]:
    results: List[Dict] = []
    root_path = Path(root).resolve()
    for dirpath, dirnames, filenames in os.walk(root_path):
        dp = Path(dirpath)
        # Skip any directory that looks like a venv or installed-package tree
        dirnames[:] = [
            d for d in dirnames
            if not _is_ignored_directory(d)
            and not (dp / d / 'pyvenv.cfg').exists()   # venv root
            and not (dp / d / 'site-packages').exists() # another venv pattern
        ]
        for fname in filenames:
            fpath = dp / fname
            try:
                stat = fpath.stat()
                ext  = fpath.suffix.lower()
                results.append({
                    'abs_path': str(fpath),
                    'rel_path': _rel(fpath, root_path),
                    'name':     fname,
                    'ext':      ext,
                    'size':     stat.st_size,
                    'modified': stat.st_mtime,
                    'status':   'unknown',
                })
            except OSError:
                pass
    return results


# ─────────────────────────────────────────────────────────────
#  Python file parser
# ─────────────────────────────────────────────────────────────

def _parse_python_file(path: Path, rel_path: str) -> Dict[str, Any]:
    try:
        src = path.read_text(encoding='utf-8', errors='replace')
    except OSError as e:
        return {'error': str(e), 'routes': [], 'functions': [], 'imports': [], 'lines': 0, 'size': 0}

    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as e:
        return {
            'error': f'SyntaxError line {e.lineno}: {e.msg}',
            'routes': [], 'functions': [], 'imports': [],
            'lines': src.count('\n') + 1,
            'size':  path.stat().st_size,
        }

    visitor = _Visitor(rel_path)
    visitor.visit(tree)

    try:
        stat = path.stat()
        size = stat.st_size
    except OSError:
        size = 0

    return {
        'routes':    visitor.routes,
        'functions': visitor.functions,
        'imports':   visitor.imports,
        'used_names': list(visitor._used_names),
        'lines': src.count('\n') + 1,
        'size':  size,
    }


# ─────────────────────────────────────────────────────────────
#  File tree builder
# ─────────────────────────────────────────────────────────────

def _build_file_tree(files: List[Dict]) -> Dict:
    root: Dict = {'name': 'masterchief', 'type': 'dir', 'children': {}, 'files': []}

    for f in files:
        parts = f['rel_path'].split('/')
        node = root
        for part in parts[:-1]:
            if part not in node['children']:
                node['children'][part] = {'name': part, 'type': 'dir', 'children': {}, 'files': []}
            node = node['children'][part]
        node['files'].append({
            'name':     f['name'],
            'rel_path': f['rel_path'],
            'ext':      f['ext'],
            'size':     f['size'],
            'status':   f['status'],
        })

    def _to_list(node: Dict) -> Dict:
        children = [_to_list(c) for c in node['children'].values()]
        children.sort(key=lambda x: (0 if x['type'] == 'dir' else 1, x['name'].lower()))
        return {
            'name':     node['name'],
            'type':     'dir',
            'children': children,
            'files':    sorted(node['files'], key=lambda f: f['name'].lower()),
        }

    return _to_list(root)


# ─────────────────────────────────────────────────────────────
#  Graph builder
# ─────────────────────────────────────────────────────────────

def _build_graph(
    all_routes: List[Dict],
    all_functions: Dict[str, Dict],
    parsed: Dict[str, Dict],
) -> Dict:
    nodes: List[Dict] = []
    edges: List[Dict] = []
    node_ids: Set[str] = set()

    def add_node(nid: str, label: Any, ntype: str, file: str = '',
                 line: int = 0, status: str = 'active', group: str = '') -> None:
        if nid not in node_ids:
            node_ids.add(nid)
            label_text = str(label) if label is not None else ''
            nodes.append({
                'id':     nid,
                'label':  label_text[:48],   # truncate long labels
                'type':   ntype,
                'file':   file,
                'line':   line,
                'status': status,
                'group':  group,
            })

    def add_edge(src: str, tgt: str, etype: str = 'calls', status: str = 'active') -> None:
        if src in node_ids and tgt in node_ids:
            edges.append({'source': src, 'target': tgt, 'type': etype, 'status': status})

    # ── File-level nodes (for high-zoom overview) ──
    file_nodes: Set[str] = set()
    for rel_path, data in parsed.items():
        fid = f'file:{rel_path}'
        if fid not in file_nodes:
            file_nodes.add(fid)
            n_routes = len(data.get('routes', []))
            n_fns    = len(data.get('functions', []))
            add_node(fid, rel_path.split('/')[-1],
                     'file', rel_path, 0, 'active', 'files')

    # ── Route → Handler ──
    route_handlers: Set[str] = set()
    for route in all_routes:
        rid  = f"route:{route['handler']}"
        fid  = f"fn:{route['handler']}"
        label = f"{','.join(route['methods'])} {route['path']}"
        add_node(rid, label, 'route', route.get('file', ''), route.get('line', 0), 'active', 'routes')
        add_node(fid, route['handler'], 'function', route.get('file', ''), route.get('line', 0), 'active', 'handlers')
        add_edge(rid, fid, 'calls')
        route_handlers.add(route['handler'])

        # Handler → called functions
        for call in route.get('calls', [])[:12]:  # cap fan-out at 12 per route
            cid = f"fn:{call}"
            if call in all_functions:
                fn = all_functions[call]
                add_node(cid, call, 'function', fn.get('file', ''), fn.get('line', 0), 'active', 'utils')
            elif call in ('jsonify', 'render_template', 'render_template_string',
                          'redirect', 'url_for', 'send_file', 'send_from_directory',
                          'abort', 'make_response', 'request', 'flash'):
                add_node(cid, call, 'external', 'flask', 0, 'active', 'flask')
            else:
                add_node(cid, call, 'function', '', 0, 'unknown', 'utils')
            add_edge(fid, cid, 'calls')

    # ── Orphan functions ──
    all_called: Set[str] = set()
    for data in parsed.values():
        for fn in data.get('functions', []):
            all_called.update(fn.get('calls', []))

    for fname, fn in all_functions.items():
        fid = f"fn:{fname}"
        if fid not in node_ids:
            status = 'orphan' if fname not in all_called and fname not in route_handlers else 'active'
            if status == 'orphan' and not fname.startswith('_'):
                add_node(fid, fname, 'function', fn.get('file', ''), fn.get('line', 0), 'orphan', 'orphans')

    # ── File dependency edges (imports) ──
    for rel_path, data in parsed.items():
        src_fid = f'file:{rel_path}'
        for imp in data.get('imports', []):
            mod = imp.get('module', '') or ''
            candidate = WORKSPACE / (mod.replace('.', '/') + '.py')
            if candidate.exists():
                tgt_fid = f"file:{_rel(candidate)}"
                if tgt_fid in node_ids:
                    add_edge(src_fid, tgt_fid, 'imports', 'active')

    return {'nodes': nodes, 'edges': edges}


# ─────────────────────────────────────────────────────────────
#  Issues builder
# ─────────────────────────────────────────────────────────────

_AUTH_DECORATORS = {
    'login_required', 'require_auth', 'jwt_required', 'token_required',
    'auth_required', 'requires_auth', 'check_auth', 'admin_required',
}
_PUBLIC_PATHS = {'/static', '/favicon', '/health', '/ping', '/sys/api'}


def _build_issues(
    parsed: Dict[str, Dict],
    all_routes: List[Dict],
    orphan_fns: List[Dict],
    all_files: List[Dict],
) -> List[Dict]:
    issues: List[Dict] = []

    # Syntax errors
    for rel_path, data in parsed.items():
        if 'error' in data:
            issues.append({
                'severity': 'error',
                'type': 'syntax_error',
                'file': rel_path,
                'line': 0,
                'message': data['error'],
                'suggestion': 'Fix syntax before the app will load this file correctly.',
            })

    # Routes without error handling
    for route in all_routes:
        calls = set(route.get('calls', []))
        decs  = ' '.join(route.get('decorators', []))
        has_auth = bool(calls & _AUTH_DECORATORS) or bool(
            re.search('|'.join(_AUTH_DECORATORS), decs)
        )
        path = route.get('path', '')
        is_public = any(path.startswith(p) for p in _PUBLIC_PATHS)

        if not has_auth and not is_public:
            issues.append({
                'severity': 'warning',
                'type': 'no_auth',
                'file': route.get('file', ''),
                'line': route.get('line', 0),
                'message': f"Route `{path}` has no auth check",
                'suggestion': 'Add @login_required or a similar auth decorator.',
            })

    # Dead / orphan functions
    for fn in orphan_fns[:30]:
        issues.append({
            'severity': 'info',
            'type': 'dead_code',
            'file': fn.get('file', ''),
            'line': fn.get('line', 0),
            'message': f"Function `{fn['name']}` is defined but never called",
            'suggestion': 'Remove, rename to _private, or confirm it is an entry point.',
        })

    # Very large files
    for f in all_files:
        if f['ext'] == '.py' and f.get('size', 0) > 400_000:
            issues.append({
                'severity': 'warning',
                'type': 'large_file',
                'file': f['rel_path'],
                'line': 0,
                'message': f"File is {f['size'] // 1024} KB — consider splitting into modules",
                'suggestion': 'Extract route groups into separate Blueprint files.',
            })

    # Duplicate route paths
    seen_paths: Dict[str, str] = {}
    for route in all_routes:
        key = f"{','.join(sorted(route.get('methods', ['GET'])))}{route.get('path', '')}"
        if key in seen_paths:
            issues.append({
                'severity': 'error',
                'type': 'duplicate_route',
                'file': route.get('file', ''),
                'line': route.get('line', 0),
                'message': f"Duplicate route `{route.get('path','')}` — also defined in {seen_paths[key]}",
                'suggestion': 'Remove or rename one of the duplicate route definitions.',
            })
        else:
            seen_paths[key] = route.get('file', '')

    # Orphan Python files (not imported, not main.py)
    for f in all_files:
        if f['ext'] == '.py' and f['status'] == 'orphan' and f['name'] != 'main.py':
            issues.append({
                'severity': 'info',
                'type': 'orphan_file',
                'file': f['rel_path'],
                'line': 0,
                'message': f"`{f['rel_path']}` is not imported by any other file",
                'suggestion': 'Verify this file is still needed. If not, archive or delete it.',
            })

    return issues


# ─────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────

def scan_workspace() -> Dict[str, Any]:
    """Full workspace scan. Returns structured data for the diagnostics UI."""
    t0 = time.time()

    all_files = _collect_files()
    python_files = [f for f in all_files if f['ext'] == PYTHON_EXT]

    parsed: Dict[str, Dict] = {}
    for finfo in python_files:
        try:
            data = _parse_python_file(Path(finfo['abs_path']), finfo['rel_path'])
        except Exception as exc:
            data = {'error': str(exc), 'routes': [], 'functions': [], 'imports': [],
                    'lines': 0, 'size': 0}
        parsed[finfo['rel_path']] = data

    # Aggregate across all files
    all_defined: Dict[str, Dict] = {}
    all_routes:  List[Dict]      = []
    all_called:  Set[str]        = set()
    local_imported: Set[str]     = set()

    for rel_path, data in parsed.items():
        for fn in data.get('functions', []):
            all_defined[fn['name']] = fn
            all_called.update(fn.get('calls', []))
        for r in data.get('routes', []):
            all_routes.append(r)
        for imp in data.get('imports', []):
            mod = imp.get('module', '') or ''
            for candidate in [
                WORKSPACE / (mod.replace('.', '/') + '.py'),
                WORKSPACE / mod.replace('.', '/') / '__init__.py',
            ]:
                if candidate.exists():
                    local_imported.add(_rel(candidate))

    # Set file statuses
    # Directories that contain runtime-loaded modules (dynamic imports, managers, plugins)
    # — never mark files inside these as orphans via static analysis alone.
    PROTECTED_DIRS = {
        'managers', 'blueprints', 'features', 'utils', 'tf_wizard', 'echo',
        'templates', 'addons', 'scripts', 'handlers', 'modules', 'plugins',
        'services', 'integrations', 'middleware', 'models', 'migrations',
        'tasks', 'workers', 'api', 'auth',
    }

    active_set = {'main.py'} | local_imported
    for f in all_files:
        r   = f['rel_path']
        ext = f['ext']
        # Any file whose first path component is a protected dir is treated as active
        first_dir = r.split('/')[0] if '/' in r else ''
        in_protected = first_dir in PROTECTED_DIRS
        # Any __init__.py is always active
        is_init = f['name'] == '__init__.py'
        if r in active_set or in_protected or is_init:
            f['status'] = 'active'
        elif ext in TEMPLATE_EXT:
            f['status'] = 'template'
        elif ext in STATIC_EXT:
            f['status'] = 'static'
        elif ext in IMAGE_EXT:
            f['status'] = 'asset'
        elif ext in DATA_EXT:
            f['status'] = 'data'
        elif ext == PYTHON_EXT:
            f['status'] = 'orphan'
        else:
            f['status'] = 'other'

    route_handlers = {r['handler'] for r in all_routes}
    orphan_fns = [
        fn for name, fn in all_defined.items()
        if name not in all_called
        and name not in route_handlers
        and not name.startswith('_')
        and name not in {'main', 'create_app', 'init', 'setup', 'teardown',
                         'conftest', 'pytest_configure'}
    ]

    issues   = _build_issues(parsed, all_routes, orphan_fns, all_files)
    graph    = _build_graph(all_routes, all_defined, parsed)
    file_tree = _build_file_tree(all_files)

    # Per-file summary for table view
    file_summary = []
    for finfo in python_files:
        data = parsed.get(finfo['rel_path'], {})
        file_summary.append({
            'rel_path':  finfo['rel_path'],
            'name':      finfo['name'],
            'size':      finfo['size'],
            'lines':     data.get('lines', 0),
            'routes':    len(data.get('routes', [])),
            'functions': len(data.get('functions', [])),
            'imports':   len(data.get('imports', [])),
            'status':    finfo['status'],
            'has_error': 'error' in data,
        })
    file_summary.sort(key=lambda x: (-x['routes'], x['rel_path']))

    elapsed = time.time() - t0

    return {
        'scan_time': round(elapsed, 3),
        'summary': {
            'total_files':       len(all_files),
            'python_files':      len(python_files),
            'routes':            len(all_routes),
            'functions':         len(all_defined),
            'orphan_functions':  len(orphan_fns),
            'issues':            len(issues),
            'errors':            sum(1 for i in issues if i['severity'] == 'error'),
            'warnings':          sum(1 for i in issues if i['severity'] == 'warning'),
        },
        'routes':           all_routes[:300],
        'orphan_functions': orphan_fns[:60],
        'issues':           issues,
        'graph':            graph,
        'file_tree':        file_tree,
        'files':            file_summary,
    }


def get_file_content(rel_path: str, line: int = 0) -> Dict[str, Any]:
    """Return file content for the inspector panel. Line is 1-based."""
    try:
        path = (WORKSPACE / rel_path).resolve()
        path.relative_to(WORKSPACE.resolve())   # security guard
        content = path.read_text(encoding='utf-8', errors='replace')
        lines   = content.splitlines()
        return {
            'content': content,
            'lines':   len(lines),
            'path':    rel_path,
            'focus_line': line,
        }
    except Exception as exc:
        return {'error': str(exc)}


# ─────────────────────────────────────────────────────────────
#  Scan cache  (TTL = 60 s; busted by ?force=1)
# ─────────────────────────────────────────────────────────────
import threading as _threading

_cache_lock   = _threading.Lock()
_cache_result: Dict = {}
_cache_ts:     float = 0.0
_CACHE_TTL     = 60.0     # seconds


def get_cached_scan(force: bool = False) -> Dict[str, Any]:
    """Return scan results, using cache when fresh enough."""
    global _cache_result, _cache_ts
    with _cache_lock:
        age = time.time() - _cache_ts
        if not force and _cache_result and age < _CACHE_TTL:
            return dict(_cache_result, _cached=True, _age=round(age, 1))
        result = scan_workspace()
        _cache_result = result
        _cache_ts = time.time()
        return result


# ─────────────────────────────────────────────────────────────
#  Orphan Sweep  (incremental safe cleanup)
# ─────────────────────────────────────────────────────────────
import queue   as _queue
import shutil  as _shutil
import urllib.request as _urlreq
import urllib.error   as _urlerr

ARCHIVE_DIR = WORKSPACE / 'backups' / 'archived'

# Sweep state  (only one sweep runs at a time)
_sweep_lock    = _threading.Lock()
_sweep_queue:  _queue.Queue = _queue.Queue()
_sweep_active: bool = False
_sweep_abort:  bool = False


def _health_check(urls: List[str], timeout: float = 8.0):
    """Hit every URL in *urls*.  Returns (True, 'OK') or (False, reason)."""
    for url in urls:
        try:
            req = _urlreq.Request(url, headers={'User-Agent': 'MCHealthCheck/1.0'})
            with _urlreq.urlopen(req, timeout=timeout) as resp:
                if resp.status >= 400:
                    return False, f'{url} → HTTP {resp.status}'
        except _urlerr.HTTPError as exc:
            return False, f'{url} → HTTP {exc.code}'
        except Exception as exc:
            return False, f'{url} → {exc}'
    return True, 'OK'


def _emit(event_type: str, **kwargs):
    """Push a typed event dict onto the sweep queue."""
    _sweep_queue.put({'type': event_type, 'ts': round(time.time(), 3), **kwargs})


def run_orphan_sweep(
    orphan_paths: List[str],
    health_urls:  List[str],
    dry_run:      bool = False,
) -> None:
    """
    Background-thread worker for the orphan sweep.

    Phase 1 — Backup all orphan files to ARCHIVE_DIR (safety net).
    Phase 2 — Move each file out one at a time.
              Hit health_urls; on any failure: restore the file, mark skipped.
              Log every outcome via SSE events.
    """
    global _sweep_active, _sweep_abort, _cache_ts

    results: Dict[str, List] = {'archived': [], 'skipped': [], 'errors': []}
    total = len(orphan_paths)
    _emit('start', total=total, dry_run=dry_run, health_urls=health_urls)

    # ── Phase 1: backup ───────────────────────────────────────
    _emit('phase', phase='backup', message=f'Backing up {total} files to backups/archived/ …')
    if not dry_run:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    for rel in orphan_paths:
        src  = WORKSPACE / rel
        slug = rel.replace('/', '_').replace('\\', '_')
        dest = ARCHIVE_DIR / slug
        if dry_run:
            _emit('backup', file=rel, dest=f'backups/archived/{slug}', dry_run=True)
        else:
            try:
                if src.exists():
                    _shutil.copy2(str(src), str(dest))
                    _emit('backup', file=rel, dest=f'backups/archived/{slug}')
                else:
                    _emit('backup_skip', file=rel, reason='not found')
            except Exception as exc:
                _emit('backup_error', file=rel, error=str(exc))
                results['errors'].append({'file': rel, 'error': f'backup failed: {exc}'})

    # ── Phase 2: incremental sweep ────────────────────────────
    _emit('phase', phase='sweep', message='Starting incremental sweep…')

    for i, rel in enumerate(orphan_paths):
        if _sweep_abort:
            _emit('aborted', completed=i, total=total, results=results)
            break

        src = WORKSPACE / rel
        if not src.exists():
            _emit('skip', file=rel, reason='already missing', index=i + 1, total=total)
            results['skipped'].append(rel)
            continue

        _emit('moving', file=rel, index=i + 1, total=total)

        # ── Dry-run path ──────────────────────────────────────
        if dry_run:
            ok, msg = _health_check(health_urls)
            action  = 'would-archive' if ok else 'would-skip'
            _emit('result', file=rel, action=action, health_ok=ok,
                  health_msg=msg, index=i + 1, total=total)
            (results['archived'] if ok else results['skipped']).append(rel)
            continue

        # ── Live path ─────────────────────────────────────────
        slug     = rel.replace('/', '_').replace('\\', '_')
        tmp_dest = ARCHIVE_DIR / ('_sweep_' + slug)

        try:
            _shutil.move(str(src), str(tmp_dest))
        except Exception as exc:
            _emit('error', file=rel, error=str(exc), index=i + 1, total=total)
            results['errors'].append({'file': rel, 'error': str(exc)})
            continue

        time.sleep(0.6)   # let any reload/settle settle

        ok, health_msg = _health_check(health_urls)

        if ok:
            # Promote to final archive name (backup copy already exists from phase 1)
            final = ARCHIVE_DIR / slug
            try:
                if not final.exists():
                    tmp_dest.rename(final)
                else:
                    tmp_dest.unlink(missing_ok=True)   # backup copy is the keeper
            except Exception:
                pass
            _emit('result', file=rel, action='archived', health_ok=True,
                  health_msg=health_msg, index=i + 1, total=total)
            results['archived'].append(rel)
            # Invalidate scan cache so next /sys/api/scan reflects reality
            with _cache_lock:
                _cache_ts = 0.0
        else:
            # Restore: try moving tmp back first, fall back to backup copy
            restored = False
            try:
                _shutil.move(str(tmp_dest), str(src))
                restored = True
            except Exception:
                backup = ARCHIVE_DIR / slug
                try:
                    _shutil.copy2(str(backup), str(src))
                    restored = True
                except Exception:
                    pass
            _emit('result', file=rel, action='restored', health_ok=False,
                  health_msg=health_msg, restored=restored, index=i + 1, total=total)
            results['skipped'].append(rel)

    _emit('done', results=results, total=total)

    with _sweep_lock:
        _sweep_active = False


def start_sweep(
    orphan_paths: List[str],
    health_urls:  List[str],
    dry_run:      bool = False,
) -> bool:
    """Kick off a sweep in a daemon thread.  Returns False if one is already running."""
    global _sweep_active, _sweep_abort
    with _sweep_lock:
        if _sweep_active:
            return False
        _sweep_active = True
        _sweep_abort  = False
    # Drain stale events
    while not _sweep_queue.empty():
        try:
            _sweep_queue.get_nowait()
        except _queue.Empty:
            break
    _threading.Thread(
        target=run_orphan_sweep, args=(orphan_paths, health_urls, dry_run),
        daemon=True, name='orphan-sweep',
    ).start()
    return True


def abort_sweep():
    """Signal the running sweep to stop after the current file."""
    global _sweep_abort
    _sweep_abort = True


def sweep_events(timeout: float = 600.0):
    """Generator that yields SSE-formatted lines from the sweep queue."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            event = _sweep_queue.get(timeout=1.0)
            yield f"data: {json.dumps(event)}\n\n"
            if event.get('type') in ('done', 'aborted'):
                break
        except _queue.Empty:
            yield 'data: {"type":"heartbeat"}\n\n'


def is_sweep_running() -> bool:
    return _sweep_active

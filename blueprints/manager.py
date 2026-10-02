import json
import html
import re
import subprocess
import sys
import threading
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, render_template_string, request, send_file

from utils.feature_flags import MASTER_MENU_ITEMS, is_feature_enabled, load_feature_flags, save_feature_flags


manager_bp = Blueprint('manager', __name__)


def _root() -> Path:
    return Path(current_app.root_path).resolve()


def _manager_tasks_file() -> Path:
    return _root() / 'data' / 'manager_tasks.json'


def _manager_tests_file() -> Path:
    return _root() / 'data' / 'manager_last_test.json'


def _load_manager_tasks():
    try:
        tasks_file = _manager_tasks_file()
        if not tasks_file.exists():
            return []
        return json.loads(tasks_file.read_text(encoding='utf-8') or '[]')
    except Exception:
        current_app.logger.exception('Failed to load manager tasks')
        return []


def _normalize_manager_tags(raw_tags):
    if isinstance(raw_tags, list):
        cleaned = []
        for tag in raw_tags:
            t = str(tag or '').strip()
            if t and t not in cleaned:
                cleaned.append(t)
        return cleaned
    if isinstance(raw_tags, str):
        return _normalize_manager_tags(raw_tags.split(','))
    return []


def _normalize_manager_task(task):
    t = dict(task or {})
    t['module'] = str(t.get('module') or '').strip()
    t['feature'] = str(t.get('feature') or '').strip()
    t['workflow_item'] = str(t.get('workflow_item') or '').strip()
    t['tags'] = _normalize_manager_tags(t.get('tags'))
    return t


def _save_manager_tasks(tasks):
    try:
        tasks_file = _manager_tasks_file()
        tasks_file.parent.mkdir(parents=True, exist_ok=True)
        tasks_file.write_text(json.dumps(tasks, indent=2), encoding='utf-8')
        return True
    except Exception:
        current_app.logger.exception('Failed to save manager tasks')
        return False


def _load_flags():
    return load_feature_flags(_root(), logger=current_app.logger)


def _save_flags(flags):
    return save_feature_flags(_root(), flags, logger=current_app.logger)


def _is_feature_enabled(flag_name):
    return is_feature_enabled(_root(), flag_name, logger=current_app.logger)


def _route_sample_defaults() -> dict:
        return {
                'module_name': 'module-system-v3',
                'filepath': 'README.md',
                'config_file': 'config.json',
                'setup_script': 'install.sh',
                'subpath': 'index.html',
                'exec_id': 'sample',
                'id': 'sample',
                'job_id': 'sample',
                'path': 'README.md',
        }


def _sample_url(rule_str: str) -> str:
        defaults = _route_sample_defaults()

        def repl(match):
                inner = match.group(1)
                name = inner.split(':', 1)[-1]
                return defaults.get(name, 'sample')

        return re.sub(r'<([^>]+)>', repl, rule_str)


def _safe_workspace_path(raw_path: str):
        if not raw_path:
                return None
        base = _root()
        candidate = Path(raw_path)
        if not candidate.is_absolute():
                candidate = (base / candidate).resolve()
        else:
                candidate = candidate.resolve()
        try:
                candidate.relative_to(base)
                return candidate
        except Exception:
                return None


def _catalog_files_list():
    base = _root()
    include_ext = {'.py', '.html', '.js', '.css', '.json', '.md', '.txt', '.yml', '.yaml', '.ps1', '.sh', '.ini', '.cfg'}
    exclude_dirs = {'.git', '__pycache__', 'venv', 'venv310', 'node_modules', '.mypy_cache', '.pytest_cache', 'build', 'dist'}
    files = []
    for p in base.rglob('*'):
        try:
            if any(part in exclude_dirs for part in p.parts):
                continue
            if p.is_file() and p.suffix.lower() in include_ext:
                rel = p.relative_to(base).as_posix()
                files.append({'path': rel, 'size_bytes': p.stat().st_size, 'abs': p})
        except Exception:
            continue
    files.sort(key=lambda f: f['path'])
    return files


def _path_kind(rel_path: str) -> str:
    p = rel_path.lower()
    if p.startswith('blueprints/'):
        return 'blueprint'
    if p.startswith('templates/') or p.endswith('.html'):
        return 'ui'
    if p.startswith('utils/'):
        return 'utility'
    if p.startswith('data/'):
        return 'data'
    if p.endswith('.py'):
        return 'python'
    if p.endswith(('.js', '.css')):
        return 'frontend'
    return 'asset'


def _resolve_reference_path(ref: str, src_path: str, all_paths: set, basenames: dict):
    normalized = ref.strip().strip('"\'').replace('\\', '/').lstrip('./')
    if not normalized:
        return None

    if normalized in all_paths:
        return normalized

    src_parent = Path(src_path).parent.as_posix()
    if src_parent and src_parent != '.':
        candidate = Path(src_parent, normalized).as_posix()
        candidate = str(Path(candidate)).replace('\\', '/')
        if candidate in all_paths:
            return candidate

    base = Path(normalized).name
    matches = basenames.get(base, [])
    if len(matches) == 1:
        return matches[0]
    return None


def _analyze_catalog_connections():
    files = _catalog_files_list()
    file_paths = [f['path'] for f in files]
    all_paths = set(file_paths)
    basenames = defaultdict(list)
    for p in file_paths:
        basenames[Path(p).name].append(p)

    inbound = defaultdict(set)
    outbound = defaultdict(set)
    route_hits = defaultdict(set)
    broken_refs = []
    broken_seen = set()
    core_inventory_ext = {'.py', '.ps1', '.sh', '.js', '.json', '.tf'}

    route_paths = set(rule.rule for rule in current_app.url_map.iter_rules())
    file_ref_pattern = re.compile(r'([A-Za-z0-9_./\\\- ]+\.(?:py|html?|js|css|json|md|txt|yml|yaml|ps1|sh|ini|cfg))', re.IGNORECASE)
    route_ref_pattern = re.compile(r'(["\'])/(?!/)([A-Za-z0-9_./\-]+)\1')

    for entry in files:
        src = entry['path']
        p = entry['abs']
        if entry['size_bytes'] > 1_500_000:
            continue

        try:
            text = p.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue

        # Generic filename references in scripts/config/docs.
        for m in file_ref_pattern.finditer(text):
            target = _resolve_reference_path(m.group(1), src, all_paths, basenames)
            if not target or target == src:
                continue
            outbound[src].add(target)
            inbound[target].add(src)

        # Python imports to local modules.
        if src.endswith('.py'):
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue

                m_from = re.match(r'^from\s+([a-zA-Z0-9_\.]+)\s+import\s+', stripped)
                m_import = re.match(r'^import\s+([a-zA-Z0-9_\.,\s]+)', stripped)
                modules = []
                if m_from:
                    modules.append(m_from.group(1).strip())
                elif m_import:
                    raw = m_import.group(1)
                    modules.extend(part.strip() for part in raw.split(',') if part.strip())

                for mod in modules:
                    mod = mod.split(' as ')[0].strip()
                    rel_mod = mod.replace('.', '/')
                    py_file = f'{rel_mod}.py'
                    pkg_init = f'{rel_mod}/__init__.py'
                    target = None
                    if py_file in all_paths:
                        target = py_file
                    elif pkg_init in all_paths:
                        target = pkg_init
                    if target and target != src:
                        outbound[src].add(target)
                        inbound[target].add(src)

        # Route href/fetch references from frontend/templates.
        if src.endswith(('.html', '.js', '.py')):
            for rm in route_ref_pattern.finditer(text):
                route = '/' + rm.group(2)
                if route in route_paths:
                    route_hits[src].add(route)
                else:
                    if route.startswith('/api/') or route.count('/') <= 3:
                        # Suppress known false-positive patterns:
                        # OS filesystem paths, Python module paths, generic single-segment prefixes.
                        _noise_prefixes = ('/var/', '/opt/', '/etc/', '/usr/', '/proc/', '/tmp/',
                                           '/.', '/run/', '/sys/fs/')
                        _noise_exact = {'/messages', '/api', '/sys', '/hello', '/api/',
                                        '/login', '/roku', '/web-ide', '/changes', '/changes/'}
                        if any(route.startswith(p) for p in _noise_prefixes):
                            pass  # skip
                        elif route in _noise_exact:
                            pass  # skip
                        elif '.' in route.split('/')[-1] and not route.startswith('/api/'):
                            pass  # filename extension in last segment → file path, not route
                        else:
                            key = (src, route)
                            if key not in broken_seen:
                                broken_seen.add(key)
                                broken_refs.append({'source': src, 'route': route})

    results = []
    orphan_paths = []
    for entry in files:
        rel = entry['path']
        in_count = len(inbound.get(rel, set()))
        out_count = len(outbound.get(rel, set()))
        routes_count = len(route_hits.get(rel, set()))
        kind = _path_kind(rel)
        candidate_orphan = in_count == 0 and out_count == 0 and routes_count == 0
        suffix = Path(rel).suffix.lower()

        # Treat top-level docs and readmes as non-orphan informational artifacts.
        if rel.lower().endswith('.md') or rel.lower().startswith('data/'):
            candidate_orphan = False

        # CI/CD configs, GitHub Actions workflows — connected by design to repository lifecycle.
        if candidate_orphan and (rel.startswith('.github/') or rel.startswith('.git')):
            candidate_orphan = False

        # Pure output/log/debug text files are not app modules.
        if candidate_orphan and suffix == '.txt':
            candidate_orphan = False

        # Known package/tool artifact subdirectories (chocolatey packages, sub-repos, generated output).
        _artifact_dirs = ('echomasterchiefx/', 'masterchiefx/', 'generated_code/', 'irc_flask_superapp_final/')
        if candidate_orphan and any(rel.startswith(d) for d in _artifact_dirs):
            candidate_orphan = False

        # Files that are directly available through Core Scripts inventory are connected by design.
        if candidate_orphan and suffix in core_inventory_ext and not rel.startswith('.github/'):
            candidate_orphan = False

        related = sorted((inbound.get(rel, set()) | outbound.get(rel, set())))[:8]
        suggestions = []
        if candidate_orphan:
            if suffix in {'.py', '.ps1', '.sh', '.js'}:
                suggestions.append('Expose via /core-scripts and run dry-check to validate runtime.')
                suggestions.append('If reusable, import as addon module via /api/core-scripts/import-module.')
            if rel.startswith('blueprints/') and suffix == '.py':
                suggestions.append('Register this blueprint in main.py app.register_blueprint(...).')
            if rel.startswith('templates/') or suffix == '.html':
                suggestions.append('Add/repair route mapping in blueprints/ui_pages.py or feature routes.')
                suggestions.append('Add menu entry in utils/feature_flags.py MASTER_MENU_ITEMS if user-facing.')
            if rel.startswith('utils/') and suffix == '.py':
                suggestions.append('Import from active blueprint/service where this utility should be consumed.')
            if not suggestions:
                suggestions.append('Review intended owner module and add explicit import, route, or catalog link.')
        row = {
            'path': rel,
            'size_bytes': entry['size_bytes'],
            'kind': kind,
            'inbound_refs': in_count,
            'outbound_refs': out_count,
            'route_refs': routes_count,
            'orphan': bool(candidate_orphan),
            'related': related,
            'suggestions': suggestions,
        }
        if row['orphan']:
            orphan_paths.append(rel)
        results.append(row)

    results.sort(key=lambda r: r['path'])
    broken_refs = sorted(broken_refs, key=lambda r: (r['source'], r['route']))[:250]

    return {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'totals': {
            'files': len(results),
            'orphans': len(orphan_paths),
            'broken_route_refs': len(broken_refs),
        },
        'files': results,
        'orphans': orphan_paths,
        'broken_route_refs': broken_refs,
    }


@manager_bp.route('/site-map')
def site_map_page():
        if not _is_feature_enabled('work_catalog'):
                return ('<h2>Work Catalog is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)

        template = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>MasterChief Site Map</title>
    <style>
        body{margin:0;background:#0b1220;color:#dbeafe;font-family:Arial,Helvetica,sans-serif}
        .wrap{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;padding:16px}
        .card{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:12px;min-height:70vh}
        .title{font-size:18px;color:#7dd3fc;margin-bottom:10px}
        input{width:100%;padding:9px;border-radius:8px;border:1px solid #334155;background:#0f172a;color:#e2e8f0}
        .list{margin-top:10px;max-height:72vh;overflow:auto}
        .row{padding:8px;border-bottom:1px solid #1f2937}
        .row a{color:#93c5fd;text-decoration:none}
        .meta{font-size:12px;color:#94a3b8}
        .warn{color:#fca5a5}
        .ok{color:#86efac}
        .suggestions{margin:3px 0 0 10px;padding:0;list-style:none;border-left:2px solid #334155}
        .suggestions li{padding:2px 6px;font-size:11px;color:#94a3b8}
        .suggestions li::before{content:"→ ";color:#38bdf8}
        .top{padding:12px 16px;background:#111827;border-bottom:1px solid #1f2937;display:flex;justify-content:space-between;align-items:center}
        .top a{color:#93c5fd;text-decoration:none}
        @media(max-width:1500px){.wrap{grid-template-columns:1fr 1fr}}
        @media(max-width:1100px){.wrap{grid-template-columns:1fr}}
    </style>
</head>
<body>
    <div class="top">
        <div><strong>MasterChief Unified Site Map</strong> - routes, pages, modules, scripts</div>
        <a href="/master-menu">Back to Master Menu</a>
    </div>
    <div class="wrap">
        <div class="card">
            <div class="title">All Routes</div>
            <input id="routeFilter" placeholder="Filter routes or endpoints...">
            <div id="routes" class="list"></div>
        </div>
        <div class="card">
            <div class="title">All Workspace Files</div>
            <input id="fileFilter" placeholder="Filter files...">
            <div id="files" class="list"></div>
        </div>
        <div class="card">
            <div class="title">Integration Analysis</div>
            <input id="analysisFilter" placeholder="Filter orphan or broken refs...">
            <div id="analysisSummary" class="meta"></div>
            <div id="analysis" class="list"></div>
        </div>
    </div>
    <script>
        let ROUTES=[];
        let FILES=[];
        let ANALYSIS=[];
        let BROKEN=[];

        function renderRoutes(){
            const q=(document.getElementById('routeFilter').value||'').toLowerCase();
            const el=document.getElementById('routes');
            el.innerHTML='';
            ROUTES.filter(r=>!q||r.rule.toLowerCase().includes(q)||r.endpoint.toLowerCase().includes(q)).forEach(r=>{
                const d=document.createElement('div'); d.className='row';
                d.innerHTML=`<a href="${r.sample_url}" target="_blank">${r.rule}</a><div class="meta">${r.endpoint} | ${r.methods.join(', ')}</div>`;
                el.appendChild(d);
            });
        }

        function renderFiles(){
            const q=(document.getElementById('fileFilter').value||'').toLowerCase();
            const el=document.getElementById('files');
            el.innerHTML='';
            FILES.filter(f=>!q||f.path.toLowerCase().includes(q)).forEach(f=>{
                const d=document.createElement('div'); d.className='row';
                d.innerHTML=`<a href="/catalog/file?path=${encodeURIComponent(f.path)}" target="_blank">${f.path}</a><div class="meta">${f.size_bytes} bytes</div>`;
                el.appendChild(d);
            });
        }

        function renderAnalysis(){
            const q=(document.getElementById('analysisFilter').value||'').toLowerCase();
            const el=document.getElementById('analysis');
            el.innerHTML='';

            const orphanRows = ANALYSIS.filter(f=>f.orphan).filter(f=>!q||f.path.toLowerCase().includes(q));
            const brokenRows = BROKEN.filter(b=>!q||b.source.toLowerCase().includes(q)||b.route.toLowerCase().includes(q));

            orphanRows.forEach(f=>{
                const d=document.createElement('div'); d.className='row';
                const related = (f.related||[]).slice(0,3).map(r=>`<a href="/catalog/file?path=${encodeURIComponent(r)}" target="_blank">${r}</a>`).join(', ');
                const sugs = (f.suggestions||[]).map(s=>`<li>${s}</li>`).join('');
                d.innerHTML=`<div class="warn"><strong>Orphan:</strong> <a href="/catalog/file?path=${encodeURIComponent(f.path)}" target="_blank">${f.path}</a></div><div class="meta">kind=${f.kind} | in=${f.inbound_refs} out=${f.outbound_refs} routes=${f.route_refs}${related?` | related: ${related}`:''}</div>${sugs?`<ul class="suggestions">${sugs}</ul>`:''}` ;
                el.appendChild(d);
            });

            brokenRows.forEach(b=>{
                const d=document.createElement('div'); d.className='row';
                d.innerHTML=`<div class="warn"><strong>Broken Route Ref:</strong> ${b.route}</div><div class="meta">source: <a href="/catalog/file?path=${encodeURIComponent(b.source)}" target="_blank">${b.source}</a></div>`;
                el.appendChild(d);
            });

            if(!orphanRows.length && !brokenRows.length){
                const d=document.createElement('div'); d.className='row';
                d.innerHTML='<div class="ok"><strong>No visible integration gaps for current filter.</strong></div>';
                el.appendChild(d);
            }
        }

        fetch('/api/catalog/routes').then(r=>r.json()).then(j=>{ ROUTES=j.routes||[]; renderRoutes(); });
        fetch('/api/catalog/files').then(r=>r.json()).then(j=>{ FILES=j.files||[]; renderFiles(); });
        fetch('/api/catalog/analysis').then(r=>r.json()).then(j=>{
            ANALYSIS=j.files||[];
            BROKEN=j.broken_route_refs||[];
            const t=j.totals||{};
            document.getElementById('analysisSummary').innerHTML=`files=${t.files||0} | orphans=<span class="warn">${t.orphans||0}</span> | broken-route-refs=<span class="warn">${t.broken_route_refs||0}</span>`;
            renderAnalysis();
        });
        document.getElementById('routeFilter').addEventListener('input',renderRoutes);
        document.getElementById('fileFilter').addEventListener('input',renderFiles);
        document.getElementById('analysisFilter').addEventListener('input',renderAnalysis);
    </script>
</body>
</html>
"""
        return render_template_string(template)


@manager_bp.route('/api/catalog/routes')
def api_catalog_routes():
        routes = []
        for rule in sorted(current_app.url_map.iter_rules(), key=lambda r: r.rule):
                methods = sorted(m for m in rule.methods if m not in {'HEAD', 'OPTIONS'})
                routes.append({
                        'rule': rule.rule,
                        'endpoint': rule.endpoint,
                        'methods': methods,
                        'sample_url': _sample_url(rule.rule),
                })
        return jsonify({'routes': routes})


@manager_bp.route('/api/catalog/files')
def api_catalog_files():
    files = [{'path': f['path'], 'size_bytes': f['size_bytes']} for f in _catalog_files_list()]
    return jsonify({'files': files})


@manager_bp.route('/api/catalog/analysis')
def api_catalog_analysis():
    return jsonify(_analyze_catalog_connections())


@manager_bp.route('/catalog/file')
def catalog_file_view():
        raw = request.args.get('path', '')
        mode = request.args.get('mode', 'view')
        p = _safe_workspace_path(raw)
        if not p or not p.exists() or not p.is_file():
                return ('File not found', 404)

        if mode == 'download':
                return send_file(str(p), as_attachment=True)

        suffix = p.suffix.lower()
        if mode == 'render' and suffix in {'.html', '.htm'}:
                return p.read_text(encoding='utf-8', errors='replace'), 200, {'Content-Type': 'text/html; charset=utf-8'}

        text = p.read_text(encoding='utf-8', errors='replace')
        rel = p.relative_to(_root()).as_posix()
        html_page = f"""
<!doctype html>
<html>
<head><meta charset='utf-8'><title>{html.escape(rel)}</title>
<style>
body{{font-family:Consolas,monospace;background:#0b1220;color:#dbeafe;margin:0}}
.top{{padding:10px 14px;background:#111827;border-bottom:1px solid #1f2937}}
a{{color:#93c5fd;text-decoration:none;margin-right:14px}}
pre{{margin:0;padding:14px;white-space:pre-wrap;word-wrap:break-word}}
</style></head>
<body>
<div class='top'>
    <a href='/site-map'>Site Map</a>
    <a href='/catalog/file?path={html.escape(rel)}&mode=download'>Download</a>
    <a href='/catalog/file?path={html.escape(rel)}&mode=render'>Render HTML</a>
    <span>{html.escape(rel)}</span>
</div>
<pre>{html.escape(text)}</pre>
</body></html>
"""
        return html_page


@manager_bp.route('/manager')
def manager_dashboard():
    if not _is_feature_enabled('manager_portal'):
        return ('<h2>Manager Portal is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)
    return render_template('manager_portal.html')


@manager_bp.route('/api/manager/tasks', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_manager_tasks():
    try:
        if request.method == 'GET':
            return jsonify([_normalize_manager_task(t) for t in _load_manager_tasks()])

        data_in = request.get_json(silent=True) or {}
        tasks = _load_manager_tasks()

        if request.method == 'POST':
            new = {
                'id': str(uuid.uuid4()),
                'title': data_in.get('title') or 'Untitled',
                'description': data_in.get('description') or '',
                'assignee': data_in.get('assignee') or '',
                'module': (data_in.get('module') or '').strip(),
                'feature': (data_in.get('feature') or '').strip(),
                'workflow_item': (data_in.get('workflow_item') or '').strip(),
                'tags': _normalize_manager_tags(data_in.get('tags')),
                'priority': data_in.get('priority') or 'medium',
                'status': data_in.get('status') or 'todo',
                'created_at': datetime.utcnow().isoformat(),
            }
            tasks.append(new)
            _save_manager_tasks(tasks)
            return jsonify(new)

        if request.method == 'PUT':
            tid = data_in.get('id')
            if not tid:
                return jsonify({'error': 'id required'}), 400

            updated = False
            for task in tasks:
                if task.get('id') == tid:
                    for key in ('title', 'description', 'assignee', 'module', 'feature', 'workflow_item', 'priority', 'status'):
                        if key in data_in:
                            task[key] = data_in[key]
                    if 'tags' in data_in:
                        task['tags'] = _normalize_manager_tags(data_in.get('tags'))

                    normalized = _normalize_manager_task(task)
                    task['module'] = normalized['module']
                    task['feature'] = normalized['feature']
                    task['workflow_item'] = normalized['workflow_item']
                    task['tags'] = normalized['tags']
                    task['updated_at'] = datetime.utcnow().isoformat()
                    updated = True
                    break

            if not updated:
                return jsonify({'error': 'task not found'}), 404

            _save_manager_tasks(tasks)
            return jsonify({'ok': True})

        if request.method == 'DELETE':
            tid = request.args.get('id')
            if not tid:
                return jsonify({'error': 'id required'}), 400

            tasks = [t for t in tasks if t.get('id') != tid]
            _save_manager_tasks(tasks)
            return jsonify({'ok': True})
    except Exception as exc:
        current_app.logger.exception('Manager tasks error')
        return jsonify({'error': str(exc)}), 500


@manager_bp.route('/master-menu')
def master_menu_page():
    if not _is_feature_enabled('master_menu'):
        return ('<h2>Master Menu is disabled by feature flag.</h2>', 503)

    grouped = {}
    for item in MASTER_MENU_ITEMS:
        grouped.setdefault(item['focus'], []).append(item)
    return render_template('master_menu.html', grouped=grouped, flags=_load_flags())


@manager_bp.route('/api/manager/feature_flags', methods=['GET', 'PUT'])
def api_manager_feature_flags():
    try:
        if request.method == 'GET':
            return jsonify(_load_flags())

        data_in = request.get_json(silent=True) or {}
        incoming = data_in.get('flags', data_in)
        if not isinstance(incoming, dict):
            return jsonify({'error': 'flags object required'}), 400

        flags = _load_flags()
        for key, value in incoming.items():
            flags[str(key)] = bool(value)

        if not _save_flags(flags):
            return jsonify({'error': 'failed to persist flags'}), 500

        return jsonify({'ok': True, 'flags': flags})
    except Exception as exc:
        current_app.logger.exception('Feature flags error')
        return jsonify({'error': str(exc)}), 500


@manager_bp.route('/api/manager/models', methods=['GET'])
def api_manager_models():
    try:
        models_dir = Path.cwd() / 'models'
        models = []
        if models_dir.exists():
            for model_path in sorted(models_dir.glob('*')):
                if model_path.is_file():
                    models.append(str(model_path.relative_to(Path.cwd())))

        default = None
        cfg = _root() / 'data' / 'echo_model.json'
        if cfg.exists():
            try:
                default = json.loads(cfg.read_text(encoding='utf-8')).get('model')
                if default and default.startswith(str(Path.cwd())):
                    default = str(Path(default).relative_to(Path.cwd()))
            except Exception:
                current_app.logger.exception('Failed reading default model')

        return jsonify({'models': models, 'default': default})
    except Exception as exc:
        current_app.logger.exception('Failed to list models')
        return jsonify({'error': str(exc)}), 500


@manager_bp.route('/api/manager/models/preload', methods=['POST'])
def api_manager_models_preload():
    try:
        data_in = request.get_json(silent=True) or {}
        model = data_in.get('model')
        if not model:
            return jsonify({'error': 'model required'}), 400

        model_path = Path(model)
        if not model_path.is_absolute():
            model_path = Path.cwd() / model
        if not model_path.exists():
            return jsonify({'error': 'model not found', 'path': str(model_path)}), 404

        cfg = _root() / 'data' / 'echo_model.json'
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps({'model': str(model_path)}), encoding='utf-8')

        return jsonify({'ok': True, 'model': str(model_path)})
    except Exception as exc:
        current_app.logger.exception('Failed to set default model')
        return jsonify({'error': str(exc)}), 500


def _run_tests_background():
    try:
        tests_file = _manager_tests_file()
        tests_file.parent.mkdir(parents=True, exist_ok=True)
        start = datetime.utcnow().isoformat()
        tests_file.write_text(json.dumps({'running': True, 'started_at': start}), encoding='utf-8')

        cmd = [sys.executable, '-m', 'pytest', '-q']
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(_root()))
        out, _ = proc.communicate()
        output = out.decode('utf-8', errors='replace') if out else ''

        finished = datetime.utcnow().isoformat()
        tests_file.write_text(
            json.dumps(
                {
                    'running': False,
                    'started_at': start,
                    'finished_at': finished,
                    'exit_code': proc.returncode,
                    'output': output,
                }
            ),
            encoding='utf-8',
        )
    except Exception:
        current_app.logger.exception('Test runner failed')
        _manager_tests_file().write_text(json.dumps({'running': False, 'error': 'runner failure'}), encoding='utf-8')


@manager_bp.route('/api/manager/run_tests', methods=['POST'])
def api_manager_run_tests():
    try:
        thread = threading.Thread(target=_run_tests_background, daemon=True)
        thread.start()
        return jsonify({'ok': True})
    except Exception as exc:
        current_app.logger.exception('Failed to start tests')
        return jsonify({'error': str(exc)}), 500


@manager_bp.route('/api/manager/run_tests/status', methods=['GET'])
def api_manager_run_tests_status():
    try:
        tests_file = _manager_tests_file()
        if not tests_file.exists():
            return jsonify({'running': False})
        return jsonify(json.loads(tests_file.read_text(encoding='utf-8') or '{}'))
    except Exception as exc:
        current_app.logger.exception('Failed to read test status')
        return jsonify({'error': str(exc)}), 500

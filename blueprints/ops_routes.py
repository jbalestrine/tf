import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil
from flask import Blueprint, current_app, jsonify, render_template_string, request

from utils import load_enabled_modules


ops_bp = Blueprint('ops_routes', __name__)


def _root() -> Path:
    return Path(current_app.root_path).resolve()


def _get_windows_services():
    if sys.platform != 'win32':
        return []
    services = []
    try:
        result = subprocess.run(['sc', 'query'], capture_output=True, text=True, timeout=15)
        lines = result.stdout.split('\n')
        service = {}
        for line in lines:
            line = line.strip()
            if line.startswith('SERVICE_NAME:'):
                if service:
                    services.append(service)
                service = {'name': line.split(':', 1)[1].strip()}
            elif line.startswith('DISPLAY_NAME:'):
                service['display_name'] = line.split(':', 1)[1].strip()
            elif line.startswith('STATE'):
                parts = line.split(':', 1)
                service['status'] = parts[1].strip() if len(parts) > 1 else ''
        if service:
            services.append(service)
    except Exception:
        pass
    return services


def _get_processes_top(limit=10):
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return sorted(processes, key=lambda item: item.get('cpu_percent', 0), reverse=True)[:limit]


def _load_sessions_index():
    sessions_file = _root() / 'data' / 'sessions.json'
    try:
        if sessions_file.exists():
            return json.loads(sessions_file.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}


def _ops_git_snapshot() -> dict:
    def _run(cmd, timeout=12):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=current_app.root_path, timeout=timeout)
            return (proc.stdout or '').strip(), proc.returncode
        except Exception:
            return '', 1

    branch, _ = _run(['git', 'branch', '--show-current'])
    branches_out, _ = _run(['git', 'branch', '--format', '%(refname:short)'])
    log_out, _ = _run(['git', 'log', '--oneline', '-12'])

    branches = [line.strip() for line in branches_out.splitlines() if line.strip()]
    commits = []
    for line in log_out.splitlines():
        if not line.strip():
            continue
        parts = line.split(' ', 1)
        commits.append({'hash': parts[0], 'message': parts[1] if len(parts) > 1 else ''})
    return {'branch': branch or 'main', 'branches': branches, 'recent_commits': commits}


def _ops_scan_snapshot() -> dict:
    try:
        import sys_diagnostics as diagnostics_module

        data = diagnostics_module.get_cached_scan(force=False)
        files = data.get('files', [])
        issues = data.get('issues', [])
        orphans = [file_row for file_row in files if file_row.get('status') == 'orphan']
        return {
            'orphans_count': len(orphans),
            'orphans': [item.get('rel_path') for item in orphans[:25]],
            'issues_count': len(issues),
            'issues': [
                {
                    'severity': issue.get('severity', 'info'),
                    'message': issue.get('message', ''),
                    'file': issue.get('file', ''),
                    'line': issue.get('line', 0),
                    'suggestion': issue.get('suggestion', ''),
                }
                for issue in issues[:30]
            ],
        }
    except Exception as exc:
        return {'error': str(exc), 'orphans_count': 0, 'issues_count': 0, 'orphans': [], 'issues': []}


def _ops_module_idea_suggestion(idea: str) -> dict:
    text = (idea or '').strip().lower()
    if not text:
        return {'name': 'new_module', 'type': 'python', 'capabilities': ['rest_api', 'settings_page']}

    base = re.sub(r'[^a-z0-9]+', '_', text).strip('_')[:40] or 'new_module'
    if base and base[0].isdigit():
        base = 'mod_' + base

    module_type = 'python'
    capabilities = ['rest_api']

    if any(key in text for key in ['ui', 'dashboard', 'web', 'page']):
        module_type = 'web'
        capabilities.append('web_ui')
    if any(key in text for key in ['rbac', 'role', 'permission', 'auth']):
        capabilities.append('rbac')
    if any(key in text for key in ['echo', 'chat', 'assistant']):
        capabilities.append('echo_hook')
    if any(key in text for key in ['schedule', 'cron', 'job', 'background']):
        capabilities.append('background_jobs')
    if any(key in text for key in ['config', 'settings']):
        capabilities.append('settings_page')

    final_caps = []
    seen = set()
    for cap in capabilities:
        if cap not in seen:
            seen.add(cap)
            final_caps.append(cap)

    return {'name': base, 'type': module_type, 'capabilities': final_caps}


@ops_bp.route('/sys/api/services')
def sys_api_services():
    """Return currently running addon services and their status."""
    try:
        running = current_app.config.get('running_services', {})
        services = []
        for name, svc in running.items():
            proc = svc.get('process')
            alive = proc is not None and proc.poll() is None
            services.append(
                {
                    'name': name,
                    'status': 'running' if alive else 'stopped',
                    'pid': svc.get('pid'),
                    'port': svc.get('port'),
                    'entry_point': svc.get('entry_point'),
                    'type': svc.get('type'),
                    'start_time': svc.get('start_time'),
                }
            )

        import os as os_module

        services.insert(
            0,
            {
                'name': 'masterchief (main)',
                'status': 'running',
                'pid': os_module.getpid(),
                'port': 8080,
                'entry_point': 'main.py',
                'type': 'python',
            },
        )
        return jsonify({'services': services})
    except Exception as exc:
        return jsonify({'error': str(exc), 'services': []}), 500


@ops_bp.route('/sys/ops')
def sys_ops_center():
    """Unified Ops Center page for diagnostics and operational controls."""
    try:
        from templates.ops_center import OPS_CENTER_TEMPLATE
        return render_template_string(OPS_CENTER_TEMPLATE)
    except Exception as exc:
        return f'<pre style="color:red">Ops Center load error: {exc}</pre>', 500


@ops_bp.route('/sys/api/ops-summary', methods=['GET'])
def sys_api_ops_summary():
    """Aggregate operational diagnostics across repo, runtime, and integrations."""
    scan = _ops_scan_snapshot()
    git = _ops_git_snapshot()

    rbac_summary = {'users': 0, 'roles': 0, 'sessions': 0}
    try:
        mgr = current_app.config.get('_rbac_mgr')
        if mgr is not None:
            rbac_summary = {
                'users': len(mgr.get_users()),
                'roles': len(mgr.get_roles()),
                'sessions': len(mgr.get_sessions()),
            }
    except Exception:
        pass

    secrets_summary = {'count': 0, 'rotation_due': 0}
    try:
        vault_mgr = (current_app.config.get('_managers') or {}).get('vault')
        if vault_mgr is not None:
            secrets = vault_mgr.list_secrets()
            due = vault_mgr.check_rotation()
            secrets_summary = {
                'count': len(secrets),
                'rotation_due': len([item for item in due if item.get('status') in ('due_soon', 'overdue')]),
            }
    except Exception:
        pass

    cloud_summary = {'accounts': 0, 'providers': [], 'costs': {}}
    try:
        cloud_mgr = (current_app.config.get('_managers') or {}).get('cloud')
        if cloud_mgr is not None:
            accounts = cloud_mgr.get_accounts()
            providers = sorted({(acc.get('provider') or '').lower() for acc in accounts if acc.get('provider')})
            cloud_summary = {'accounts': len(accounts), 'providers': providers, 'costs': cloud_mgr.get_costs()}
    except Exception:
        pass

    echo_sessions = {'count': 0, 'recent': []}
    try:
        idx = _load_sessions_index()
        sessions = idx.get('sessions') or []
        sessions_sorted = sorted(sessions, key=lambda session: session.get('updated_at', ''), reverse=True)
        echo_sessions = {'count': len(sessions_sorted), 'recent': sessions_sorted[:8]}
    except Exception:
        pass

    motd = ''
    try:
        settings_path = current_app.config.get('API_SETTINGS')
        if settings_path:
            settings_file = Path(settings_path)
        else:
            settings_file = _root() / 'api_settings.json'
        if settings_file.exists():
            settings = json.loads(settings_file.read_text(encoding='utf-8'))
            motd = str(settings.get('motd') or '').strip()
    except Exception:
        pass

    addons = []
    modules_cfg = load_enabled_modules() or {}
    try:
        ui_modules_file = Path(current_app.config['UPLOAD_FOLDER']) / 'ui_modules.json'
        ui_links = json.loads(ui_modules_file.read_text(encoding='utf-8')) if ui_modules_file.exists() else {}
    except Exception:
        ui_links = {}

    try:
        extracted = Path(current_app.config['UPLOAD_FOLDER']) / 'extracted'
        if extracted.exists():
            for item in extracted.iterdir():
                if item.is_dir():
                    addons.append(item.name)
        addons = sorted(addons)
    except Exception:
        pass

    services = []
    try:
        running = current_app.config.get('running_services', {})
        for name, svc in running.items():
            process = svc.get('process')
            services.append(
                {
                    'name': name,
                    'status': 'running' if (process is not None and process.poll() is None) else 'stopped',
                    'pid': svc.get('pid'),
                    'port': svc.get('port'),
                    'type': svc.get('type'),
                }
            )
        if sys.platform == 'win32':
            for service in _get_windows_services()[:25]:
                service_name = service.get('name') or service.get('display_name') or 'unknown'
                if not any((row.get('name') or '').lower() == str(service_name).lower() for row in services):
                    services.append(
                        {
                            'name': service_name,
                            'status': 'running' if 'RUNNING' in str(service.get('status', '')).upper() else 'stopped',
                            'pid': None,
                            'port': None,
                            'type': 'windows_service',
                        }
                    )
    except Exception:
        pass

    proc_top = []
    try:
        proc_top = _get_processes_top(limit=10)
    except Exception:
        pass

    tf_wizard = {
        'route': '/web_tf_wizard',
        'api_validate': '/api/terraform/enterprise/validate',
        'available': bool((_root() / 'web_tf_wizard.html').exists()),
    }

    payload = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'diagnostics': scan,
        'git': git,
        'rbac': rbac_summary,
        'terraform_wizard': tf_wizard,
        'secrets': secrets_summary,
        'cloud': cloud_summary,
        'echo_sessions': echo_sessions,
        'motd': motd,
        'addons': {'installed': addons, 'count': len(addons)},
        'modules': {'enabled_config': modules_cfg, 'count': len(modules_cfg)},
        'ui_links': ui_links,
        'services': services,
        'processes_top': proc_top,
        'actions': {
            'diagnostics_page': '/sys/diagnostics',
            'scm_page': '/sys/scm',
            'ops_page': '/sys/ops',
            'processes_page': '/processes',
            'services_page': '/services',
            'addons_page': '/addons',
            'modules_page': '/modules',
            'echo_chat': '/echo-chat',
            'kill_process': '/processes/kill/<pid>',
            'service_start': '/services/start/<service_name>',
            'service_stop': '/services/stop/<service_name>',
            'service_restart': '/services/restart/<service_name>',
            'create_blank_module': '/addons/create_blank_module',
        },
    }
    return jsonify(payload)


@ops_bp.route('/sys/api/ops-action', methods=['POST'])
def sys_api_ops_action():
    """Run safe operational actions from Ops Center and return JSON results."""
    data = request.get_json(silent=True) or {}
    action = str(data.get('action') or '').strip().lower()

    if not action:
        return jsonify({'ok': False, 'error': 'action is required'}), 400

    try:
        if action == 'kill_process':
            pid = int(data.get('pid'))
            proc = psutil.Process(pid)
            proc.terminate()
            return jsonify({'ok': True, 'action': action, 'pid': pid, 'status': 'terminated'})

        if action in ('service_start', 'service_stop', 'service_restart'):
            if sys.platform != 'win32':
                return jsonify({'ok': False, 'error': 'Service control is only supported on Windows in this runtime'}), 400

            service_name = str(data.get('service_name') or '').strip()
            if not service_name:
                return jsonify({'ok': False, 'error': 'service_name is required'}), 400

            if action == 'service_start':
                subprocess.run(['sc', 'start', service_name], check=True, capture_output=True, text=True)
                status = 'running'
            elif action == 'service_stop':
                subprocess.run(['sc', 'stop', service_name], check=True, capture_output=True, text=True)
                status = 'stopped'
            else:
                subprocess.run(['sc', 'stop', service_name], check=False, capture_output=True, text=True)
                time.sleep(1.5)
                subprocess.run(['sc', 'start', service_name], check=True, capture_output=True, text=True)
                status = 'running'

            return jsonify({'ok': True, 'action': action, 'service_name': service_name, 'status': status})

        return jsonify({'ok': False, 'error': f'Unknown action: {action}'}), 400
    except psutil.NoSuchProcess:
        return jsonify({'ok': False, 'error': 'Process not found'}), 404
    except psutil.AccessDenied:
        return jsonify({'ok': False, 'error': 'Access denied'}), 403
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or '').strip()
        stdout = (exc.stdout or '').strip()
        return jsonify({'ok': False, 'error': stderr or stdout or str(exc)}), 500
    except Exception as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 500


@ops_bp.route('/sys/api/modules/from-idea', methods=['POST'])
def sys_api_modules_from_idea():
    """Suggest module scaffolding payload from a plain-language idea."""
    data = request.get_json(silent=True) or {}
    idea = str(data.get('idea') or '').strip()
    if not idea:
        return jsonify({'ok': False, 'error': 'idea is required'}), 400

    suggestion = _ops_module_idea_suggestion(idea)
    return jsonify(
        {
            'ok': True,
            'idea': idea,
            'suggestion': suggestion,
            'create_payload': {
                'name': suggestion['name'],
                'type': suggestion['type'],
                'description': idea,
                'auto_load': True,
                'capabilities': suggestion['capabilities'],
            },
            'create_endpoint': '/addons/create_blank_module',
        }
    )

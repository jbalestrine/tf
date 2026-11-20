import os
import threading
import time

import psutil
from flask import Blueprint, current_app, jsonify, request


dashboard_processes_bp = Blueprint('dashboard_processes', __name__)
_sample_lock = threading.Lock()
_previous = {}
_previous_time = None


@dashboard_processes_bp.before_request
def _require_admin():
    guard = current_app.config.get(
        'SCM_ADMIN_GET_GUARD' if request.method == 'GET' else 'SCM_ADMIN_POST_GUARD'
    )
    if guard is None:
        return jsonify(ok=False, error='Process authorization is not configured.'), 503
    return guard()


def collect_processes():
    global _previous, _previous_time
    with _sample_lock:
        now = time.monotonic()
        elapsed = now - _previous_time if _previous_time is not None else None
        current = {}
        rows = []
        skipped = 0
        cores = psutil.cpu_count() or 1
        for proc in psutil.process_iter():
            try:
                with proc.oneshot():
                    pid = proc.pid
                    created = proc.create_time()
                    name = proc.name()
                    status = proc.status()
                    times = proc.cpu_times()
                    memory = proc.memory_info().rss
                key = (pid, created)
                total = times.user + times.system
                previous = _previous.get(key)
                cpu = None
                if previous is not None and elapsed and elapsed > 0 and total >= previous:
                    cpu = round((total - previous) / elapsed / cores * 100, 1)
                current[key] = total
                rows.append({'pid': pid, 'created': created, 'name': name, 'status': status,
                             'cpu': cpu, 'memory_bytes': memory,
                             'can_end': pid not in (0, 1, os.getpid())})
            except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
                skipped += 1
        _previous, _previous_time = current, now
    rows.sort(key=lambda row: (row['cpu'] is not None, row['cpu'] or 0, row['memory_bytes']), reverse=True)
    return {'ok': True, 'processes': rows, 'skipped': skipped}


@dashboard_processes_bp.get('/api/dashboard/processes')
def dashboard_processes():
    try:
        return jsonify(collect_processes())
    except (OSError, psutil.Error):
        current_app.logger.exception('Unable to collect dashboard processes')
        return jsonify(ok=False, error='Unable to collect process readings on the server.'), 503


@dashboard_processes_bp.post('/api/dashboard/processes/<int:pid>/terminate')
def dashboard_terminate_process(pid):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or type(data.get('created')) not in (int, float) or data.get('confirmation') != pid:
        return jsonify(ok=False, error='Confirm the selected process before ending it.'), 400
    if pid in (0, 1, os.getpid()):
        return jsonify(ok=False, error='This process is protected from the dashboard action.'), 403
    try:
        proc = psutil.Process(pid)
        if proc.create_time() != data['created']:
            return jsonify(ok=False, error='The process has changed. Refresh the list before trying again.'), 409
        name = proc.name()
        proc.terminate()
        current_app.logger.warning('Dashboard process termination requested: pid=%s name=%s', pid, name)
        return jsonify(ok=True, message=f'Termination requested for {name} (PID {pid}). Refresh to check its status.')
    except psutil.NoSuchProcess:
        return jsonify(ok=False, error='The process is no longer running. Refresh the list.'), 404
    except psutil.AccessDenied:
        return jsonify(ok=False, error='The server does not have permission to end this process.'), 403
    except psutil.Error:
        current_app.logger.exception('Unable to terminate dashboard process %s', pid)
        return jsonify(ok=False, error='The server could not end this process.'), 503

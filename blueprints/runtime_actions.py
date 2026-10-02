import subprocess
import sys
import time

import psutil
from flask import Blueprint, flash, jsonify, redirect, url_for


runtime_actions_bp = Blueprint('runtime_actions', __name__)


def _get_system_stats():
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    try:
        disk_path = 'C:\\' if sys.platform == 'win32' else '/'
        disk = psutil.disk_usage(disk_path)
    except Exception:
        disk = psutil.disk_usage('.')
    return {
        'cpu': {'percent': cpu_percent, 'count': psutil.cpu_count()},
        'memory': {
            'total': memory.total,
            'available': memory.available,
            'percent': memory.percent,
            'used': memory.used,
        },
        'disk': {'total': disk.total, 'used': disk.used, 'free': disk.free, 'percent': disk.percent},
        'uptime': time.time() - psutil.boot_time(),
    }


@runtime_actions_bp.route('/api/stats')
def api_stats():
    return jsonify(_get_system_stats())


@runtime_actions_bp.route('/processes/kill/<int:pid>')
def processes_kill(pid):
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        flash(f'Process {pid} terminated successfully!', 'success')
    except psutil.NoSuchProcess:
        flash(f'Process {pid} not found', 'error')
    except psutil.AccessDenied:
        flash(f'Access denied to terminate process {pid}', 'error')
    except Exception as exc:
        flash(f'Failed to terminate process: {str(exc)}', 'error')
    return redirect(url_for('processes_list'))


@runtime_actions_bp.route('/services/start/<service_name>')
def services_start(service_name):
    if sys.platform == 'win32':
        try:
            subprocess.run(['sc', 'start', service_name], check=True)
            flash(f'Service {service_name} started successfully!', 'success')
        except Exception as exc:
            flash(f'Failed to start service: {str(exc)}', 'error')
    return redirect(url_for('services_list'))


@runtime_actions_bp.route('/services/stop/<service_name>')
def services_stop(service_name):
    if sys.platform == 'win32':
        try:
            subprocess.run(['sc', 'stop', service_name], check=True)
            flash(f'Service {service_name} stopped successfully!', 'success')
        except Exception as exc:
            flash(f'Failed to stop service: {str(exc)}', 'error')
    return redirect(url_for('services_list'))


@runtime_actions_bp.route('/services/restart/<service_name>')
def services_restart(service_name):
    if sys.platform == 'win32':
        try:
            subprocess.run(['sc', 'stop', service_name], check=False)
            time.sleep(2)
            subprocess.run(['sc', 'start', service_name], check=True)
            flash(f'Service {service_name} restarted successfully!', 'success')
        except Exception as exc:
            flash(f'Failed to restart service: {str(exc)}', 'error')
    return redirect(url_for('services_list'))

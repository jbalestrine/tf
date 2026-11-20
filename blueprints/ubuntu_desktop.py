import os
from pathlib import Path
import subprocess
import threading
import time
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, request
from simple_websocket import ConnectionClosed, Server


ubuntu_desktop_bp = Blueprint('ubuntu_desktop', __name__)
_vm_name = 'MasterChief Ubuntu Test'
_connections = threading.BoundedSemaphore(2)


def _credential_dir():
    local_app_data = os.environ.get('LOCALAPPDATA')
    if not local_app_data:
        raise RuntimeError('LOCALAPPDATA is not available on the MasterChief server.')
    return Path(local_app_data) / 'MasterChief' / 'ubuntu-test'


def _vbox():
    program_files = os.environ.get('PROGRAMFILES')
    if not program_files:
        raise RuntimeError('This desktop requires VirtualBox on a Windows MasterChief server.')
    return str(Path(program_files) / 'Oracle' / 'VirtualBox' / 'VBoxManage.exe')


def _vm_command(*args):
    return subprocess.run([_vbox(), *args], capture_output=True, text=True,
                          check=True, timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def _vm_state():
    result = _vm_command('showvminfo', _vm_name, '--machinereadable')
    for line in result.stdout.splitlines():
        if line.startswith('VMState='):
            return line.split('=', 1)[1].strip('"')
    raise RuntimeError('VirtualBox did not report the test VM state.')


def _ssh_base():
    credentials = _credential_dir()
    key = credentials / 'ubuntu-test-ed25519'
    known_hosts = credentials / 'ubuntu-known-hosts'
    if not key.is_file() or not known_hosts.is_file():
        raise RuntimeError('Ubuntu test VM SSH credentials are not configured on this server.')
    return ['ssh.exe', '-i', str(key), '-p', '22242',
            '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=yes', '-o', f'UserKnownHostsFile={known_hosts}']


def _ssh_command():
    return [*_ssh_base(), '-W', '127.0.0.1:5901', 'ubuntu@127.0.0.1']


def _source_command(*args):
    command = [*_ssh_base(), 'ubuntu@127.0.0.1',
               'sudo', '-n', '/usr/local/sbin/ubuntu-masterchief-source', *args]
    return subprocess.run(command, capture_output=True, text=True, timeout=100, check=True,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def _same_origin():
    source = request.headers.get('Origin', '')
    try:
        parsed = urlsplit(source)
    except ValueError:
        return False
    return (parsed.scheme == request.scheme and parsed.netloc.casefold() == request.host.casefold()
            and not parsed.path and not parsed.query and not parsed.fragment)


@ubuntu_desktop_bp.before_request
def _require_admin():
    guard = current_app.config.get(
        'SCM_ADMIN_POST_GUARD' if request.method == 'POST' else 'SCM_ADMIN_GET_GUARD'
    )
    if guard is None:
        return jsonify(ok=False, error='Desktop authorization is not configured.'), 503
    return guard()


@ubuntu_desktop_bp.get('/api/ubuntu-desktop/status')
def status():
    try:
        return jsonify(ok=True, state=_vm_state())
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        current_app.logger.warning('Unable to inspect Ubuntu test VM: %s', exc)
        return jsonify(ok=False, error=f'Unable to inspect the Ubuntu test VM: {exc}'), 503


@ubuntu_desktop_bp.post('/api/ubuntu-desktop/start')
def start():
    try:
        state = _vm_state()
        if state == 'running':
            return jsonify(ok=True, message='Ubuntu test VM is already running.')
        if state not in ('poweroff', 'saved', 'aborted'):
            return jsonify(ok=False, error=f'Cannot start the VM while its state is {state}.'), 409
        _vm_command('startvm', _vm_name, '--type', 'headless')
        return jsonify(ok=True, message='Ubuntu is starting. Wait for the desktop, then connect.')
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        current_app.logger.warning('Unable to start Ubuntu test VM: %s', exc)
        return jsonify(ok=False, error=f'Unable to start the Ubuntu test VM: {exc}'), 503


@ubuntu_desktop_bp.get('/api/ubuntu-desktop/source')
def source_status():
    try:
        result = _source_command('status')
        data = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        if data.get('source') not in ('pypi', 'github', 'stopped', 'conflict'):
            raise RuntimeError('The guest did not report a valid app source.')
        return jsonify(ok=True, source=data['source'], github_commit=data.get('github_commit'))
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        current_app.logger.warning('Unable to inspect Ubuntu app source: %s', exc)
        return jsonify(ok=False, error='Unable to inspect the Ubuntu app source. Check that the VM and source switch are configured.'), 503


@ubuntu_desktop_bp.post('/api/ubuntu-desktop/source')
def switch_source():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get('source') not in ('pypi', 'github') or data.get('confirm') is not True:
        return jsonify(ok=False, error='Choose and confirm the Ubuntu app source.'), 400
    try:
        result = _source_command('switch', data['source'])
        return jsonify(ok=True, message=result.stdout.strip(), source=data['source'])
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or 'The guest source switch failed.').strip()
        current_app.logger.warning('Ubuntu source switch failed: %s', message)
        return jsonify(ok=False, error=message), 503
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        current_app.logger.warning('Ubuntu source switch failed: %s', exc)
        return jsonify(ok=False, error=f'Ubuntu source switch failed: {exc}'), 503


@ubuntu_desktop_bp.route('/api/ubuntu-desktop/socket', websocket=True)
def desktop_socket():
    if not _same_origin():
        return jsonify(ok=False, error='Desktop connection must originate from this MasterChief page.'), 403
    if not _connections.acquire(blocking=False):
        return jsonify(ok=False, error='Desktop connection limit reached.'), 429
    process = None
    ws = None
    try:
        if _vm_state() != 'running':
            return jsonify(ok=False, error='Start the Ubuntu test VM before connecting.'), 409
        command = _ssh_command()
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, bufsize=0,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        ws = Server.accept(request.environ, ping_interval=25, max_message_size=1024 * 1024)
        logger = current_app.logger

        def copy_output():
            try:
                while True:
                    data = os.read(process.stdout.fileno(), 65536)
                    if not data:
                        break
                    ws.send(data)
            except (OSError, ConnectionClosed):
                pass
            finally:
                try:
                    ws.close()
                except (OSError, ConnectionClosed):
                    pass

        def log_errors():
            for line in iter(process.stderr.readline, b''):
                logger.warning('Ubuntu desktop SSH: %s', line.decode('utf-8', errors='replace').rstrip())

        threading.Thread(target=copy_output, daemon=True).start()
        threading.Thread(target=log_errors, daemon=True).start()
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            data = ws.receive(timeout=1)
            if data is not None:
                if not isinstance(data, bytes):
                    break
                process.stdin.write(data)
            if process.poll() is not None:
                break
    except (OSError, RuntimeError, subprocess.SubprocessError, ConnectionClosed) as exc:
        current_app.logger.warning('Ubuntu desktop connection ended: %s', exc)
        if ws is None:
            return jsonify(ok=False, error=f'Unable to connect to the Ubuntu desktop: {exc}'), 503
    finally:
        if ws is not None:
            try:
                ws.close()
            except (OSError, ConnectionClosed):
                pass
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        _connections.release()
    return ''

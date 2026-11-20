import subprocess

import pytest
from flask import Flask, jsonify

from blueprints import ubuntu_desktop as desktop


@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SCM_ADMIN_GET_GUARD'] = lambda: None
    app.config['SCM_ADMIN_POST_GUARD'] = lambda: None
    app.register_blueprint(desktop.ubuntu_desktop_bp)
    monkeypatch.setattr(desktop, '_vm_state', lambda: 'running')
    return app.test_client()


def test_status_and_start_use_fixed_vm(client, monkeypatch):
    calls = []
    monkeypatch.setattr(desktop, '_vm_state', lambda: 'poweroff')
    monkeypatch.setattr(desktop, '_vm_command', lambda *args: calls.append(args))
    assert client.get('/api/ubuntu-desktop/status').json['state'] == 'poweroff'
    assert client.post('/api/ubuntu-desktop/start').status_code == 200
    assert calls == [('startvm', 'MasterChief Ubuntu Test', '--type', 'headless')]
    monkeypatch.setattr(desktop, '_vm_state', lambda: 'paused')
    assert client.post('/api/ubuntu-desktop/start').status_code == 409


def test_admin_denials_and_virtualbox_errors_are_visible(client, monkeypatch):
    client.application.config['SCM_ADMIN_GET_GUARD'] = lambda: (jsonify(error='denied'), 403)
    client.application.config['SCM_ADMIN_POST_GUARD'] = lambda: (jsonify(error='denied'), 403)
    assert client.get('/api/ubuntu-desktop/status').status_code == 403
    assert client.post('/api/ubuntu-desktop/start').status_code == 403
    client.application.config['SCM_ADMIN_GET_GUARD'] = lambda: None
    def failed():
        raise subprocess.TimeoutExpired('VBoxManage', 30)
    monkeypatch.setattr(desktop, '_vm_state', failed)
    assert client.get('/api/ubuntu-desktop/status').status_code == 503


def test_websocket_requires_correct_origin_and_admin(client):
    url = 'ws://localhost/api/ubuntu-desktop/socket'
    assert client.get(url, headers={'Origin': 'http://example.com'}).status_code == 403
    assert client.get(url, headers={'Origin': 'https://localhost'}).status_code == 403
    assert client.get(url, headers={'Origin': 'http://[invalid'}).status_code == 403
    assert client.get(url).status_code == 403
    client.application.config['SCM_ADMIN_GET_GUARD'] = lambda: (jsonify(error='denied'), 403)
    assert client.get(url, headers={'Origin': 'http://localhost'}).status_code == 403


def test_ssh_is_fixed_to_local_guest_vnc(tmp_path, monkeypatch):
    (tmp_path / 'ubuntu-test-ed25519').touch()
    (tmp_path / 'ubuntu-known-hosts').touch()
    monkeypatch.setattr(desktop, '_credential_dir', lambda: tmp_path)
    command = desktop._ssh_command()
    assert command[-3:] == ['-W', '127.0.0.1:5901', 'ubuntu@127.0.0.1']
    assert 'StrictHostKeyChecking=yes' in command
    (tmp_path / 'ubuntu-known-hosts').unlink()
    with pytest.raises(RuntimeError, match='credentials'):
        desktop._ssh_command()


def test_source_switch_validates_and_runs_only_fixed_commands(client, monkeypatch):
    calls = []
    def fake(*args):
        calls.append(args)
        if args == ('status',):
            return subprocess.CompletedProcess(args, 0, 'source=pypi\ngithub_commit=abc123\n', '')
        return subprocess.CompletedProcess(args, 0, 'Running github.', '')
    monkeypatch.setattr(desktop, '_source_command', fake)
    assert client.get('/api/ubuntu-desktop/source').json == {
        'ok': True, 'source': 'pypi', 'github_commit': 'abc123'
    }
    assert client.post('/api/ubuntu-desktop/source', json={'source': 'github'}).status_code == 400
    assert client.post('/api/ubuntu-desktop/source', json={'source': 'other', 'confirm': True}).status_code == 400
    response = client.post('/api/ubuntu-desktop/source', json={'source': 'github', 'confirm': True})
    assert response.status_code == 200 and response.json['source'] == 'github'
    assert calls == [('status',), ('switch', 'github')]
    client.application.config['SCM_ADMIN_POST_GUARD'] = lambda: (jsonify(error='denied'), 403)
    assert client.post('/api/ubuntu-desktop/source', json={'source': 'pypi', 'confirm': True}).status_code == 403


def test_source_switch_surfaces_guest_failure(client, monkeypatch):
    def failed(*args):
        raise subprocess.CalledProcessError(1, args, stderr='Switch failed; previous app restored.')
    monkeypatch.setattr(desktop, '_source_command', failed)
    response = client.post('/api/ubuntu-desktop/source', json={'source': 'github', 'confirm': True})
    assert response.status_code == 503
    assert 'previous app restored' in response.json['error']

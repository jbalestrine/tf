from types import SimpleNamespace

import psutil
import pytest
from flask import Flask, jsonify

from blueprints import dashboard_processes as monitor


@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SCM_ADMIN_GET_GUARD'] = lambda: None
    app.config['SCM_ADMIN_POST_GUARD'] = lambda: None
    app.register_blueprint(monitor.dashboard_processes_bp)
    monkeypatch.setattr(monitor, '_previous', {})
    monkeypatch.setattr(monitor, '_previous_time', None)
    return app.test_client()


class FakeProcess:
    def __init__(self, pid=12345, created=100.0, cpu=2.0):
        self.pid = pid
        self.created = created
        self.cpu = cpu
        self.terminated = False

    def oneshot(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def create_time(self):
        return self.created

    def name(self):
        return 'example'

    def status(self):
        return 'running'

    def cpu_times(self):
        return SimpleNamespace(user=self.cpu, system=0)

    def memory_info(self):
        return SimpleNamespace(rss=1048576)

    def terminate(self):
        self.terminated = True


def test_process_sampling_calculates_total_cpu_and_handles_new_processes(client, monkeypatch):
    proc = FakeProcess()
    clock = iter([100, 105, 110])
    monkeypatch.setattr(monitor.psutil, 'process_iter', lambda: [proc])
    monkeypatch.setattr(monitor.psutil, 'cpu_count', lambda: 4)
    monkeypatch.setattr(monitor.time, 'monotonic', lambda: next(clock))
    first = client.get('/api/dashboard/processes').get_json()['processes'][0]
    assert first['cpu'] is None
    proc.cpu = 4
    second = client.get('/api/dashboard/processes').get_json()['processes'][0]
    assert second['cpu'] == 10.0
    assert second['memory_bytes'] == 1048576
    proc.created = 200
    assert client.get('/api/dashboard/processes').get_json()['processes'][0]['cpu'] is None


def test_process_end_checks_confirmation_identity_and_protected_pids(client, monkeypatch):
    proc = FakeProcess()
    monkeypatch.setattr(monitor.psutil, 'Process', lambda pid: proc)
    url = '/api/dashboard/processes/12345/terminate'
    assert client.post(url, json={'created': 100, 'confirmation': 1}).status_code == 400
    assert client.post(url, json={'created': 99, 'confirmation': 12345}).status_code == 409
    assert not proc.terminated
    assert client.post(f'/api/dashboard/processes/{monitor.os.getpid()}/terminate',
                       json={'created': 100, 'confirmation': monitor.os.getpid()}).status_code == 403
    response = client.post(url, json={'created': 100, 'confirmation': 12345})
    assert response.status_code == 200 and proc.terminated
    assert 'Termination requested' in response.get_json()['message']


def test_denied_access_and_process_errors_are_explicit(client, monkeypatch):
    client.application.config['SCM_ADMIN_GET_GUARD'] = lambda: (jsonify(ok=False, error='denied'), 403)
    client.application.config['SCM_ADMIN_POST_GUARD'] = lambda: (jsonify(ok=False, error='denied'), 403)
    assert client.get('/api/dashboard/processes').status_code == 403
    assert client.post('/api/dashboard/processes/12345/terminate', json={}).status_code == 403
    client.application.config['SCM_ADMIN_POST_GUARD'] = lambda: None
    def denied(pid):
        raise psutil.AccessDenied(pid)
    monkeypatch.setattr(monitor.psutil, 'Process', denied)
    response = client.post('/api/dashboard/processes/12345/terminate',
                           json={'created': 100, 'confirmation': 12345})
    assert response.status_code == 403
    assert 'permission' in response.get_json()['error']

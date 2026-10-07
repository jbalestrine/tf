from types import SimpleNamespace

from flask import Flask

from blueprints import observability_routes


def _client():
    app = Flask(__name__)
    app.register_blueprint(observability_routes.observability_bp)
    return app.test_client()


def test_metrics_endpoint_requires_loopback_or_valid_token(monkeypatch):
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    client = _client()

    assert client.get("/metrics", environ_base={"REMOTE_ADDR": "203.0.113.8"}).status_code == 403
    monkeypatch.setenv("METRICS_TOKEN", "scraper-secret")
    assert client.get("/metrics", environ_base={"REMOTE_ADDR": "203.0.113.8"}).status_code == 401
    response = client.get(
        "/metrics",
        headers={"Authorization": "Bearer scraper-secret"},
        environ_base={"REMOTE_ADDR": "203.0.113.8"},
    )
    assert response.status_code == 200
    assert response.mimetype == "text/plain"


def test_status_checks_existing_services_without_returning_tokens(monkeypatch):
    for key, value in {
        "PROMETHEUS_URL": "http://prometheus.example:9090",
        "GRAFANA_URL": "http://grafana.example:3000",
        "LOKI_URL": "http://loki.example:3100",
        "PROMETHEUS_TOKEN": "prom-secret",
        "GRAFANA_API_TOKEN": "grafana-secret",
        "LOKI_TOKEN": "loki-secret",
        "GRAFANA_DASHBOARD_UID": "platform-overview",
    }.items():
        monkeypatch.setenv(key, value)
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append((url, headers, timeout))
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(observability_routes.requests, "get", fake_get)
    response = _client().get("/api/observability/status")

    assert response.status_code == 200
    result = response.get_json()
    assert all(service["status"] == "connected" for service in result["services"].values())
    assert result["grafana_dashboard_url"] == "http://grafana.example:3000/d/platform-overview"
    assert [call[1]["Authorization"] for call in calls] == [
        "Bearer prom-secret",
        "Bearer grafana-secret",
        "Bearer loki-secret",
    ]
    assert b"prom-secret" not in response.data
    assert b"grafana-secret" not in response.data
    assert b"loki-secret" not in response.data


def test_prometheus_query_reports_missing_configuration(monkeypatch):
    monkeypatch.delenv("PROMETHEUS_URL", raising=False)

    response = _client().post(
        "/api/observability/prometheus/query",
        json={"query": "up"},
    )

    assert response.status_code == 503
    assert response.get_json()["ok"] is False

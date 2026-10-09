"""Prometheus metrics and read-only Prometheus, Grafana, and Loki integrations."""

from __future__ import annotations

import hmac
import ipaddress
import os
import re
import subprocess
import sys
import time
from base64 import urlsafe_b64encode
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import requests
from flask import Blueprint, Response, abort, current_app, g, jsonify, request, send_file
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST


observability_bp = Blueprint("observability", __name__)
_registry = CollectorRegistry()
_request_count = Counter(
    "masterchief_http_requests_total",
    "HTTP requests served by MasterChief.",
    ("method", "endpoint", "status"),
    registry=_registry,
)
_request_duration = Histogram(
    "masterchief_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "endpoint"),
    registry=_registry,
)
_TOKEN_NAMES = {
    "prometheus": "PROMETHEUS_TOKEN",
    "grafana": "GRAFANA_API_TOKEN",
    "loki": "LOKI_TOKEN",
}
_SERVICE_SETTINGS = {
    "prometheus": ("PROMETHEUS_URL", "/-/healthy"),
    "grafana": ("GRAFANA_URL", "/api/health"),
    "loki": ("LOKI_URL", "/ready"),
}
_SAFE_DASHBOARD_UID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_SETUP_ACTIONS = {"setup", "install", "start", "stop"}
_setup_jobs: dict[str, subprocess.Popen] = {}

try:
    from auth_module import requires_permission
except ImportError:
    from functools import wraps

    def requires_permission(_permission):
        def decorator(func):
            @wraps(func)
            def authentication_unavailable(*args, **kwargs):
                abort(503, description="Authentication is unavailable; setup scripts are disabled.")
            return authentication_unavailable
        return decorator


def _stack():
    from scripts import observability_stack

    return observability_stack


def _setup_log(target: str) -> Path:
    stack = _stack()
    base = stack.TOOLS_DIR if target == "all" else stack.service_dir(target)
    base.mkdir(parents=True, exist_ok=True)
    return base / ("observability-setup.log" if target == "all" else "setup.log")


def _service_url(service: str) -> str | None:
    env_name, _ = _SERVICE_SETTINGS[service]
    raw_url = os.environ.get(env_name, "").strip()
    if not raw_url:
        return None

    parsed = urlsplit(raw_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{env_name} must be an http(s) base URL without credentials or query parameters.")
    return raw_url.rstrip("/")


def _service_headers(service: str) -> dict[str, str]:
    token = os.environ.get(_TOKEN_NAMES[service], "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _probe_service(service: str, logger) -> dict[str, object]:
    env_name, health_path = _SERVICE_SETTINGS[service]
    try:
        base_url = _service_url(service)
    except ValueError as exc:
        return {
            "configured": False,
            "status": "invalid_configuration",
            "error": str(exc),
            "url": "",
        }
    if not base_url:
        return {
            "configured": False,
            "status": "not_configured",
            "error": f"Set {env_name} in the app environment.",
            "url": "",
        }

    try:
        response = requests.get(
            f"{base_url}{health_path}",
            headers=_service_headers(service),
            timeout=3,
        )
    except requests.RequestException:
        logger.warning("Could not reach configured %s service.", service, exc_info=True)
        return {
            "configured": True,
            "status": "unreachable",
            "error": "Could not reach the configured service.",
            "url": base_url,
        }

    healthy = 200 <= response.status_code < 300
    return {
        "configured": True,
        "status": "connected" if healthy else "unhealthy",
        "error": "" if healthy else f"Health check returned HTTP {response.status_code}.",
        "url": base_url,
    }


@observability_bp.before_app_request
def _start_request_timer() -> None:
    if request.path != "/metrics":
        g._masterchief_metrics_started = time.perf_counter()


@observability_bp.after_app_request
def _record_request(response: Response) -> Response:
    started = getattr(g, "_masterchief_metrics_started", None)
    if started is None or request.path == "/metrics":
        return response

    endpoint = request.endpoint or "unmatched"
    _request_count.labels(request.method, endpoint, str(response.status_code)).inc()
    _request_duration.labels(request.method, endpoint).observe(time.perf_counter() - started)
    return response


@observability_bp.get("/metrics")
def prometheus_metrics() -> Response:
    """Expose low-cardinality app metrics to a trusted Prometheus scraper."""
    configured_token = os.environ.get("METRICS_TOKEN", "").strip()
    if configured_token:
        supplied_token = request.headers.get("Authorization", "")
        if supplied_token.startswith("Bearer "):
            supplied_token = supplied_token[7:]
        else:
            supplied_token = ""
        if not hmac.compare_digest(supplied_token, configured_token):
            abort(401)
    else:
        try:
            is_loopback = ipaddress.ip_address(request.remote_addr or "").is_loopback
        except ValueError:
            is_loopback = False
        if not is_loopback:
            abort(403)

    return Response(generate_latest(_registry), content_type=CONTENT_TYPE_LATEST)


@observability_bp.get("/observability")
def observability_page() -> Response:
    return send_file("observability.html")


@observability_bp.get("/api/observability/status")
def observability_status():
    """Return service health without exposing configured bearer tokens."""
    logger = current_app.logger
    with ThreadPoolExecutor(max_workers=3) as executor:
        probes = {
            name: executor.submit(_probe_service, name, logger)
            for name in _SERVICE_SETTINGS
        }
        services = {name: probe.result() for name, probe in probes.items()}

    dashboard_uid = os.environ.get("GRAFANA_DASHBOARD_UID", "").strip()
    grafana_url = services["grafana"]["url"]
    dashboard_url = ""
    if (
        isinstance(grafana_url, str)
        and grafana_url
        and _SAFE_DASHBOARD_UID.fullmatch(dashboard_uid)
    ):
        dashboard_url = f"{grafana_url}/d/{dashboard_uid}"

    return jsonify({
        "ok": True,
        "services": services,
        "metrics": {"url": "/metrics", "status": "available"},
        "grafana_dashboard_url": dashboard_url,
    })


@observability_bp.post("/api/observability/prometheus/query")
def prometheus_query():
    body = request.get_json(silent=True) or {}
    query = body.get("query")
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        return jsonify({"ok": False, "error": "Provide a PromQL query up to 500 characters."}), 400

    try:
        base_url = _service_url("prometheus")
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if not base_url:
        return jsonify({"ok": False, "error": "Prometheus is not configured. Set PROMETHEUS_URL."}), 503

    try:
        response = requests.get(
            f"{base_url}/api/v1/query",
            params={"query": query.strip()},
            headers=_service_headers("prometheus"),
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException:
        current_app.logger.warning("Prometheus query failed.", exc_info=True)
        return jsonify({"ok": False, "error": "Prometheus query failed."}), 502
    except ValueError:
        return jsonify({"ok": False, "error": "Prometheus returned invalid JSON."}), 502

    return jsonify({"ok": True, "result": result})


@observability_bp.post("/api/observability/loki/query")
def loki_query():
    body = request.get_json(silent=True) or {}
    query = body.get("query")
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        return jsonify({"ok": False, "error": "Provide a LogQL query up to 500 characters."}), 400

    try:
        base_url = _service_url("loki")
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if not base_url:
        return jsonify({"ok": False, "error": "Loki is not configured. Set LOKI_URL."}), 503

    end = time.time_ns()
    params = {
        "query": query.strip(),
        "start": str(end - 60 * 60 * 1_000_000_000),
        "end": str(end),
        "limit": "100",
        "direction": "backward",
    }
    try:
        response = requests.get(
            f"{base_url}/loki/api/v1/query_range",
            params=params,
            headers=_service_headers("loki"),
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException:
        current_app.logger.warning("Loki query failed.", exc_info=True)
        return jsonify({"ok": False, "error": "Loki query failed."}), 502
    except ValueError:
        return jsonify({"ok": False, "error": "Loki returned invalid JSON."}), 502

    return jsonify({"ok": True, "result": result})


@observability_bp.get("/api/observability/setup")
@requires_permission("scripts")
def setup_state():
    """Report install/run state and script locations for the optional local stack."""
    stack = _stack()
    services = {}
    for name, spec in stack.SERVICES.items():
        installed = bool(stack.homepath(name))
        script = stack.ROOT / "scripts" / f"setup_{name}.py"
        if installed:
            os.environ.setdefault(spec["env"], stack.default_url(name))
        services[name] = {
            "label": spec["label"],
            "installed": installed,
            "running": bool(stack.running_pid(name)) or stack.healthy(name, 1),
            "busy": name in _setup_jobs and _setup_jobs[name].poll() is None,
            "script": f"scripts/setup_{name}.py",
            "edit_url": "/scripts/edit/" + urlsafe_b64encode(str(script).encode()).decode(),
        }
    all_script = stack.ROOT / "scripts" / "setup_observability.py"
    return jsonify({
        "ok": True,
        "services": services,
        "all": {
            "busy": "all" in _setup_jobs and _setup_jobs["all"].poll() is None,
            "script": "scripts/setup_observability.py",
            "edit_url": "/scripts/edit/" + urlsafe_b64encode(str(all_script).encode()).decode(),
        },
    })


@observability_bp.post("/api/observability/setup/<target>/<action>")
@requires_permission("scripts")
def setup_run(target: str, action: str):
    """Run an optional setup script in the background and log its output."""
    stack = _stack()
    if target not in {*stack.SERVICES, "all"} or action not in _SETUP_ACTIONS:
        return jsonify({"ok": False, "error": "Unknown service or action."}), 400
    busy = [key for key, job in _setup_jobs.items() if job.poll() is None]
    if busy:
        return jsonify({"ok": False, "error": f"Setup already running for: {', '.join(busy)}."}), 409

    script = "setup_observability.py" if target == "all" else f"setup_{target}.py"
    log_path = _setup_log(target)
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"$ python scripts/{script} {action}\n")
    log = open(log_path, "ab")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    _setup_jobs[target] = subprocess.Popen(
        [sys.executable, "-u", str(stack.ROOT / "scripts" / script), action],
        cwd=str(stack.ROOT), stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
    )
    log.close()
    return jsonify({"ok": True, "started": f"{target} {action}"}), 202


@observability_bp.get("/api/observability/setup/<target>/log")
@requires_permission("scripts")
def setup_log(target: str):
    stack = _stack()
    if target not in {*stack.SERVICES, "all"}:
        return jsonify({"ok": False, "error": "Unknown service."}), 400
    path = _setup_log(target)
    text = path.read_text(encoding="utf-8", errors="replace")[-6000:] if path.exists() else ""
    job = _setup_jobs.get(target)
    return jsonify({
        "ok": True,
        "running": bool(job and job.poll() is None),
        "exit_code": job.poll() if job else None,
        "log": text,
    })

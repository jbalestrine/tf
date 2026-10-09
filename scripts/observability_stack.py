"""Optional, Docker-free installer/runner for Grafana, Prometheus and Loki.

Each service is downloaded as a standalone Windows build into tools/<service>/,
started in the background on localhost, and wired into MasterChief by writing
its URL (GRAFANA_URL / PROMETHEUS_URL / LOKI_URL) to .env.

Usage (also available from the Observability page and the Core Scripts GUI):
    python scripts/observability_stack.py <grafana|prometheus|loki|all> <command>

Commands: setup (install + start), install, start, stop, status, uninstall
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"
ENV_FILE = ROOT / ".env"
MASTERCHIEF_TARGET = "localhost:8080"

SERVICES = {
    "grafana": {
        "label": "Grafana",
        "env": "GRAFANA_URL",
        "port": 3000,
        "version": "12.2.0",
        "url": "https://dl.grafana.com/oss/release/grafana-{v}.windows-amd64.zip",
        "dir_glob": "grafana*",
        "exe": Path("bin") / "grafana-server.exe",
        "health": "/api/health",
    },
    "prometheus": {
        "label": "Prometheus",
        "env": "PROMETHEUS_URL",
        "port": 9090,
        "version": "3.15.0",
        "url": "https://github.com/prometheus/prometheus/releases/download/v{v}/prometheus-{v}.windows-amd64.zip",
        "dir_glob": "prometheus*",
        "exe": Path("prometheus.exe"),
        "health": "/-/healthy",
    },
    "loki": {
        "label": "Loki",
        "env": "LOKI_URL",
        "port": 3100,
        "version": "3.7.8",
        "url": "https://github.com/grafana/loki/releases/download/v{v}/loki-windows-amd64.exe.zip",
        "dir_glob": ".",
        "exe": Path("loki-windows-amd64.exe"),
        "health": "/ready",
    },
}


def service_dir(name: str) -> Path:
    return TOOLS_DIR / name


def pid_file(name: str) -> Path:
    return service_dir(name) / f"{name}.pid"


def homepath(name: str) -> Path | None:
    spec = SERVICES[name]
    base = service_dir(name)
    candidates = [base] if spec["dir_glob"] == "." else sorted(base.glob(spec["dir_glob"]))
    for candidate in candidates:
        if (candidate / spec["exe"]).exists():
            return candidate
    return None


def default_url(name: str) -> str:
    return f"http://localhost:{SERVICES[name]['port']}"


def set_env_value(key: str, value: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    out, found = [], False
    for line in lines:
        if line.split("=", 1)[0].strip() == key:
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")


def running_pid(name: str) -> int | None:
    path = pid_file(name)
    if not path.exists():
        return None
    try:
        pid = int(path.read_text().strip())
    except ValueError:
        return None
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return pid if f" {pid} " in out else None


def healthy(name: str, timeout: float = 2) -> bool:
    try:
        with urllib.request.urlopen(default_url(name) + SERVICES[name]["health"], timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except OSError:
        return False


def _download(label: str, url: str, dest: Path) -> None:
    last = {"pct": -10}

    def hook(blocks: int, size: int, total: int) -> None:
        if total <= 0:
            return
        pct = min(100, blocks * size * 100 // total)
        if pct >= last["pct"] + 10:
            last["pct"] = pct
            print(f"Downloading {label}... {pct}%", flush=True)

    urllib.request.urlretrieve(url, dest, hook)


def _write_configs(name: str, home: Path) -> None:
    base = service_dir(name)
    if name == "prometheus":
        cfg = base / "prometheus.yml"
        if not cfg.exists():
            cfg.write_text(
                "global:\n  scrape_interval: 15s\n"
                "scrape_configs:\n"
                "  - job_name: masterchief\n"
                "    metrics_path: /metrics\n"
                f"    static_configs:\n      - targets: ['{MASTERCHIEF_TARGET}']\n"
                "  - job_name: prometheus\n"
                f"    static_configs:\n      - targets: ['localhost:{SERVICES['prometheus']['port']}']\n",
                encoding="utf-8",
            )
    elif name == "loki":
        cfg = base / "loki-config.yaml"
        if not cfg.exists():
            data = (base / "data").as_posix()
            cfg.write_text(
                "auth_enabled: false\n"
                "server:\n"
                "  http_listen_address: 127.0.0.1\n"
                f"  http_listen_port: {SERVICES['loki']['port']}\n"
                "  grpc_listen_address: 127.0.0.1\n"
                "  grpc_listen_port: 9096\n"
                "common:\n"
                "  instance_addr: 127.0.0.1\n"
                f"  path_prefix: {data}\n"
                "  storage:\n"
                "    filesystem:\n"
                f"      chunks_directory: {data}/chunks\n"
                f"      rules_directory: {data}/rules\n"
                "  replication_factor: 1\n"
                "  ring:\n"
                "    kvstore:\n"
                "      store: inmemory\n"
                "schema_config:\n"
                "  configs:\n"
                "    - from: 2024-04-01\n"
                "      store: tsdb\n"
                "      object_store: filesystem\n"
                "      schema: v13\n"
                "      index:\n"
                "        prefix: index_\n"
                "        period: 24h\n"
                "limits_config:\n"
                "  allow_structured_metadata: true\n",
                encoding="utf-8",
            )
    elif name == "grafana":
        ds_dir = base / "provisioning" / "datasources"
        ds_dir.mkdir(parents=True, exist_ok=True)
        (ds_dir / "masterchief.yaml").write_text(
            "apiVersion: 1\n"
            "datasources:\n"
            "  - name: Prometheus\n    type: prometheus\n    access: proxy\n"
            f"    url: {default_url('prometheus')}\n    isDefault: true\n"
            "  - name: Loki\n    type: loki\n    access: proxy\n"
            f"    url: {default_url('loki')}\n",
            encoding="utf-8",
        )


def install(name: str, version: str | None = None) -> None:
    spec = SERVICES[name]
    if not homepath(name):
        if sys.platform != "win32":
            sys.exit(f"This helper downloads Windows builds. Install {spec['label']} yourself and set {spec['env']}.")
        base = service_dir(name)
        base.mkdir(parents=True, exist_ok=True)
        archive = base / f"{name}.zip"
        url = spec["url"].format(v=version or spec["version"])
        _download(spec["label"], url, archive)
        print(f"Extracting {spec['label']}...", flush=True)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(base)
        archive.unlink()
    home = homepath(name)
    if not home:
        sys.exit(f"{spec['label']} executable was not found after extraction.")
    _write_configs(name, home)
    set_env_value(spec["env"], default_url(name))
    print(f"{spec['label']} installed. {spec['env']}={default_url(name)} written to {ENV_FILE.name}", flush=True)


def _command(name: str, home: Path) -> tuple[list[str], dict[str, str], Path]:
    base = service_dir(name)
    exe = str(home / SERVICES[name]["exe"])
    env = os.environ.copy()
    port = SERVICES[name]["port"]
    if name == "grafana":
        env.update({
            "GF_SERVER_HTTP_PORT": str(port),
            "GF_SERVER_HTTP_ADDR": "127.0.0.1",
            "GF_PATHS_DATA": str(base / "data"),
            "GF_PATHS_LOGS": str(base / "logs"),
            "GF_PATHS_PROVISIONING": str(base / "provisioning"),
        })
        return [exe, "--homepath", str(home)], env, home
    if name == "prometheus":
        return [
            exe,
            f"--config.file={base / 'prometheus.yml'}",
            f"--web.listen-address=127.0.0.1:{port}",
            f"--storage.tsdb.path={base / 'data'}",
        ], env, home
    return [exe, f"-config.file={base / 'loki-config.yaml'}"], env, base


def start(name: str) -> None:
    spec = SERVICES[name]
    home = homepath(name)
    if not home:
        sys.exit(f"{spec['label']} is not installed. Run: python scripts/observability_stack.py {name} install")
    if running_pid(name):
        print(f"{spec['label']} is already running.", flush=True)
        return
    cmd, env, cwd = _command(name, home)
    for sub in ("data", "logs"):
        (service_dir(name) / sub).mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
    log = open(service_dir(name) / f"{name}.log", "ab")
    proc = subprocess.Popen(cmd, cwd=str(cwd), env=env, creationflags=flags, stdout=log, stderr=log)
    pid_file(name).write_text(str(proc.pid))
    for _ in range(90):
        if healthy(name):
            print(f"{spec['label']} is up at {default_url(name)}", flush=True)
            return
        if proc.poll() is not None:
            sys.exit(f"{spec['label']} exited early. See tools/{name}/{name}.log")
        time.sleep(1)
    print(f"{spec['label']} started but is not answering yet; check tools/{name}/{name}.log", flush=True)


def stop(name: str) -> None:
    pid = running_pid(name)
    if not pid:
        print(f"{SERVICES[name]['label']} is not running.", flush=True)
        return
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    pid_file(name).unlink(missing_ok=True)
    print(f"{SERVICES[name]['label']} stopped.", flush=True)


def status(name: str) -> dict[str, bool]:
    info = {"installed": bool(homepath(name)), "running": bool(running_pid(name)) or healthy(name, 1)}
    print(f"{SERVICES[name]['label']}: installed={info['installed']} running={info['running']}", flush=True)
    return info


def uninstall(name: str) -> None:
    stop(name)
    shutil.rmtree(service_dir(name), ignore_errors=True)
    print(f"Removed tools/{name}. Remove {SERVICES[name]['env']} from .env if no longer wanted.", flush=True)


def run(names: list[str], command: str, version: str | None = None) -> None:
    for name in names:
        if command == "setup":
            install(name, version)
            start(name)
        elif command == "install":
            install(name, version)
        elif command == "start":
            start(name)
        elif command == "stop":
            stop(name)
        elif command == "status":
            status(name)
        elif command == "uninstall":
            uninstall(name)
    if command in {"setup", "install"}:
        print("Done. MasterChief picks up the new URLs automatically (or after a restart).", flush=True)


def main(default_service: str | None = None, argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    if default_service is None:
        parser.add_argument("service", choices=[*SERVICES, "all"])
    parser.add_argument("command", nargs="?", default="setup",
                        choices=["setup", "install", "start", "stop", "status", "uninstall"])
    parser.add_argument("--version", default=None, help="Override the pinned download version.")
    args = parser.parse_args(argv)
    service = default_service or args.service
    names = list(SERVICES) if service == "all" else [service]
    # Prometheus and Loki first so Grafana's provisioned data sources have targets.
    names.sort(key=lambda n: n == "grafana")
    run(names, args.command, args.version if service != "all" else None)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Set up the local environment and start MasterChief Resume Studio."""

import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import venv
import webbrowser


BASE_DIR = Path(__file__).resolve().parent
ENV_DIR = BASE_DIR / ".venv"
REQUIREMENTS = BASE_DIR / "requirements.txt"
MARKER = ENV_DIR / ".masterchief-requirements"
URL = "http://127.0.0.1:8080/"


def environment_python():
    if os.name == "nt":
        return ENV_DIR / "Scripts" / "python.exe"
    return ENV_DIR / "bin" / "python"


def prepare_environment():
    if not ENV_DIR.exists():
        print(f"Creating virtual environment in {ENV_DIR}...", flush=True)
        venv.create(ENV_DIR, with_pip=True)
    python = environment_python()
    if not python.is_file():
        raise RuntimeError(
            f"The existing environment has no Python at {python}. "
            "Recreate .venv on this machine and run again."
        )
    try:
        result = subprocess.run(
            [str(python), "-c", "import sys; print(sys.prefix)"],
            cwd=BASE_DIR, capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            f"The environment at {ENV_DIR} cannot run on this machine. "
            "Recreate .venv and run again."
        ) from exc
    if Path(result.stdout.strip()).resolve() != ENV_DIR.resolve():
        raise RuntimeError(
            f"The environment at {ENV_DIR} points to a different location. "
            "Recreate .venv on this machine and run again."
        )

    digest = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    if not MARKER.is_file() or MARKER.read_text(encoding="utf-8").strip() != digest:
        print("Installing application requirements...", flush=True)
        subprocess.run(
            [str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
            cwd=BASE_DIR, check=True,
        )
        MARKER.write_text(digest + "\n", encoding="utf-8")
    return python


def open_when_ready(process):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and process.poll() is None:
        try:
            with socket.create_connection(("127.0.0.1", 8080), timeout=0.5):
                if not webbrowser.open(URL):
                    print(f"Open {URL} in a browser.", flush=True)
                return
        except OSError:
            time.sleep(0.25)
    if process.poll() is None:
        print(f"Server has not responded yet; open {URL} when it is ready.", flush=True)


def main():
    python = prepare_environment()
    print(f"Starting server at {URL}", flush=True)
    print("Warning: the server listens on all interfaces and has no authentication.", flush=True)
    process = subprocess.Popen(
        [str(python), "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"],
        cwd=BASE_DIR,
    )
    threading.Thread(target=open_when_ready, args=(process,), daemon=True).start()
    try:
        return process.wait()
    except KeyboardInterrupt:
        if process.poll() is None:
            process.terminate()
        return process.wait()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        sys.exit(1)

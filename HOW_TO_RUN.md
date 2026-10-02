# Fresh Install and Run

## Prerequisites

- Python 3.10 or newer
- Git

## One-command Install and Run

From the parent directory, paste one command for your shell. It clones the repository, sets up the base environment and bundled CLI/modules, then starts the app.

PowerShell:

```powershell
git clone https://github.com/jbalestrine/masterchief.git; if ($LASTEXITCODE -ne 0) { throw 'Clone failed' }; Set-Location masterchief; Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned; .\MasterchiefRun.ps1
```

Linux/macOS:

```bash
git clone https://github.com/jbalestrine/masterchief.git && cd masterchief && bash scripts/start.sh
```

If already cloned, run `.\MasterchiefRun.ps1` in PowerShell or `bash scripts/start.sh` in a POSIX shell. Windows uses port 8084; Linux/macOS uses port 8080. For optional integrations and advanced profiles, see [QUICKSTART.md](QUICKSTART.md) and [MASTER_SETUP.ps1](MASTER_SETUP.ps1).

## Optional Dependencies

AI and audio packages are intentionally separate from the basic install. Install all optional integrations with `python -m pip install -r requirements-optional.txt`, or install selected package extras such as `.[ai]` and `.[audio]`. Install `requirements-dev.txt` for tests and development tools.

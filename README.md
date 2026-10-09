# MasterChief V4 Recovery / Restoration Guide

MasterChief is a modular platform for DevOps, automation, dashboards, addon hosting, and AI-assisted operational workflows. This repository represents the recovered and stabilized state of the app after a major restoration pass, with route inventory corrected, dashboard navigation rebuilt, diagnostics repaired, additive feature wiring restored, and the app brought back to a working, navigable condition.

## MasterChief 4.0 MASTERCLASS

Version 4.0 consolidates the current application upgrades into a review-first release milestone. Highlights include the guided Terraform architecture workflow, readable hub-and-spoke blueprint diagrams with SVG/Visio export, code archetypes and editor handoff, expanded Echo/ChatOps and Roku workflows, and safer project navigation and diagnostics.

Generated Terraform, sandbox instructions, and CI/CD starter files are previews or validation/plan scaffolding. They do not automatically apply infrastructure. See the [4.0 MASTERCLASS release notes](docs/releases/4.0.0-masterclass.md) for the scope and limitations.

This README is meant to be both a working developer guide and a fail-safe operational document. It specifically emphasizes how to protect the current working state, create safe release branches, and roll back quickly if a deployment or code change causes issues.

## Current Recovery Status

The current branch state is intended to preserve a usable, repaired project while keeping a clean rollback path.

Key restoration areas include:
- core dashboard startup and runtime initialization
- route mapping and route inventory recovery
- UI and menu restoration
- diagnostics and system health API recovery
- gallery and metadata operations
- addon/module loading and dynamic route safety
- Echo chat and voice command support
- general project stability and route coverage

This repo should be treated as a working operational platform, not a throwaway prototype. The project has been repaired, extended, and stabilized enough to be used and released with caution.

## Critical Safety Principle

Do not push directly from the active working directory unless you have verified the branch, commit set, and release scope.

The safest process is:
- keep the current live project directory as-is
- create a dedicated release branch for the recovered work
- back up the project directory before major changes
- tag and push only the intended release branch
- keep the old version available as a reference and rollback target

## Recommended Branch Strategy

Use a separate release branch so the old version remains available for restore.

Suggested pattern:
- masterchief-V4: recovered and stabilized release branch
- legacy/backups: preserved old version branch or archived copy

Example:

```powershell
git checkout -b masterchief-V4
```

If you want to preserve an older branch for posterity instead of touching it:

```powershell
git checkout -b retro-version
```

This keeps the older version intact while allowing the recovered version to move forward cleanly.

## Backup Before Any Risky Move

Before any commit, tag, or push, create a backup of the working directory.

### Windows backup example

```powershell
Copy-Item -Recurse -Force "C:\Users\Echo\masterchief" "C:\Users\Echo\masterchief-backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
```

### Alternative archive example

```powershell
Compress-Archive -Path "C:\Users\Echo\masterchief" -DestinationPath "C:\Users\Echo\masterchief-backup-$(Get-Date -Format yyyyMMdd-HHmmss).zip" -Force
```

This is the safest fail-safe if anything goes wrong during a release or branch change.

## Fast Fail-Safe Rollback

If something breaks after a push, tag, merge, or release attempt, use the following rollback path.

### Option 1: Roll back to the last good commit

```powershell
git log --oneline --decorate --max-count=20
git checkout <last-good-commit>
```

or if you want to reset the current branch cleanly:

```powershell
git reset --hard <last-good-commit>
```

### Option 2: Revert a recent bad commit

```powershell
git revert <commit-sha>
```

### Option 3: Restore from backup folder

If the repo or working directory becomes unsafe:

```powershell
Copy-Item -Recurse -Force "C:\Users\Echo\masterchief-backup-<timestamp>" "C:\Users\Echo\masterchief"
```

or if you archived it:

```powershell
Expand-Archive -Path "C:\Users\Echo\masterchief-backup-<timestamp>.zip" -DestinationPath "C:\Users\Echo"
```

## Safe Release Workflow

Before pushing, do not use broad staging commands such as:

```powershell
git add .
```

Instead, stage intentionally:

```powershell
git status
git add -p
git diff --cached --name-only
```

Then review exactly what is being included.

### Example release tag

```powershell
git tag -a v0.9.0 -m "MasterChief V4 recovery release"
git push origin masterchief-V4 --follow-tags
```

This creates a clean, recordable version marker for the recovered build.

## Fresh Setup

Install Python 3.10 or newer and Git first. The Windows setup below matches the local source workflow: create an isolated `.venv`, install `requirements.txt` and the editable app, then serve on `0.0.0.0:8080`. Python 3.14.2 was used for the current local verification; the project supports Python 3.10+.

### Windows PowerShell: line-by-line source setup

1. Open PowerShell and go to the parent folder where you keep projects:

   ```powershell
   Set-Location C:\Users\Echo
   ```

2. Clone the repository. GitHub access is required if the repository is private:

   ```powershell
   git clone https://github.com/jbalestrine/masterchief.git
   ```

3. Enter the project:

   ```powershell
   Set-Location .\masterchief
   ```

4. Allow this PowerShell process to run the setup script (this does not change the machine-wide policy):

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```

5. Install the base application into `.venv` without starting it yet:

   ```powershell
   .\MasterchiefRun.ps1 -SetupOnly -Port 8080
   ```

   This upgrades pip, installs `requirements.txt`, and installs the source checkout in editable mode. It does not download a model or configure cloud credentials.

6. Start the app bound to this computer only:

   ```powershell
   .\.venv\Scripts\python.exe .\main.py --host 0.0.0.0 --port 8080
   ```

7. On the MasterChief machine, open [http://localhost:8080/](http://localhost:8080/) in a browser. From another device on the trusted network, use `http://<masterchief-machine-ip>:8080/`. The Terraform Wizard is at `/tf_wizard`; Echo Chat is at `/echo-chat`.

   `0.0.0.0` listens on all IPv4 interfaces; it is a bind address, not the browser URL. This deployment is intended for a trusted network. All authenticated users receive GOD access, so restrict network reachability and configure authentication accordingly.

8. Stop the foreground server with `Ctrl+C`. For later starts, repeat step 6. To have the setup script install and start in one step instead, run `.\MasterchiefRun.ps1 -Port 8080` after cloning.

### One-command Windows setup

From the parent directory, the following clones, installs, and starts the app:

```powershell
git clone https://github.com/jbalestrine/masterchief.git; if ($LASTEXITCODE -ne 0) { throw 'Clone failed' }; Set-Location .\masterchief; Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; .\MasterchiefRun.ps1 -Port 8080
```

For a prompted setup menu, use [MASTER_SETUP.ps1](MASTER_SETUP.ps1). Its default port is also 8080.

### Linux or macOS

Install Python 3.10+, Git, and a POSIX shell, then run:

```bash
git clone https://github.com/jbalestrine/masterchief.git
cd masterchief
bash scripts/start.sh
```

The POSIX starter creates or reuses `.venv` and installs `requirements.txt` on first run. It starts `run.py`; consult its startup output for the actual local URL.

### Optional capabilities and requirements files

- `requirements.txt` installs the source app's base and bundled integration dependencies.
- `requirements-optional.txt` adds heavy AI/ML, audio, asynchronous messaging, and database dependencies; it can require gigabytes of downloads and native system libraries. Do not install it unless those capabilities are needed.
- `requirements-training.txt` is for the optional local LoRA training workflow and compatible hardware/checkpoints.
- Cloud integrations use the credentials each user supplies and can operate only on resources those credentials are authorized to manage. MasterChief admin/GOD access does not expand the cloud provider's IAM permissions. Provider services also need configuration. The Terraform Wizard's generated code and CI templates do not automatically deploy resources.
- To install optional groups from the source checkout, use extras such as `python -m pip install -e ".[ai]"` or `python -m pip install -e ".[cloud]"`. See [QUICKSTART.md](QUICKSTART.md) for CLI examples.

### Observability integrations

Open the Observability Center at `/observability`. Set `PROMETHEUS_URL`, `GRAFANA_URL`, and `LOKI_URL` in the MasterChief server environment to connect existing services. Optional read-only bearer tokens are `PROMETHEUS_TOKEN`, `GRAFANA_API_TOKEN`, and `LOKI_TOKEN`. These credentials remain server-side.

**Optional local stack (no Docker).** If you don't already run these services, use the "Local stack setup" panel on `/observability`, or run the scripts directly (they also appear in Core Scripts and the Web IDE):

```powershell
python scripts/setup_observability.py setup   # Prometheus + Loki + Grafana in one go
python scripts/setup_grafana.py setup         # or one service at a time (setup_prometheus.py, setup_loki.py)
python scripts/setup_observability.py stop    # also: start, status, install, uninstall
```

Standalone Windows builds are downloaded into `tools/` (git-ignored) and bound to localhost: Grafana `:3000`, Prometheus `:9090`, Loki `:3100`. The scripts write the matching `*_URL` values to `.env`, configure Prometheus to scrape MasterChief's `/metrics` on `localhost:8080`, and provision Prometheus and Loki as Grafana data sources. Grafana's first login is `admin` / `admin`. Loki starts empty until a log shipper pushes logs to it.

MasterChief exposes request counters and latency histograms at `/metrics`. By default this endpoint is loopback-only; set `METRICS_TOKEN` to allow a Prometheus scraper on another host and configure its scrape job using [observability/prometheus-scrape-example.yml](observability/prometheus-scrape-example.yml). The sample Grafana dashboard and alert rules are in `observability/dashboards/` and `observability/alerts/`. Loki queries require a log shipper to send MasterChief logs to the configured Loki service.

### From PyPI

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install masterchief
```

The source checkout is the recommended way to run the complete web UI. The PyPI package and CLI provide a package-based installation path; optional provider services still need configuration.

## Release PyPI and Chocolatey Together

The single release entry point is [CHOCO_PYPI_DEPLOY.ps1](CHOCO_PYPI_DEPLOY.ps1). First update `setup.py` to a new version, commit the intended source, create and push a matching `v*` tag, then run from that tagged checkout. Tag pushes run package-build validation only; they do not publish separately.

In `/secrets`, add encrypted entries named `TWINE_PASSWORD` and `CHOCOLATEY_API_KEY`. Choose `API Key` for `TWINE_PASSWORD` and `Chocolatey API Key` for `CHOCOLATEY_API_KEY`. Then run:

```powershell
.\CHOCO_PYPI_DEPLOY.ps1 -DryRun
.\CHOCO_PYPI_DEPLOY.ps1 -UseVault
```

The script reads the secrets from the local encrypted Vault, builds both packages from the exact tag, verifies availability and metadata, uploads Chocolatey first and PyPI second, then clears any Vault-loaded values from its process environment. Registry uploads are not atomic: if the PyPI upload fails after Chocolatey accepts the package, fix PyPI and check both package pages before retrying.

## Core Application Layout

This project is organized around a central Flask app and modular runtime components.

### Main entry points
- main.py: application bootstrap, routes, UI shell, and app wiring
- templates/: dashboard and HTML shell assets
- blueprints/: modular route groups and feature surfaces
- features/: feature registration and manager logic
- data/: persistent app data and uploaded/generated content
- echo/: echo chat, prompt flow, and runtime logic
- addons/, modules/, scripts/: extension and automation surfaces

## Notable Functional Areas Restored

- route inventory and app shell recovery
- dashboard navigation and menu system restoration
- diagnostics and system route health checks
- gallery screens and upload workflow
- module loading and dynamic route startup safety
- Echo chat and voice command UI interactions
- internal feature manager and plugin-style registration
- platform configuration and runtime safe fallback behavior

## Do Not Do This Without Verifying

Avoid the following when preparing a release:
- force-pushing without a backup
- staging every changed file indiscriminately
- pushing from a dirty working tree without review
- replacing an old branch with a new one unless you deliberately intend to do so
- deleting the old version before preserving a restore copy

## Release Checklist

Before a push, confirm all of the following:
- project backup has been created
- working tree is reviewed
- only intended files are staged
- branch is a dedicated recovery/release branch
- version tag is created
- push is limited to the release branch and tags
- rollback path is documented and preserved

## Example Safe Commands

```powershell
# 1) create backup
Copy-Item -Recurse -Force "C:\Users\Echo\masterchief" "C:\Users\Echo\masterchief-backup-$(Get-Date -Format yyyyMMdd-HHmmss)"

# 2) branch cleanly
git checkout -b masterchief-V4

# 3) stage intentionally
git add -p

git diff --cached --name-only

# 4) commit
git commit -m "Restore app stability and dashboard functionality"

# 5) tag
git tag -a v0.9.0 -m "MasterChief V4 recovery release"

# 6) push
git push origin masterchief-V4 --follow-tags
```

## Troubleshooting Notes

If the app fails to start or route pages stop working:
1. restore from the latest backup
2. verify the app entrypoint is still main.py
3. confirm required runtime files still exist under data/ and templates/
4. check for stale artifact directories or local generated folders that may have drifted
5. revert only the last bad commit instead of a broad rollback

## Recommended Operating Principle

Treat this repository as a living operational system with a documented rollback path. The key to preserving progress is to keep old versions intact, create new release branches, and always have a backup ready before changing the repo state.

## License

This project should be treated according to the repository's existing licensing terms. See the included LICENSE file if present in the project root.

## Final Notes

This V4 recovery version is a meaningful milestone: the app is functional again, the key route structure is restored, and the system has been repaired enough to continue forward safely. The safest release is not the fastest push; it is the one that preserves the old version and allows a clean rollback if the new version has issues.

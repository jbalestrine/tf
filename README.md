# MasterChief V4 Recovery / Restoration Guide

MasterChief is a modular platform for DevOps, automation, dashboards, addon hosting, and AI-assisted operational workflows. This repository represents the recovered and stabilized state of the app after a major restoration pass, with route inventory corrected, dashboard navigation rebuilt, diagnostics repaired, additive feature wiring restored, and the app brought back to a working, navigable condition.

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

Install Python 3.10 or newer and Git first. From the parent folder, paste the one-line command for your shell; it clones the repository, installs the base app and bundled modules into a virtual environment, registers the CLI, and starts the web app.

### Windows PowerShell

```powershell
git clone https://github.com/jbalestrine/masterchief.git; if ($LASTEXITCODE -ne 0) { throw 'Clone failed' }; Set-Location masterchief; Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned; .\MasterchiefRun.ps1
```

### Linux or macOS

```bash
git clone https://github.com/jbalestrine/masterchief.git && cd masterchief && bash scripts/start.sh
```

If the repository is already cloned, run `.\MasterchiefRun.ps1` in PowerShell or `bash scripts/start.sh` on Linux/macOS. For prompted profiles and advanced options, use [MASTER_SETUP.ps1](MASTER_SETUP.ps1). Optional AI, audio, and cloud dependencies are available through `requirements-optional.txt` or the package extras.

For a prebuilt Python package install, use `python -m pip install masterchief` and then `masterchief --help`. See [QUICKSTART.md](QUICKSTART.md) for additional setup options.

## Release PyPI and Chocolatey Together

The single release entry point is [CHOCO_PYPI_DEPLOY.ps1](CHOCO_PYPI_DEPLOY.ps1). First update `setup.py` to a new version, commit the intended source, create and push a matching `v*` tag, then run from that tagged checkout. Tag pushes run package-build validation only; they do not publish separately.

In `/secrets`, add encrypted entries named `TWINE_PASSWORD` and `CHOCOLATEY_API_KEY`. Choose `API Key` for `TWINE_PASSWORD` and `Chocolatey API Key` for `CHOCOLATEY_API_KEY`. Then run:

```powershell
.\CHOCO_PYPI_DEPLOY.ps1 -DryRun
.\CHOCO_PYPI_DEPLOY.ps1 -UseVault
```

The script reads the secrets from the local encrypted Vault, builds both packages from the exact tag, verifies availability and metadata, uploads PyPI followed by Chocolatey, then clears the loaded values from its process environment. Registry uploads are not atomic: if the second upload fails, the first may already be published. Never retry the same version; fix the failed registry and check both package pages first.

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

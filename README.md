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

## Feature and module management

### UBUNTU MASTERCHIEF OS

The dashboard's **UBUNTU MASTERCHIEF OS** desktop connects an authenticated RBAC admin to
the VirtualBox VM named `MasterChief Ubuntu Test`. On the Windows server, install
VirtualBox and keep the VM's SSH key and known-hosts file in
`%LOCALAPPDATA%\MasterChief\ubuntu-test` as `ubuntu-test-ed25519` and
`ubuntu-known-hosts`. The VM must forward host loopback port 22242 to guest SSH
and run its VNC desktop on guest loopback port 5901. The dashboard connects
automatically when the VM is running. Otherwise start it with the dashboard
button, wait for Ubuntu to boot, then choose **Connect desktop**. Choose
**Full screen** to expand the desktop; choose **Exit full screen** or press
Escape to return to the dashboard. The guest resolution adapts when supported.
Disconnecting leaves the VM running. Desktop sessions end after 30 minutes and
can be reconnected. This VM uses NAT with network access; it is not a security
sandbox. Exposing MasterChief on a network gives an authenticated admin control
over this desktop, so use a strong password and HTTPS for network access.

The **Ubuntu app source** selector switches the guest app between the installed
PyPI release and a separate checkout of the `Masterchief4` branch. It restarts
the app on guest port 8080, checks its login page, and attempts to restore the
previous service if the switch fails. Their app data directories, including
RBAC accounts and settings, are separate; both use the same Ubuntu user, home
directory, network and external resources. The GitHub checkout is a snapshot, not automatically
updated; the displayed commit identifies the snapshot. Switching sources does
not guarantee feature parity: features can also depend on configuration or
optional packages. Existing provisioning places the checkout and its virtual
environment under `/home/ubuntu/masterchief-github` and
`/home/ubuntu/masterchief-github-venv`; the root-owned guest switch helper and
service are based on `scripts/ubuntu-masterchief-source` and
`scripts/ubuntu-masterchief-github.service`.

The desktop client bundles noVNC 1.7.0 (MPL-2.0) and its included pako
components. Their licenses and attribution are in `static/novnc-*.txt`.
Unmodified noVNC source is available from the [noVNC 1.7.0 release](https://github.com/novnc/noVNC/tree/v1.7.0)
and the package/version pinned in `package-lock.json`; rebuild the client with `npm ci` and
`npm run build:ubuntu-desktop`.

The **Management Center** menu links Master Menu (page flags and navigation),
Feature Management (configured handlers), Module Management (built-in manager
configuration), Add-on Modules (installed files and services), and Code Manager
(isolated app features and linked blueprints). These are separate controls and
do not necessarily enable or disable the same underlying component.

The Feature Management, Module Management, and Add-on Modules pages include a
shared, searchable **Platform inventory** for the authenticated RBAC platform
administrator. It combines configured features, isolated app features, built-in
managers, page flags, blueprints, add-on folders, and historical add-on feature
entries. A discovered folder or registry entry is not proof that it is runnable;
the inventory labels unverified states and keeps configured and runtime states
separate. Use the linked management page for the controls supported by each
system. Inventory entries do not add enable/disable controls to unsupported
components.

Configured-feature and built-in-module changes require a MasterChief restart.
Existing routes can remain available until restart; enabling a feature runs
its handler on the next startup. Core RBAC cannot be disabled from the module
page. Isolated app features are managed in Code Manager and also require a
restart. Add-on process start/stop is a separate operation and does not mean
that all features within an add-on can be toggled individually.

The **Git Command Center** at `/sys/scm` provides an admin-only workflow guide
and allowlisted Git/GitHub CLI actions for the MasterChief repository. Mutating
actions require confirmation; high-risk recovery actions can discard work or
rewrite history. Inspect status and staged changes before committing or pushing.
The Command Center and Git Workflow Field Guide include an executable everyday
walkthrough: check status, optionally stage all with `git add -A`, review status
and staged diff, commit, then push. Stage all includes tracked edits and
deletions plus non-ignored new files across the repository; choose individual
paths instead when appropriate. Commits include everything already staged.
Open **Quick guided Git workflow** on either Git page to check for an existing
PR, create one if needed, review it, explicitly confirm a merge commit, and
fetch the base before creating and switching to the next feature branch. A
push updates an existing PR but does not create one. Review GitHub checks,
approvals, the PR number and base before merging; a merge may be blocked or
queued by repository policies. The workflow does not request branch deletion:
keep local and remote branches until deliberate cleanup is appropriate, though
GitHub settings may automatically delete a merged remote branch. Branches are
references, not backups; verify work before switching or cleanup.
The pull request overview shows open, closed and merged PRs in GitHub's
most-recently-updated order, with pagination and links to review them on
GitHub. The activity shown is from GitHub, not an app-only action history.
Selecting an open PR prepares a confirmed merge action; it does not merge
automatically. The list uses the repository GitHub CLI resolves from the
local MasterChief repository and requires administrator access.
Commands run non-interactively; configure Git and GitHub authentication outside
the app first. PR creation and pushes affect the remote repository immediately.
Its Source Control navigation also links to **GitHub Integration** (`/github`)
for browsing and cloning repositories and saving scripts. Selecting or cloning
a repository there does not change the repository used by Git Command Center.
The Browse Files tab lists actual cloned repositories in `data/github_repos`
and refreshes when opened. The remote browser and GitHub repository list use
the server's GitHub CLI login and require Source Control administrator access.
Other GitHub integration API operations may still use the app's separate
`GITHUB_TOKEN` configuration. Errors are displayed rather than reported as an
empty list.
Both pages link to the Git Workflow Field Guide, including the everyday diagram,
safety and recovery notes, and the downloadable four-page editable Visio file.
The guide's **Check update & PR** button reports local uncommitted changes,
compares HEAD directly with its configured remote upstream, and finds the
latest-created same-repository PR for the current branch in the GitHub
CLI-resolved repository; fork-based PRs are not included.
It performs read-only network checks without fetching; a different remote HEAD
does not identify whether the branch is ahead or behind. A merged PR with a
different head does not establish that the current commit was merged.
The optional **Release Journey** visualizes the same workflow as workshop,
checkpoint, launch, review, merge, and arrival. Opening or refreshing it
performs read-only status and network checks; action buttons prepare the
existing confirmed commands. The completion receipt requires GitHub to report
a merged PR and matching commit information; it is not a deployment status.
Refresh after changes outside the app. PRs from forks are not included.
The guide also runs the same admin-protected commands and shows working-tree
and latest-commit file activity. A rotatable 3D file ecosystem complements
the grouped file list and import relationship list; select a file to see its
direct imports and importers. Its Python import data is static and
best-effort: it is not a runtime dependency map, does not cover other
languages or dynamic imports, and displays its scan and result limits.
File links open the MasterChief Code UI for editing the local repository;
Web IDE permission is required and deleted, binary, or non-UTF-8 files may
not be readable. The ecosystem and its editor links do not target repositories
selected in GitHub Integration.
Selecting a file in the activity list or 3D map also opens an inline editor.
Saving requires Source Control admin access and rejects a file changed since
opening. Stage and commit are separate confirmed actions; committing includes
all staged files, which the editor displays for review before confirmation.
The main navigation, Git Command Center, and GitHub Integration link directly
to the file ecosystem. Source Map reports duplicate registered route patterns
as warnings; review their handlers before changing registration order.

The **Workspaces** button opens a separate searchable slide-out navigation for
signed-in users without replacing existing menus. It groups common destinations
by task, folds less-used tools into expandable sections, and includes loaded
feature navigation and installed add-ons. The dashboard offers task-based
starting points, system metrics, and the original quick actions. Use the star
beside a workspace to add or remove a favorite. Favorites and the last eight
workspaces opened through the drawer or dashboard are stored in that browser,
not synchronized between devices; clear recent workspaces from the dashboard.
Saved destinations are shown only when they still appear in the current
catalog. Browser storage restrictions are reported in the interface.
Links containing query parameters are not saved as favorites or recent
workspaces, to avoid retaining potentially sensitive parameters.
Pinned add-ons link to their pinned
entry; other installed add-ons open their manager without automatically starting
them. Links do not override permissions or feature flags. The directory uses
curated app links and registered feature navigation, not arbitrary API routes;
the Unified Site Map remains available for technical route discovery.

The dashboard's **Your workspace & next step** check is read-only and runs only
when requested. It requires Source Control admin access and contacts GitHub;
its result is a snapshot, not an automatic monitor. It checks the local
MasterChief repository, not a clone selected in GitHub Integration. Remote
differences do not establish which side is ahead, and fork-based pull requests
and ignored files are excluded. The expandable tour can be reopened after
dismissal, and the safety center links to recovery guidance.

The Git Command Center and workflow guide show **command receipts** for
confirmed commands executed through their shared command panel in the current
browser tab. Receipts show the branch observed before execution and the outcome;
an interrupted request is explicitly unconfirmed. They are stored in session
storage and disappear when the tab closes; they are not a complete audit log,
do not include actions through other app interfaces or outside the app, and
should not be used to verify a merge. Storage errors are displayed.

On the main menu, **Build → Pinned Add-ons** includes a **Start** button next
to each pinned add-on link. Pin an installed add-on from Add-on Modules first.
Start checks its current service state and starts it only if stopped; the link
remains separate and does not open automatically. A newly started service may
take a few seconds to be ready. Use Add-on Modules to stop services or manage
installation and configuration.

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

MasterChief exposes request counters and latency histograms at `/metrics`. By default this endpoint is loopback-only; set `METRICS_TOKEN` to allow a Prometheus scraper on another host and configure its scrape job using [observability/prometheus-scrape-example.yml](observability/prometheus-scrape-example.yml). The sample Grafana dashboard and alert rules are in `observability/dashboards/` and `observability/alerts/`. Loki queries require a log shipper to send MasterChief logs to the configured Loki service.

### From PyPI

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install masterchief
```

The source checkout is the recommended way to run the complete web UI. The PyPI package and CLI provide a package-based installation path; optional provider services still need configuration.

The dashboard's process panel shows processes on the MasterChief server, not
necessarily the browser's computer. It requires an authenticated RBAC admin
and samples CPU as a percentage of total server CPU between refreshes; memory
is resident memory. Per-process disk, network, GPU and power readings are not
provided. Expanding the panel allows selecting a process and confirming a
termination request. The server process and protected system PIDs cannot be
ended from this panel; operating system permissions still apply. A termination
request is not proof the process has exited, so refresh to check.

### Publish to PyPI only

[PYPI_ONLY_DEPLOY.ps1](PYPI_ONLY_DEPLOY.ps1) builds a locally available,
matching semantic tag and publishes only to PyPI. First update `setup.py` to
an unused version, commit and merge the intended changes, and create and push
the matching tag for that merged commit. The script builds the tag, not
uncommitted changes or necessarily the current checkout. Use a Python
environment with `build` and `twine` already installed, Git, and network
access. Replace `v1.2.3` below with the actual release tag:

```powershell
.\PYPI_ONLY_DEPLOY.ps1 -Tag v1.2.3 -DryRun
.\PYPI_ONLY_DEPLOY.ps1 -Tag v1.2.3 -UseVault
```

The dry run checks PyPI version availability and builds and validates the
artifacts without uploading. For the actual upload, store the PyPI token as
`TWINE_PASSWORD` in the local encrypted Vault at `/secrets`, or configure it in
the process environment. Check the PyPI project page after upload or an
uncertain failure. The checked-in PyPI GitHub workflow has an invalid first
key and must be repaired and tested before relying on it; if repaired, a
published GitHub release is configured to trigger a separate PyPI upload.
The Git Command Center and Git Workflow Guide also offer Windows-server buttons
for a dry run and a separately confirmed publish using the server's selected
Python interpreter and Vault. The guided steps distinguish saving a local
version from committing and pushing it, merging the PR, tagging, and publishing.
A PR needs a new commit pushed to the feature branch; saving a file alone does
not add it to GitHub. Verify the published version and both artifacts on PyPI
before considering the release complete. The UI requires a successful dry run first and
rechecks the tag's commit before publishing. Its guided tag button checks the
live `origin/Masterchief4` commit against the local tracking ref, reads the
version from that committed `setup.py`, and creates and pushes the matching tag
only after confirmation. Fetch origin if the tracking ref is stale; update and
merge the version first if a new version is needed. It never replaces an
existing tag. If tag pushing fails, the local tag may remain; inspect both
before retrying. The Source Control admin guards apply. An interrupted or timed-out
upload has an unconfirmed outcome: inspect PyPI before retrying. Do not rely on
the in-process lock to coordinate separate app server processes.
The version editor in the same panel suggests the next patch based on the
working-copy `setup.py` version; it does not verify PyPI availability. After
confirmation it changes only that file on the selected feature branch, with a
stale-file and branch check. Review, stage, commit, push and merge the change
before preparing the merged release tag.

## Release PyPI and Chocolatey Together

**Release setup needs repair before use:** [chocolatey/release.ps1](chocolatey/release.ps1) downloads tagged source from `jbalestrine/masterchief`, which may differ from this checkout's `origin` (`jbalestrine/tf`). Verify the intended repository and tag and correct the source URL before publishing. The checked-in `.github/workflows/pypi-publish.yml` currently has an invalid first key; do not rely on its build or publish jobs until it is repaired and tested. If repaired, a GitHub published-release event is configured to publish to PyPI separately, so avoid competing uploads.

The existing combined release entry point is [CHOCO_PYPI_DEPLOY.ps1](CHOCO_PYPI_DEPLOY.ps1); it publishes to both registries, not just PyPI. First update `setup.py` to an unused version, commit and merge the intended source, create and push a matching semantic `v*` tag to the verified source repository, then run from that exact tagged checkout. Uncommitted changes are excluded. The script installs `build` and `twine` into the selected Python environment, including for a dry run.

In `/secrets`, add encrypted entries named `TWINE_PASSWORD` and `CHOCOLATEY_API_KEY`. Choose `API Key` for `TWINE_PASSWORD` and `Chocolatey API Key` for `CHOCOLATEY_API_KEY`. Then run:

```powershell
.\CHOCO_PYPI_DEPLOY.ps1 -DryRun
.\CHOCO_PYPI_DEPLOY.ps1 -UseVault
```

The script reads the secrets from the local encrypted Vault, builds both packages from the exact tag, verifies availability and metadata, uploads Chocolatey first and PyPI second, then clears any Vault-loaded values from its process environment. Registry uploads are not atomic: if the PyPI upload fails after Chocolatey accepts the package, fix PyPI and check both package pages before retrying.
The Git Command Center and Git Workflow Guide also show this checklist under **PYPI DEPLOY**. Neither merging nor pushing a tag confirms that a package was published; check both registry pages.

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

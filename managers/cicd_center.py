"""CI/CD control center: inspect workflows, choose deploy targets, trigger pipelines.

Secrets are read from environment variables only and are never stored or returned.
Every trigger defaults to a dry run that reports what would be sent.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import requests
import yaml

REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/\-]{0,199}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$")
SLUG_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,100}$")
HTTP_TIMEOUT = 20


class CICDError(ValueError):
    """Raised for invalid input or a failed provider call."""


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def _glob_match(patterns: list[str], value: str) -> bool:
    return any(fnmatch.fnmatchcase(value, p.replace("**", "*")) for p in patterns)


class CICDCenter:
    PROVIDER_INFO = [
        {
            "id": "github",
            "name": "GitHub Actions",
            "needs": "Free. Public repos have unlimited minutes; private repos get a monthly free allowance. Self-hosted runners cost nothing extra.",
            "auth": "`gh auth login` on this machine (or GH_TOKEN).",
        },
        {
            "id": "gitlab",
            "name": "GitLab CI/CD",
            "needs": "Free tier on gitlab.com has a limited monthly compute allowance. Self-managed GitLab and your own GitLab Runner are free.",
            "auth": "Env GITLAB_TOKEN (personal/project access token with api scope). Optional GITLAB_URL.",
        },
        {
            "id": "tfe",
            "name": "Terraform Cloud / Enterprise",
            "needs": "HCP Terraform has a free tier with limits. Terraform Enterprise (self-hosted) needs a paid license. Check HashiCorp pricing for current limits.",
            "auth": "Env TFE_TOKEN (user/team token). Optional TFE_ADDRESS for Enterprise.",
        },
        {
            "id": "render",
            "name": "Render deploy hook",
            "needs": "Any Render service has a deploy hook URL; no extra subscription.",
            "auth": "Env RENDER_DEPLOY_HOOK_URL (treat the URL as a secret).",
        },
    ]

    def __init__(self, project_root: str | Path):
        self.root = Path(project_root).resolve()
        self.workflow_dir = self.root / ".github" / "workflows"
        self.config_path = self.root / "data" / "cicd_config.json"

    # ---------- config ----------
    def default_config(self) -> dict:
        return {
            "repo": self._origin_repo(),
            "ref": self._git(["branch", "--show-current"]) or "main",
            "selected": [],
            "gitlab": {"url": os.environ.get("GITLAB_URL", "https://gitlab.com"), "project": ""},
            "tfe": {"org": "", "workspace": "", "message": "Triggered from MasterChief"},
        }

    def load_config(self) -> dict:
        config = self.default_config()
        try:
            stored = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stored = {}
        if isinstance(stored, dict):
            for key, value in stored.items():
                if isinstance(value, dict) and isinstance(config.get(key), dict):
                    config[key].update(value)
                elif key in config:
                    config[key] = value
        return config

    def save_config(self, update: dict) -> dict:
        if not isinstance(update, dict):
            raise CICDError("Config must be an object.")
        config = self.load_config()
        if "repo" in update:
            repo = str(update["repo"] or "").strip()
            if repo and not REPO_RE.match(repo):
                raise CICDError("Repository must look like owner/name.")
            config["repo"] = repo
        if "ref" in update:
            config["ref"] = self._check_ref(update["ref"])
        if "selected" in update:
            valid = {t["id"] for t in self.targets()}
            selected = [str(s) for s in _as_list(update["selected"])]
            unknown = [s for s in selected if s not in valid]
            if unknown:
                raise CICDError("Unknown target: " + ", ".join(unknown))
            config["selected"] = selected
        if isinstance(update.get("gitlab"), dict):
            url = str(update["gitlab"].get("url", config["gitlab"]["url"])).strip().rstrip("/")
            if not re.match(r"^https?://[A-Za-z0-9.\-:]+(/[A-Za-z0-9._/\-]*)?$", url):
                raise CICDError("GitLab URL must be http(s)://host.")
            project = str(update["gitlab"].get("project", config["gitlab"]["project"])).strip()
            if project and not re.match(r"^[A-Za-z0-9_.\-/]+$", project):
                raise CICDError("GitLab project must be an id or group/project path.")
            config["gitlab"] = {"url": url, "project": project}
        if isinstance(update.get("tfe"), dict):
            tfe = dict(config["tfe"])
            for key in ("org", "workspace"):
                value = str(update["tfe"].get(key, tfe[key])).strip()
                if value and not SLUG_RE.match(value):
                    raise CICDError(f"Invalid TFE {key}.")
                tfe[key] = value
            tfe["message"] = str(update["tfe"].get("message", tfe["message"]))[:200]
            config["tfe"] = tfe
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return config

    # ---------- git helpers ----------
    def _git(self, args: list[str]) -> str:
        try:
            result = subprocess.run(
                ["git", *args], cwd=self.root, capture_output=True, text=True, timeout=15
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return result.stdout.strip() if result.returncode == 0 else ""

    def _origin_repo(self) -> str:
        url = self._git(["remote", "get-url", "origin"])
        match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
        return match.group(1) if match else ""

    def git_info(self) -> dict:
        remotes = {}
        for line in self._git(["remote", "-v"]).splitlines():
            parts = line.split()
            if len(parts) >= 2 and line.endswith("(push)"):
                remotes[parts[0]] = parts[1]
        return {
            "branch": self._git(["branch", "--show-current"]),
            "upstream": self._git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]),
            "remotes": remotes,
            "branches": [b for b in self._git(["branch", "--format", "%(refname:short)"]).splitlines() if b],
        }

    @staticmethod
    def _check_ref(value: Any) -> str:
        ref = str(value or "").strip()
        if not REF_RE.match(ref) or ".." in ref:
            raise CICDError("Invalid branch or tag name.")
        return ref

    # ---------- workflow analysis ----------
    def workflows(self) -> list[dict]:
        found = []
        if not self.workflow_dir.is_dir():
            return found
        for path in sorted(self.workflow_dir.glob("*.y*ml")):
            try:
                doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                found.append({"file": path.name, "name": path.name, "error": "Could not parse YAML", "triggers": {}, "jobs": [], "dispatchable": False})
                continue
            if not isinstance(doc, dict):
                continue
            on = doc.get("on", doc.get(True, {}))
            if isinstance(on, str):
                on = {on: {}}
            elif isinstance(on, list):
                on = {str(k): {} for k in on}
            elif not isinstance(on, dict):
                on = {}
            triggers: dict[str, dict] = {}
            for event, cfg in on.items():
                cfg = cfg if isinstance(cfg, dict) else {}
                entry = {k: _as_list(cfg.get(k)) for k in ("branches", "branches-ignore", "tags", "tags-ignore", "paths", "types") if cfg.get(k)}
                if event == "workflow_dispatch":
                    entry["inputs"] = {
                        str(name): {
                            "description": str((spec or {}).get("description", "")),
                            "default": (spec or {}).get("default"),
                            "required": bool((spec or {}).get("required", False)),
                        }
                        for name, spec in (cfg.get("inputs") or {}).items()
                    }
                if event == "schedule":
                    entry = {"cron": [c.get("cron") for c in on[event] if isinstance(c, dict)]}
                triggers[str(event)] = entry
            jobs = [
                {"id": str(jid), "name": str((job or {}).get("name", jid)), "runs_on": (job or {}).get("runs-on")}
                for jid, job in (doc.get("jobs") or {}).items()
            ]
            found.append({
                "file": path.name,
                "name": str(doc.get("name", path.name)),
                "triggers": triggers,
                "jobs": jobs,
                "dispatchable": "workflow_dispatch" in triggers,
            })
        return found

    @staticmethod
    def _push_matches(trigger: dict, branch: str | None, tag: str | None) -> bool:
        if tag:
            tags = trigger.get("tags", [])
            if trigger.get("tags-ignore") and _glob_match(trigger["tags-ignore"], tag):
                return False
            if tags:
                return _glob_match(tags, tag)
            return not trigger.get("branches")
        if branch:
            if trigger.get("branches-ignore") and _glob_match(trigger["branches-ignore"], branch):
                return False
            if trigger.get("branches"):
                return _glob_match(trigger["branches"], branch)
            return not trigger.get("tags")
        return False

    def explain(self, event: str, ref: str) -> list[dict]:
        """Which workflows would start for `event` ('push', 'pull_request', 'release') on `ref`."""
        ref = self._check_ref(ref)
        results = []
        for wf in self.workflows():
            trigger = wf["triggers"].get(event)
            runs, why = False, "No " + event + " trigger"
            if trigger is not None:
                if event == "push":
                    is_tag = ref.startswith("v") and bool(re.match(r"^v?\d", ref))
                    runs = self._push_matches(trigger, None if is_tag else ref, ref if is_tag else None)
                    why = "Matches the push filters" if runs else "Branch/tag filters do not match"
                elif event == "pull_request":
                    branches = trigger.get("branches")
                    runs = not branches or _glob_match(branches, ref)
                    why = "Matches the PR target filters" if runs else "PR target branch filters do not match"
                else:
                    runs, why = True, "Triggers on every " + event
            results.append({"file": wf["file"], "name": wf["name"], "runs": runs, "reason": why})
        return results

    # ---------- targets ----------
    def targets(self) -> list[dict]:
        items = []
        for wf in self.workflows():
            items.append({
                "id": "gh:" + wf["file"],
                "provider": "github",
                "label": wf["name"],
                "detail": wf["file"] + (" (manual run supported)" if wf["dispatchable"] else " (needs a workflow_dispatch trigger to run manually)"),
                "available": wf["dispatchable"],
            })
        items.append({"id": "gitlab:pipeline", "provider": "gitlab", "label": "GitLab pipeline", "detail": "Starts a pipeline on the configured project/ref", "available": True})
        items.append({"id": "tfe:run", "provider": "tfe", "label": "Terraform Cloud run", "detail": "Queues a run on the configured workspace", "available": True})
        items.append({"id": "render:deploy", "provider": "render", "label": "Render deploy", "detail": "Calls the Render deploy hook", "available": True})
        return items

    # ---------- providers ----------
    @staticmethod
    def _gh(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        if not shutil.which("gh"):
            raise CICDError("GitHub CLI (gh) is not installed.")
        return subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout)

    def _repo(self, config: dict) -> str:
        repo = config.get("repo") or ""
        if not REPO_RE.match(repo):
            raise CICDError("Set the GitHub repository (owner/name) first.")
        return repo

    def provider_status(self) -> list[dict]:
        statuses = []
        for info in self.PROVIDER_INFO:
            status = dict(info)
            if info["id"] == "github":
                status["configured"] = bool(shutil.which("gh"))
                status["note"] = "gh CLI found" if status["configured"] else "gh CLI not installed"
            elif info["id"] == "gitlab":
                status["configured"] = bool(os.environ.get("GITLAB_TOKEN"))
                status["note"] = "GITLAB_TOKEN set" if status["configured"] else "GITLAB_TOKEN not set"
            elif info["id"] == "tfe":
                status["configured"] = bool(os.environ.get("TFE_TOKEN"))
                status["note"] = "TFE_TOKEN set" if status["configured"] else "TFE_TOKEN not set"
            else:
                status["configured"] = bool(os.environ.get("RENDER_DEPLOY_HOOK_URL"))
                status["note"] = "Deploy hook set" if status["configured"] else "RENDER_DEPLOY_HOOK_URL not set"
            statuses.append(status)
        return statuses

    def test_provider(self, provider: str) -> dict:
        """Read-only connectivity check. Never triggers anything."""
        config = self.load_config()
        try:
            if provider == "github":
                result = self._gh(["auth", "status"])
                ok = result.returncode == 0
                return {"ok": ok, "message": (result.stdout + result.stderr).strip().splitlines()[0] if (result.stdout + result.stderr).strip() else ("Authenticated" if ok else "Not authenticated")}
            if provider == "gitlab":
                token = os.environ.get("GITLAB_TOKEN")
                if not token:
                    return {"ok": False, "message": "GITLAB_TOKEN is not set."}
                resp = requests.get(config["gitlab"]["url"] + "/api/v4/user", headers={"PRIVATE-TOKEN": token}, timeout=HTTP_TIMEOUT)
                return {"ok": resp.ok, "message": f"GitLab answered HTTP {resp.status_code}" + (f" as {resp.json().get('username')}" if resp.ok else "")}
            if provider == "tfe":
                token = os.environ.get("TFE_TOKEN")
                if not token:
                    return {"ok": False, "message": "TFE_TOKEN is not set."}
                resp = requests.get(self._tfe_base() + "/api/v2/account/details", headers=self._tfe_headers(token), timeout=HTTP_TIMEOUT)
                return {"ok": resp.ok, "message": f"Terraform answered HTTP {resp.status_code}"}
            if provider == "render":
                return {"ok": bool(os.environ.get("RENDER_DEPLOY_HOOK_URL")), "message": "Deploy hook is configured (not called)." if os.environ.get("RENDER_DEPLOY_HOOK_URL") else "RENDER_DEPLOY_HOOK_URL is not set."}
        except (requests.RequestException, subprocess.SubprocessError, CICDError) as exc:
            return {"ok": False, "message": f"{type(exc).__name__}: {exc}"}
        raise CICDError("Unknown provider.")

    def recent_runs(self, limit: int = 15) -> dict:
        config = self.load_config()
        try:
            repo = self._repo(config)
            result = self._gh([
                "run", "list", "-R", repo, "--limit", str(max(1, min(limit, 50))),
                "--json", "databaseId,workflowName,displayTitle,status,conclusion,headBranch,event,createdAt,url",
            ])
        except (CICDError, subprocess.SubprocessError) as exc:
            return {"ok": False, "error": str(exc), "runs": []}
        if result.returncode != 0:
            return {"ok": False, "error": (result.stderr or "gh run list failed").strip()[:300], "runs": []}
        try:
            return {"ok": True, "runs": json.loads(result.stdout or "[]")}
        except ValueError:
            return {"ok": False, "error": "Unexpected gh output.", "runs": []}

    # ---------- triggering ----------
    def _tfe_base(self) -> str:
        address = os.environ.get("TFE_ADDRESS", "https://app.terraform.io").rstrip("/")
        if not re.match(r"^https?://[A-Za-z0-9.\-:]+$", address):
            raise CICDError("TFE_ADDRESS is invalid.")
        return address

    @staticmethod
    def _tfe_headers(token: str) -> dict:
        return {"Authorization": "Bearer " + token, "Content-Type": "application/vnd.api+json"}

    def plan(self, selected: list[str], ref: str, config: dict | None = None) -> list[dict]:
        config = config or self.load_config()
        ref = self._check_ref(ref)
        known = {t["id"]: t for t in self.targets()}
        steps = []
        for target_id in selected:
            target = known.get(target_id)
            if target is None:
                raise CICDError("Unknown target: " + str(target_id))
            step = {"id": target_id, "provider": target["provider"], "label": target["label"]}
            if target["provider"] == "github":
                if not target["available"]:
                    raise CICDError(f"{target['label']} has no workflow_dispatch trigger, so it cannot be run manually.")
                step["action"] = f"gh workflow run {target_id[3:]} -R {self._repo(config)} --ref {ref}"
            elif target["provider"] == "gitlab":
                project = config["gitlab"]["project"]
                if not project:
                    raise CICDError("Set the GitLab project first.")
                step["action"] = f"POST {config['gitlab']['url']}/api/v4/projects/{project}/pipeline?ref={ref}"
            elif target["provider"] == "tfe":
                if not (config["tfe"]["org"] and config["tfe"]["workspace"]):
                    raise CICDError("Set the Terraform org and workspace first.")
                step["action"] = f"Queue a run on {config['tfe']['org']}/{config['tfe']['workspace']}"
            else:
                step["action"] = "POST to the Render deploy hook"
            steps.append(step)
        return steps

    def run(self, selected: list[str], ref: str, dry_run: bool = True) -> dict:
        config = self.load_config()
        ref = self._check_ref(ref)
        steps = self.plan(selected, ref, config)
        if dry_run:
            return {"dry_run": True, "ref": ref, "steps": [dict(s, status="planned") for s in steps]}
        results = []
        for step in steps:
            try:
                message = self._execute(step, ref, config)
                results.append(dict(step, status="started", message=message))
            except (CICDError, requests.RequestException, subprocess.SubprocessError) as exc:
                results.append(dict(step, status="failed", message=f"{type(exc).__name__}: {exc}"))
        return {"dry_run": False, "ref": ref, "steps": results}

    def _execute(self, step: dict, ref: str, config: dict) -> str:
        provider = step["provider"]
        if provider == "github":
            result = self._gh(["workflow", "run", step["id"][3:], "-R", self._repo(config), "--ref", ref])
            if result.returncode != 0:
                raise CICDError((result.stderr or "gh workflow run failed").strip()[:300])
            return "Workflow dispatched."
        if provider == "gitlab":
            token = os.environ.get("GITLAB_TOKEN")
            if not token:
                raise CICDError("GITLAB_TOKEN is not set.")
            project = requests.utils.quote(config["gitlab"]["project"], safe="")
            resp = requests.post(f"{config['gitlab']['url']}/api/v4/projects/{project}/pipeline", params={"ref": ref}, headers={"PRIVATE-TOKEN": token}, timeout=HTTP_TIMEOUT)
            if not resp.ok:
                raise CICDError(f"GitLab returned HTTP {resp.status_code}")
            return "Pipeline " + str(resp.json().get("id", "")) + " created."
        if provider == "tfe":
            token = os.environ.get("TFE_TOKEN")
            if not token:
                raise CICDError("TFE_TOKEN is not set.")
            base, headers = self._tfe_base(), self._tfe_headers(token)
            ws = requests.get(f"{base}/api/v2/organizations/{config['tfe']['org']}/workspaces/{config['tfe']['workspace']}", headers=headers, timeout=HTTP_TIMEOUT)
            if not ws.ok:
                raise CICDError(f"Workspace lookup returned HTTP {ws.status_code}")
            body = {"data": {"type": "runs", "attributes": {"message": config["tfe"]["message"]}, "relationships": {"workspace": {"data": {"type": "workspaces", "id": ws.json()["data"]["id"]}}}}}
            resp = requests.post(base + "/api/v2/runs", headers=headers, json=body, timeout=HTTP_TIMEOUT)
            if not resp.ok:
                raise CICDError(f"Run creation returned HTTP {resp.status_code}")
            return "Run queued (it still needs plan approval in Terraform unless auto-apply is on)."
        hook = os.environ.get("RENDER_DEPLOY_HOOK_URL")
        if not hook:
            raise CICDError("RENDER_DEPLOY_HOOK_URL is not set.")
        resp = requests.post(hook, timeout=HTTP_TIMEOUT)
        if not resp.ok:
            raise CICDError(f"Render returned HTTP {resp.status_code}")
        return "Render deploy requested."

    # ---------- generators ----------
    def gitlab_ci_template(self) -> str:
        return (
            "# Generated by MasterChief. Review before committing.\n"
            "stages: [test, package, deploy]\n\n"
            "test:\n  stage: test\n  image: python:3.13\n"
            "  script:\n    - pip install -r requirements.txt\n    - pytest -q\n\n"
            "package:\n  stage: package\n  image: python:3.13\n"
            "  script:\n    - pip install build\n    - python -m build\n"
            "  artifacts:\n    paths: [dist/]\n"
            "  rules:\n    - if: $CI_COMMIT_TAG\n\n"
            "deploy_render:\n  stage: deploy\n  image: curlimages/curl\n"
            "  script:\n    - curl -fsS -X POST \"$RENDER_DEPLOY_HOOK_URL\"\n"
            "  rules:\n    - if: $CI_COMMIT_BRANCH == \"main\"\n      when: manual\n"
        )

    def write_gitlab_ci(self) -> str:
        path = self.root / ".gitlab-ci.yml"
        if path.exists():
            raise CICDError(".gitlab-ci.yml already exists; it will not be overwritten.")
        path.write_text(self.gitlab_ci_template(), encoding="utf-8", newline="\n")
        return str(path.name)

    def overview(self) -> dict:
        config = self.load_config()
        branch = self.git_info()["branch"] or config["ref"]
        return {
            "config": config,
            "git": self.git_info(),
            "workflows": self.workflows(),
            "targets": self.targets(),
            "providers": self.provider_status(),
            "current_branch_push": self.explain("push", branch) if REF_RE.match(branch or "") else [],
        }

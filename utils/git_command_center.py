"""Allowlisted Git workflow commands for the local command center."""

import json
import os
import re
import subprocess


# Commands are argument vectors, never shell strings. Parameters must be supplied
# individually and refs cannot be interpreted as options.
COMMANDS = {
    "status": ("Inspect", "Working tree", ["git", "status"], [], False),
    "status_short": ("Inspect", "Short status", ["git", "status", "--short"], [], False),
    "status_all": ("Inspect", "All untracked files", ["git", "status", "--short", "--untracked-files=all"], [], False),
    "branches": ("Inspect", "Branches and upstreams", ["git", "branch", "-vv"], [], False),
    "remotes": ("Inspect", "Remote destinations", ["git", "remote", "-v"], [], False),
    "log": ("Inspect", "Recent history", ["git", "log", "--oneline", "--decorate", "-10"], [], False),
    "diff": ("Inspect", "Unstaged diff", ["git", "diff"], [], False),
    "staged_diff": ("Inspect", "Staged diff", ["git", "diff", "--staged"], [], False),
    "show_stat": ("Inspect", "Inspect commit summary", ["git", "show", "--stat", "{ref}", "--"], ["ref"], False),
    "show": ("Inspect", "Inspect commit", ["git", "show", "{ref}", "--"], ["ref"], False),
    "reflog": ("Recovery", "Local reflog", ["git", "reflog"], [], False),
    "check_ignore": ("Inspect", "Check ignore rule", ["git", "check-ignore", "-v", "--", "{path}"], ["path"], False),
    "fetch": ("Prepare", "Fetch origin", ["git", "fetch", "origin"], [], True),
    "prune": ("Recovery", "Fetch and prune stale remote references", ["git", "fetch", "--prune", "origin"], [], True),
    "new_branch": ("Prepare", "Create feature branch from a ref", ["git", "switch", "-c", "{branch}", "{ref}"], ["branch", "ref"], True),
    "switch_branch": ("Prepare", "Switch to an existing branch", ["git", "switch", "{branch}"], ["branch"], True),
    "stage": ("Save", "Stage a selected path", ["git", "add", "--", "{path}"], ["path"], True),
    "stage_all": ("Save", "Stage all changes", ["git", "add", "-A"], [], True),
    "commit": ("Save", "Commit staged files", ["git", "commit", "-m", "{message}"], ["message"], True),
    "push_upstream": ("Publish", "Push branch and set upstream", ["git", "push", "-u", "origin", "{branch}"], ["branch"], True),
    "push": ("Publish", "Push current upstream", ["git", "push"], [], True),
    "pull": ("Publish", "Pull current upstream", ["git", "pull"], [], True),
    "pr": ("Publish", "Create GitHub pull request", ["gh", "pr", "create", "--base", "{base}", "--head", "{branch}", "--title", "{title}", "--body", "{body}"], ["base", "branch", "title", "body"], True),
    "pr_view": ("Publish", "Find pull request for current branch", ["gh", "pr", "view", "--json", "number,title,url,state,baseRefName,headRefName,isDraft,mergeable,mergeStateStatus"], [], False),
    "pr_merge": ("Publish", "Merge a pull request with a merge commit", ["gh", "pr", "merge", "{pr_number}", "--merge"], ["pr_number"], True),
    "delete_branch": ("Recovery", "Delete merged local branch", ["git", "branch", "-d", "--", "{branch}"], ["branch"], True),
    "revert": ("Recovery", "Revert a commit", ["git", "revert", "--no-edit", "{ref}"], ["ref"], True),
    "rebase_continue": ("Recovery", "Continue rebase", ["git", "rebase", "--continue"], [], True),
    "rebase_abort": ("Recovery", "Abort rebase", ["git", "rebase", "--abort"], [], True),
    "merge_abort": ("Recovery", "Abort merge", ["git", "merge", "--abort"], [], True),
    "reset_hard": ("High risk", "Discard tracked changes and reset", ["git", "reset", "--hard", "{ref}"], ["ref"], True),
    "force_delete": ("High risk", "Force-delete local branch", ["git", "branch", "-D", "--", "{branch}"], ["branch"], True),
    "force_push": ("High risk", "Force-push with lease", ["git", "push", "--force-with-lease", "origin", "{branch}"], ["branch"], True),
}


def catalog():
    return [{"id": key, "group": group, "label": label, "command": args,
             "fields": fields, "confirm": confirm}
            for key, (group, label, args, fields, confirm) in COMMANDS.items()]


def build_command(action, values):
    if action not in COMMANDS or not isinstance(values, dict):
        raise ValueError("Unknown command or invalid parameters.")
    _, _, args, fields, _ = COMMANDS[action]
    if set(values) != set(fields):
        raise ValueError("Provide exactly the required fields.")
    clean = {}
    for field in fields:
        value = values[field]
        if not isinstance(value, str) or not value.strip() or "\0" in value or len(value) > 4000:
            raise ValueError(f"{field} is required and must be valid text.")
        if field != "path":
            value = value.strip()
        if field in ("ref", "branch", "base") and (value.startswith("-") or
                not re.fullmatch(r"[A-Za-z0-9._/@+-]+", value)):
            raise ValueError(f"{field} contains invalid characters.")
        if field == "pr_number" and not re.fullmatch(r"[1-9][0-9]*", value):
            raise ValueError("pr_number must be a positive pull request number.")
        clean[field] = value
    return [clean[arg[1:-1]] if arg.startswith("{") and arg.endswith("}") else arg for arg in args]


def execute(root, action, values, confirmation):
    args = build_command(action, values)
    if COMMANDS[action][4] and confirmation != action:
        raise ValueError("Confirm this specific operation before running it.")
    env = os.environ.copy()
    env.update(GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat", PAGER="cat", GH_PROMPT_DISABLED="1")
    if action == "stage":
        env["GIT_LITERAL_PATHSPECS"] = "1"
    try:
        result = subprocess.run(args, cwd=root, env=env, capture_output=True,
                                text=True, errors="replace", timeout=90, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Command could not complete: {exc}") from exc
    return {"ok": result.returncode == 0, "returncode": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def list_pull_requests(root, page):
    if not isinstance(page, int) or isinstance(page, bool) or not 1 <= page <= 10000:
        raise ValueError("Page must be an integer between 1 and 10000.")
    env = os.environ.copy()
    env.update(GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat", PAGER="cat", GH_PROMPT_DISABLED="1")
    endpoint = f"repos/{{owner}}/{{repo}}/pulls?state=all&sort=updated&direction=desc&per_page=30&page={page}"
    try:
        result = subprocess.run(["gh", "api", endpoint], cwd=root, env=env,
                                capture_output=True, text=True, errors="replace",
                                timeout=90, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Unable to list pull requests: {exc}") from exc
    if result.returncode:
        raise RuntimeError(f"Unable to list pull requests: {result.stderr.strip() or 'GitHub CLI failed.'}")
    try:
        data = json.loads(result.stdout)
        if not isinstance(data, list):
            raise ValueError("Expected a list of pull requests.")
        prs = [{
            "number": pr["number"], "title": pr["title"], "url": pr["html_url"],
            "state": "merged" if pr["merged_at"] else pr["state"],
            "draft": pr["draft"], "updated_at": pr["updated_at"],
            "head": pr["head"]["ref"], "base": pr["base"]["ref"],
            "author": pr["user"]["login"], "repository": pr["base"]["repo"]["full_name"],
        } for pr in data]
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"Invalid pull request response from GitHub: {exc}") from exc
    return {"pull_requests": prs, "page": page, "has_next": len(prs) == 30}

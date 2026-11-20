"""Read-only verification of the working tree, upstream, and latest branch PR."""

import json
import os
import subprocess


def _run(root, args, allow_missing=False):
    env = os.environ.copy()
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GH_PROMPT_DISABLED="1",
               GIT_PAGER="cat", GH_PAGER="cat")
    try:
        result = subprocess.run(args, cwd=root, env=env, capture_output=True, text=True,
                                errors="replace", timeout=60, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"{args[0]} could not complete: {exc}") from exc
    if result.returncode:
        if allow_missing and result.returncode == 1:
            return None
        raise RuntimeError(f"{args[0]} failed: {result.stderr.strip() or 'command failed'}")
    return result.stdout.strip()


def check_update(root):
    branch = _run(root, ["git", "branch", "--show-current"])
    head = _run(root, ["git", "rev-parse", "--verify", "HEAD"])
    status = _run(root, ["git", "status", "--porcelain", "--untracked-files=all"])
    result = {
        "branch": branch or None,
        "head": head,
        "worktree": "changes" if status else "clean",
        "upstream": {"state": "unknown"},
        "pull_request": {"state": "unknown"},
    }
    if not branch:
        result["upstream"]["message"] = "Detached HEAD has no branch upstream."
        result["pull_request"]["message"] = "No current branch to check."
        return result
    try:
        remote = _run(root, ["git", "config", "--get", f"branch.{branch}.remote"], allow_missing=True)
        ref = _run(root, ["git", "config", "--get", f"branch.{branch}.merge"], allow_missing=True)
        if not remote or not ref:
            result["upstream"] = {"state": "not_configured", "message": "No upstream configured."}
        elif remote == "." or not ref.startswith("refs/heads/"):
            result["upstream"] = {"state": "unknown", "message": "The configured upstream is not a remote branch."}
        else:
            output = _run(root, ["git", "ls-remote", "--heads", "--", remote, ref])
            rows = [line.split("\t", 1) for line in output.splitlines() if line]
            matching = [parts[0] for parts in rows if len(parts) == 2 and parts[1] == ref]
            if not matching:
                result["upstream"] = {"state": "missing", "remote": remote, "ref": ref}
            else:
                result["upstream"] = {"state": "matches" if matching[0] == head else "different",
                                      "remote": remote, "ref": ref, "remote_head": matching[0]}
    except RuntimeError as exc:
        result["upstream"] = {"state": "unknown", "message": str(exc)}
    try:
        repo = _run(root, ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
        if not repo:
            raise RuntimeError("GitHub repository could not be resolved.")
        raw = _run(root, ["gh", "pr", "list", "--repo", repo, "--head", branch, "--state", "all",
                          "--limit", "100", "--json",
                          "number,state,url,headRefOid,baseRefName,headRepository,headRepositoryOwner"])
        prs = json.loads(raw)
        if not isinstance(prs, list):
            raise ValueError("Expected a PR list.")
        owner, name = repo.split("/", 1)
        matches = [pr for pr in prs if pr.get("headRepository") and pr.get("headRepositoryOwner")
                   and pr["headRepository"]["name"].casefold() == name.casefold()
                   and pr["headRepositoryOwner"]["login"].casefold() == owner.casefold()]
        if not matches and len(prs) >= 100:
            raise RuntimeError("Too many similarly named PRs to determine the latest matching PR.")
        if not matches:
            result["pull_request"] = {"state": "none", "repository": repo}
        else:
            pr = matches[0]
            result["pull_request"] = {
                "state": pr["state"].lower(), "number": pr["number"], "url": pr["url"],
                "base": pr["baseRefName"], "repository": repo,
                "head_matches": pr["headRefOid"] == head,
            }
            try:
                details = json.loads(_run(root, ["gh", "pr", "view", str(pr["number"]), "--repo", repo,
                                                "--json", "mergedAt,mergeCommit,commits,reviewDecision,statusCheckRollup,isDraft"]))
                commits = details["commits"]
                result["pull_request"].update({
                    "merged_at": details["mergedAt"],
                    "merge_commit": (details["mergeCommit"] or {}).get("oid"),
                    "merged_head_matches": bool(commits and commits[-1]["oid"] == head),
                    "review_decision": details["reviewDecision"],
                    "checks": details["statusCheckRollup"],
                    "draft": details["isDraft"],
                })
            except (RuntimeError, ValueError, KeyError, TypeError) as exc:
                result["pull_request"]["details_error"] = str(exc)
    except (RuntimeError, ValueError, KeyError, TypeError) as exc:
        result["pull_request"] = {"state": "unknown", "message": str(exc)}
    return result

"""Cached lookup of the repository's current GitHub version."""

from __future__ import annotations

import re
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests


_REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_CACHE_TTL_SECONDS = 900
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()


def _github_json(url: str) -> tuple[int, dict[str, Any]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MasterChief-About-Version",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(
        url,
        headers=headers,
        timeout=5,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return response.status_code, payload


def _fetch_version(repo: str) -> dict[str, Any]:
    api_root = f"https://api.github.com/repos/{repo}"
    status, release = _github_json(f"{api_root}/releases/latest")
    checked_at = datetime.now(timezone.utc).isoformat()

    if status == 200 and isinstance(release.get("tag_name"), str) and release["tag_name"].strip():
        url = release.get("html_url", "")
        return {
            "ok": True,
            "version": release["tag_name"].strip(),
            "kind": "release",
            "url": url if isinstance(url, str) and url.startswith("https://github.com/") else "",
            "published_at": release.get("published_at"),
            "checked_at": checked_at,
            "repository": repo,
            "stale": False,
        }
    if status not in (200, 404):
        raise RuntimeError(f"GitHub release lookup returned HTTP {status}.")

    repo_status, metadata = _github_json(api_root)
    if repo_status != 200:
        raise RuntimeError(f"GitHub repository lookup returned HTTP {repo_status}.")
    branch = metadata.get("default_branch")
    if not isinstance(branch, str) or not branch.strip():
        raise RuntimeError("GitHub repository response did not include its default branch.")

    commit_status, commit = _github_json(f"{api_root}/commits/{quote(branch, safe='')}")
    sha = commit.get("sha")
    if commit_status != 200 or not isinstance(sha, str) or len(sha) < 7:
        raise RuntimeError(f"GitHub branch lookup returned HTTP {commit_status}.")
    commit_url = commit.get("html_url", "")
    return {
        "ok": True,
        "version": f"{branch}@{sha[:7]}",
        "kind": "commit",
        "url": commit_url if isinstance(commit_url, str) and commit_url.startswith("https://github.com/") else "",
        "published_at": None,
        "checked_at": checked_at,
        "repository": repo,
        "stale": False,
    }


def get_github_current_version(repo: str, *, force_refresh: bool = False) -> dict[str, Any]:
    """Return the latest release, or the default-branch commit if no release exists."""
    if not isinstance(repo, str) or not _REPO_PATTERN.fullmatch(repo):
        return {"ok": False, "error": "GitHub repository must be in owner/repository form."}

    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(repo)
        if cached and not force_refresh and now - cached[0] < _CACHE_TTL_SECONDS:
            return {**cached[1], "cached": True}

        try:
            result = _fetch_version(repo)
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            if cached:
                return {
                    **cached[1],
                    "cached": True,
                    "stale": True,
                    "warning": f"GitHub could not be reached; showing the last successful version. {exc}",
                }
            return {"ok": False, "repository": repo, "error": str(exc)}

        _CACHE[repo] = (now, result)
        return {**result, "cached": False}


def clear_github_version_cache() -> None:
    """Clear in-process cache for tests and explicit refresh workflows."""
    with _CACHE_LOCK:
        _CACHE.clear()

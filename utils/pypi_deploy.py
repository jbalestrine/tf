"""Run the existing PyPI-only release script from the Source Control UI."""

import os
import re
import shutil
import subprocess
import sys
import threading

_lock = threading.Lock()

_VERSION_LINE = re.compile(r'^([ \t]*version=")([0-9]+\.[0-9]+\.[0-9]+)("[ \t]*,)', re.MULTILINE)


def _version_match(content):
    matches = list(_VERSION_LINE.finditer(content))
    if len(matches) != 1:
        raise ValueError("Could not uniquely identify the version in setup.py.")
    return matches[0]


def version_preview(root):
    from utils.git_activity_editor import load
    data = load(root, "setup.py")
    current = _version_match(data["content"]).group(2)
    major, minor, patch = (int(part) for part in current.split("."))
    branch = _git(root, ["branch", "--show-current"]).stdout.strip()
    return {"ok": True, "current": current, "suggested": f"{major}.{minor}.{patch + 1}",
            "file_version": data["version"], "branch": branch or None}


def update_version(root, new_version, expected_file_version, expected_branch, confirmation):
    from utils.git_activity_editor import EditConflict, load, save
    if not isinstance(new_version, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", new_version):
        raise ValueError("Enter a version such as 4.0.1 using three non-negative numbers.")
    if confirmation != new_version or not isinstance(expected_file_version, str) or not isinstance(expected_branch, str) or not expected_branch:
        raise ValueError("Review and confirm the new version and branch first.")
    if not _lock.acquire(blocking=False):
        raise RuntimeError("Another release operation is running in this server process.")
    try:
        branch = _git(root, ["branch", "--show-current"]).stdout.strip()
        if branch != expected_branch:
            raise EditConflict("The branch changed. Reload the version editor before saving.")
        if branch == "Masterchief4":
            raise ValueError("Create or switch to a feature branch before changing the release version.")
        data = load(root, "setup.py")
        if data["version"] != expected_file_version:
            raise EditConflict("setup.py changed since preview. Reload before saving.")
        match = _version_match(data["content"])
        current = match.group(2)
        if tuple(map(int, new_version.split("."))) <= tuple(map(int, current.split("."))):
            raise ValueError("Choose a version greater than the current working-copy version.")
        content = data["content"][:match.start(2)] + new_version + data["content"][match.end(2):]
        result = save(root, "setup.py", content, expected_file_version)
        return {"ok": True, "previous": current, "version": new_version, "branch": branch,
                "file_version": result["version"]}
    finally:
        _lock.release()


def _git(root, args, allowed=(0,)):
    env = os.environ.copy()
    env.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", GIT_PAGER="cat")
    try:
        result = subprocess.run(["git", *args], cwd=root, env=env, capture_output=True,
                                text=True, errors="replace", timeout=60, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Git could not complete; check the server and remote before retrying.") from exc
    if result.returncode not in allowed:
        raise RuntimeError(f"Git failed while running {args[0]}; check the repository and remote.")
    return result


def release_preview(root):
    branch_ref = "refs/heads/Masterchief4"
    remote = _git(root, ["ls-remote", "--refs", "origin", branch_ref]).stdout.strip().splitlines()
    if len(remote) != 1 or "\t" not in remote[0]:
        raise RuntimeError("Could not verify origin/Masterchief4 on the remote.")
    commit, remote_ref = remote[0].split("\t", 1)
    if remote_ref != branch_ref or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise RuntimeError("Unexpected response from origin/Masterchief4.")
    local = _git(root, ["rev-parse", "--verify", "refs/remotes/origin/Masterchief4^{commit}"]).stdout.strip()
    if local != commit:
        raise RuntimeError("Local origin/Masterchief4 is out of date. Fetch origin, then check again.")
    setup = _git(root, ["show", f"{commit}:setup.py"]).stdout
    versions = re.findall(r'^\s*version="([0-9]+\.[0-9]+\.[0-9]+)"\s*,', setup, re.MULTILINE)
    if len(versions) != 1:
        raise RuntimeError("Could not uniquely determine the package version in the merged commit.")
    tag = "v" + versions[0]
    ref = f"refs/tags/{tag}"
    local_tag = _git(root, ["rev-parse", "--verify", f"{ref}^{{commit}}"], allowed=(0, 128))
    remote_tag = _git(root, ["ls-remote", "--refs", "origin", ref]).stdout.strip()
    return {"ok": True, "commit": commit, "version": versions[0], "tag": tag,
            "base": "origin/Masterchief4", "local_tag_commit": local_tag.stdout.strip() if local_tag.returncode == 0 else None,
            "remote_tag_exists": bool(remote_tag)}


def create_release_tag(root, tag, expected_commit, confirmation):
    if not isinstance(tag, str) or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("Enter a semantic release tag such as v1.2.3.")
    if confirmation != tag or not isinstance(expected_commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", expected_commit):
        raise ValueError("Confirm the tag and reviewed commit before creating it.")
    if not _lock.acquire(blocking=False):
        raise RuntimeError("Another release operation is running in this server process.")
    try:
        preview = release_preview(root)
        if preview["commit"] != expected_commit:
            raise ValueError("The merged branch has changed. Check the release again before creating a tag.")
        if preview["tag"] != tag:
            raise ValueError(f"Tag must match the merged setup.py version: {preview['tag']}. Update and merge setup.py first.")
        ref = f"refs/tags/{tag}"
        if _git(root, ["show-ref", "--verify", "--quiet", ref], allowed=(0, 1)).returncode == 0:
            raise ValueError("That local tag already exists; it was not changed.")
        if _git(root, ["ls-remote", "--refs", "origin", ref]).stdout.strip():
            raise ValueError("That tag already exists on origin; it was not changed.")
        _git(root, ["tag", "--", tag, expected_commit])
        try:
            _git(root, ["push", "origin", f"{ref}:{ref}"])
        except RuntimeError as exc:
            raise RuntimeError(f"Local tag {tag} was created, but pushing to origin failed or is unconfirmed. "
                               "Check the remote tag and local tag before retrying; no tag was deleted.") from exc
        return {**preview, "message": "Tag created locally and pushed to origin."}
    finally:
        _lock.release()


def deploy(root, tag, mode, confirmation=None, expected_commit=None):
    if not isinstance(tag, str) or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("Enter a semantic release tag such as v1.2.3.")
    if mode not in ("dry_run", "publish"):
        raise ValueError("Choose dry run or publish.")
    if mode == "publish" and (confirmation != tag or not isinstance(expected_commit, str)
                              or not re.fullmatch(r"[0-9a-f]{40,64}", expected_commit)):
        raise ValueError("Confirm the release tag and rerun the dry run before publishing.")
    if sys.platform != "win32":
        raise RuntimeError("The PyPI deployment button requires a Windows server.")
    executable = shutil.which("powershell.exe")
    if not executable:
        raise RuntimeError("Windows PowerShell was not found on the server.")
    script = root / "PYPI_ONLY_DEPLOY.ps1"
    if not script.is_file():
        raise RuntimeError("The PyPI-only deployment script is missing.")
    if not _lock.acquire(blocking=False):
        raise RuntimeError("A PyPI deployment is already running in this server process.")
    try:
        env = os.environ.copy()
        env.pop("TWINE_PASSWORD", None)
        env.pop("TWINE_USERNAME", None)
        env["GIT_TERMINAL_PROMPT"] = "0"
        try:
            resolved = subprocess.run(
                ["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
                cwd=root, env=env, capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
            )
            commit = resolved.stdout.strip()
            if resolved.returncode or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
                raise ValueError("The release tag does not resolve to a local commit. Fetch and verify the tag first.")
            if mode == "publish" and commit != expected_commit:
                raise ValueError("The tag now points to a different commit. Review it and run the dry run again.")
            args = [executable, "-NoProfile", "-NonInteractive", "-File", str(script),
                    "-Tag", tag, "-PythonPath", sys.executable,
                    "-DryRun" if mode == "dry_run" else "-UseVault"]
            result = subprocess.run(args, cwd=root, env=env, capture_output=True,
                                    text=True, errors="replace", timeout=600, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Deployment timed out; its outcome is unconfirmed. Check PyPI before retrying.") from exc
        except OSError as exc:
            raise RuntimeError("Unable to start the release process. Check server tools and configuration.") from exc
        if result.returncode:
            output = (result.stdout or "") + "\n" + (result.stderr or "")
            hints = [
                ("already exists", "The package version already exists on PyPI."),
                ("does not match package version", "The tag does not match the version in the tagged setup.py."),
                ("Could not read Vault secret", "Could not read TWINE_PASSWORD from the application Vault."),
                ("No module named build", "The server Python environment is missing the build package."),
                ("No module named twine", "The server Python environment is missing the twine package."),
                ("Could not verify PyPI version availability", "Could not verify version availability on PyPI."),
            ]
            hint = next((message for marker, message in hints if marker in output),
                        "Check the tag, server build tools, Vault access, and network connection.")
            raise RuntimeError(f"Release script failed (exit {result.returncode}). {hint} "
                               "If upload may have started, check PyPI before retrying.")
        return {"ok": True, "tag": tag, "commit": commit, "mode": mode}
    finally:
        _lock.release()

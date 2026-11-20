"""Bounded working-tree activity and static Python import relationships."""

import ast
import os
import subprocess
from pathlib import Path


def _git(root, *args):
    env = os.environ.copy()
    env.update(GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat")
    try:
        result = subprocess.run(["git", *args], cwd=root, env=env, capture_output=True,
                                timeout=20, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Git activity could not be collected: {exc}") from exc
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or "Git activity failed.")
    return result.stdout.decode("utf-8", "replace")


def _entries(output):
    return [entry for entry in output.split("\0") if entry]


def collect(root):
    root = Path(root).resolve()
    changes = {}
    items = iter(_entries(_git(root, "status", "--porcelain", "-z", "--untracked-files=all")))
    for entry in items:
        code, name = entry[:2], entry[3:]
        if "R" in code or "C" in code:
            next(items, None)
        changes.setdefault(name, []).append("working tree: " + code)
    for name in _entries(_git(root, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", "HEAD")):
        changes.setdefault(name, []).append("latest commit")
    all_changes = len(changes)
    selected = dict(sorted(changes.items(), key=lambda item: (
        not any(source.startswith("working tree") for source in item[1]), item[0]))[:200])
    tracked = _entries(_git(root, "ls-files", "-z", "--", "*.py"))
    candidates = sorted(set(tracked) | {name for name in selected if name.endswith(".py")})
    total_python = len(candidates)
    candidates = candidates[:2500]
    modules = {}
    for name in candidates:
        parts = name[:-3].split("/")
        if parts[-1] == "__init__":
            parts.pop()
        if parts and all(part.isidentifier() for part in parts):
            modules.setdefault(".".join(parts), []).append(name)
    edges = set()
    warnings = []
    for name in candidates:
        path = root / name
        try:
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
                continue
            if path.stat().st_size > 1_000_000:
                warnings.append(f"Skipped oversized Python file: {name}")
                continue
            with path.open("rb") as source:
                tree = ast.parse(source.read(), filename=name)
        except (OSError, SyntaxError, UnicodeError, ValueError) as exc:
            warnings.append(f"Could not inspect {name}: {type(exc).__name__}")
            continue
        package = name[:-3].split("/")[:-1]
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    if node.level > len(package) + 1:
                        continue
                    prefix = package[:len(package) - node.level + 1]
                    base = ".".join(prefix + ([node.module] if node.module else []))
                else:
                    base = node.module or ""
                names = ([base] if base else []) + [
                    f"{base}.{alias.name}" for alias in node.names if base and alias.name != "*"
                ]
            for module in names:
                targets = modules.get(module, [])
                if len(targets) == 1 and targets[0] != name and (name in selected or targets[0] in selected):
                    edges.add((name, targets[0]))
    sorted_edges = sorted(edges)
    return {"files": [{"path": name, "sources": sources} for name, sources in selected.items()],
            "edges": [{"from": source, "to": target} for source, target in sorted_edges[:400]],
            "coverage": {"changed_total": all_changes, "changed_shown": len(selected),
                         "python_total": total_python, "python_scanned": len(candidates),
                         "edges_total": len(sorted_edges), "warnings": warnings[:30],
                         "warning_count": len(warnings)}}

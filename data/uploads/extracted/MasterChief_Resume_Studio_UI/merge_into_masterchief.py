#!/usr/bin/env python3
"""
Safe Migration Script: Packages Career & TechLearn Studio into your `masterchief` PyPI repo.
Strictly excludes personal secrets (.env, processed_emails.json, backups, dist, .venv).
"""

import shutil
import sys
from pathlib import Path

STUDIO_SRC = Path(__file__).resolve().parent

PYTHON_MODULES = [
    "app.py",
    "build_resumes.py",
    "email_agent.py",
    "profile_store.py",
    "studio_tools.py",
    "techlearn_router.py",
]

HTML_TEMPLATES = [
    "index.html",
    "portfolio.html",
    "techlearn.html",
    "template_v2.html",
]

DEFAULT_ASSETS = [
    "resume.yaml",
    "techlearn_knowledge.json",
    ".env.example",
]

TEST_FILES = [
    "test_build_resumes.py",
    "test_email_agent.py",
    "test_preview.py",
    "test_profiles.py",
    "test_run.py",
    "test_studio_features.py",
]


def main():
    print("\n=== MASTERCHIEF STUDIO -> PYPI REPO MERGE UTILITY ===")
    if len(sys.argv) > 1:
        repo_input = sys.argv[1]
    else:
        repo_input = input("Enter full path to your `masterchief` repo root: ").strip().strip('"')

    repo_root = Path(repo_input).resolve()
    if not repo_root.exists():
        print(f"[ERROR] Target directory not found: {repo_root}")
        sys.exit(1)

    # Detect src/masterchief vs masterchief layout
    if (repo_root / "src" / "masterchief").is_dir():
        pkg_dir = repo_root / "src" / "masterchief"
    elif (repo_root / "masterchief").is_dir():
        pkg_dir = repo_root / "masterchief"
    else:
        print(f"[ERROR] Could not locate `src/masterchief` or `masterchief` inside {repo_root}")
        sys.exit(1)

    studio_dir = pkg_dir / "studio"
    templates_dir = studio_dir / "templates"
    defaults_dir = studio_dir / "defaults"
    tests_dir = repo_root / "tests" / "studio"

    for d in (studio_dir, templates_dir, defaults_dir, tests_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Create __init__.py files
    (studio_dir / "__init__.py").write_text(
        '"""MasterChief Career & TechLearn Studio Addon."""\n', encoding="utf-8"
    )
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")

    # Copy Python modules
    for fname in PYTHON_MODULES:
        src = STUDIO_SRC / fname
        if src.exists():
            shutil.copy2(src, studio_dir / fname)
            print(f"[OK] Module   -> {studio_dir / fname}")

    # Copy HTML templates
    for fname in HTML_TEMPLATES:
        src = STUDIO_SRC / fname
        if src.exists():
            shutil.copy2(src, templates_dir / fname)
            print(f"[OK] Template -> {templates_dir / fname}")

    # Copy clean default seed assets
    for fname in DEFAULT_ASSETS:
        src = STUDIO_SRC / fname
        if src.exists():
            shutil.copy2(src, defaults_dir / fname)
            print(f"[OK] Default  -> {defaults_dir / fname}")

    # Copy test suites
    for fname in TEST_FILES:
        src = STUDIO_SRC / fname
        if src.exists():
            shutil.copy2(src, tests_dir / fname)
            print(f"[OK] Test     -> {tests_dir / fname}")

    print("\n[SUCCESS] Clean merge complete! Zero secrets or local state copied.")
    print(f"Next step: Open {repo_root} in VS Code and run the Copilot PyPI wiring prompt.")


if __name__ == "__main__":
    main()

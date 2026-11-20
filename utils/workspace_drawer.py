"""User-facing destinations for the independent workspace drawer."""

import json
from pathlib import Path
from urllib.parse import quote, urlsplit

from utils.feature_flags import MASTER_MENU_ITEMS, load_feature_flags
from utils.navigation import visible_pinned_modules


PRIMARY = [
    ("Home", "Dashboard", "/", "System overview"),
    ("Develop", "Code UI", "/masterchief_code_ui", "Edit project files"),
    ("Develop", "File Ecosystem", "/static/git-workflow-guide.html#activity-status", "Explore and edit recent changes"),
    ("Develop", "Source Map", "/source-map", "Find the files behind a page"),
    ("Source Control", "Git Command Center", "/sys/scm", "Review and run Git commands"),
    ("Source Control", "GitHub Integration", "/github", "Browse and clone repositories"),
    ("Source Control", "Git Workflow Guide", "/static/git-workflow-guide.html", "Workflow diagrams and commands"),
    ("Source Control", "Release Journey", "/static/git-workflow-guide.html#release-journey", "Guide an update from changes to merge"),
    ("Build & Deploy", "Pipelines", "/pipelines", "Delivery workflows"),
    ("Build & Deploy", "Architecture & Code", "/archetypes", "Design architecture and explore code"),
    ("Build & Deploy", "IaC Manager", "/iac_manager", "Manage infrastructure as code"),
    ("Operate", "Diagnostics", "/sys/diagnostics", "Inspect the application"),
    ("Operate", "Ops Center", "/sys/ops", "Operations overview"),
    ("Automate & AI", "Scripts", "/scripts", "Manage and run scripts"),
    ("Automate & AI", "Echo Chat", "/echo-chat", "Talk with Echo"),
    ("Manage", "Master Menu", "/master-menu", "Feature map and controls"),
    ("Manage", "Code Manager", "/ext/code_manager/", "Manage features and blueprints"),
    ("Manage", "Add-on Modules", "/addons/modules", "Manage installed add-ons"),
]

EXTRA = [
    ("Develop", "Web IDE", "/web_ide"), ("Develop", "Page Editor", "/page-editor"),
    ("Automate & AI", "Core Scripts", "/core-scripts"),
    ("Build & Deploy", "CI/CD Center", "/cicd"), ("Build & Deploy", "Terraform Wizard", "/tf_wizard"),
    ("Build & Deploy", "ARM Creator", "/arm_creator"), ("Build & Deploy", "IaC Manager", "/iac_manager"),
    ("Build & Deploy", "Blueprint Wizard", "/blueprint-wizard"), ("Build & Deploy", "Code Archetypes", "/archetypes"),
    ("Build & Deploy", "Add-ons", "/addons"), ("Operate", "Cloud Dashboard", "/cloud"),
    ("Operate", "Observability", "/observability"), ("Operate", "Notifications", "/notifications"),
    ("Operate", "Processes", "/processes"), ("Operate", "Services", "/services"),
    ("Operate", "Backups", "/backups"), ("Operate", "Chaos Monkey", "/chaos-monkey"),
    ("Manage", "Feature Management", "/features"), ("Manage", "Modules", "/modules"),
    ("Manage", "Manager Portal", "/manager"), ("Manage", "Site Settings", "/site-settings"),
    ("Manage", "Permissions (RBAC)", "/rbac"), ("Manage", "Secrets", "/secrets"),
    ("Manage", "Unified Site Map", "/site-map"), ("Manage", "About", "/about"),
    ("Automate & AI", "Echo Commands", "/echo-commands"),
    ("Automate & AI", "Echo Training", "/echo-train"), ("Automate & AI", "Echo Approvals", "/echo-approvals"),
    ("Automate & AI", "Echo Memory", "/echo-memory"), ("More tools", "Teams", "/teams"),
    ("More tools", "Okta", "/okta"), ("More tools", "Google Services", "/google-services"),
    ("More tools", "Gallery", "/gallery"), ("More tools", "Marketplace", "/marketplace"),
    ("More tools", "Roku Builder", "/media/roku"),
]


def _local_url(value):
    if not isinstance(value, str) or "\\" in value or any(ord(c) < 32 for c in value):
        return False
    parsed = urlsplit(value)
    return not parsed.scheme and not parsed.netloc and value.startswith("/") and not value.startswith("//")


def catalog(app):
    root = Path(app.root_path)
    flags = load_feature_flags(root, logger=app.logger)
    flag_by_path = {item["path"]: item["flag"] for item in MASTER_MENU_ITEMS}
    live = {rule.rule for rule in app.url_map.iter_rules() if "GET" in rule.methods}
    result, seen = [], set()

    def add(group, title, url, description="", extra=False, flag=None, always=False):
        if not title or not _local_url(url) or url in seen:
            return
        route = urlsplit(url).path
        if not always and route not in live:
            return
        seen.add(url)
        result.append({"group": group, "title": title, "url": url, "description": description,
                       "extra": extra, "disabled": bool(flag and not flags.get(flag, True))})

    for group, title, url, description in PRIMARY:
        add(group, title, url, description, flag=flag_by_path.get(url),
            always=url.startswith("/static/"))
    for group, title, url in EXTRA:
        add(group, title, url, extra=True, flag=flag_by_path.get(url))
    for item in MASTER_MENU_ITEMS:
        add("More tools", item["title"], item["path"], item["description"], True, item["flag"])
    for feature in app.config.get("_feature_nav", []):
        add("Manage", feature.get("label"), feature.get("href"), "Installed feature", True)

    upload = Path(app.config.get("UPLOAD_FOLDER", root / "data" / "uploads"))
    pinned_path = upload / "ui_modules.json"
    try:
        pins = json.loads(pinned_path.read_text(encoding="utf-8")) if pinned_path.exists() else {}
        pinned = visible_pinned_modules(pins, upload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read pinned add-ons: {exc}") from exc
    for name, info in sorted(pinned.items()):
        add("Installed add-ons", name, info["url"], "Pinned add-on", always=True)
    extracted = upload / "extracted"
    if extracted.is_dir():
        for folder in sorted(extracted.iterdir(), key=lambda entry: entry.name.casefold()):
            if folder.is_dir() and not folder.is_symlink() and folder.name not in pinned:
                add("Installed add-ons", folder.name, f"/addons/modules/{quote(folder.name, safe='')}/manager",
                    "Open add-on manager", True, always=True)
    return result

import json
from pathlib import Path

DEFAULT_FEATURE_FLAGS = {
    'dashboard': True,
    'master_menu': True,
    'manager_portal': True,
    'web_ide': True,
    'masterchief_code_ui': True,
    'echo_chat': True,
    'echo_train': True,
    'pipelines': True,
    'cloud': True,
    'secrets': True,
    'echo_memory': True,
    'marketplace': True,
    'notifications': True,
    'scripts': True,
    'processes': True,
    'services': True,
    'core_scripts': True,
    'blueprint_wizard': True,
    'modules': True,
    'addon_modules': True,
    'addons': True,
    'teams': True,
    'okta': True,
    'rbac': True,
    'diagnostics': True,
    'scm': True,
    'arm_creator': True,
    'iac_manager': True,
    'about': True,
    'work_catalog': True,
}

MASTER_MENU_ITEMS = [
    {'focus': 'Operate', 'title': 'Dashboard', 'path': '/', 'flag': 'dashboard', 'description': 'System overview, KPIs, and quick status checks.'},
    {'focus': 'Operate', 'title': 'Master Menu', 'path': '/master-menu', 'flag': 'master_menu', 'description': 'Feature map and centralized toggle controls.'},
    {'focus': 'Operate', 'title': 'Unified Site Map', 'path': '/site-map', 'flag': 'work_catalog', 'description': 'All routes and workspace files in a single live catalog.'},
    {'focus': 'Operate', 'title': 'Manager Portal', 'path': '/manager', 'flag': 'manager_portal', 'description': 'Timeline, workflow, test and model operations.'},
    {'focus': 'Operate', 'title': 'System Diagnostics', 'path': '/sys/diagnostics', 'flag': 'diagnostics', 'description': 'Repository scan, symbol map, and diagnostics inspector.'},
    {'focus': 'Operate', 'title': 'Source Control', 'path': '/sys/scm', 'flag': 'scm', 'description': 'Git status, commits, push/pull, and staging controls.'},
    {'focus': 'Operate', 'title': 'Cloud Dashboard', 'path': '/cloud', 'flag': 'cloud', 'description': 'Cloud resources, posture, and runtime visibility.'},
    {'focus': 'Operate', 'title': 'Notifications', 'path': '/notifications', 'flag': 'notifications', 'description': 'Alerts and operational notification center.'},
    {'focus': 'Operate', 'title': 'Web IDE', 'path': '/web_ide', 'flag': 'web_ide', 'description': 'CAF-backed in-browser IDE workspace.'},
    {'focus': 'Operate', 'title': 'MasterChief Code UI', 'path': '/masterchief_code_ui', 'flag': 'masterchief_code_ui', 'description': 'Full project code interface and tooling.'},
    {'focus': 'Operate', 'title': 'Scripts', 'path': '/scripts', 'flag': 'scripts', 'description': 'Script runbook and quick execution entry points.'},
    {'focus': 'Operate', 'title': 'Processes', 'path': '/processes', 'flag': 'processes', 'description': 'Runtime process visibility and controls.'},
    {'focus': 'Operate', 'title': 'Services', 'path': '/services', 'flag': 'services', 'description': 'Service state and lifecycle operations.'},
    {'focus': 'Build', 'title': 'Pipelines', 'path': '/pipelines', 'flag': 'pipelines', 'description': 'Delivery orchestration and release flow.'},
    {'focus': 'Build', 'title': 'Modules', 'path': '/modules', 'flag': 'modules', 'description': 'Composable module architecture and extension points.'},
    {'focus': 'Build', 'title': 'Addons', 'path': '/addons', 'flag': 'addons', 'description': 'Addon package management and activation.'},
    {'focus': 'Build', 'title': 'Addon Modules', 'path': '/addons/modules', 'flag': 'addon_modules', 'description': 'Installed addon module status and controls.'},
    {'focus': 'Build', 'title': 'Core Scripts', 'path': '/core-scripts', 'flag': 'core_scripts', 'description': 'Inventory and direct links for legacy and core scripts.'},
    {'focus': 'Build', 'title': 'Blueprint Wizard', 'path': '/blueprint-wizard', 'flag': 'blueprint_wizard', 'description': 'Analyze and progressively extract main.py into managed modules/templates.'},
    {'focus': 'Secure', 'title': 'Secrets Vault', 'path': '/secrets', 'flag': 'secrets', 'description': 'Credential and secret lifecycle operations.'},
    {'focus': 'Secure', 'title': 'RBAC', 'path': '/rbac', 'flag': 'rbac', 'description': 'Access policy controls and permission boundaries.'},
    {'focus': 'Collaborate', 'title': 'Teams', 'path': '/teams', 'flag': 'teams', 'description': 'Team collaboration and schedule integration.'},
    {'focus': 'Collaborate', 'title': 'Okta', 'path': '/okta', 'flag': 'okta', 'description': 'Identity, app assignments, and SSO controls.'},
    {'focus': 'AI', 'title': 'Echo Chat', 'path': '/echo-chat', 'flag': 'echo_chat', 'description': 'Continuous AI assistant conversation and action support.'},
    {'focus': 'AI', 'title': 'Echo Train', 'path': '/echo-train', 'flag': 'echo_train', 'description': 'Model training, files, and job controls.'},
    {'focus': 'AI', 'title': 'Echo Memory', 'path': '/echo-memory', 'flag': 'echo_memory', 'description': 'Conversation memory views and persistence controls.'},
    {'focus': 'Marketplace', 'title': 'Marketplace', 'path': '/marketplace', 'flag': 'marketplace', 'description': 'Third-party integrations and capability hooks.'},
    {'focus': 'Build', 'title': 'ARM Creator', 'path': '/arm_creator', 'flag': 'arm_creator', 'description': 'Azure ARM template creation workspace.'},
    {'focus': 'Build', 'title': 'IaC Manager', 'path': '/iac_manager', 'flag': 'iac_manager', 'description': 'Alternate Terraform/IaC wizard workspace.'},
    {'focus': 'Operate', 'title': 'About', 'path': '/about', 'flag': 'about', 'description': 'Product information and version notes.'},
]


def _feature_flags_file(base_dir: Path) -> Path:
    return base_dir / 'data' / 'feature_flags.json'


def load_feature_flags(base_dir: Path, logger=None) -> dict:
    flags = dict(DEFAULT_FEATURE_FLAGS)
    try:
        f = _feature_flags_file(base_dir)
        if f.exists():
            raw = json.loads(f.read_text(encoding='utf-8') or '{}')
            if isinstance(raw, dict):
                for key, value in raw.items():
                    flags[str(key)] = bool(value)
    except Exception:
        if logger:
            logger.exception('Failed to load feature flags')
    return flags


def save_feature_flags(base_dir: Path, flags: dict, logger=None) -> bool:
    try:
        f = _feature_flags_file(base_dir)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(flags, indent=2), encoding='utf-8')
        return True
    except Exception:
        if logger:
            logger.exception('Failed to save feature flags')
        return False


def is_feature_enabled(base_dir: Path, flag_name: str, logger=None) -> bool:
    return bool(load_feature_flags(base_dir, logger).get(flag_name, True))

from pathlib import Path

from flask import Blueprint, current_app, redirect, send_file, url_for

from utils.code_archetypes import with_archetype_client
from utils.feature_flags import is_feature_enabled

try:
    from auth_module import requires_permission
except Exception:
    def requires_permission(_permission):
        def decorator(func):
            return func
        return decorator

ui_pages_bp = Blueprint('ui_pages', __name__)


def _root() -> Path:
    return Path(current_app.root_path).resolve()


def _is_feature_enabled(flag_name: str) -> bool:
    try:
        return is_feature_enabled(_root(), flag_name, logger=current_app.logger)
    except Exception:
        current_app.logger.exception('Feature flag check failed for %s', flag_name)
        return True


@ui_pages_bp.route('/arm_creator')
def arm_creator():
    """Serve the ARM Template Creator web UI."""
    if not _is_feature_enabled('arm_creator'):
        return ('<h2>ARM Creator is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)
    try:
        page = _root() / 'arm_creator.html'
        if page.exists():
            return page.read_text(encoding='utf-8'), 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception:
        current_app.logger.exception('Failed to serve arm_creator.html')
    return ('ARM Creator not available', 404)


@ui_pages_bp.route('/web_ide')
def web_ide():
    """Serve local caf.html page for Web IDE fallback."""
    if not _is_feature_enabled('web_ide'):
        return ('<h2>Web IDE is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)
    try:
        page = _root() / 'caf.html'
        if page.exists():
            return page.read_text(encoding='utf-8'), 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception:
        current_app.logger.exception('Failed to serve web_ide.html')

    try:
        return redirect(url_for('index'))
    except Exception:
        return ('Web IDE not available', 404)


@ui_pages_bp.route('/caf_generator')
def caf_generator():
        if not _is_feature_enabled('caf_generator'):
            return ('<h2>CAF Generator is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)
        try:
            page = _root() / 'caf_generator.html'
            if page.exists():
                html = with_archetype_client(page.read_text(encoding='utf-8'))
                return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
        except Exception:
            current_app.logger.exception('Failed to serve caf_generator.html')
        return ('CAF Generator not available', 404)


@ui_pages_bp.route('/iac_manager')
def iac_manager():
    """Serve IaC Manager with TF Wizard-first fallback order."""
    if not _is_feature_enabled('iac_manager'):
        return ('<h2>IaC Manager is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)

    # Preferred legacy source from local worktree.
    try:
        page = Path(r'C:\Users\Echo\masterchief\.claude\worktrees\cool-elbakyan\web_tf_wizard.html')
        if page.exists():
            return page.read_text(encoding='utf-8'), 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception:
        current_app.logger.exception('Failed to serve alternate web_tf_wizard.html')

    # Primary in-repo IaC experience.
    try:
        return redirect(url_for('tf_wizard_routes.tf_wizard_index'))
    except Exception:
        current_app.logger.exception('Failed to redirect to TF Wizard route')

    # Last-resort fallback so route always resolves.
    try:
        return redirect(url_for('ui_pages.arm_creator'))
    except Exception:
        return redirect('/arm_creator')


@ui_pages_bp.route('/pipelines')
def pipelines_page():
    if not _is_feature_enabled('pipelines'):
        return ('<h2>Pipelines is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)
    return send_file('pipelines.html')


@ui_pages_bp.route('/cloud')
def cloud_page():
    if not _is_feature_enabled('cloud'):
        return ('<h2>Cloud Dashboard is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)
    return send_file('cloud_dashboard.html')


@ui_pages_bp.route('/secrets')
def secrets_page():
    if not _is_feature_enabled('secrets'):
        return ('<h2>Secrets Vault is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)
    return send_file('secrets_vault.html')


@ui_pages_bp.route('/echo-memory')
def echo_memory_page():
    if not _is_feature_enabled('echo_memory'):
        return ('<h2>Echo Memory is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)
    return send_file('echo_memory.html')


@ui_pages_bp.route('/marketplace')
def marketplace_page():
    if not _is_feature_enabled('marketplace'):
        return ('<h2>Marketplace is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)
    return send_file('marketplace.html')


@ui_pages_bp.route('/notifications')
def notifications_page():
    if not _is_feature_enabled('notifications'):
        return ('<h2>Notifications is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)
    return send_file('notifications.html')


@ui_pages_bp.route('/rbac')
@requires_permission('rbac')
def rbac_page():
    return send_file('rbac.html')


@ui_pages_bp.route('/masterchief_code_ui')
@requires_permission('web_ide')
def masterchief_code_ui():
    """Serve the MasterChief Code UI (Web IDE)."""
    if not _is_feature_enabled('masterchief_code_ui'):
        return ('<h2>MasterChief Code UI is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)
    try:
        ide_path = _root() / 'web_ide.html'
        if ide_path.exists():
            html = with_archetype_client(ide_path.read_text(encoding='utf-8'))
            return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
        return f'<h1>MasterChief Code UI</h1><p>Web IDE file not found at {ide_path}</p>', 404
    except Exception as exc:
        current_app.logger.exception('Failed to serve MasterChief Code UI')
        return f'<h1>Error</h1><p>Failed to load Code UI: {exc}</p>', 500


@ui_pages_bp.route('/about')
def about_page():
    if not _is_feature_enabled('about'):
        return ('<h2>About page is disabled by feature flag.</h2><p>Use <a href="/master-menu">Master Menu</a> to re-enable it.</p>', 503)
    return send_file('about.html')


@ui_pages_bp.route('/favicon.ico')
def favicon():
    """Serve a minimal inline SVG favicon to stop 404 noise in logs."""
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        b'<rect width="32" height="32" rx="4" fill="#0f172a"/>'
        b'<text x="4" y="25" font-family="monospace" font-size="22" font-weight="bold" fill="#38bdf8">M</text>'
        b'</svg>'
    )
    return svg, 200, {
        'Content-Type': 'image/svg+xml',
        'Cache-Control': 'public, max-age=604800',
    }


@ui_pages_bp.route('/hello')
def hello():
    """Minimal health/hello endpoint — referenced by CAF and other tooling."""
    return (
        '<html><head><title>MasterChief</title>'
        '<style>body{background:#0f172a;color:#38bdf8;font-family:monospace;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}'
        'h1{font-size:2rem}a{color:#7dd3fc;margin-left:16px}</style></head>'
        '<body><div><h1>Hello from MasterChief</h1>'
        '<p>Platform is running. <a href="/">Dashboard</a> | <a href="/master-menu">Menu</a></p>'
        '</div></body></html>',
        200,
        {'Content-Type': 'text/html; charset=utf-8'},
    )

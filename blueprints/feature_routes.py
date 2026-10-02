import json
from pathlib import Path

from flask import Blueprint, current_app, jsonify, redirect, request, url_for

try:
    from auth_module import requires_permission
except Exception:
    def requires_permission(_permission):
        def decorator(func):
            return func
        return decorator

try:
    from features.manager import get_feature_manager
    FEATURE_MANAGER_AVAILABLE = True
except Exception:
    FEATURE_MANAGER_AVAILABLE = False


feature_routes_bp = Blueprint('feature_routes', __name__)


def _root() -> Path:
    return Path(current_app.root_path).resolve()


@feature_routes_bp.route('/features')
def features_page():
    """Serve the Feature Management page."""
    try:
        page = _root() / 'features' / 'templates' / 'feature_manager.html'
        if page.exists():
            return page.read_text(encoding='utf-8'), 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception:
        current_app.logger.exception('Failed to serve feature_manager.html')
    return jsonify({'error': 'Feature manager not available'}), 404


@feature_routes_bp.route('/api/features/enabled')
def api_features_enabled():
    """Return list of enabled features for the toolbar."""
    if not FEATURE_MANAGER_AVAILABLE:
        return jsonify([])
    try:
        feature_manager = get_feature_manager()
        if feature_manager is None:
            return jsonify([])

        enabled = []
        for _, handler in feature_manager.features.items():
            if handler.config.enabled:
                enabled.append(
                    {
                        'key': handler.config.name,
                        'label': handler.config.display_name,
                        'addon': 'features',
                        'description': handler.config.description,
                    }
                )

        for name, config in feature_manager.feature_configs.items():
            if config.enabled and name not in feature_manager.features:
                enabled.append(
                    {
                        'key': config.name,
                        'label': config.display_name,
                        'addon': 'features',
                        'description': config.description,
                    }
                )

        return jsonify(enabled)
    except Exception:
        current_app.logger.exception('Failed to list enabled features')
        return jsonify([])


@feature_routes_bp.route('/api/features/settings', methods=['GET', 'POST'])
def api_features_settings():
    """Get or save API management settings."""
    settings_file = _root() / 'api_settings.json'

    if request.method == 'GET':
        try:
            if settings_file.exists():
                settings = json.loads(settings_file.read_text(encoding='utf-8'))
                return jsonify(settings)
            return jsonify(
                {
                    'core_features': {
                        'masterchief_code_ui': True,
                        'web_ide': True,
                        'caf_generator': True,
                        'echo_chat': True,
                    },
                    'development_tools': {
                        'github_integration': True,
                        'azure_integration': True,
                        'cloud_dashboard': True,
                        'pipelines': True,
                    },
                    'system_management': {
                        'rbac': True,
                        'notifications': True,
                        'marketplace': True,
                        'app_management': True,
                    },
                    'advanced_features': {
                        'echo_memory': True,
                        'scenario_bot': True,
                        'irc_bridge': True,
                        'data_ingestion': True,
                    },
                }
            )
        except Exception:
            current_app.logger.exception('Failed to load API settings')
            return jsonify({'error': 'Failed to load settings'}), 500

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        required = ['core_features', 'development_tools', 'system_management', 'advanced_features']
        for category in required:
            if category not in data:
                return jsonify({'error': f'Missing category: {category}'}), 400

        settings_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
        return jsonify({'success': True, 'message': 'Settings saved successfully'})
    except Exception:
        current_app.logger.exception('Failed to save API settings')
        return jsonify({'error': 'Failed to save settings'}), 500


@feature_routes_bp.route('/feature/run/<path:feature_key>', methods=['POST'])
def feature_run(feature_key):
    """Run a feature by key."""
    if not FEATURE_MANAGER_AVAILABLE:
        return jsonify({'success': False, 'error': 'Feature manager not available'}), 503

    try:
        feature_manager = get_feature_manager()
        if feature_manager is None:
            return jsonify({'success': False, 'error': 'Feature manager not initialized'}), 503

        data = request.get_json(silent=True) or {}
        if feature_key in feature_manager.features:
            handler = feature_manager.features[feature_key]
            if handler.instance and callable(getattr(handler.instance, 'run', None)):
                result = handler.instance.run(**data)
                return jsonify({'success': True, 'result': result})
            return jsonify({'success': True, 'result': f'Feature {feature_key} is enabled but has no run method'})

        if feature_key in feature_manager.feature_configs:
            return jsonify({'success': False, 'error': f'Feature {feature_key} is configured but not enabled. Enable it first.'})

        return jsonify({'success': False, 'error': f'Feature {feature_key} not found'}), 404
    except Exception as exc:
        current_app.logger.exception('Failed to run feature %s', feature_key)
        return jsonify({'success': False, 'error': str(exc)}), 500


@feature_routes_bp.route('/web_tf_wizard')
def web_tf_wizard():
    """Serve the TF Wizard static page if present."""
    try:
        page = _root() / 'web_tf_wizard.html'
        if page.exists():
            return page.read_text(encoding='utf-8'), 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception:
        current_app.logger.exception('Failed to serve web_tf_wizard.html')
    return redirect(url_for('web_ide'))


@feature_routes_bp.route('/api/modules/toggle', methods=['POST'])
@requires_permission('dashboard')
def api_modules_toggle():
    module = request.form.get('module')
    enabled_modules = current_app.config.get('ENABLED_MODULES') or {}
    if module not in enabled_modules:
        return jsonify({'ok': False, 'error': 'Module not found'}), 400

    enabled_modules[module]['enabled'] = not enabled_modules[module]['enabled']
    cfg_file = current_app.config.get('MODULES_CONFIG')
    if cfg_file:
        cfg_file.write_text(json.dumps(enabled_modules, indent=2), encoding='utf-8')
    current_app.config['ENABLED_MODULES'] = enabled_modules
    return jsonify({'ok': True, 'enabled': enabled_modules[module]['enabled']})


@feature_routes_bp.route('/api/test')
def api_test():
    return jsonify({'ok': True, 'message': 'API is working'})

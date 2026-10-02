import json
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request


echo_control_bp = Blueprint('echo_control_bp', __name__)


def _voice_commands_file() -> Path:
    path = Path(current_app.root_path).resolve() / 'data' / 'voice_commands.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_voice_commands():
    try:
        voice_commands_file = _voice_commands_file()
        if voice_commands_file.exists():
            return json.loads(voice_commands_file.read_text(encoding='utf-8'))
    except Exception:
        pass
    return [
        {'id': 'vc_clear', 'phrase': 'clear chat', 'action': 'clear_chat', 'label': 'Clear Chat'},
        {'id': 'vc_image', 'phrase': 'show your face', 'action': 'echo_image', 'label': 'Show Echo Image'},
        {'id': 'vc_status', 'phrase': 'system status', 'action': 'send_message', 'param': 'What is the system status?', 'label': 'System Status'},
        {'id': 'vc_help', 'phrase': 'help', 'action': 'send_message', 'param': 'What can you help me with?', 'label': 'Help'},
        {'id': 'vc_deploy', 'phrase': 'deploy status', 'action': 'send_message', 'param': 'Show me the current deployment status.', 'label': 'Deploy Status'},
    ]


def _save_voice_commands(cmds):
    _voice_commands_file().write_text(json.dumps(cmds, indent=2), encoding='utf-8')


def _echo_integrations_file() -> Path:
    return Path(current_app.root_path).resolve() / 'data' / 'echo_integrations.json'


def _load_echo_integrations() -> dict:
    defaults = {
        'enabled': True,
        'lock_core_scopes': True,
        'auto': {'chat': True, 'web_ide': True, 'training': True},
        'modules': {},
    }
    try:
        cfg_file = _echo_integrations_file()
        if cfg_file.exists():
            try:
                data = json.loads(cfg_file.read_text(encoding='utf-8'))
            except Exception:
                data = {}
        else:
            data = {}

        return {
            'enabled': bool(data.get('enabled', defaults['enabled'])),
            'lock_core_scopes': bool(data.get('lock_core_scopes', defaults['lock_core_scopes'])),
            'auto': {
                'chat': bool((data.get('auto') or {}).get('chat', defaults['auto']['chat'])),
                'web_ide': bool((data.get('auto') or {}).get('web_ide', defaults['auto']['web_ide'])),
                'training': bool((data.get('auto') or {}).get('training', defaults['auto']['training'])),
            },
            'modules': dict(data.get('modules') or {}),
        }
    except Exception:
        current_app.logger.exception('Failed to load echo integrations config')
        return defaults


def _save_echo_integrations(cfg: dict):
    try:
        cfg_file = _echo_integrations_file()
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        cfg_file.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    except Exception:
        current_app.logger.exception('Failed to save echo integrations config')


def _echo_integration_enabled(scope: str, module_name: str = None, default_for_module: bool = False) -> bool:
    cfg = current_app.config.get('ECHO_INTEGRATIONS') or _load_echo_integrations()
    if not cfg.get('enabled', True):
        return False

    auto = cfg.get('auto') or {}
    if scope in ('chat', 'web_ide', 'training'):
        if cfg.get('lock_core_scopes', True):
            return True
        return bool(auto.get(scope, True))

    modules = cfg.get('modules') or {}
    if module_name:
        return bool(modules.get(module_name, default_for_module))
    return bool(default_for_module)


@echo_control_bp.route('/api/echo/voice_commands', methods=['GET'])
def api_voice_commands_get():
    return jsonify({'commands': _load_voice_commands()})


@echo_control_bp.route('/api/echo/voice_commands', methods=['POST'])
def api_voice_commands_post():
    try:
        data = request.get_json() or {}
        phrase = (data.get('phrase') or '').strip().lower()
        action = (data.get('action') or 'send_message').strip()
        param = (data.get('param') or '').strip()
        label = (data.get('label') or phrase).strip()
        if not phrase:
            return jsonify({'error': 'phrase required'}), 400

        cmds = _load_voice_commands()
        new_id = 'vc_' + uuid.uuid4().hex[:8]
        cmds.append({'id': new_id, 'phrase': phrase, 'action': action, 'param': param, 'label': label})
        _save_voice_commands(cmds)
        return jsonify({'ok': True, 'id': new_id})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@echo_control_bp.route('/api/echo/voice_commands/<cmd_id>', methods=['DELETE'])
def api_voice_commands_delete(cmd_id):
    try:
        cmds = [c for c in _load_voice_commands() if c.get('id') != cmd_id]
        _save_voice_commands(cmds)
        return jsonify({'ok': True})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@echo_control_bp.route('/api/echo/voice_commands/<cmd_id>', methods=['PUT'])
def api_voice_commands_update(cmd_id):
    try:
        data = request.get_json() or {}
        cmds = _load_voice_commands()
        for cmd in cmds:
            if cmd.get('id') == cmd_id:
                if 'phrase' in data:
                    cmd['phrase'] = data['phrase'].strip().lower()
                if 'action' in data:
                    cmd['action'] = data['action'].strip()
                if 'param' in data:
                    cmd['param'] = data['param'].strip()
                if 'label' in data:
                    cmd['label'] = data['label'].strip()
                break
        _save_voice_commands(cmds)
        return jsonify({'ok': True})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@echo_control_bp.route('/api/echo/action_handlers', methods=['GET'])
def api_echo_action_handlers():
    registry = current_app.config.get('_echo_action_registry')
    handlers = registry.list_handlers() if registry is not None else []
    return jsonify({'handlers': handlers})


@echo_control_bp.route('/api/echo/integrations', methods=['GET', 'POST'])
def api_echo_integrations():
    try:
        cfg = current_app.config.get('ECHO_INTEGRATIONS') or _load_echo_integrations()
        warnings = []

        if request.method == 'POST':
            body = request.get_json(silent=True) or {}

            if 'enabled' in body:
                requested = bool(body.get('enabled'))
                if cfg.get('lock_core_scopes', True) and not requested:
                    warnings.append('ignored enabled=false because lock_core_scopes is true')
                else:
                    cfg['enabled'] = requested

            if 'lock_core_scopes' in body:
                cfg['lock_core_scopes'] = bool(body.get('lock_core_scopes'))

            auto = body.get('auto')
            if isinstance(auto, dict):
                cfg.setdefault('auto', {})
                for key in ('chat', 'web_ide', 'training'):
                    if key in auto:
                        requested = bool(auto.get(key))
                        if cfg.get('lock_core_scopes', True) and not requested:
                            warnings.append(f'ignored auto.{key}=false because lock_core_scopes is true')
                            cfg['auto'][key] = True
                        else:
                            cfg['auto'][key] = requested

            mod = body.get('module')
            if mod is not None:
                mod_name = str(mod).strip()
                if mod_name:
                    cfg.setdefault('modules', {})
                    cfg['modules'][mod_name] = bool(body.get('enabled', True))

            current_app.config['ECHO_INTEGRATIONS'] = cfg
            _save_echo_integrations(cfg)

        enabled_modules = current_app.config.get('ENABLED_MODULES') or {}
        effective_modules = {}
        for mod_name in enabled_modules.keys():
            effective_modules[mod_name] = _echo_integration_enabled('module', module_name=mod_name, default_for_module=False)

        return jsonify({
            'ok': True,
            'warnings': warnings,
            'config': cfg,
            'effective': {
                'chat': _echo_integration_enabled('chat'),
                'web_ide': _echo_integration_enabled('web_ide'),
                'training': _echo_integration_enabled('training'),
                'modules': effective_modules,
            },
        })
    except Exception as exc:
        current_app.logger.exception('Echo integrations endpoint failed')
        return jsonify({'ok': False, 'error': str(exc)}), 500


@echo_control_bp.route('/api/echo/session_prefs', methods=['GET', 'POST'])
def api_echo_session_prefs():
    try:
        from echo.conversation_storage import get_storage

        storage = get_storage()
        if request.method == 'GET':
            session_id = request.args.get('session_id') or 'default'
            meta = storage.get_session_meta(session_id) or {}
            prefs = meta.get('echo_prefs') or {}
            prefs.setdefault('auto_continue', bool(current_app.config.get('ECHO_AUTO_CONTINUE', False)))
            prefs.setdefault('save_to_file', False)
            prefs.setdefault('lang', 'en')
            return jsonify({'prefs': prefs})

        data = request.get_json() or {}
        session_id = data.get('session_id') or 'default'
        prefs = data.get('prefs') or {}
        meta = storage.get_session_meta(session_id) or {}
        meta['echo_prefs'] = meta.get('echo_prefs', {})

        if 'auto_continue' in prefs:
            meta['echo_prefs']['auto_continue'] = bool(prefs.get('auto_continue'))
        if 'save_to_file' in prefs:
            meta['echo_prefs']['save_to_file'] = bool(prefs.get('save_to_file'))
        if 'lang' in prefs:
            meta['echo_prefs']['lang'] = str(prefs.get('lang'))

        storage.set_session_meta(session_id, meta)
        return jsonify({'ok': True, 'prefs': meta['echo_prefs']})
    except Exception as exc:
        current_app.logger.exception('Session prefs failed')
        return jsonify({'error': str(exc)}), 500

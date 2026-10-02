import io
import os
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_from_directory


tf_wizard_bp = Blueprint('tf_wizard_routes', __name__)

try:
    from tf_wizard.generator import generate_module_zip, tf_type_from_spec
    import tf_wizard.app as tf_wizard_app

    TF_WIZARD_AVAILABLE = True
except Exception:
    generate_module_zip = None
    tf_type_from_spec = None
    tf_wizard_app = None
    TF_WIZARD_AVAILABLE = False


def _unavailable():
    return jsonify({'error': 'TF Wizard not available'}), 503


@tf_wizard_bp.route('/tf_wizard/static/<path:filename>')
def tf_wizard_static_files(filename):
    if not TF_WIZARD_AVAILABLE:
        return _unavailable()
    try:
        tf_wizard_static = os.path.join(os.path.dirname(tf_wizard_app.__file__), 'static')
        return send_from_directory(tf_wizard_static, filename)
    except Exception:
        current_app.logger.exception('Failed to serve TF Wizard static file')
        return _unavailable()


@tf_wizard_bp.route('/tf_wizard')
def tf_wizard_index():
    if not TF_WIZARD_AVAILABLE:
        return _unavailable()
    try:
        from jinja2 import Environment, FileSystemLoader

        tf_wizard_dir = os.path.dirname(tf_wizard_app.__file__)
        templates_dir = os.path.join(tf_wizard_dir, 'templates')
        env = Environment(loader=FileSystemLoader(templates_dir), autoescape=tf_wizard_app.templates.autoescape)
        tmpl = env.get_template('index.html')
        return tmpl.render()
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400


@tf_wizard_bp.route('/tf_wizard/generate', methods=['POST'])
def tf_wizard_generate():
    if not TF_WIZARD_AVAILABLE:
        return _unavailable()
    try:
        data = request.get_json()
        zip_bytes = generate_module_zip(data)
        return Response(
            io.BytesIO(zip_bytes),
            mimetype='application/zip',
            headers={'Content-Disposition': f"attachment; filename=terraform_module_{data.get('module_name', 'module')}.zip"},
        )
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400


@tf_wizard_bp.route('/tf_wizard/schema/apply', methods=['POST'])
def tf_wizard_apply_schema():
    if not TF_WIZARD_AVAILABLE:
        return _unavailable()
    try:
        from jsonschema import Draft7Validator

        payload = request.get_json()
        schema = payload.get('schema')
        if not schema:
            return jsonify({'error': 'schema is required'}), 400

        Draft7Validator.check_schema(schema)

        props = schema.get('properties', {})
        vars_out = []

        def build_var(name, meta):
            js_type = meta.get('type')
            tf_type = tf_type_from_spec(meta) if isinstance(meta, dict) else tf_type_from_spec(js_type or '')
            v = {
                'name': name,
                'type': js_type or 'string',
                'tf_type': tf_type,
                'default': meta.get('default') if isinstance(meta, dict) and 'default' in meta else None,
                'description': meta.get('description', '') if isinstance(meta, dict) else '',
            }
            if isinstance(meta, dict) and meta.get('type') == 'object' and isinstance(meta.get('properties'), dict):
                nested = []
                for nk, nv in meta.get('properties', {}).items():
                    nested.append(build_var(nk, nv))
                v['nested'] = nested
            if isinstance(meta, dict) and 'enum' in meta:
                v['enum'] = meta.get('enum')
            return v

        for name, meta in props.items():
            vars_out.append(build_var(name, meta))
        return jsonify({'variables': vars_out})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400

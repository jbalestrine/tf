import json
import re

from flask import Blueprint, current_app, jsonify, request


okta_bp = Blueprint('okta_routes', __name__)


@okta_bp.route('/api/okta/signin', methods=['POST'])
def api_okta_signin():
    """Authenticate with Okta Primary Authentication API and create a session."""
    try:
        import urllib.request as urllib_request

        data = request.get_json() or {}
        domain = re.sub(r'^https?://', '', data.get('domain', '').strip()).rstrip('/')
        username = data.get('username', '').strip()
        password = data.get('password', '')
        if not domain or not username or not password:
            return jsonify({'error': 'domain, username and password required'}), 400

        authn_url = f'https://{domain}/api/v1/authn'
        authn_body = json.dumps(
            {
                'username': username,
                'password': password,
                'options': {'warnBeforePasswordExpired': False, 'multiOptionalFactorEnroll': False},
            }
        ).encode()
        req = urllib_request.Request(authn_url, data=authn_body, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Accept', 'application/json')
        with urllib_request.urlopen(req, timeout=15) as resp:
            authn = json.loads(resp.read().decode())

        status = authn.get('status')
        if status == 'SUCCESS':
            session_token = authn['sessionToken']
        elif status in ('MFA_REQUIRED', 'MFA_ENROLL_ACTIVATE'):
            state_token = authn.get('stateToken', '')
            factors = authn.get('_embedded', {}).get('factors', [])
            factor = next((row for row in factors if row.get('factorType') == 'token:software:totp'), None)
            if not factor:
                factor = next((row for row in factors if row.get('factorType') == 'push'), None)
            if not factor and factors:
                factor = factors[0]
            if not factor:
                return jsonify({'error': 'MFA required but no factors available'}), 400
            prompt = f'Enter code for: {factor.get("provider","")}'
            return jsonify(
                {
                    'mfa_required': True,
                    'state_token': state_token,
                    'factor_id': factor.get('id', ''),
                    'mfa_prompt': prompt,
                }
            )
        elif status == 'LOCKED_OUT':
            return jsonify({'error': 'Account is locked out.'}), 403
        elif status == 'PASSWORD_EXPIRED':
            return jsonify({'error': 'Password has expired. Reset it in Okta first.'}), 403
        else:
            return jsonify({'error': f'Unexpected status: {status}'}), 400

        sess_url = f'https://{domain}/api/v1/sessions'
        sess_body = json.dumps({'sessionToken': session_token}).encode()
        req2 = urllib_request.Request(sess_url, data=sess_body, method='POST')
        req2.add_header('Content-Type', 'application/json')
        req2.add_header('Accept', 'application/json')
        with urllib_request.urlopen(req2, timeout=15) as resp2:
            session = json.loads(resp2.read().decode())

        return jsonify(
            {
                'session_id': session.get('id'),
                'login': session.get('login', username),
                'display_name': (authn.get('_embedded', {}).get('user', {}).get('profile') or {}).get('displayName', ''),
            }
        )
    except Exception as exc:
        current_app.logger.exception('Okta signin failed')
        err_msg = str(exc)
        try:
            if hasattr(exc, 'read'):
                body_err = json.loads(exc.read().decode())
                err_msg = body_err.get('errorSummary') or body_err.get('message') or err_msg
        except Exception:
            pass
        return jsonify({'error': err_msg}), 500


@okta_bp.route('/api/okta/mfa', methods=['POST'])
def api_okta_mfa():
    """Verify an MFA factor and return a session."""
    try:
        import urllib.request as urllib_request

        data = request.get_json() or {}
        domain = re.sub(r'^https?://', '', data.get('domain', '').strip()).rstrip('/')
        state_token = data.get('state_token', '')
        factor_id = data.get('factor_id', '')
        passcode = data.get('passcode', '').strip()
        if not all([domain, state_token, factor_id, passcode]):
            return jsonify({'error': 'domain, state_token, factor_id and passcode required'}), 400

        verify_url = f'https://{domain}/api/v1/authn/factors/{factor_id}/verify'
        body = json.dumps({'stateToken': state_token, 'passCode': passcode}).encode()
        req = urllib_request.Request(verify_url, data=body, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Accept', 'application/json')
        with urllib_request.urlopen(req, timeout=15) as resp:
            authn = json.loads(resp.read().decode())

        if authn.get('status') != 'SUCCESS':
            return jsonify({'error': f"MFA status: {authn.get('status')}. Check your code."}), 400

        session_token = authn['sessionToken']
        sess_url = f'https://{domain}/api/v1/sessions'
        sess_body = json.dumps({'sessionToken': session_token}).encode()
        req2 = urllib_request.Request(sess_url, data=sess_body, method='POST')
        req2.add_header('Content-Type', 'application/json')
        req2.add_header('Accept', 'application/json')
        with urllib_request.urlopen(req2, timeout=15) as resp2:
            session = json.loads(resp2.read().decode())

        return jsonify({'session_id': session.get('id'), 'login': session.get('login', '')})
    except Exception as exc:
        current_app.logger.exception('Okta MFA failed')
        err_msg = str(exc)
        try:
            if hasattr(exc, 'read'):
                body_err = json.loads(exc.read().decode())
                err_msg = body_err.get('errorSummary') or err_msg
        except Exception:
            pass
        return jsonify({'error': err_msg}), 500


@okta_bp.route('/api/okta/apps', methods=['POST'])
def api_okta_apps():
    """Fetch app links assigned to the current Okta user."""
    try:
        import urllib.request as urllib_request

        data = request.get_json() or {}
        domain = re.sub(r'^https?://', '', data.get('domain', '').strip()).rstrip('/')
        session_id = data.get('session_id', '').strip()
        if not domain or not session_id:
            return jsonify({'error': 'domain and session_id required'}), 400

        url = f'https://{domain}/api/v1/users/me/appLinks'
        apps = None
        last_err = ''

        try:
            req = urllib_request.Request(url)
            req.add_header('Accept', 'application/json')
            req.add_header('Cookie', f'sid={session_id}')
            with urllib_request.urlopen(req, timeout=20) as resp:
                apps = json.loads(resp.read().decode())
        except Exception as err1:
            last_err = str(err1)
            try:
                if hasattr(err1, 'read'):
                    body = json.loads(err1.read().decode())
                    last_err = body.get('errorSummary') or last_err
            except Exception:
                pass

        if apps is None:
            try:
                req2 = urllib_request.Request(url)
                req2.add_header('Accept', 'application/json')
                req2.add_header('Authorization', f'SSWS {session_id}')
                with urllib_request.urlopen(req2, timeout=20) as resp2:
                    apps = json.loads(resp2.read().decode())
                last_err = ''
            except Exception as err2:
                try:
                    if hasattr(err2, 'read'):
                        body2 = json.loads(err2.read().decode())
                        last_err = body2.get('errorSummary') or str(err2)
                except Exception:
                    last_err = str(err2)

        if apps is None:
            return jsonify({'error': last_err or 'Could not retrieve apps from Okta'}), 500

        if isinstance(apps, dict):
            apps = apps.get('appLinks') or apps.get('value') or []

        return jsonify({'apps': apps, 'count': len(apps)})
    except Exception as exc:
        current_app.logger.exception('Okta apps failed')
        return jsonify({'error': str(exc)}), 500

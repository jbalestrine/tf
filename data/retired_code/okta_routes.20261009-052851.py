# Retired from main.py on 20261009-052851; now served by blueprints.okta_routes.
# Kept for reference - restore by pasting back into main.py.

@app.route('/api/okta/signin', methods=['POST'])
def api_okta_signin():
    """Authenticate with Okta Primary Authentication API and create a session."""
    try:
        import urllib.request as _ur, urllib.parse as _up, re as _re
        data = request.get_json() or {}
        domain   = _re.sub(r'^https?://', '', data.get('domain', '').strip()).rstrip('/')
        username = data.get('username', '').strip()
        password = data.get('password', '')
        if not domain or not username or not password:
            return jsonify({'error': 'domain, username and password required'}), 400

        # Step 1: Primary authentication
        authn_url = f'https://{domain}/api/v1/authn'
        authn_body = json.dumps({'username': username, 'password': password,
                                  'options': {'warnBeforePasswordExpired': False, 'multiOptionalFactorEnroll': False}}).encode()
        req = _ur.Request(authn_url, data=authn_body, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Accept', 'application/json')
        with _ur.urlopen(req, timeout=15) as resp:
            authn = json.loads(resp.read().decode())

        status = authn.get('status')

        if status == 'SUCCESS':
            session_token = authn['sessionToken']
        elif status in ('MFA_REQUIRED', 'MFA_ENROLL_ACTIVATE'):
            # Return MFA challenge info to the client
            state_token = authn.get('stateToken', '')
            factors = authn.get('_embedded', {}).get('factors', [])
            # Prefer TOTP (token:software:totp) or push
            factor = next((f for f in factors if f.get('factorType') == 'token:software:totp'), None)
            if not factor:
                factor = next((f for f in factors if f.get('factorType') == 'push'), None)
            if not factor and factors:
                factor = factors[0]
            if not factor:
                return jsonify({'error': 'MFA required but no factors available'}), 400
            prompt = f'Enter code for: {factor.get("provider","")}'
            return jsonify({'mfa_required': True, 'state_token': state_token,
                            'factor_id': factor.get('id', ''), 'mfa_prompt': prompt})
        elif status == 'LOCKED_OUT':
            return jsonify({'error': 'Account is locked out.'}), 403
        elif status == 'PASSWORD_EXPIRED':
            return jsonify({'error': 'Password has expired. Reset it in Okta first.'}), 403
        else:
            return jsonify({'error': f'Unexpected status: {status}'}), 400

        # Step 2: Exchange session token for a session (get session id for API calls)
        sess_url = f'https://{domain}/api/v1/sessions'
        sess_body = json.dumps({'sessionToken': session_token}).encode()
        req2 = _ur.Request(sess_url, data=sess_body, method='POST')
        req2.add_header('Content-Type', 'application/json')
        req2.add_header('Accept', 'application/json')
        with _ur.urlopen(req2, timeout=15) as resp2:
            session = json.loads(resp2.read().decode())

        return jsonify({
            'session_id': session.get('id'),
            'login': session.get('login', username),
            'user_id': (authn.get('_embedded', {}).get('user') or {}).get('id', ''),
            'display_name': (authn.get('_embedded', {}).get('user', {}).get('profile') or {}).get('displayName', ''),
        })
    except Exception as e:
        app.logger.exception('Okta signin failed')
        err_msg = str(e)
        try:
            if hasattr(e, 'read'):
                body_err = json.loads(e.read().decode())
                err_msg = body_err.get('errorSummary') or body_err.get('message') or err_msg
        except Exception:
            pass
        return jsonify({'error': err_msg}), 500


@app.route('/api/okta/mfa', methods=['POST'])
def api_okta_mfa():
    """Verify an MFA factor and return a session."""
    try:
        import urllib.request as _ur, re as _re
        data = request.get_json() or {}
        domain      = _re.sub(r'^https?://', '', data.get('domain', '').strip()).rstrip('/')
        state_token = data.get('state_token', '')
        factor_id   = data.get('factor_id', '')
        passcode    = data.get('passcode', '').strip()
        if not all([domain, state_token, factor_id, passcode]):
            return jsonify({'error': 'domain, state_token, factor_id and passcode required'}), 400

        verify_url = f'https://{domain}/api/v1/authn/factors/{factor_id}/verify'
        body = json.dumps({'stateToken': state_token, 'passCode': passcode}).encode()
        req = _ur.Request(verify_url, data=body, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Accept', 'application/json')
        with _ur.urlopen(req, timeout=15) as resp:
            authn = json.loads(resp.read().decode())

        if authn.get('status') != 'SUCCESS':
            return jsonify({'error': f"MFA status: {authn.get('status')}. Check your code."}), 400

        session_token = authn['sessionToken']
        sess_url  = f'https://{domain}/api/v1/sessions'
        sess_body = json.dumps({'sessionToken': session_token}).encode()
        req2 = _ur.Request(sess_url, data=sess_body, method='POST')
        req2.add_header('Content-Type', 'application/json')
        req2.add_header('Accept', 'application/json')
        with _ur.urlopen(req2, timeout=15) as resp2:
            session = json.loads(resp2.read().decode())

        return jsonify({
            'session_id': session.get('id'),
            'login': session.get('login', ''),
            'user_id': (authn.get('_embedded', {}).get('user') or {}).get('id', ''),
        })
    except Exception as e:
        app.logger.exception('Okta MFA failed')
        err_msg = str(e)
        try:
            if hasattr(e, 'read'):
                body_err = json.loads(e.read().decode())
                err_msg = body_err.get('errorSummary') or err_msg
        except Exception:
            pass
        return jsonify({'error': err_msg}), 500


@app.route('/api/okta/apps', methods=['POST'])
def api_okta_apps():
    """Fetch the app links assigned to the current Okta user."""
    try:
        import urllib.request as _ur, re as _re
        data = request.get_json() or {}
        domain     = _re.sub(r'^https?://', '', data.get('domain', '').strip()).rstrip('/')
        session_id = data.get('session_id', '').strip()
        user_id    = data.get('user_id', '').strip()
        if not domain or not session_id or not user_id:
            return jsonify({'error': 'domain, session_id and user_id required; sign in again if user identity is missing'}), 400

        from urllib.parse import quote as _quote
        url = f'https://{domain}/api/v1/users/{_quote(user_id, safe="")}/appLinks'
        req = _ur.Request(url)
        req.add_header('Accept', 'application/json')
        req.add_header('Cookie', f'sid={session_id}')
        try:
            with _ur.urlopen(req, timeout=20) as resp:
                apps = json.loads(resp.read().decode())
        except Exception as apps_error:
            error_message = str(apps_error)
            try:
                if hasattr(apps_error, 'read'):
                    body = json.loads(apps_error.read().decode())
                    error_message = body.get('errorSummary') or body.get('message') or error_message
            except (ValueError, AttributeError):
                pass
            return jsonify({'error': f'Okta app links request failed: {error_message}'}), 502

        # apps may be a list or a dict with embedded list
        if isinstance(apps, dict):
            apps = apps.get('appLinks') or apps.get('value') or []

        return jsonify({'apps': apps, 'count': len(apps)})
    except Exception as e:
        app.logger.exception('Okta apps failed')
        return jsonify({'error': str(e)}), 500

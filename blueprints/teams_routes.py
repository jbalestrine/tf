import base64
import json
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path

from flask import Blueprint, current_app, get_flashed_messages, jsonify, render_template_string, request

from auth_module import requires_permission


teams_bp = Blueprint('teams_routes', __name__)

_CONTENT_MARKER = '{% block content %}{% endblock %}'


@teams_bp.route('/teams')
@requires_permission('dashboard')
def teams_page():
    """Teams page. Markup: templates/teams.html. The site layout comes from main.py via the feature loader."""
    content = (Path(current_app.root_path) / 'templates' / 'teams.html').read_text(encoding='utf-8')
    layout = current_app.config.get('_layout_template', _CONTENT_MARKER)
    return render_template_string(layout.replace(_CONTENT_MARKER, content), request=request, get_flashed_messages=get_flashed_messages)


@teams_bp.route('/api/teams/connect', methods=['POST'])
def api_teams_connect():
    """Acquire an Azure AD token for Microsoft Graph."""
    try:
        import urllib.parse as urllib_parse
        import urllib.request as urllib_request

        data = request.get_json() or {}
        tenant_id = data.get('tenant_id', '').strip()
        client_id = data.get('client_id', '').strip()
        grant_type = data.get('grant_type', 'client_credentials')

        if not client_id:
            if grant_type == 'password':
                client_id = '04b07795-8542-4c45-a359-a4867a4e20c5'
            else:
                return jsonify({'error': 'client_id required'}), 400

        if grant_type == 'password':
            if not tenant_id or tenant_id.lower() in ('common', 'consumers'):
                tenant_id = 'organizations'
        else:
            if not tenant_id:
                tenant_id = 'common'

        token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'

        if grant_type == 'password':
            username = data.get('username', '').strip()
            password = data.get('password', '')
            if not username or not password:
                return jsonify({'error': 'username and password required for password grant'}), 400
            form = {
                'grant_type': 'password',
                'client_id': client_id,
                'username': username,
                'password': password,
                'scope': 'https://graph.microsoft.com/Calendars.Read https://graph.microsoft.com/Chat.Read https://graph.microsoft.com/Chat.ReadWrite https://graph.microsoft.com/User.Read offline_access openid',
            }
        else:
            client_secret = data.get('client_secret', '').strip()
            if not client_secret:
                return jsonify({'error': 'client_secret required for client_credentials grant'}), 400
            form = {
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret,
                'scope': 'https://graph.microsoft.com/.default',
            }

        body = urllib_parse.urlencode(form).encode()
        req = urllib_request.Request(token_url, data=body, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        with urllib_request.urlopen(req, timeout=15) as resp:
            token_json = json.loads(resp.read().decode())

        token = token_json.get('access_token')
        if not token:
            return jsonify({'error': token_json.get('error_description') or token_json.get('error_codes') or 'No token in response'}), 400

        return jsonify({'token': token, 'scope': token_json.get('scope', ''), 'grant_type': grant_type})
    except Exception as exc:
        current_app.logger.exception('Teams connect failed')
        err_msg = str(exc)
        try:
            if hasattr(exc, 'read'):
                body_err = json.loads(exc.read().decode())
                err_msg = body_err.get('error_description') or body_err.get('error') or err_msg
        except Exception:
            pass
        return jsonify({'error': err_msg}), 500


@teams_bp.route('/api/teams/calendar', methods=['POST'])
def api_teams_calendar():
    """Fetch calendar events from Microsoft Graph."""
    try:
        import urllib.parse as urllib_parse
        import urllib.request as urllib_request

        data = request.get_json() or {}
        token = data.get('token', '').strip()
        start_date = data.get('start_date', '')
        end_date = data.get('end_date', '')
        upn = (data.get('upn') or '').strip()

        if not token:
            return jsonify({'error': 'token required'}), 400
        if not start_date or not end_date:
            return jsonify({'error': 'start_date and end_date required'}), 400

        start_iso = start_date + 'T00:00:00' if 'T' not in start_date else start_date
        end_iso = end_date + 'T23:59:59' if 'T' not in end_date else end_date

        use_me = data.get('use_me', False)
        if use_me or not upn:
            endpoint = 'https://graph.microsoft.com/v1.0/me/calendarView'
        else:
            endpoint = f'https://graph.microsoft.com/v1.0/users/{urllib_parse.quote(upn)}/calendarView'

        params = urllib_parse.urlencode(
            {
                'startDateTime': start_iso,
                'endDateTime': end_iso,
                '$top': 200,
                '$select': 'subject,start,end,location,organizer,showAs,isOnlineMeeting,onlineMeetingUrl,bodyPreview,webLink',
                '$orderby': 'start/dateTime',
            }
        )
        url = endpoint + '?' + params
        req = urllib_request.Request(url)
        req.add_header('Authorization', 'Bearer ' + token)
        req.add_header('Content-Type', 'application/json')
        with urllib_request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode())

        events = result.get('value', [])
        next_link = result.get('@odata.nextLink')
        while next_link and len(events) < 1000:
            nr = urllib_request.Request(next_link)
            nr.add_header('Authorization', 'Bearer ' + token)
            with urllib_request.urlopen(nr, timeout=20) as page_resp:
                page = json.loads(page_resp.read().decode())
            events.extend(page.get('value', []))
            next_link = page.get('@odata.nextLink')

        return jsonify({'events': events, 'count': len(events)})
    except Exception as exc:
        current_app.logger.exception('Teams calendar fetch failed')
        err_msg = str(exc)
        try:
            if hasattr(exc, 'read'):
                body_err = json.loads(exc.read().decode())
                err_msg = body_err.get('error', {}).get('message') or err_msg
        except Exception:
            pass
        return jsonify({'error': err_msg}), 500


@teams_bp.route('/api/teams/chats', methods=['POST'])
def api_teams_chats():
    """List current user's recent chats via Microsoft Graph."""
    try:
        import urllib.request as urllib_request

        data = request.get_json() or {}
        token = data.get('token', '').strip()
        if not token:
            return jsonify({'error': 'token required'}), 400

        url = 'https://graph.microsoft.com/v1.0/me/chats?$top=50&$expand=members&$select=id,topic,chatType,lastMessagePreview'
        req = urllib_request.Request(url)
        req.add_header('Authorization', 'Bearer ' + token)
        with urllib_request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode())

        return jsonify({'chats': result.get('value', [])})
    except Exception as exc:
        current_app.logger.exception('Teams chats failed')
        err_msg = str(exc)
        try:
            if hasattr(exc, 'read'):
                body_err = json.loads(exc.read().decode())
                err_msg = (body_err.get('error') or {}).get('message') or err_msg
        except Exception:
            pass
        return jsonify({'error': err_msg}), 500


@teams_bp.route('/api/teams/chat/messages', methods=['POST'])
def api_teams_chat_messages():
    """Fetch recent messages from a specific Teams chat."""
    try:
        import urllib.parse as urllib_parse
        import urllib.request as urllib_request

        data = request.get_json() or {}
        token = data.get('token', '').strip()
        chat_id = data.get('chat_id', '').strip()
        if not token or not chat_id:
            return jsonify({'error': 'token and chat_id required'}), 400

        url = (
            'https://graph.microsoft.com/v1.0/me/chats/'
            + urllib_parse.quote(chat_id, safe='')
            + '/messages?$top=50&$select=id,body,from,createdDateTime,messageType'
        )
        req = urllib_request.Request(url)
        req.add_header('Authorization', 'Bearer ' + token)
        with urllib_request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode())

        messages = [msg for msg in result.get('value', []) if msg.get('messageType') == 'message']
        return jsonify({'messages': messages})
    except Exception as exc:
        current_app.logger.exception('Teams chat messages failed')
        err_msg = str(exc)
        try:
            if hasattr(exc, 'read'):
                body_err = json.loads(exc.read().decode())
                err_msg = (body_err.get('error') or {}).get('message') or err_msg
        except Exception:
            pass
        return jsonify({'error': err_msg}), 500


@teams_bp.route('/api/teams/chat/send', methods=['POST'])
def api_teams_chat_send():
    """Send a text message to a Teams chat."""
    try:
        import urllib.parse as urllib_parse
        import urllib.request as urllib_request

        data = request.get_json() or {}
        token = data.get('token', '').strip()
        chat_id = data.get('chat_id', '').strip()
        message = data.get('message', '').strip()
        if not token or not chat_id or not message:
            return jsonify({'error': 'token, chat_id and message required'}), 400

        url = 'https://graph.microsoft.com/v1.0/me/chats/' + urllib_parse.quote(chat_id, safe='') + '/messages'
        body = json.dumps({'body': {'content': message, 'contentType': 'text'}}).encode()
        req = urllib_request.Request(url, data=body, method='POST')
        req.add_header('Authorization', 'Bearer ' + token)
        req.add_header('Content-Type', 'application/json')
        with urllib_request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode())

        return jsonify({'ok': True, 'id': result.get('id')})
    except Exception as exc:
        current_app.logger.exception('Teams chat send failed')
        err_msg = str(exc)
        try:
            if hasattr(exc, 'read'):
                body_err = json.loads(exc.read().decode())
                err_msg = (body_err.get('error') or {}).get('message') or err_msg
        except Exception:
            pass
        return jsonify({'error': err_msg}), 500


@teams_bp.route('/api/teams/device_start', methods=['POST'])
def api_teams_device_start():
    """Start OAuth2 device code flow for Microsoft Graph."""
    try:
        import urllib.parse as urllib_parse
        import urllib.request as urllib_request

        data = request.get_json() or {}
        tenant_id = data.get('tenant_id', 'common').strip() or 'common'
        if tenant_id.lower() == 'consumers':
            tenant_id = 'common'

        client_id = data.get('client_id', '').strip() or '04b07795-8542-4c45-a359-a4867a4e20c5'
        url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/devicecode'
        form = urllib_parse.urlencode(
            {
                'client_id': client_id,
                'scope': 'https://graph.microsoft.com/Calendars.Read https://graph.microsoft.com/Chat.Read https://graph.microsoft.com/Chat.ReadWrite https://graph.microsoft.com/User.Read offline_access openid',
            }
        ).encode()
        req = urllib_request.Request(url, data=form, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        with urllib_request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode())
        return jsonify(payload)
    except Exception as exc:
        current_app.logger.exception('Device start failed')
        err_msg = str(exc)
        try:
            if hasattr(exc, 'read'):
                err_msg = json.loads(exc.read().decode()).get('error_description') or err_msg
        except Exception:
            pass
        return jsonify({'error': err_msg}), 500


@teams_bp.route('/api/teams/device_poll', methods=['POST'])
def api_teams_device_poll():
    """Poll for a token after device code login completes."""
    try:
        import urllib.parse as urllib_parse
        import urllib.request as urllib_request

        data = request.get_json() or {}
        tenant_id = data.get('tenant_id', 'common').strip() or 'common'
        device_code = data.get('device_code', '').strip()
        if not device_code:
            return jsonify({'error': 'device_code required'}), 400

        client_id = data.get('client_id', '').strip() or '04b07795-8542-4c45-a359-a4867a4e20c5'
        url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
        form = urllib_parse.urlencode(
            {
                'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                'client_id': client_id,
                'device_code': device_code,
            }
        ).encode()
        req = urllib_request.Request(url, data=form, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')

        try:
            with urllib_request.urlopen(req, timeout=15) as resp:
                token_json = json.loads(resp.read().decode())

            token = token_json.get('access_token')
            if not token:
                return jsonify({'error': token_json.get('error_description') or 'No token'}), 400

            upn = ''
            id_token = token_json.get('id_token', '')
            if id_token:
                try:
                    parts = id_token.split('.')
                    padded = parts[1] + '=' * (4 - len(parts[1]) % 4)
                    claims = json.loads(base64.urlsafe_b64decode(padded).decode('utf-8', errors='ignore'))
                    upn = claims.get('preferred_username') or claims.get('upn') or claims.get('email') or ''
                except Exception:
                    pass

            return jsonify({'token': token, 'upn': upn})
        except Exception as poll_err:
            err_body = {}
            try:
                if hasattr(poll_err, 'read'):
                    err_body = json.loads(poll_err.read().decode())
            except Exception:
                pass

            err_code = err_body.get('error', '')
            if err_code == 'authorization_pending':
                return jsonify({'pending': True})
            if err_code in ('expired_token', 'code_expired', 'authorization_declined'):
                return jsonify({'expired': True})
            return jsonify({'error': err_body.get('error_description') or str(poll_err)}), 400
    except Exception as exc:
        current_app.logger.exception('Device poll failed')
        return jsonify({'error': str(exc)}), 500


@teams_bp.route('/api/teams/ps_status', methods=['POST'])
def api_teams_ps_status():
    """Check if MicrosoftTeams PS module is installed and detect cached session."""
    try:
        ps_script = textwrap.dedent(
            r"""
            $m = Get-Module MicrosoftTeams -ListAvailable | Sort-Object Version -Descending | Select-Object -First 1
            if (-not $m) { [PSCustomObject]@{module_found=$false} | ConvertTo-Json -Compress; exit }
            $ver = $m.Version.ToString()
            try {
                $conn = Connect-MicrosoftTeams -UseDeviceAuthentication:$false -ErrorAction Stop 2>$null
                if (-not $conn -or -not $conn.Account) { throw 'no account' }
                [PSCustomObject]@{module_found=$true; version=$ver; connected=$true; account=[string]$conn.Account; tenant_id=[string]$conn.TenantId} | ConvertTo-Json -Compress
            } catch {
                [PSCustomObject]@{module_found=$true; version=$ver; connected=$false} | ConvertTo-Json -Compress
            }
            """
        ).strip()

        tf = tempfile.NamedTemporaryFile(suffix='.ps1', mode='w', delete=False, encoding='utf-8')
        tf.write(ps_script)
        tf.close()
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', tf.name],
                capture_output=True,
                text=True,
                timeout=30,
            )
        finally:
            Path(tf.name).unlink(missing_ok=True)

        stdout = result.stdout.strip()
        if not stdout:
            return jsonify({'error': result.stderr.strip() or 'No output from PowerShell'}), 500

        match = re.search(r'\{.*\}', stdout, re.DOTALL)
        data = json.loads(match.group(0) if match else stdout)
        return jsonify(data)
    except Exception as exc:
        current_app.logger.exception('PS status check failed')
        return jsonify({'error': str(exc)}), 500


@teams_bp.route('/api/teams/ps_connect', methods=['POST'])
def api_teams_ps_connect():
    """Run Connect-MicrosoftTeams and return account/tenant."""
    try:
        ps_script = textwrap.dedent(
            r"""
            Import-Module MicrosoftTeams -ErrorAction Stop
            $conn = Connect-MicrosoftTeams -ErrorAction Stop
            if ($conn -and $conn.Account) {
                [PSCustomObject]@{connected=$true; account=[string]$conn.Account; tenant_id=[string]$conn.TenantId; tenant_name=[string]$conn.TenantDomain} | ConvertTo-Json -Compress
            } else {
                [PSCustomObject]@{connected=$false; error='Connect-MicrosoftTeams returned no account'} | ConvertTo-Json -Compress
            }
            """
        ).strip()

        tf = tempfile.NamedTemporaryFile(suffix='.ps1', mode='w', delete=False, encoding='utf-8')
        tf.write(ps_script)
        tf.close()
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', tf.name],
                capture_output=True,
                text=True,
                timeout=120,
            )
        finally:
            Path(tf.name).unlink(missing_ok=True)

        stdout = result.stdout.strip()
        if not stdout:
            return jsonify({'connected': False, 'error': result.stderr.strip() or 'No output from PowerShell'}), 500

        match = re.search(r'\{.*\}', stdout, re.DOTALL)
        data = json.loads(match.group(0) if match else stdout)
        if data.get('connected') and not data.get('tenant_name'):
            data['tenant_name'] = data.get('account', '')
        return jsonify(data)
    except Exception as exc:
        current_app.logger.exception('PS connect failed')
        return jsonify({'connected': False, 'error': str(exc)}), 500


@teams_bp.route('/api/teams/ps_teams', methods=['POST'])
def api_teams_ps_teams():
    """Return Teams the signed-in user can see."""
    try:
        ps_script = textwrap.dedent(
            r"""
            Import-Module MicrosoftTeams -ErrorAction Stop
            $conn = Connect-MicrosoftTeams -ErrorAction Stop
            $teams = $null
            try { $teams = Get-Team -ErrorAction Stop | Select-Object GroupId, DisplayName, Description, Visibility } catch {}
            if (-not $teams) {
                try { $teams = Get-AssociatedTeam -ErrorAction Stop | Select-Object GroupId, DisplayName, Description, Visibility } catch {}
            }
            if ($teams) { $teams | ConvertTo-Json -Compress -Depth 3 } else { Write-Output '[]' }
            """
        ).strip()

        tf = tempfile.NamedTemporaryFile(suffix='.ps1', mode='w', delete=False, encoding='utf-8')
        tf.write(ps_script)
        tf.close()
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', tf.name],
                capture_output=True,
                text=True,
                timeout=180,
            )
        finally:
            Path(tf.name).unlink(missing_ok=True)

        stdout = result.stdout.strip()
        if not stdout:
            return jsonify({'error': result.stderr.strip() or 'No output'}), 500

        match = re.search(r'(\[.*\]|\{.*\})', stdout, re.DOTALL)
        raw = match.group(0) if match else stdout
        try:
            parsed = json.loads(raw)
        except Exception:
            return jsonify({'error': 'Could not parse Teams output', 'raw': stdout[:500]}), 500

        if isinstance(parsed, dict):
            parsed = [parsed]
        return jsonify({'teams': parsed})
    except Exception as exc:
        current_app.logger.exception('PS get-team failed')
        return jsonify({'error': str(exc)}), 500

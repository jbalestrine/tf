import datetime
import json
import os
import re
import subprocess
import tempfile
import threading

from flask import Blueprint, jsonify, request


certs_bp = Blueprint('certs_routes', __name__)

_CERT_AUDIT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cert_audit.json')
_cert_audit_lock = threading.Lock()
CERT_STORES_ALL = ['My', 'Root', 'CA', 'TrustedPeople', 'WebHosting']


def _cert_audit_add(action, subject='', detail='', thumbprint=''):
    entry = {
        'action': action,
        'subject': subject,
        'thumbprint': thumbprint,
        'detail': detail,
        'timestamp': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
    }
    with _cert_audit_lock:
        try:
            existing = []
            if os.path.exists(_CERT_AUDIT_FILE):
                with open(_CERT_AUDIT_FILE, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
        except Exception:
            existing = []
        existing.insert(0, entry)
        existing = existing[:500]
        with open(_CERT_AUDIT_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing, f)


def _run_ps(script, timeout=30):
    try:
        r = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as exc:
        return '', str(exc), 1


def _ps_list_certs(store):
    script = (
        'Get-ChildItem -Path Cert:\\LocalMachine\\{store} -ErrorAction SilentlyContinue | '
        'Select-Object -Property Subject,Issuer,Thumbprint,NotBefore,NotAfter | '
        'ConvertTo-Json -Depth 2'
    ).format(store=store)
    out, err, _ = _run_ps(script)
    if not out:
        return [], err
    try:
        raw = json.loads(out)
        if isinstance(raw, dict):
            raw = [raw]
        certs = []

        def _msdate(v):
            if not v:
                return ''
            m2 = re.search(r'(\d+)', str(v))
            if m2:
                try:
                    ts = int(m2.group(1)) / 1000
                    return datetime.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')
                except Exception:
                    pass
            return str(v)[:10]

        for c in raw or []:
            certs.append(
                {
                    'store': store,
                    'subject': c.get('Subject', ''),
                    'issuer': c.get('Issuer', ''),
                    'thumbprint': c.get('Thumbprint', ''),
                    'valid_from': _msdate(c.get('NotBefore', '')),
                    'expiry': _msdate(c.get('NotAfter', '')),
                }
            )
        return certs, None
    except Exception as exc:
        return [], str(exc)


@certs_bp.route('/api/certs/summary')
def api_certs_summary():
    total = 0
    expired = 0
    expiring_soon = 0
    now = datetime.datetime.utcnow()
    for st in CERT_STORES_ALL:
        certs, _ = _ps_list_certs(st)
        for c in certs:
            total += 1
            exp_str = c.get('expiry', '')
            if exp_str:
                try:
                    exp = datetime.datetime.strptime(exp_str[:10], '%Y-%m-%d')
                    dl = (exp - now).days
                    if dl < 0:
                        expired += 1
                    elif dl <= 30:
                        expiring_soon += 1
                except Exception:
                    pass
    return jsonify({'total': total, 'expired': expired, 'expiring_soon': expiring_soon, 'key_vault': '-', 'app_services': '-'})


@certs_bp.route('/api/certs/list', methods=['POST'])
def api_certs_list():
    data = request.get_json() or {}
    store = data.get('store', 'My').strip()
    if store == 'ALL':
        all_certs = []
        for st in CERT_STORES_ALL:
            certs, _ = _ps_list_certs(st)
            all_certs.extend(certs)
        return jsonify({'certs': all_certs})
    certs, err = _ps_list_certs(store)
    if err and not certs:
        return jsonify({'error': err}), 500
    return jsonify({'certs': certs})


@certs_bp.route('/api/certs/details', methods=['POST'])
def api_certs_details():
    data = request.get_json() or {}
    thumb = data.get('thumbprint', '').strip().replace(' ', '')
    store = data.get('store', 'My').strip()
    if not thumb:
        return jsonify({'error': 'thumbprint required'}), 400
    try:
        r = subprocess.run(['certutil', '-store', store, thumb], capture_output=True, text=True, timeout=20)
        output = r.stdout or r.stderr
    except Exception as exc:
        output = str(exc)
    _cert_audit_add('check', thumbprint=thumb, detail='Viewed details from ' + store)
    return jsonify({'output': output})


@certs_bp.route('/api/certs/expiring', methods=['POST'])
def api_certs_expiring():
    data = request.get_json() or {}
    days = int(data.get('days', 30))
    now = datetime.datetime.utcnow()
    result = []
    for st in CERT_STORES_ALL:
        certs, _ = _ps_list_certs(st)
        for c in certs:
            exp_str = c.get('expiry', '')
            if not exp_str:
                continue
            try:
                exp = datetime.datetime.strptime(exp_str[:10], '%Y-%m-%d')
                dl = (exp - now).days
                if dl <= days:
                    c['days_left'] = dl
                    result.append(c)
            except Exception:
                pass
    result.sort(key=lambda x: x.get('days_left', 0))
    _cert_audit_add('check', detail='Scanned expiring within ' + str(days) + 'd')
    return jsonify({'certs': result})


@certs_bp.route('/api/certs/wizard', methods=['POST'])
def api_certs_wizard():
    data = request.get_json() or {}
    op = data.get('op', '').strip()

    if op == 'selfsigned':
        cn = data.get('cn', '').strip()
        days = int(data.get('days', 365))
        store = data.get('store', 'My').strip()
        exportable = str(data.get('export', 'true')).lower() == 'true'
        if not cn:
            return jsonify({'error': 'Common Name required'}), 400
        ef = '-KeyExportPolicy Exportable' if exportable else '-KeyExportPolicy NonExportable'
        script = (
            '$cert = New-SelfSignedCertificate -Subject "CN={cn}" '
            '-DnsName "{cn}" '
            '-CertStoreLocation "Cert:\\LocalMachine\\{store}" '
            '-NotAfter (Get-Date).AddDays({days}) {ef}; '
            'Write-Output ("Thumbprint: " + $cert.Thumbprint); '
            'Write-Output ("Expires: " + $cert.NotAfter)'
        ).format(cn=cn.replace('"', '\\"'), store=store, days=days, ef=ef)
        out, err, rc = _run_ps(script)
        success = rc == 0 and 'Thumbprint' in out
        _cert_audit_add('create', subject='CN=' + cn, detail='Self-signed in ' + store + ', ' + str(days) + 'd')
        return jsonify({'output': out + ('\n[stderr]\n' + err if err else ''), 'success': success, 'message': 'Certificate created' if success else 'Creation may have failed'})

    if op == 'export_pfx':
        thumb = data.get('thumb', '').replace(' ', '').strip()
        store = data.get('store', 'My').strip()
        pfx_path = data.get('pfx-path', '').strip()
        pfx_pass = data.get('pfx-pass', '')
        if not thumb or not pfx_path:
            return jsonify({'error': 'Thumbprint and output path required'}), 400
        pp = ('$pw = ConvertTo-SecureString -String "{p}" -Force -AsPlainText; '.format(p=pfx_pass.replace('"', '\\"')) if pfx_pass else '$pw = $null; ')
        script = (
            '{pp}$cert = Get-ChildItem -Path "Cert:\\LocalMachine\\{store}" | '
            'Where-Object {{$_.Thumbprint -eq "{t}"}}; '
            'if(!$cert){{Write-Error "Cert not found"; exit 1}} '
            'Export-PfxCertificate -Cert $cert -FilePath "{path}" -Password $pw | Out-Null; '
            'Write-Output "Exported: {path}"'
        ).format(pp=pp, store=store, t=thumb.upper(), path=pfx_path.replace('"', '\\"'))
        out, err, rc = _run_ps(script)
        success = rc == 0
        _cert_audit_add('export', thumbprint=thumb, detail='Exported PFX to ' + pfx_path)
        return jsonify({'output': out + ('\n[stderr]\n' + err if err else ''), 'success': success, 'message': 'PFX exported' if success else 'Export failed'})

    if op == 'import_pfx':
        pfx_path = data.get('pfx-path', '').strip()
        pfx_pass = data.get('pfx-pass', '')
        store = data.get('store', 'My').strip()
        exportable = str(data.get('export', 'true')).lower() == 'true'
        if not pfx_path:
            return jsonify({'error': 'PFX file path required'}), 400
        pp = ('-Password (ConvertTo-SecureString -String "{p}" -Force -AsPlainText)'.format(p=pfx_pass.replace('"', '\\"')) if pfx_pass else '')
        ef = '-Exportable' if exportable else ''
        script = (
            '$cert = Import-PfxCertificate -FilePath "{path}" '
            '-CertStoreLocation "Cert:\\LocalMachine\\{store}" {pp} {ef}; '
            'Write-Output ("Imported: " + $cert.Thumbprint)'
        ).format(path=pfx_path.replace('"', '\\"'), store=store, pp=pp, ef=ef)
        out, err, rc = _run_ps(script)
        success = rc == 0 and 'Imported' in out
        _cert_audit_add('import', detail='Imported PFX from ' + pfx_path + ' into ' + store)
        return jsonify({'output': out + ('\n[stderr]\n' + err if err else ''), 'success': success, 'message': 'PFX imported into ' + store if success else 'Import failed'})

    if op == 'verify':
        pfx_path = data.get('pfx-path', '').strip()
        pfx_pass = data.get('pfx-pass', '')
        if not pfx_path:
            return jsonify({'error': 'File path required'}), 400
        cmd = ['certutil']
        if pfx_pass:
            cmd += ['-p', pfx_pass]
        cmd += ['-dump', pfx_path]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            out = r.stdout or r.stderr
        except Exception as exc:
            out = str(exc)
        _cert_audit_add('verify', detail='Verified: ' + pfx_path)
        return jsonify({'output': out, 'success': 'command completed successfully' in out.lower()})

    if op == 'delete':
        thumb = data.get('thumb', '').replace(' ', '').strip()
        store = data.get('store', 'My').strip()
        if not thumb:
            return jsonify({'error': 'Thumbprint required'}), 400
        try:
            r = subprocess.run(['certutil', '-delstore', store, thumb], capture_output=True, text=True, timeout=20)
            out = r.stdout + r.stderr
            success = r.returncode == 0
        except Exception as exc:
            out = str(exc)
            success = False
        _cert_audit_add('delete', thumbprint=thumb, detail='Deleted from ' + store)
        return jsonify({'output': out, 'success': success, 'message': 'Certificate deleted' if success else 'Delete failed'})

    if op == 'csr':
        cn = data.get('cn', '').strip()
        san_raw = data.get('san', '').strip()
        csr_path = data.get('pfx-path', '').strip()
        if not cn or not csr_path:
            return jsonify({'error': 'CN and output path required'}), 400
        sans = [cn] + [s.strip() for s in san_raw.split(',') if s.strip()]
        sans = list(dict.fromkeys(sans))
        inf_path = os.path.join(tempfile.gettempdir(), 'csr_' + cn.replace('.', '_')[:24] + '.inf')
        inf_lines = [
            '[Version]',
            'Signature="$Windows NT$"',
            '',
            '[NewRequest]',
            'Subject = "CN=' + cn + '"',
            'KeySpec = 1',
            'KeyLength = 2048',
            'Exportable = TRUE',
            'MachineKeySet = TRUE',
            'SMIME = False',
            'PrivateKeyArchive = FALSE',
            'UserProtected = FALSE',
            'UseExistingKeySet = FALSE',
            'ProviderName = "Microsoft RSA SChannel Cryptographic Provider"',
            'ProviderType = 12',
            'RequestType = PKCS10',
            'KeyUsage = 0xa0',
            '',
            '[EnhancedKeyUsageExtension]',
            'OID=1.3.6.1.5.5.7.3.1',
            '',
            '[Extensions]',
            '2.5.29.17 = "{text}"',
        ]
        for s in sans:
            inf_lines.append('_Continue_ = "dns=' + s + '&"')
        with open(inf_path, 'w', encoding='utf-8') as f:
            f.write('\r\n'.join(inf_lines) + '\r\n')
        try:
            rr = subprocess.run(['certreq', '-new', '-machine', inf_path, csr_path], capture_output=True, text=True, timeout=30)
            out = rr.stdout + rr.stderr
            success = rr.returncode == 0 or os.path.exists(csr_path)
            if success and os.path.exists(csr_path):
                with open(csr_path, 'r', errors='replace', encoding='utf-8') as f2:
                    out = 'CSR generated: ' + csr_path + '\n\n' + f2.read()[:3000]
        except Exception as exc:
            out = str(exc)
            success = False
        finally:
            if os.path.exists(inf_path):
                os.remove(inf_path)
        _cert_audit_add('create', subject='CN=' + cn, detail='CSR generated: ' + csr_path)
        return jsonify({'output': out, 'success': success, 'message': 'CSR written to ' + csr_path if success else 'CSR generation failed'})

    if op == 'export_cer':
        thumb = data.get('thumb', '').replace(' ', '').strip()
        store = data.get('store', 'My').strip()
        out_path = data.get('pfx-path', '').strip()
        fmt = data.get('fmt', 'DER').strip().upper()
        if not thumb or not out_path:
            return jsonify({'error': 'Thumbprint and output path required'}), 400
        esc = lambda v: v.replace('"', '\\"')
        if fmt == 'PEM':
            script = (
                '$cert = Get-ChildItem "Cert:\\LocalMachine\\{s}" | '
                'Where-Object {{ $_.Thumbprint -eq "{t}" }}; '
                'if(!$cert){{ Write-Error "Not found"; exit 1 }} '
                '$b64 = [Convert]::ToBase64String($cert.RawData,"InsertLineBreaks"); '
                '"-----BEGIN CERTIFICATE-----`n$b64`n-----END CERTIFICATE-----" | '
                'Out-File -FilePath "{p}" -Encoding ASCII; '
                'Write-Output "PEM exported: {p}"'
            ).format(s=store, t=thumb.upper(), p=esc(out_path))
        elif fmt == 'P7B':
            script = (
                '$cert = Get-ChildItem "Cert:\\LocalMachine\\{s}" | '
                'Where-Object {{ $_.Thumbprint -eq "{t}" }}; '
                'if(!$cert){{ Write-Error "Not found"; exit 1 }} '
                'Export-Certificate -Cert $cert -FilePath "{p}" -Type P7B | Out-Null; '
                'Write-Output "P7B exported: {p}"'
            ).format(s=store, t=thumb.upper(), p=esc(out_path))
        else:
            script = (
                '$cert = Get-ChildItem "Cert:\\LocalMachine\\{s}" | '
                'Where-Object {{ $_.Thumbprint -eq "{t}" }}; '
                'if(!$cert){{ Write-Error "Not found"; exit 1 }} '
                'Export-Certificate -Cert $cert -FilePath "{p}" -Type CERT | Out-Null; '
                'Write-Output "DER exported: {p}"'
            ).format(s=store, t=thumb.upper(), p=esc(out_path))
        out, err, rc = _run_ps(script)
        success = rc == 0
        _cert_audit_add('export', thumbprint=thumb, detail='Exported ' + fmt + ' to ' + out_path)
        return jsonify({'output': out + ('\n[stderr]\n' + err if err else ''), 'success': success, 'message': fmt + ' exported: ' + out_path if success else 'Export failed'})

    return jsonify({'error': 'Unknown operation: ' + op}), 400


@certs_bp.route('/api/certs/delete', methods=['POST'])
def api_certs_delete():
    data = request.get_json() or {}
    thumb = data.get('thumbprint', '').replace(' ', '').strip()
    store = data.get('store', 'My').strip()
    if not thumb:
        return jsonify({'error': 'thumbprint required'}), 400
    try:
        r = subprocess.run(['certutil', '-delstore', store, thumb], capture_output=True, text=True, timeout=20)
        success = r.returncode == 0
        out = r.stdout + r.stderr
    except Exception as exc:
        out = str(exc)
        success = False
    _cert_audit_add('delete', thumbprint=thumb, detail='Deleted from ' + store)
    if not success:
        return jsonify({'error': out or 'Delete failed'}), 500
    return jsonify({'ok': True})


@certs_bp.route('/api/certs/appservices', methods=['POST'])
def api_certs_appservices():
    data = request.get_json() or {}
    sub_id = data.get('subscription_id', '').strip()
    if not sub_id:
        return jsonify({'error': 'subscription_id required'}), 400
    try:
        r = subprocess.run(
            ['az', 'webapp', 'list', '--subscription', sub_id, '--query', '[].{name:name,location:location,rg:resourceGroup}', '-o', 'json'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            return jsonify({'error': 'Azure CLI error: ' + r.stderr}), 500
        webapp_list = json.loads(r.stdout or '[]')
        apps = []
        for w in webapp_list[:20]:
            ssl_r = subprocess.run(
                ['az', 'webapp', 'config', 'ssl', 'list', '--subscription', sub_id, '--resource-group', w.get('rg', ''), '--output', 'json'],
                capture_output=True,
                text=True,
                timeout=20,
            )
            bindings = []
            if ssl_r.returncode == 0:
                try:
                    for b in json.loads(ssl_r.stdout or '[]'):
                        bindings.append({'hostname': b.get('hostName', ''), 'thumbprint': b.get('thumbprint', ''), 'expiry': b.get('expirationDate', '')})
                except Exception:
                    pass
            apps.append({'name': w.get('name', ''), 'location': w.get('location', ''), 'resource_group': w.get('rg', ''), 'ssl_bindings': bindings})
        return jsonify({'apps': apps})
    except FileNotFoundError:
        return jsonify({'error': 'Azure CLI (az) not found. Install it and run `az login`.'}), 500
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@certs_bp.route('/api/certs/appgw', methods=['POST'])
def api_certs_appgw():
    data = request.get_json() or {}
    sub_id = data.get('subscription_id', '').strip()
    rg = data.get('resource_group', '').strip()
    if not sub_id:
        return jsonify({'error': 'subscription_id required'}), 400
    try:
        gw_cmd = ['az', 'network', 'application-gateway', 'list', '--subscription', sub_id, '--query', '[].{name:name,rg:resourceGroup,location:location,sku:sku.name}', '-o', 'json']
        if rg:
            gw_cmd += ['--resource-group', rg]
        r = subprocess.run(gw_cmd, capture_output=True, text=True, timeout=40)
        if r.returncode != 0:
            return jsonify({'error': 'Azure CLI error: ' + r.stderr}), 500
        gw_list = json.loads(r.stdout or '[]')
        gateways = []
        for gw in gw_list[:15]:
            gw_name = gw.get('name', '')
            gw_rg = gw.get('rg', '')
            ssl_r = subprocess.run(
                ['az', 'network', 'application-gateway', 'ssl-cert', 'list', '--gateway-name', gw_name, '--resource-group', gw_rg, '--subscription', sub_id, '-o', 'json'],
                capture_output=True,
                text=True,
                timeout=20,
            )
            ssl_certs = []
            if ssl_r.returncode == 0:
                try:
                    for c in json.loads(ssl_r.stdout or '[]'):
                        props = c.get('properties', c)
                        ssl_certs.append({'name': c.get('name', ''), 'thumbprint': props.get('publicCertData', '')[:16] or '', 'expiry': props.get('keyVaultSecretId', '')})
                except Exception:
                    pass

            ls_r = subprocess.run(
                ['az', 'network', 'application-gateway', 'http-listener', 'list', '--gateway-name', gw_name, '--resource-group', gw_rg, '--subscription', sub_id, '-o', 'json'],
                capture_output=True,
                text=True,
                timeout=20,
            )
            listeners = []
            if ls_r.returncode == 0:
                try:
                    for l in json.loads(ls_r.stdout or '[]'):
                        props = l.get('properties', l)
                        ssl_ref = props.get('sslCertificate', {})
                        ssl_name = ssl_ref.get('id', '').split('/')[-1] if ssl_ref else ''
                        listeners.append(
                            {
                                'name': l.get('name', ''),
                                'hostname': props.get('hostName', '') or (props.get('hostnames', [''])[0] if props.get('hostnames') else props.get('hostName', '')),
                                'protocol': props.get('protocol', ''),
                                'ssl_cert': ssl_name,
                            }
                        )
                except Exception:
                    pass

            gateways.append({'name': gw_name, 'resource_group': gw_rg, 'location': gw.get('location', ''), 'sku': gw.get('sku', ''), 'ssl_certs': ssl_certs, 'listeners': listeners})
        return jsonify({'gateways': gateways})
    except FileNotFoundError:
        return jsonify({'error': 'Azure CLI (az) not found. Install it and run `az login`.'}), 500
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@certs_bp.route('/api/certs/keyvault/list', methods=['POST'])
def api_certs_kv_list():
    data = request.get_json() or {}
    vault_url = data.get('vault_url', '').strip().rstrip('/')
    if not vault_url:
        return jsonify({'error': 'vault_url required'}), 400
    vault_name = vault_url.split('//')[1].split('.')[0] if '//' in vault_url else vault_url
    try:
        r = subprocess.run(['az', 'keyvault', 'certificate', 'list', '--vault-name', vault_name, '-o', 'json'], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return jsonify({'error': 'Azure CLI error: ' + r.stderr}), 500
        raw = json.loads(r.stdout or '[]')
        certs = []
        for c in raw:
            attr = c.get('attributes', {})
            certs.append({'name': c.get('name', '') or c.get('id', '').split('/')[-1], 'id': c.get('id', ''), 'enabled': attr.get('enabled', True), 'expiry': attr.get('expires', ''), 'created': attr.get('created', '')})
        return jsonify({'certs': certs})
    except FileNotFoundError:
        return jsonify({'error': 'Azure CLI not found'}), 500
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@certs_bp.route('/api/certs/keyvault/versions', methods=['POST'])
def api_certs_kv_versions():
    data = request.get_json() or {}
    vault_url = data.get('vault_url', '').strip().rstrip('/')
    cert_id = data.get('cert_id', '').strip()
    cert_name = cert_id.split('/')[-1] if '/' in cert_id else cert_id
    vault_name = vault_url.split('//')[1].split('.')[0] if '//' in vault_url else vault_url
    try:
        r = subprocess.run(['az', 'keyvault', 'certificate', 'list-versions', '--vault-name', vault_name, '--name', cert_name, '-o', 'json'], capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            return jsonify({'error': r.stderr}), 500
        return jsonify(json.loads(r.stdout or '[]'))
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@certs_bp.route('/api/certs/keyvault/sync', methods=['POST'])
def api_certs_kv_sync():
    data = request.get_json() or {}
    thumb = data.get('thumbprint', '').replace(' ', '').strip()
    cert_name = data.get('cert_name', '').strip()
    vault_url = data.get('vault_url', '').strip().rstrip('/')
    if not thumb or not cert_name or not vault_url:
        return jsonify({'error': 'thumbprint, cert_name, and vault_url required'}), 400
    vault_name = vault_url.split('//')[1].split('.')[0] if '//' in vault_url else vault_url
    tmp_pfx = os.path.join(tempfile.gettempdir(), 'kvsync_' + thumb[:8] + '.pfx')
    tmp_pass = 'KVSync_' + thumb[:6]
    try:
        script = (
            '$pw = ConvertTo-SecureString -String "{p}" -Force -AsPlainText; '
            '$cert = Get-ChildItem -Path "Cert:\\LocalMachine\\My" | Where-Object {{$_.Thumbprint -eq "{t}"}}; '
            'if(!$cert){{Write-Error "Cert not found in My store"; exit 1}} '
            'Export-PfxCertificate -Cert $cert -FilePath "{f}" -Password $pw | Out-Null; '
            'Write-Output "exported"'
        ).format(p=tmp_pass, t=thumb.upper(), f=tmp_pfx)
        out, err, rc = _run_ps(script)
        if rc != 0 or 'exported' not in out:
            return jsonify({'error': 'Failed to export PFX: ' + err}), 500
        r = subprocess.run(
            ['az', 'keyvault', 'certificate', 'import', '--vault-name', vault_name, '--name', cert_name, '--file', tmp_pfx, '--password', tmp_pass],
            capture_output=True,
            text=True,
            timeout=60,
        )
        success = r.returncode == 0
        _cert_audit_add('sync', thumbprint=thumb, detail='Synced to KV ' + vault_name + ' as ' + cert_name)
        if os.path.exists(tmp_pfx):
            os.remove(tmp_pfx)
        if not success:
            return jsonify({'error': 'KV import error: ' + r.stderr}), 500
        return jsonify({'ok': True, 'message': 'Synced to Key Vault as ' + cert_name})
    except FileNotFoundError:
        return jsonify({'error': 'Azure CLI not found'}), 500
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@certs_bp.route('/api/certs/audit')
def api_certs_audit():
    action_filter = request.args.get('action', '').strip()
    try:
        if os.path.exists(_CERT_AUDIT_FILE):
            with open(_CERT_AUDIT_FILE, 'r', encoding='utf-8') as f:
                entries = json.load(f)
        else:
            entries = []
    except Exception:
        entries = []
    if action_filter:
        entries = [e for e in entries if e.get('action', '') == action_filter]
    return jsonify({'entries': entries})


@certs_bp.route('/api/certs/audit/clear', methods=['POST'])
def api_certs_audit_clear():
    with _cert_audit_lock:
        try:
            with open(_CERT_AUDIT_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f)
        except Exception as exc:
            return jsonify({'error': str(exc)}), 500
    return jsonify({'ok': True})


@certs_bp.route('/api/certs/chain', methods=['POST'])
def api_certs_chain():
    data = request.get_json() or {}
    thumb = data.get('thumbprint', '').replace(' ', '').strip()
    store = data.get('store', 'My').strip()
    if not thumb:
        return jsonify({'error': 'thumbprint required'}), 400
    try:
        r1 = subprocess.run(['certutil', '-verifystore', store, thumb], capture_output=True, text=True, timeout=30)
        r2 = subprocess.run(['certutil', '-store', store, thumb], capture_output=True, text=True, timeout=15)
        return jsonify({'ok': r1.returncode == 0, 'chain': r1.stdout + r1.stderr, 'dump': r2.stdout + r2.stderr})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

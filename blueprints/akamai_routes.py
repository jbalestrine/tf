import datetime
import os
import socket
import ssl
import subprocess
import tempfile

from flask import Blueprint, jsonify, request

from blueprints.certs_routes import _cert_audit_add, _ps_list_certs, _run_ps


akamai_bp = Blueprint('akamai_routes', __name__)

try:
    import importlib as _importlib
    _boto3 = _importlib.import_module('boto3')
    _HAS_BOTO3 = True
except Exception:
    _boto3 = None
    _HAS_BOTO3 = False


_ak_creds_store = {}


def _ak_eg_request(method, url_path, body, creds):
    import requests as rq

    host = creds.get('host', '').strip('/')
    if not host:
        raise ValueError('Akamai host not configured')

    base = 'https://' + host if not host.startswith('http') else host
    full_url = url_path if url_path.startswith('http') else base + url_path

    try:
        import importlib as _importlib

        edgegrid_auth = _importlib.import_module('akamai.edgegrid').EdgeGridAuth
        session = rq.Session()
        session.auth = edgegrid_auth(
            client_token=creds.get('client_token', ''),
            client_secret=creds.get('client_secret', ''),
            access_token=creds.get('access_token', ''),
        )
        r = session.request(
            method,
            full_url,
            json=body if body else None,
            headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
            timeout=30,
        )
    except Exception:
        r = rq.request(
            method,
            full_url,
            json=body or None,
            headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
            timeout=20,
        )

    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {'_text': r.text[:500]}


def _r53_client(creds):
    if not _HAS_BOTO3:
        raise RuntimeError('boto3 not installed - run: pip install boto3')
    return _boto3.client(
        'route53',
        aws_access_key_id=creds.get('aws_key') or None,
        aws_secret_access_key=creds.get('aws_secret') or None,
        region_name=creds.get('aws_region') or 'us-east-1',
    )


def _get_ak_creds():
    return _ak_creds_store.get('default', {})


@akamai_bp.route('/api/akamai/creds/save', methods=['POST'])
def api_akamai_creds_save():
    data = request.get_json() or {}
    _ak_creds_store['default'] = {
        'host': data.get('host', '').strip(),
        'client_token': data.get('client_token', '').strip(),
        'access_token': data.get('access_token', '').strip(),
        'client_secret': data.get('client_secret', '').strip(),
        'aws_key': data.get('aws_key', '').strip(),
        'aws_secret': data.get('aws_secret', '').strip(),
        'aws_region': data.get('aws_region', 'us-east-1').strip(),
        'r53_zone': data.get('r53_zone', '').strip(),
        'contract': data.get('contract', '').strip(),
    }
    return jsonify({'ok': True})


@akamai_bp.route('/api/akamai/creds/test', methods=['POST'])
def api_akamai_creds_test():
    creds = _get_ak_creds()
    result = {}

    if creds.get('host') and creds.get('client_token'):
        try:
            sc, _ = _ak_eg_request('GET', '/cps/v2/enrollments?contractId=dummy', None, creds)
            result['akamai_ok'] = sc < 500
            if sc >= 500:
                result['akamai_err'] = 'HTTP ' + str(sc)
        except Exception as exc:
            result['akamai_ok'] = False
            result['akamai_err'] = str(exc)[:120]
    else:
        result['akamai_ok'] = False
        result['akamai_err'] = 'Host / credentials not set'

    try:
        r53 = _r53_client(creds)
        r53.list_hosted_zones(MaxItems='1')
        result['aws_ok'] = True
    except RuntimeError as exc:
        result['aws_ok'] = False
        result['aws_err'] = str(exc)
    except Exception as exc:
        result['aws_ok'] = False
        result['aws_err'] = str(exc)[:120]

    return jsonify(result)


@akamai_bp.route('/api/akamai/cps/list', methods=['POST'])
def api_akamai_cps_list():
    data = request.get_json() or {}
    creds = _get_ak_creds()
    contract_id = data.get('contract_id', creds.get('contract', '')).strip()
    if not contract_id:
        return jsonify({'error': 'contract_id required'}), 400

    try:
        enrollments = []
        next_url = '/cps/v2/enrollments?contractId=' + contract_id
        while next_url:
            sc, resp = _ak_eg_request('GET', next_url, None, creds)
            if sc >= 400:
                return jsonify({'error': 'Akamai API ' + str(sc) + ': ' + str(resp)[:200]}), 502
            for e in resp.get('enrollments', []):
                csr = e.get('csr', {})
                loc = e.get('location', '')
                eid = loc.split('/')[-1] if loc else str(e.get('id', ''))
                cert = e.get('signedCert', {}) or {}
                changes = e.get('pendingChanges', [])
                enrollments.append(
                    {
                        'id': eid,
                        'cn': csr.get('cn', ''),
                        'cert_type': e.get('certificateType', ''),
                        'validation_type': e.get('validationType', ''),
                        'status': 'active' if cert else ('pending' if changes else 'inactive'),
                        'expiry': cert.get('notAfter', ''),
                        'pending_changes': bool(changes),
                        'sans': csr.get('sans', []),
                    }
                )
            next_url = resp.get('nextPageLink', None) or None
        return jsonify({'enrollments': enrollments})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@akamai_bp.route('/api/akamai/cps/details', methods=['POST'])
def api_akamai_cps_details():
    data = request.get_json() or {}
    eid = str(data.get('enrollment_id', '')).strip()
    if not eid:
        return jsonify({'error': 'enrollment_id required'}), 400
    creds = _get_ak_creds()
    try:
        sc, resp = _ak_eg_request('GET', '/cps/v2/enrollments/' + eid, None, creds)
        if sc >= 400:
            return jsonify({'error': 'CPS ' + str(sc)}), 502
        return jsonify(resp)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@akamai_bp.route('/api/akamai/cps/changes', methods=['POST'])
def api_akamai_cps_changes():
    data = request.get_json() or {}
    eid = str(data.get('enrollment_id', '')).strip()
    creds = _get_ak_creds()
    try:
        sc, resp = _ak_eg_request('GET', '/cps/v2/enrollments/' + eid + '/changes', None, creds)
        if sc >= 400:
            return jsonify({'error': 'CPS changes error ' + str(sc)}), 502
        return jsonify({'changes': resp.get('changes', [])})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@akamai_bp.route('/api/akamai/cps/deploy', methods=['POST'])
def api_akamai_cps_deploy():
    data = request.get_json() or {}
    eid = str(data.get('enrollment_id', '')).strip()
    creds = _get_ak_creds()
    try:
        sc, resp = _ak_eg_request('GET', '/cps/v2/enrollments/' + eid + '/changes', None, creds)
        if sc >= 400:
            return jsonify({'error': 'Cannot fetch changes: ' + str(sc)}), 502
        changes = resp.get('changes', [])
        if not changes:
            return jsonify({'ok': True, 'message': 'No pending changes to deploy'})
        change_loc = str(changes[0])
        change_id = change_loc.split('/')[-1]
        expire_dt = (datetime.datetime.utcnow() + datetime.timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%SZ')
        body = {'certificationNotAfter': expire_dt, 'notAfter': expire_dt}
        sc2, resp2 = _ak_eg_request('PUT', '/cps/v2/enrollments/' + eid + '/changes/' + change_id + '/deployment-schedule', body, creds)
        ok = sc2 < 400
        _cert_audit_add('sync', detail='Akamai deploy enrollment ' + eid + ': HTTP ' + str(sc2))
        return jsonify({'ok': ok, 'message': 'Deployment ' + ('submitted' if ok else ('failed: ' + str(resp2)[:80]))})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@akamai_bp.route('/api/akamai/cps/dv-challenges', methods=['POST'])
def api_akamai_cps_dv_challenges():
    data = request.get_json() or {}
    eid = str(data.get('enrollment_id', '')).strip()
    creds = _get_ak_creds()
    try:
        sc, resp = _ak_eg_request('GET', '/cps/v2/enrollments/' + eid + '/changes', None, creds)
        if sc >= 400:
            return jsonify({'error': 'CPS error ' + str(sc)}), 502
        changes = resp.get('changes', [])
        if not changes:
            return jsonify({'challenges': []})
        change_id = str(changes[0]).split('/')[-1]
        sc2, chg = _ak_eg_request('GET', '/cps/v2/enrollments/' + eid + '/changes/' + change_id, None, creds)
        if sc2 >= 400:
            return jsonify({'error': 'Change detail error ' + str(sc2)}), 502
        raw = chg.get('dvChallenges', []) or chg.get('allowedInput', [])
        out = []
        for ch in raw:
            out.append({'domain': ch.get('domain', ''), 'token': ch.get('token', ''), 'answer': ch.get('answer', '')})
        return jsonify({'challenges': out})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@akamai_bp.route('/api/akamai/r53/add-record', methods=['POST'])
def api_akamai_r53_add_record():
    data = request.get_json() or {}
    zone_id = data.get('zone_id', '').strip()
    name = data.get('name', '').strip()
    value = data.get('value', '').strip()
    rtype = data.get('type', 'CNAME').strip().upper()
    ttl = int(data.get('ttl', 300))
    comment = data.get('comment', 'Added by MasterChief cert manager')
    if not zone_id or not name or not value:
        return jsonify({'error': 'zone_id, name, and value are required'}), 400

    creds = _get_ak_creds()
    try:
        r53 = _r53_client(creds)
        fqdn = name if name.endswith('.') else name + '.'
        fvalue = value if (rtype != 'CNAME' or value.endswith('.')) else value + '.'
        r53.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={
                'Comment': comment,
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {'Name': fqdn, 'Type': rtype, 'TTL': ttl, 'ResourceRecords': [{'Value': fvalue}]},
                    }
                ],
            },
        )
        _cert_audit_add('sync', detail='Route53 UPSERT ' + rtype + ': ' + fqdn + ' -> ' + fvalue)
        return jsonify({'ok': True, 'message': rtype + ' upserted: ' + fqdn + ' -> ' + fvalue})
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 500
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@akamai_bp.route('/api/akamai/r53/check-record', methods=['POST'])
def api_akamai_r53_check_record():
    data = request.get_json() or {}
    zone_id = data.get('zone_id', '').strip()
    name = data.get('name', '').strip()
    creds = _get_ak_creds()
    found = False
    rvalue = ''
    dns_val = ''

    if zone_id:
        try:
            r53 = _r53_client(creds)
            pager = r53.get_paginator('list_resource_record_sets')
            search = name if name.endswith('.') else name + '.'
            for page in pager.paginate(HostedZoneId=zone_id):
                for rr in page.get('ResourceRecordSets', []):
                    if rr['Name'].rstrip('.') == search.rstrip('.'):
                        found = True
                        rvalue = ', '.join(v['Value'] for v in rr.get('ResourceRecords', []))
                        break
                if found:
                    break
        except Exception:
            pass

    try:
        dns_val = socket.getaddrinfo(name.rstrip('.'), None)[0][4][0]
    except Exception:
        pass

    return jsonify({'found': found, 'value': rvalue, 'dns_value': dns_val})


@akamai_bp.route('/api/akamai/r53/list-records', methods=['POST'])
def api_akamai_r53_list_records():
    data = request.get_json() or {}
    zone_id = data.get('zone_id', '').strip()
    if not zone_id:
        return jsonify({'error': 'zone_id required'}), 400

    creds = _get_ak_creds()
    try:
        r53 = _r53_client(creds)
        pager = r53.get_paginator('list_resource_record_sets')
        records = []
        for page in pager.paginate(HostedZoneId=zone_id):
            for rr in page.get('ResourceRecordSets', []):
                vals = [v['Value'] for v in rr.get('ResourceRecords', [])]
                if rr.get('AliasTarget'):
                    vals = [rr['AliasTarget'].get('DNSName', '')]
                records.append({'name': rr['Name'].rstrip('.'), 'type': rr['Type'], 'ttl': rr.get('TTL', ''), 'values': vals, 'value': ', '.join(vals)})
        return jsonify({'records': records})
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 500
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@akamai_bp.route('/api/akamai/origins/check-ssl', methods=['POST'])
def api_akamai_origins_check_ssl():
    data = request.get_json() or {}
    origins = data.get('origins', {})
    results = {}
    for region, hostname in origins.items():
        hostname = (hostname or '').strip()
        if not hostname:
            continue
        try:
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
                s.settimeout(8)
                s.connect((hostname, 443))
                cert = s.getpeercert()
            not_after = cert.get('notAfter', '')
            try:
                exp = datetime.datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                exp_str = exp.strftime('%Y-%m-%d')
            except Exception:
                exp_str = not_after
            results[region] = {'ok': True, 'expiry': exp_str, 'subject': dict(x[0] for x in cert.get('subject', []))}
        except Exception as exc:
            results[region] = {'ok': False, 'error': str(exc)[:80]}
    return jsonify({'results': results})


@akamai_bp.route('/api/akamai/origins/sync-to-kv', methods=['POST'])
def api_akamai_origins_sync_to_kv():
    data = request.get_json() or {}
    origin = data.get('origin', '').strip()
    region = data.get('region', 'ctrl').strip()
    vault_url = data.get('vault_url', '').strip().rstrip('/')
    if not origin or not vault_url:
        return jsonify({'error': 'origin and vault_url required'}), 400

    vault_name = vault_url.split('//')[1].split('.')[0] if '//' in vault_url else vault_url
    certs, _ = _ps_list_certs('My')
    match = next((c for c in certs if origin.lower() in (c.get('subject') or '').lower()), None)
    if not match:
        return jsonify({'error': 'No cert in My store matching: ' + origin}), 404

    thumb = match['thumbprint']
    cert_name = ('origin-' + region + '-' + origin.replace('.', '-'))[:127]
    tmp_pfx = os.path.join(tempfile.gettempdir(), 'orig_sync_' + region + '.pfx')
    tmp_pass = 'OrigSync_' + region

    script = (
        '$pw = ConvertTo-SecureString -String "{p}" -Force -AsPlainText; '
        '$cert = Get-ChildItem -Path "Cert:\\LocalMachine\\My" | Where-Object {{$_.Thumbprint -eq "{t}"}}; '
        'if(!$cert){{Write-Error "not found"; exit 1}} '
        'Export-PfxCertificate -Cert $cert -FilePath "{f}" -Password $pw | Out-Null; '
        'Write-Output "ok"'
    ).format(p=tmp_pass, t=thumb.upper(), f=tmp_pfx)

    out, err, rc = _run_ps(script)
    if rc != 0 or 'ok' not in out:
        return jsonify({'error': 'PFX export failed: ' + err}), 500

    try:
        r = subprocess.run(
            ['az', 'keyvault', 'certificate', 'import', '--vault-name', vault_name, '--name', cert_name, '--file', tmp_pfx, '--password', tmp_pass],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if os.path.exists(tmp_pfx):
            os.remove(tmp_pfx)
        if r.returncode != 0:
            return jsonify({'error': 'KV import: ' + r.stderr}), 500
        _cert_audit_add('sync', thumbprint=thumb, detail='Synced origin ' + region + ' (' + origin + ') to KV as ' + cert_name)
        return jsonify({'ok': True, 'cert_name': cert_name})
    except FileNotFoundError:
        return jsonify({'error': 'Azure CLI not found'}), 500
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@akamai_bp.route('/api/akamai/cps/upload-cert', methods=['POST'])
def api_akamai_cps_upload_cert():
    data = request.get_json() or {}
    eid = str(data.get('enrollment_id', '')).strip()
    cert = data.get('certificate', '').strip()
    chain = data.get('trust_chain', '').strip()
    if not eid or not cert:
        return jsonify({'error': 'enrollment_id and certificate required'}), 400

    creds = _get_ak_creds()
    try:
        sc, resp = _ak_eg_request('GET', '/cps/v2/enrollments/' + eid + '/changes', None, creds)
        if sc >= 400:
            return jsonify({'error': 'Cannot fetch changes: HTTP ' + str(sc)}), 502
        changes = resp.get('changes', [])
        if not changes:
            return jsonify({'error': 'No pending changes found for enrollment ' + eid}), 404
        change_id = str(changes[0]).split('/')[-1]
        body = {'certificatesAndTrustChains': [{'certificate': cert, 'trustChain': chain if chain else None, 'keyAlgorithm': 'RSA'}]}
        sc2, resp2 = _ak_eg_request('POST', '/cps/v2/enrollments/' + eid + '/changes/' + change_id + '/input/update/third-party-csr', body, creds)
        if sc2 >= 400:
            return jsonify({'error': 'CPS upload HTTP ' + str(sc2) + ': ' + str(resp2)[:200]}), 502
        _cert_audit_add('sync', detail='Uploaded cert to CPS enrollment ' + eid + ' change ' + change_id)
        return jsonify({'ok': True, 'message': 'Certificate uploaded to enrollment ' + eid + ' (change ' + change_id + ')'})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@akamai_bp.route('/api/akamai/cps/acknowledge', methods=['POST'])
def api_akamai_cps_acknowledge():
    data = request.get_json() or {}
    eid = str(data.get('enrollment_id', '')).strip()
    if not eid:
        return jsonify({'error': 'enrollment_id required'}), 400

    creds = _get_ak_creds()
    try:
        sc0, enr = _ak_eg_request('GET', '/cps/v2/enrollments/' + eid, None, creds)
        cert_type = ''
        val_type = ''
        if sc0 < 400:
            cert_type = str(enr.get('certificateType', '')).lower()
            val_type = str(enr.get('validationType', '')).lower()

        sc, resp = _ak_eg_request('GET', '/cps/v2/enrollments/' + eid + '/changes', None, creds)
        if sc >= 400:
            return jsonify({'error': 'Cannot fetch changes: HTTP ' + str(sc)}), 502
        changes = resp.get('changes', [])
        if not changes:
            return jsonify({'ok': True, 'message': 'No pending changes to acknowledge'})

        change_id = str(changes[0]).split('/')[-1]
        ack_path = None
        sc_chg, chg_detail = _ak_eg_request('GET', '/cps/v2/enrollments/' + eid + '/changes/' + change_id, None, creds)
        if sc_chg < 400:
            for inp in chg_detail.get('allowedInput') or []:
                ack = inp.get('acknowledge', inp.get('href', ''))
                if 'lets-encrypt' in ack.lower():
                    ack_path = ack
                    break
                if 'post-verification' in ack.lower() and ack_path is None:
                    ack_path = ack

        if not ack_path:
            is_le = cert_type in ('lets-encrypt', "let's-encrypt") or val_type == 'dv'
            if is_le:
                ack_path = '/cps/v2/enrollments/' + eid + '/changes/' + change_id + '/input/acknowledge/lets-encrypt-challenges-completed'
            else:
                ack_path = '/cps/v2/enrollments/' + eid + '/changes/' + change_id + '/input/acknowledge/post-verification-warnings'

        sc2, resp2 = _ak_eg_request('POST', ack_path, {'acknowledgement': 'acknowledge'}, creds)
        ok = sc2 < 400
        _cert_audit_add('check', detail='Acknowledged enrollment ' + eid + ' change ' + change_id + ' path=' + ack_path.split('/')[-1] + ' HTTP ' + str(sc2))
        return jsonify({'ok': ok, 'ack_path': ack_path.split('/')[-1], 'message': 'Acknowledged' if ok else 'Acknowledge failed: HTTP ' + str(sc2) + ' ' + str(resp2)[:120]})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@akamai_bp.route('/api/akamai/cps/sprint-scan', methods=['POST'])
def api_akamai_cps_sprint_scan():
    data = request.get_json() or {}
    contracts = [c.strip() for c in data.get('contracts', []) if str(c).strip()]
    zone_id = data.get('zone', '').strip()
    san_threshold = int(data.get('san_threshold', 85))
    expiry_days = int(data.get('expiry_days', 60))
    creds = _get_ak_creds()

    if not contracts:
        return jsonify({'error': 'At least one contract ID is required'}), 400

    now_dt = datetime.datetime.utcnow()
    warn_dt = now_dt + datetime.timedelta(days=expiry_days)
    all_enr = []
    errors = []

    def _fetch_challenges(eid, changes):
        out = []
        try:
            change_id = str(changes[0]).split('/')[-1]
            sc2, chg = _ak_eg_request('GET', '/cps/v2/enrollments/' + eid + '/changes/' + change_id, None, creds)
            if sc2 >= 400:
                return out

            for inp in chg.get('allowedInput') or []:
                link = inp.get('update', inp.get('href', ''))
                if 'lets-encrypt' in link.lower():
                    sc3, le = _ak_eg_request('GET', link, None, creds)
                    if sc3 < 400:
                        raw = le.get('dns-challenges') or le.get('dv-challenges') or le.get('dvChallenges') or []
                        for dc in raw:
                            fp = dc.get('fullPath', dc.get('full_path', dc.get('token', '')))
                            rv = dc.get('responseBody', dc.get('response', dc.get('answer', '')))
                            out.append({'domain': dc.get('domain', dc.get('hostname', '')), 'full_path': fp, 'name': fp, 'response': rv, 'value': rv})
                    break

            if not out:
                for dc in chg.get('dvChallenges') or chg.get('dv-challenges') or []:
                    fp = dc.get('fullPath', dc.get('full_path', dc.get('token', '')))
                    rv = dc.get('responseBody', dc.get('response', dc.get('answer', '')))
                    out.append({'domain': dc.get('domain', dc.get('hostname', '')), 'full_path': fp, 'name': fp, 'response': rv, 'value': rv})
        except Exception:
            pass
        return out

    def _r53_check(cname):
        if not zone_id or not cname:
            return None
        try:
            r53 = _r53_client(creds)
            search = cname if cname.endswith('.') else cname + '.'
            pager = r53.get_paginator('list_resource_record_sets')
            for page in pager.paginate(HostedZoneId=zone_id):
                for rr in page.get('ResourceRecordSets', []):
                    rn = rr.get('Name', '')
                    if rn == search or rn.rstrip('.') == cname.rstrip('.'):
                        return 'found'
            return 'missing'
        except Exception:
            return 'error'

    for contract_id in contracts:
        try:
            raw_enrollments = []
            next_url = '/cps/v2/enrollments?contractId=' + contract_id
            while next_url:
                sc, resp = _ak_eg_request('GET', next_url, None, creds)
                if sc >= 400:
                    errors.append({'contract': contract_id, 'error': 'CPS API HTTP ' + str(sc)})
                    next_url = None
                    break
                raw_enrollments.extend(resp.get('enrollments', []))
                next_url = resp.get('nextPageLink', None) or None

            for e in raw_enrollments:
                csr_obj = e.get('csr', {}) or {}
                loc = e.get('location', '')
                eid = loc.split('/')[-1] if loc else str(e.get('id', ''))
                cert_obj = e.get('signedCert', {}) or {}
                changes = e.get('pendingChanges', [])
                sans = csr_obj.get('sans', []) or []
                san_count = len(sans) + 1
                cn = csr_obj.get('cn', '')
                val_type = e.get('validationType', '').lower()
                cert_type = e.get('certificateType', '')
                not_after_str = cert_obj.get('notAfter', '')

                status = 'active' if cert_obj else ('pending' if changes else 'inactive')
                not_after_dt = None
                if not_after_str:
                    for fmt in ('%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
                        try:
                            clean = not_after_str[:19]
                            not_after_dt = datetime.datetime.strptime(clean, fmt[: len(clean)])
                            break
                        except Exception:
                            pass

                flag_dv = bool(changes) and val_type == 'dv'
                flag_expiry = bool(not_after_dt and not_after_dt <= warn_dt)
                flag_capacity = san_count >= san_threshold

                challenges = _fetch_challenges(eid, changes) if flag_dv else []
                r53_status = None
                if flag_dv and challenges and zone_id:
                    cname = challenges[0].get('full_path') or challenges[0].get('name', '')
                    r53_status = _r53_check(cname)

                all_enr.append(
                    {
                        'enrollment_id': eid,
                        'cn': cn,
                        'contract': contract_id,
                        'cert_type': cert_type,
                        'validation_type': val_type,
                        'status': status,
                        'not_after': not_after_str[:10] if not_after_str else '',
                        'san_count': san_count,
                        'sans_preview': sans[:5],
                        'pending_changes': bool(changes),
                        'flag_dv': flag_dv,
                        'flag_expiry': flag_expiry,
                        'flag_capacity': flag_capacity,
                        'challenges': challenges,
                        'r53_status': r53_status,
                    }
                )
        except Exception as ex:
            errors.append({'contract': contract_id, 'error': str(ex)})

    all_enr.sort(key=lambda x: (0 if x['flag_dv'] else (1 if (x['flag_expiry'] or x['flag_capacity']) else 2), x.get('not_after', '9999') or '9999'))

    flagged = sum(1 for e in all_enr if e['flag_dv'] or e['flag_expiry'] or e['flag_capacity'])
    _cert_audit_add('check', detail='Sprint scan: ' + str(len(contracts)) + ' contract(s), ' + str(len(all_enr)) + ' enrollments, ' + str(flagged) + ' flagged')

    return jsonify({'enrollments': all_enr, 'total': len(all_enr), 'flagged': flagged, 'errors': errors})


@akamai_bp.route('/api/akamai/cps/renew', methods=['POST'])
def api_akamai_cps_renew():
    data = request.get_json() or {}
    eid = str(data.get('enrollment_id', '')).strip()
    if not eid:
        return jsonify({'error': 'enrollment_id required'}), 400

    creds = _get_ak_creds()
    try:
        sc0, enr = _ak_eg_request('GET', '/cps/v2/enrollments/' + eid, None, creds)
        if sc0 >= 400:
            return jsonify({'error': 'Cannot fetch enrollment: HTTP ' + str(sc0)}), 502

        changes = enr.get('pendingChanges', [])
        if changes:
            return jsonify({'ok': True, 'message': 'Enrollment already has a pending change - no renewal needed', 'change_id': str(changes[0]).split('/')[-1]})

        csr_obj = enr.get('csr', {}) or {}
        renew_body = {
            'csr': {
                'cn': csr_obj.get('cn', ''),
                'sans': csr_obj.get('sans', []),
                'c': csr_obj.get('c', ''),
                'st': csr_obj.get('st', ''),
                'l': csr_obj.get('l', ''),
                'o': csr_obj.get('o', ''),
                'ou': csr_obj.get('ou', ''),
            },
            'ra': enr.get('ra', 'lets-encrypt'),
            'validationType': enr.get('validationType', 'dv'),
            'certificateType': enr.get('certificateType', 'san'),
            'networkConfiguration': enr.get('networkConfiguration', {}),
            'signatureAlgorithm': enr.get('signatureAlgorithm', 'SHA-256'),
            'changeManagement': enr.get('changeManagement', False),
            'autoRenewalStartTime': None,
        }

        sc2, resp2 = _ak_eg_request('PUT', '/cps/v2/enrollments/' + eid + '?allow-cancel-pending-changes=true&force-renewal=true', renew_body, creds)
        if sc2 >= 400:
            return jsonify({'error': 'Renewal request failed: HTTP ' + str(sc2) + ' - ' + str(resp2)[:200]}), 502

        change_id = None
        if isinstance(resp2, dict):
            loc = resp2.get('enrollment', '') or resp2.get('location', '') or ''
            if not loc:
                sc3, ch = _ak_eg_request('GET', '/cps/v2/enrollments/' + eid + '/changes', None, creds)
                if sc3 < 400:
                    chlist = ch.get('changes', [])
                    change_id = str(chlist[0]).split('/')[-1] if chlist else None
            else:
                change_id = loc.split('/')[-1]

        _cert_audit_add('sync', detail='Renewal triggered for enrollment ' + eid + (' change ' + change_id if change_id else '') + ' HTTP ' + str(sc2))
        return jsonify({'ok': True, 'message': 'Renewal submitted for enrollment ' + eid, 'change_id': change_id})
    except Exception as ex:
        return jsonify({'error': str(ex)}), 500

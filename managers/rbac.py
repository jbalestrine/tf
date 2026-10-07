# ---------------------------------------------------------------------------
#  RBAC Manager Module
# ---------------------------------------------------------------------------

from pathlib import Path
import json, hashlib, uuid, hmac
from datetime import datetime
from flask import request, jsonify

class RBACManager:
    ALL_PERMISSIONS = [
        'dashboard','echo-chat','scripts','web_ide','processes','services',
        'addons','training','pipelines','cloud','secrets_read','secrets_write',
        'resources','notifications','rbac','marketplace'
    ]

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self._ensure_db()

    def _ensure_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            self._save({
                'users': [{
                    'id': str(uuid.uuid4()), 'username': 'admin',
                    'password_hash': hashlib.sha256('admin'.encode()).hexdigest(),
                    'role': 'admin', 'created': datetime.now().isoformat(),
                    'active': True, 'api_keys': []
                }, {
                    'id': str(uuid.uuid4()), 'username': 'public',
                    'password_hash': hashlib.sha256('public'.encode()).hexdigest(),
                    'role': 'viewer', 'created': datetime.now().isoformat(),
                    'active': True, 'api_keys': []
                }],
                'roles': [
                    {'name': 'admin', 'permissions': ['*'], 'builtin': True},
                    {'name': 'developer', 'permissions': ['dashboard','echo-chat','scripts','web_ide','resources','secrets_read','pipelines','marketplace','training'], 'builtin': True},
                    {'name': 'operator', 'permissions': ['dashboard','pipelines','processes','services','cloud','secrets_read','notifications'], 'builtin': True},
                    {'name': 'viewer', 'permissions': ['dashboard','echo-chat'], 'builtin': True}
                ],
                'sessions': [],
                'audit_log': []
            })

    def _load(self):
        try:
            return json.loads(self.db_path.read_text(encoding='utf-8'))
        except Exception:
            return {'users': [], 'roles': [], 'sessions': [], 'audit_log': []}

    def _save(self, data):
        self.db_path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def get_users(self):
        d = self._load()
        return [{ k: v for k, v in u.items() if k != 'password_hash' } for u in d['users']]

    def add_user(self, username, password, role='viewer'):
        d = self._load()
        if any(u['username'] == username for u in d['users']):
            raise ValueError(f'User {username} already exists')
        user = {
            'id': str(uuid.uuid4()), 'username': username,
            'password_hash': hashlib.sha256(password.encode()).hexdigest(),
            'role': role, 'created': datetime.now().isoformat(),
            'active': True, 'api_keys': []
        }
        d['users'].append(user)
        self._audit(d, 'system', 'user_created', f'User {username} created with role {role}')
        self._save(d)
        return {k: v for k, v in user.items() if k != 'password_hash'}

    def update_user(self, user_id, updates):
        d = self._load()
        for u in d['users']:
            if u['id'] == user_id:
                for k, v in updates.items():
                    if k == 'password':
                        u['password_hash'] = hashlib.sha256(v.encode()).hexdigest()
                    elif k not in ('id', 'password_hash'):
                        u[k] = v
                self._audit(d, 'system', 'user_updated', f'User {u["username"]} updated')
                self._save(d)
                return {k2: v2 for k2, v2 in u.items() if k2 != 'password_hash'}
        raise ValueError('User not found')

    def delete_user(self, user_id):
        d = self._load()
        d['users'] = [u for u in d['users'] if u['id'] != user_id]
        self._audit(d, 'system', 'user_deleted', f'User {user_id} deleted')
        self._save(d)

    def get_roles(self):
        return self._load().get('roles', [])

    def add_role(self, name, permissions):
        d = self._load()
        if any(r['name'] == name for r in d['roles']):
            raise ValueError(f'Role {name} already exists')
        role = {'name': name, 'permissions': permissions, 'builtin': False}
        d['roles'].append(role)
        self._audit(d, 'system', 'role_created', f'Role {name} created')
        self._save(d)
        return role

    def update_role(self, name, permissions):
        d = self._load()
        for r in d['roles']:
            if r['name'] == name:
                if r.get('builtin') and name == 'admin':
                    raise ValueError('Cannot modify admin role')
                r['permissions'] = permissions
                self._audit(d, 'system', 'role_updated', f'Role {name} updated')
                self._save(d)
                return r
        raise ValueError('Role not found')

    def delete_role(self, name):
        d = self._load()
        d['roles'] = [r for r in d['roles'] if r['name'] != name or r.get('builtin')]
        self._save(d)

    def authenticate(self, username, password):
        if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
            return None
        d = self._load()
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        for u in d['users']:
            stored_hash = u.get('password_hash', '')
            if (
                u.get('username') == username.strip()
                and isinstance(stored_hash, str)
                and hmac.compare_digest(stored_hash, pw_hash)
                and u.get('active', True)
            ):
                sess = {
                    'id': str(uuid.uuid4()), 'user_id': u['id'], 'username': username,
                    'created': datetime.now().isoformat(), 'last_active': datetime.now().isoformat(),
                    'ip': request.remote_addr or 'unknown'
                }
                d['sessions'].append(sess)
                self._audit(d, username, 'login', f'User {username} logged in')
                self._save(d)
                return sess
        return None

    def get_sessions(self):
        return self._load().get('sessions', [])

    def delete_session(self, session_id):
        d = self._load()
        d['sessions'] = [s for s in d['sessions'] if s['id'] != session_id]
        self._audit(d, 'system', 'session_revoked', f'Session {session_id[:8]}... revoked')
        self._save(d)

    def generate_api_key(self, user_id):
        d = self._load()
        for u in d['users']:
            if u['id'] == user_id:
                key = f'mc_{uuid.uuid4().hex}'
                key_entry = {'id': str(uuid.uuid4()), 'key': key, 'created': datetime.now().isoformat()}
                u.setdefault('api_keys', []).append(key_entry)
                self._audit(d, u['username'], 'api_key_generated', f'API key generated for {u["username"]}')
                self._save(d)
                return key_entry
        raise ValueError('User not found')

    def revoke_api_key(self, key_id):
        d = self._load()
        for u in d['users']:
            u['api_keys'] = [k for k in u.get('api_keys', []) if k['id'] != key_id]
        self._save(d)

    def get_audit_log(self, limit=100):
        d = self._load()
        return list(reversed(d.get('audit_log', [])))[:limit]

    def _audit(self, data, user, action, details=''):
        data.setdefault('audit_log', []).append({
            'id': str(uuid.uuid4()), 'timestamp': datetime.now().isoformat(),
            'user': user, 'action': action, 'details': details
        })
        if len(data['audit_log']) > 1000:
            data['audit_log'] = data['audit_log'][-1000:]

def register_rbac_module(app, db_path='data/rbac.json'):
    rbac_mgr = RBACManager(db_path)

    @app.before_request
    def protect_rbac_management_api():
        if not request.path.startswith('/api/rbac/') or request.path == '/api/rbac/login' or request.method == 'OPTIONS':
            return None
        from flask_login import current_user

        if not current_user.is_authenticated:
            return jsonify({'ok': False, 'error': 'Sign in is required.'}), 401
        permissions = getattr(current_user, 'permissions', [])
        if '*' not in permissions and 'rbac' not in permissions:
            return jsonify({'ok': False, 'error': 'RBAC administrator permission is required.'}), 403
        return None

    @app.route('/api/rbac/users', methods=['GET'])
    def api_rbac_users_list():
        try:
            return jsonify({'ok': True, 'result': rbac_mgr.get_users()})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/rbac/users', methods=['POST'])
    def api_rbac_users_create():
        try:
            d = request.get_json(silent=True) or {}
            user = rbac_mgr.add_user(d.get('username', ''), d.get('password', ''), d.get('role', 'viewer'))
            return jsonify({'ok': True, 'result': user})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 400

    @app.route('/api/rbac/users/<user_id>', methods=['PUT'])
    def api_rbac_users_update(user_id):
        try:
            d = request.get_json(silent=True) or {}
            user = rbac_mgr.update_user(user_id, d)
            return jsonify({'ok': True, 'result': user})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 400

    @app.route('/api/rbac/users/<user_id>', methods=['DELETE'])
    def api_rbac_users_delete(user_id):
        try:
            rbac_mgr.delete_user(user_id)
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/rbac/roles', methods=['GET'])
    def api_rbac_roles_list():
        try:
            return jsonify({'ok': True, 'result': rbac_mgr.get_roles()})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/rbac/roles', methods=['POST'])
    def api_rbac_roles_create():
        try:
            d = request.get_json(silent=True) or {}
            role = rbac_mgr.add_role(d.get('name', ''), d.get('permissions', []))
            return jsonify({'ok': True, 'result': role})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 400

    @app.route('/api/rbac/roles/<role_name>', methods=['PUT'])
    def api_rbac_roles_update(role_name):
        try:
            d = request.get_json(silent=True) or {}
            role = rbac_mgr.update_role(role_name, d.get('permissions', []))
            return jsonify({'ok': True, 'result': role})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 400

    @app.route('/api/rbac/roles/<role_name>', methods=['DELETE'])
    def api_rbac_roles_delete(role_name):
        try:
            rbac_mgr.delete_role(role_name)
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/rbac/sessions', methods=['GET'])
    def api_rbac_sessions_list():
        try:
            return jsonify({'ok': True, 'result': rbac_mgr.get_sessions()})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/rbac/sessions/<session_id>', methods=['DELETE'])
    def api_rbac_sessions_delete(session_id):
        try:
            rbac_mgr.delete_session(session_id)
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/rbac/sessions/all', methods=['DELETE'])
    def api_rbac_sessions_delete_all():
        try:
            d = rbac_mgr._load()
            d['sessions'] = []
            rbac_mgr._audit(d, 'system', 'sessions_revoked', 'All RBAC sessions were revoked')
            rbac_mgr._save(d)
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/rbac/audit', methods=['GET'])
    def api_rbac_audit():
        try:
            limit = request.args.get('limit', 100, type=int)
            return jsonify({'ok': True, 'result': rbac_mgr.get_audit_log(limit)})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/rbac/api_keys', methods=['POST'])
    def api_rbac_api_keys_create():
        try:
            d = request.get_json(silent=True) or {}
            key = rbac_mgr.generate_api_key(d.get('user_id', ''))
            return jsonify({'ok': True, 'result': key})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 400

    @app.route('/api/rbac/api_keys/<key_id>', methods=['DELETE'])
    def api_rbac_api_keys_delete(key_id):
        try:
            rbac_mgr.revoke_api_key(key_id)
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/rbac/login', methods=['POST'])
    def api_rbac_login():
        try:
            d = request.get_json(silent=True) or {}
            sess = rbac_mgr.authenticate(d.get('username', ''), d.get('password', ''))
            if sess:
                from auth_module import User
                from flask_login import login_user

                user = next((item for item in rbac_mgr.get_users() if item['id'] == sess['user_id']), None)
                if user is None:
                    return jsonify({'ok': False, 'error': 'The authenticated account could not be loaded.'}), 500
                role = next((item for item in rbac_mgr.get_roles() if item['name'] == user.get('role')), None)
                login_user(User(
                    user_id=user['id'],
                    username=user['username'],
                    email=f"{user['username']}@localhost",
                    provider='rbac',
                    role=user.get('role'),
                    permissions=role.get('permissions', []) if role else [],
                ))
                return jsonify({
                    'ok': True,
                    'result': {
                        'username': user['username'],
                        'role': user.get('role'),
                    },
                })
            return jsonify({'ok': False, 'error': 'Invalid credentials'}), 401
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    return rbac_mgr
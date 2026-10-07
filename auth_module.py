"""
MasterChief Authentication Module
Handles user authentication, session management, and OAuth flows
"""

from flask import Flask, request, redirect, url_for, session, jsonify, g, flash, current_app, abort, get_flashed_messages
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client import OAuthError
import requests
from datetime import datetime, timedelta
import jwt
from urllib.parse import urlencode
import logging
from functools import wraps
from html import escape as html_escape
from urllib.parse import urlsplit

from auth_config import auth_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def requires_permission(permission):
    """Decorator to check if user has required permission"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Fail closed if the authentication subsystem did not initialize.
            if not hasattr(current_app, 'login_manager'):
                abort(503, description='Authentication is unavailable; protected access is disabled.')

            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            
            # Admin has all permissions
            if hasattr(current_user, 'permissions') and ('*' in current_user.permissions or permission in current_user.permissions):
                return f(*args, **kwargs)
            
            # Permission denied - redirect to login instead of dashboard to avoid infinite loop
            flash(f'Access denied: {permission} permission required', 'error')
            return redirect(url_for('login'))
        return wrapper
    return decorator

class User(UserMixin):
    """User model for Flask-Login"""

    def __init__(self, user_id, username=None, email=None, provider=None, profile_data=None, role=None, permissions=None):
        self.id = user_id
        self.username = username
        self.email = email
        self.provider = provider
        self.profile_data = profile_data or {}
        self.role = role
        self.permissions = permissions or []

    @staticmethod
    def get(user_id):
        """Get user by ID (mock implementation)"""
        # In a real app, this would query a database
        return User(user_id)

class AuthModule:
    """Main authentication module"""

    def __init__(self, app: Flask):
        self.app = app
        self.oauth = OAuth(app)
        self.login_manager = LoginManager()
        self.login_manager.init_app(app)
        self.login_manager.login_view = 'login'

        # Configure OAuth providers
        self._configure_oauth_providers()

        # Register routes
        self._register_routes()

        # User session store (in production, use a database)
        self.user_sessions = {}

    def _configure_oauth_providers(self):
        """Configure OAuth providers"""

        # Azure AD
        if auth_config.is_configured('azure'):
            self.oauth.register(
                name='azure',
                client_id=auth_config.azure_client_id,
                client_secret=auth_config.azure_client_secret,
                server_metadata_url=f'https://login.microsoftonline.com/{auth_config.azure_tenant_id}/v2.0/.well-known/openid_connect_configuration',
                client_kwargs={
                    'scope': 'openid email profile https://graph.microsoft.com/User.Read'
                }
            )

        # OKTA
        if auth_config.is_configured('okta'):
            self.oauth.register(
                name='okta',
                client_id=auth_config.okta_client_id,
                client_secret=auth_config.okta_client_secret,
                server_metadata_url=f'{auth_config.okta_issuer}/.well-known/openid_configuration',
                client_kwargs={
                    'scope': 'openid email profile'
                }
            )

        # GitHub
        if auth_config.is_configured('github'):
            self.oauth.register(
                name='github',
                client_id=auth_config.github_client_id,
                client_secret=auth_config.github_client_secret,
                access_token_url='https://github.com/login/oauth/access_token',
                authorize_url='https://github.com/login/oauth/authorize',
                api_base_url='https://api.github.com/',
                client_kwargs={'scope': 'user:email read:user'},
            )

    def _register_routes(self):
        """Register authentication routes"""

        @self.app.route('/auth/status')
        def auth_status():
            """Get current authentication status"""
            if current_user.is_authenticated:
                return jsonify({
                    'authenticated': True,
                    'user': {
                        'id': current_user.id,
                        'username': current_user.username,
                        'email': current_user.email,
                        'provider': current_user.provider
                    }
                })
            return jsonify({'authenticated': False})

        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            """Simple login form"""
            if request.method == 'POST':
                username = (request.form.get('username') or '').strip()
                password = request.form.get('password') or ''
                
                # --- Try RBAC manager first ---
                rbac_mgr = current_app.config.get('_rbac_mgr')
                if rbac_mgr and username and password:
                    session_data = rbac_mgr.authenticate(username, password)
                    if session_data:
                        user = next(
                            (item for item in rbac_mgr.get_users() if item['id'] == session_data['user_id']),
                            None,
                        )
                        if user:
                            role = next(
                                (item for item in rbac_mgr.get_roles() if item['name'] == user.get('role')),
                                None,
                            )
                            rbac_user = User(
                                user_id=user['id'],
                                username=user['username'],
                                email=f"{user['username']}@localhost",
                                provider='rbac',
                                role=user.get('role'),
                                permissions=role.get('permissions', []) if role else [],
                            )
                            login_user(rbac_user)
                            next_page = request.args.get('next', '')
                            parsed_next = urlsplit(next_page)
                            if not next_page.startswith('/') or next_page.startswith('//') or parsed_next.netloc:
                                next_page = '/'
                            return redirect(next_page)
                
                flash('Sign-in failed. Check your username, password, and account status.', 'error')
                return redirect(url_for('login'))
            
            # GET request - show login form
            messages = ''.join(
                f'<div class="error">{html_escape(message)}</div>'
                for _category, message in get_flashed_messages(with_categories=True)
            )
            return '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>MasterChief Login</title>
                <style>
                    body { font-family: Arial, sans-serif; background: #1a1a1a; color: #e0e0e0; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                    .login-container { background: #2d2d2d; padding: 2rem; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); width: 400px; border: 1px solid #4CAF50; }
                    h2 { text-align: center; color: #4CAF50; margin-bottom: 1rem; }
                    form { display: flex; flex-direction: column; }
                    input { margin: 0.5rem 0; padding: 0.75rem; background: #1a1a1a; border: 1px solid #3a3a3a; color: #e0e0e0; border-radius: 5px; font-size: 1em; }
                    input:focus { outline: none; border-color: #4CAF50; }
                    button { background: #4CAF50; color: #fff; border: none; padding: 0.75rem; border-radius: 5px; cursor: pointer; margin-top: 1rem; font-size: 1em; transition: all 0.3s; }
                    button:hover { background: #45a049; transform: translateY(-2px); }
                    .contact { text-align: center; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #3a3a3a; color: #888; }
                </style>
            </head>
            <body>
                <div class="login-container">
                    <h2>MasterChief Access</h2>
                    __LOGIN_MESSAGES__
                    
                    <form method="post" autocomplete="on">
                        <input type="text" name="username" placeholder="Username" autocomplete="username" required>
                        <input type="password" name="password" placeholder="Password" autocomplete="current-password" required>
                        <button type="submit">Login</button>
                    </form>
                    
                    <div class="contact">
                        <p>For full access, contact: <a href="mailto:JosephBalestrine@yahoo.com" style="color: #4CAF50;">JosephBalestrine@yahoo.com</a></p>
                    </div>
                </div>
            </body>
            </html>
            '''.replace('__LOGIN_MESSAGES__', messages)

        @self.app.route('/roku')
        def roku_autologin():
            """Require normal authentication before opening the private Roku client."""
            return redirect(url_for('login', next='/'))

        @self.app.route('/auth/azure/login')
        def azure_login():
            """Initiate Azure AD login"""
            if not auth_config.is_configured('azure'):
                return jsonify({'error': 'Azure AD not configured'}), 500

            redirect_uri = url_for('azure_callback', _external=True)
            return self.oauth.azure.authorize_redirect(redirect_uri)

        @self.app.route('/auth/azure/callback')
        def azure_callback():
            """Handle Azure AD callback"""
            try:
                token = self.oauth.azure.authorize_access_token()
                user_info = self.oauth.azure.get('https://graph.microsoft.com/v1.0/me').json()

                user = User(
                    user_id=user_info.get('id'),
                    username=user_info.get('displayName'),
                    email=user_info.get('mail') or user_info.get('userPrincipalName'),
                    provider='azure',
                    profile_data=user_info
                )

                login_user(user)
                session['provider'] = 'azure'
                session['token'] = token

                return redirect('/okta')

            except OAuthError as e:
                logger.error(f"Azure OAuth error: {e}")
                return jsonify({'error': 'Authentication failed'}), 400

        @self.app.route('/auth/okta/login')
        def okta_login():
            """Initiate OKTA login"""
            if not auth_config.is_configured('okta'):
                return jsonify({'error': 'OKTA not configured'}), 500

            redirect_uri = url_for('okta_callback', _external=True)
            return self.oauth.okta.authorize_redirect(redirect_uri)

        @self.app.route('/auth/okta/callback')
        def okta_callback():
            """Handle OKTA callback"""
            try:
                token = self.oauth.okta.authorize_access_token()
                user_info = token.get('userinfo', {})

                user = User(
                    user_id=user_info.get('sub'),
                    username=user_info.get('name'),
                    email=user_info.get('email'),
                    provider='okta',
                    profile_data=user_info
                )

                login_user(user)
                session['provider'] = 'okta'
                session['token'] = token

                return redirect('/web-ide')

            except OAuthError as e:
                logger.error(f"OKTA OAuth error: {e}")
                return jsonify({'error': 'Authentication failed'}), 400

        @self.app.route('/auth/github/login')
        def github_login():
            """Initiate GitHub login"""
            if not auth_config.is_configured('github'):
                return jsonify({'error': 'GitHub not configured'}), 500

            redirect_uri = url_for('github_callback', _external=True)
            return self.oauth.github.authorize_redirect(redirect_uri)

        @self.app.route('/auth/github/callback')
        def github_callback():
            """Handle GitHub callback"""
            try:
                token = self.oauth.github.authorize_access_token()
                resp = self.oauth.github.get('user')
                user_info = resp.json()

                # Get user email if not provided
                if not user_info.get('email'):
                    email_resp = self.oauth.github.get('user/emails')
                    emails = email_resp.json()
                    primary_email = next((email for email in emails if email.get('primary')), None)
                    if primary_email:
                        user_info['email'] = primary_email['email']

                user = User(
                    user_id=str(user_info.get('id')),
                    username=user_info.get('login'),
                    email=user_info.get('email'),
                    provider='github',
                    profile_data=user_info
                )

                login_user(user)
                session['provider'] = 'github'
                session['token'] = token

                return redirect('/web-ide')

            except OAuthError as e:
                logger.error(f"GitHub OAuth error: {e}")
                return jsonify({'error': 'Authentication failed'}), 400

        @self.app.route('/auth/logout', methods=['POST'])
        def logout():
            """Logout user"""
            logout_user()
            session.clear()
            return jsonify({'message': 'Logged out successfully'})

    @staticmethod
    def init_app(app: Flask):
        """Initialize authentication for Flask app"""
        auth_module = AuthModule(app)

        @app.before_request
        def load_user():
            """Load current user before each request"""
            g.user = current_user

        # Register user loader
        @auth_module.login_manager.user_loader
        def load_user(user_id):
            """Load user by ID"""
            rbac_mgr = current_app.config.get('_rbac_mgr')
            if rbac_mgr:
                users = rbac_mgr.get_users()
                user = next((u for u in users if u['id'] == user_id), None)
                if user:
                    # Get user permissions
                    roles = rbac_mgr.get_roles()
                    role = next((r for r in roles if r['name'] == user.get('role')), None)
                    permissions = role.get('permissions', []) if role else []
                    
                    return User(
                        user_id=user['id'],
                        username=user['username'],
                        email=f"{user['username']}@localhost",
                        provider='rbac',
                        role=user.get('role'),
                        permissions=permissions
                    )
            return None

        return auth_module


def init_auth(app: Flask):
    """Initialize authentication module"""
    return AuthModule.init_app(app)
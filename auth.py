"""Simple in-memory auth for local development.

Provides register/login/logout and a token_required decorator that
stores sessions in-memory. This keeps the project minimal and avoids
requiring a database for local testing.
"""

import secrets
import time
from functools import wraps
from flask import Blueprint, request, jsonify, current_app, redirect, url_for
import requests
import urllib.parse
from werkzeug.security import generate_password_hash, check_password_hash

# Import Firebase auth helper
try:
    from firebase_auth import verify_firebase_token, is_firebase_enabled
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    def verify_firebase_token(token): return None
    def is_firebase_enabled(): return False

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# In-memory stores (dev only)
# USERS keyed by lowercased username to enforce case-insensitive uniqueness
USERS = {}  # username_lower -> { id, username, password_hash, created_at }
SESSIONS = {}  # token -> username_lower
OAUTH_STATES = {}  # state -> timestamp (for CSRF protection)

# Simple failed-login tracking to mitigate brute-force attempts (dev convenience)
FAILED_LOGINS = {}  # username_lower -> { count, first_attempt_ts }
LOCKOUT_THRESHOLD = 5
LOCKOUT_WINDOW_SECONDS = 300  # 5 minutes
OAUTH_STATE_TTL = 600  # OAuth state valid for 10 minutes


def generate_token():
    return secrets.token_hex(32)


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token_header = request.headers.get('Authorization')
        if not token_header or not token_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization token is missing or invalid'}), 401
        token = token_header.split(' ', 1)[1]
        username_lower = SESSIONS.get(token)
        if not username_lower:
            return jsonify({'error': 'Invalid or expired token'}), 401
        user = USERS.get(username_lower)
        if not user:
            return jsonify({'error': 'Invalid session user'}), 401
        # Pass user id as the first arg to handlers (existing convention)
        return f(user.get('id'), *args, **kwargs)
    return decorated


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    # Basic validation
    if not username or not isinstance(username, str):
        return jsonify({'error': 'Valid username is required'}), 400
    if not password or not isinstance(password, str) or len(password) < 6:
        return jsonify({'error': 'Password is required and must be at least 6 characters'}), 400

    username_clean = username.strip()
    if len(username_clean) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400

    username_lower = username_clean.lower()
    if username_lower in USERS:
        return jsonify({'error': 'Username already exists'}), 409

    user_id = secrets.token_hex(8)
    USERS[username_lower] = {
        'id': user_id,
        'username': username_clean,
        'password_hash': generate_password_hash(password),
        'created_at': int(time.time())
    }
    return jsonify({'message': 'User registered successfully', 'user_id': user_id}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not isinstance(username, str):
        return jsonify({'error': 'Username is required'}), 400
    username_lower = username.strip().lower()

    # Check lockout state
    now = int(time.time())
    fl = FAILED_LOGINS.get(username_lower)
    if fl and fl.get('count', 0) >= LOCKOUT_THRESHOLD and (now - fl.get('first_attempt_ts', now)) < LOCKOUT_WINDOW_SECONDS:
        return jsonify({'error': 'Account temporarily locked due to repeated failed login attempts. Try again later.'}), 429

    user = USERS.get(username_lower)
    if not user or not check_password_hash(user.get('password_hash', ''), password):
        # record failed attempt
        if not fl:
            FAILED_LOGINS[username_lower] = {'count': 1, 'first_attempt_ts': now}
        else:
            # reset window if too old
            if now - fl.get('first_attempt_ts', now) > LOCKOUT_WINDOW_SECONDS:
                FAILED_LOGINS[username_lower] = {'count': 1, 'first_attempt_ts': now}
            else:
                fl['count'] = fl.get('count', 0) + 1
                FAILED_LOGINS[username_lower] = fl
        return jsonify({'error': 'Invalid username or password'}), 401

    # Successful login: clear failed attempts and create session
    if username_lower in FAILED_LOGINS:
        try:
            del FAILED_LOGINS[username_lower]
        except Exception:
            pass

    token = generate_token()
    SESSIONS[token] = username_lower
    return jsonify({'token': token, 'user_id': user.get('id'), 'username': user.get('username')}), 200


@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(user_id):
    token = request.headers.get('Authorization').split(' ', 1)[1]
    if token in SESSIONS:
        del SESSIONS[token]
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/me', methods=['GET'])
@token_required
def me(user_id):
    # Return minimal user profile for the current token
    # Find user by id (scan USERS)
    for uname, u in USERS.items():
        if u.get('id') == user_id:
            return jsonify({'user_id': u.get('id'), 'username': u.get('username'), 'created_at': u.get('created_at')}), 200
    return jsonify({'error': 'User not found'}), 404



@auth_bp.route('/firebase-config', methods=['GET'])
def firebase_config():
    """
    Return Firebase configuration for frontend initialization.
    Only returns public configuration (API key, project ID, auth domain).
    """
    cfg = current_app.config
    
    api_key = cfg.get('FIREBASE_WEB_API_KEY')
    project_id = cfg.get('FIREBASE_PROJECT_ID')
    auth_domain = cfg.get('FIREBASE_AUTH_DOMAIN')
    
    if not api_key or not project_id:
        return jsonify({'error': 'Firebase not configured'}), 501
    
    # Return public Firebase config for frontend
    return jsonify({
        'apiKey': api_key,
        'authDomain': auth_domain or f"{project_id}.firebaseapp.com",
        'projectId': project_id
    }), 200


@auth_bp.route('/firebase', methods=['POST'])
def firebase_auth():
    """
    Authenticate user with Firebase ID token.
    Client sends Firebase ID token, server verifies it and creates a session.
    """
    data = request.get_json() or {}
    id_token = data.get('idToken')
    user_hint = data.get('user') or {}

    if not id_token:
        return jsonify({'error': 'ID token is required'}), 400

    # Try to verify with Firebase if configured
    user_info = None
    if is_firebase_enabled():
        user_info = verify_firebase_token(id_token)
    
    # Fallback: if Firebase Admin not available, create a dev session from token claims
    if not user_info:
        # For dev without Firebase Admin: decode JWT manually to get basic info
        try:
            import base64
            parts = id_token.split('.')
            if len(parts) >= 2:
                # Decode the payload (second part)
                payload = parts[1]
                # Add padding if needed
                padding = 4 - len(payload) % 4
                if padding != 4:
                    payload += '=' * padding
                decoded = base64.urlsafe_b64decode(payload)
                import json
                user_info = json.loads(decoded)
        except Exception as e:
            current_app.logger.debug(f"Failed to decode JWT manually: {e}")
            user_info = None

    # Final fallback: accept minimal user info from client in dev when Firebase isn't configured
    # This is only used when Firebase Admin is not initialized and token decode failed.
    if not user_info and not is_firebase_enabled() and isinstance(user_hint, dict):
        email_hint = user_hint.get('email')
        if email_hint:
            user_info = {
                'uid': user_hint.get('uid') or secrets.token_hex(8),
                'email': email_hint,
                'email_verified': False,
                'name': user_hint.get('display_name') or email_hint.split('@')[0],
                'picture': user_hint.get('picture')
            }
    
    if not user_info:
        return jsonify({'error': 'Invalid or expired token'}), 401

    # Extract user data
    email = user_info.get('email')
    if not email:
        return jsonify({'error': 'Email not found in token'}), 400

    username_lower = email.lower()

    # Create or update user
    if username_lower not in USERS:
        user_id = secrets.token_hex(8)
        USERS[username_lower] = {
            'id': user_id,
            'username': email,
            'display_name': user_info.get('name') or email.split('@')[0],
            'avatar': user_info.get('picture'),
            'firebase_uid': user_info.get('uid'),
            'email_verified': user_info.get('email_verified', False),
            'password_hash': generate_password_hash(secrets.token_hex(16)),
            'created_at': int(time.time())
        }
        current_app.logger.info(f"New Firebase user registered: {email}")
    else:
        # Update user profile from Firebase
        USERS[username_lower]['display_name'] = user_info.get('name') or USERS[username_lower].get('display_name')
        USERS[username_lower]['avatar'] = user_info.get('picture') or USERS[username_lower].get('avatar')
        USERS[username_lower]['email_verified'] = user_info.get('email_verified', False)
        current_app.logger.info(f"Firebase user logged in: {email}")

    # Create session token
    token = generate_token()
    SESSIONS[token] = username_lower

    # Return session token and user info
    user_data = USERS[username_lower]
    return jsonify({
        'token': token,
        'user_id': user_data.get('id'),
        'username': user_data.get('username'),
        'display_name': user_data.get('display_name'),
        'avatar': user_data.get('avatar'),
        'email_verified': user_data.get('email_verified', False)
    }), 200


@auth_bp.route('/google', methods=['GET', 'POST'])
def google_auth_start():
    """Start the OAuth2 flow with Google. In production supply GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET and GOOGLE_OAUTH_REDIRECT in the environment.
    For local development, if GOOGLE_CLIENT_ID is not configured, we perform a
    dev shortcut that creates/returns a session for a dummy Google user so the
    frontend flow can be tested without external credentials.
    """
    cfg = current_app.config
    client_id = cfg.get('GOOGLE_CLIENT_ID')
    redirect_uri = cfg.get('GOOGLE_OAUTH_REDIRECT') or (request.url_root.rstrip('/') + url_for('auth.google_auth_callback'))

    # Dev shortcut: if no client_id configured, support an email selection UI (GET ?choose=1)
    # and also accept POST with JSON payload { email, display_name, picture }.
    if not client_id:
        # If this is a POST, create a session for the provided payload
        if request.method == 'POST':
            data = request.get_json() or {}
            email = data.get('email') or f'google_dev_user@local'
            display_name = data.get('display_name') or email
            picture = data.get('picture') or ''

            username_lower = email.lower()
            if username_lower not in USERS:
                user_id = secrets.token_hex(8)
                USERS[username_lower] = {
                    'id': user_id,
                    'username': email,
                    'display_name': display_name,
                    'avatar': picture or None,
                    'password_hash': generate_password_hash(secrets.token_hex(8)),
                    'created_at': int(time.time())
                }

            # create session token
            token = generate_token()
            SESSIONS[token] = username_lower

            # return HTML to post message to opener including display name and picture for frontend
            html = f"""<html><body><script>
                try {{ window.opener.postMessage({{'type':'google_auth','token':'{token}','username':'{email}','display_name':'{display_name}','picture':'{picture}'}}, '*'); }} catch(e) {{}}
                try {{ window.close(); }} catch(e) {{ window.location = '/'; }}
                </script></body></html>"""
            return html, 200

        # Otherwise, render a small selection UI when ?choose=1 to let the developer
        # pick an email/display name/picture for local testing.
        if request.args.get('choose'):
            html = """
            <html><body>
              <h3>Select an email for dev Google sign-in</h3>
              <form id="dev-form">
                <label>Email: <input id="email" name="email" value="google_dev_user@local"></label><br>
                <label>Display name: <input id="display_name" name="display_name" value="Google Dev"></label><br>
                <label>Avatar URL: <input id="picture" name="picture" placeholder="https://... (optional)"></label><br>
                <button type="button" id="submit">Sign in</button>
              </form>
              <script>
                document.getElementById('submit').addEventListener('click', async function(){
                  const payload = {
                    email: document.getElementById('email').value,
                    display_name: document.getElementById('display_name').value,
                    picture: document.getElementById('picture').value
                  };
                  try {
                    const r = await fetch(window.location.href, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
                    const text = await r.text();
                    // write returned HTML into the document so it executes the postMessage
                    document.open(); document.write(text); document.close();
                  } catch (e) { alert('Failed to create dev session: '+e.message); }
                });
              </script>
            </body></html>
            """
            return html, 200

        # Default dev shortcut behavior (no choose param): create a simple dev user
        email = f'google_dev_user@local'
        username_lower = email.lower()
        if username_lower not in USERS:
            user_id = secrets.token_hex(8)
            USERS[username_lower] = {'id': user_id, 'username': email, 'password_hash': generate_password_hash(secrets.token_hex(8)), 'created_at': int(time.time())}
        # create session token
        token = generate_token()
        SESSIONS[token] = username_lower
        # return HTML to post message to opener including display_name and picture fields (defaults)
        display_name = 'Google Dev'
        picture = ''
        html = f"""<html><body><script>
            window.opener.postMessage({{'type':'google_auth','token':'{token}','username':'{email}','display_name':'{display_name}','picture':'{picture}'}}, '*');
            window.close();
            </script></body></html>"""
        return html, 200

    # Generate and store state parameter for CSRF protection
    state = secrets.token_hex(16)
    OAUTH_STATES[state] = int(time.time())
    
    # Clean up old states (older than TTL)
    now = int(time.time())
    expired_states = [s for s, ts in OAUTH_STATES.items() if now - ts > OAUTH_STATE_TTL]
    for s in expired_states:
        del OAUTH_STATES[s]
    
    scope = 'openid email profile'
    auth_uri = 'https://accounts.google.com/o/oauth2/v2/auth'
    params = {
        'client_id': client_id,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': redirect_uri,
        'access_type': 'offline',
        'prompt': 'select_account',
        'state': state
    }
    url = auth_uri + '?' + urllib.parse.urlencode(params)
    return redirect(url)


@auth_bp.route('/google/callback', methods=['GET'])
def google_auth_callback():
    cfg = current_app.config
    client_id = cfg.get('GOOGLE_CLIENT_ID')
    client_secret = cfg.get('GOOGLE_CLIENT_SECRET')
    redirect_uri = cfg.get('GOOGLE_OAUTH_REDIRECT') or (request.url_root.rstrip('/') + url_for('auth.google_auth_callback'))

    # If no client configured, support the dev shortcut where caller may hit this
    # endpoint directly (treat as error)
    if not client_id:
        return jsonify({'error': 'Google OAuth not configured on server.'}), 501

    # Verify state parameter for CSRF protection
    state = request.args.get('state')
    if not state or state not in OAUTH_STATES:
        error_msg = 'Invalid or expired OAuth state. This may be a CSRF attack or the session expired.'
        return f"<html><body><h3>Authentication Error</h3><p>{error_msg}</p><p><a href='/'>Return to app</a></p></body></html>", 400
    
    # Clean up used state
    del OAUTH_STATES[state]
    
    code = request.args.get('code')
    if not code:
        error_msg = 'Missing authorization code from Google. The sign-in may have been cancelled.'
        return f"<html><body><h3>Sign-in Cancelled</h3><p>{error_msg}</p><p><a href='/'>Return to app</a></p></body></html>", 400

    # Exchange code for tokens
    token_url = 'https://oauth2.googleapis.com/token'
    data = {
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }
    try:
        r = requests.post(token_url, data=data, timeout=10)
        r.raise_for_status()
        tok = r.json()
    except Exception as e:
        error_msg = f'Failed to exchange authorization code with Google: {str(e)}'
        return f"<html><body><h3>Authentication Error</h3><p>{error_msg}</p><p>Please try signing in again.</p><p><a href='/'>Return to app</a></p></body></html>", 502

    access_token = tok.get('access_token')
    if not access_token:
        error_msg = 'Google did not return an access token. Please try again.'
        return f"<html><body><h3>Authentication Error</h3><p>{error_msg}</p><p><a href='/'>Return to app</a></p></body></html>", 502

    # Fetch userinfo
    try:
        ui = requests.get('https://openidconnect.googleapis.com/v1/userinfo', headers={'Authorization': f'Bearer {access_token}'}, timeout=10)
        ui.raise_for_status()
        userinfo = ui.json()
    except Exception as e:
        error_msg = f'Failed to fetch user information from Google: {str(e)}'
        return f"<html><body><h3>Authentication Error</h3><p>{error_msg}</p><p>Please try signing in again.</p><p><a href='/'>Return to app</a></p></body></html>", 502

    email = userinfo.get('email') or userinfo.get('sub')
    if not email:
        error_msg = 'Google did not return an email for your account. Please ensure your Google account has an email address.'
        return f"<html><body><h3>Authentication Error</h3><p>{error_msg}</p><p><a href='/'>Return to app</a></p></body></html>", 502

    username_lower = email.lower()
    # Create user if missing
    if username_lower not in USERS:
        user_id = secrets.token_hex(8)
        USERS[username_lower] = {
            'id': user_id,
            'username': email,
            'display_name': userinfo.get('name') or email,
            'avatar': userinfo.get('picture') or None,
            'password_hash': generate_password_hash(secrets.token_hex(8)),
            'created_at': int(time.time())
        }

    # create our session token
    token = generate_token()
    SESSIONS[token] = username_lower

    # Include display name and avatar so the frontend can show the profile immediately
    display_name = USERS[username_lower].get('display_name')
    picture = USERS[username_lower].get('avatar')
    html = f"""<html><body><script>
        try {{ window.opener.postMessage({{'type':'google_auth','token':'{token}','username':'{email}','display_name':'{display_name}','picture':'{picture}'}}, '*'); }} catch(e) {{}}
        try {{ window.close(); }} catch(e) {{ window.location = '/'; }}
        </script></body></html>"""
    return html, 200
# End of in-memory auth implementation.
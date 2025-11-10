"""Simple in-memory auth for local development.

Provides register/login/logout and a token_required decorator that
stores sessions in-memory. This keeps the project minimal and avoids
requiring a database for local testing.
"""

import secrets
from functools import wraps
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# In-memory stores (dev only)
USERS = {}  # username -> { id, username, password_hash }
SESSIONS = {}  # token -> username


def generate_token():
    return secrets.token_hex(32)


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token_header = request.headers.get('Authorization')
        if not token_header or not token_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization token is missing or invalid'}), 401
        token = token_header.split(' ', 1)[1]
        username = SESSIONS.get(token)
        if not username:
            return jsonify({'error': 'Invalid or expired token'}), 401
        user = USERS.get(username)
        if not user:
            return jsonify({'error': 'Invalid session user'}), 401
        # Pass username as user_id to match existing handler signatures
        return f(user.get('id'), *args, **kwargs)
    return decorated


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    if username in USERS:
        return jsonify({'error': 'Username already exists'}), 409
    user_id = secrets.token_hex(8)
    USERS[username] = {'id': user_id, 'username': username, 'password_hash': generate_password_hash(password)}
    return jsonify({'message': 'User registered successfully', 'user_id': user_id}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    user = USERS.get(username)
    if not user or not check_password_hash(user.get('password_hash',''), password):
        return jsonify({'error': 'Invalid username or password'}), 401
    token = generate_token()
    SESSIONS[token] = username
    return jsonify({'token': token, 'user_id': user.get('id'), 'username': username}), 200


@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(user_id):
    token = request.headers.get('Authorization').split(' ', 1)[1]
    if token in SESSIONS:
        del SESSIONS[token]
    return jsonify({'message': 'Logged out successfully'}), 200
# End of in-memory auth implementation.
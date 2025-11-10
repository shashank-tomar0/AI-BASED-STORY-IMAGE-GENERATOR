# story_manager.py

from flask import Blueprint, request, jsonify
from auth import token_required
import json

# Simple in-memory story storage per user for local dev
STORY_SESSIONS = {}  # user_id -> session dict

story_bp = Blueprint('story', __name__, url_prefix='/api/story')


@story_bp.route('/save-session', methods=['POST'])
@token_required
def save_session(user_id):
    data = request.get_json() or {}
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    # Save the whole session in-memory (dev only)
    STORY_SESSIONS[user_id] = data
    return jsonify({'message': 'Session saved successfully'}), 200


@story_bp.route('/load-session', methods=['GET'])
@token_required
def load_session(user_id):
    data = STORY_SESSIONS.get(user_id)
    if not data:
        return jsonify({
            'storyHistory': [],
            'sceneCounter': 0,
            'scenes': [],
            'summaryBullets': [],
            'initialPrompt': '',
            'artStyle': 'photorealistic cinematic',
            'username': 'User'
        }), 200
    return jsonify(data), 200
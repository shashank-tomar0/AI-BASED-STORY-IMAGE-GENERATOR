# app.py

import json
from flask import Flask, render_template, jsonify
from flask_cors import CORS

from config import Config
from auth import auth_bp
from ai_service import ai_bp
from story_manager import story_bp

# Import Firebase initialization
try:
    from firebase_auth import init_firebase
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    def init_firebase(): pass

# --- FLASK APP FACTORY ---
def create_app(config_class=Config):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(config_class)
    
    # Enable CORS for all routes
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Initialize Firebase if configured
    if FIREBASE_AVAILABLE:
        with app.app_context():
            init_firebase()

    # For a simplified local development experience we don't initialize
    # a database here (auth and session storage are in-memory).

    # --- REGISTER BLUEPRINTS (Separate Logic) ---
    app.register_blueprint(auth_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(story_bp)

    # --- BASIC ROUTE ---
    # NOTE: In a production app, you would configure Nginx/Apache to serve static files
    # but for Flask-only development, this is fine.
    @app.route('/')
    def index():
        return render_template('index.html')

    # Optional lightweight compatibility endpoint: some browser extensions
    # or injected scripts attempt to fetch /prompts.json. Return an empty
    # JSON object so those requests don't generate console errors in the
    # user's browser. This keeps the UI clean while not affecting app
    # behavior.
    @app.route('/prompts.json')
    def prompts_json():
        return jsonify({}), 200

    return app

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # NOTE: You must install Flask and requests (pip install Flask requests)
    # The debug flag must be False in production
    app = create_app()
    # Run the dev server
    # Disable the auto-reloader when we start the server from scripts so
    # the background process doesn't spawn child processes which can make
    # status probes miss the real server. Safe for local dev.
    app.run(debug=True, port=5000, use_reloader=False)
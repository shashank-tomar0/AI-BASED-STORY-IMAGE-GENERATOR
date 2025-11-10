# app.py

import json
from flask import Flask, render_template

from config import Config
from auth import auth_bp
from ai_service import ai_bp
from story_manager import story_bp

# --- FLASK APP FACTORY ---
def create_app(config_class=Config):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(config_class)

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

    return app

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # NOTE: You must install Flask and requests (pip install Flask requests)
    # The debug flag must be False in production
    app = create_app()
    # Run the dev server
    app.run(debug=True, port=5000)
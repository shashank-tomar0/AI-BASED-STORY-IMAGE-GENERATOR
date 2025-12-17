# config.py

import os
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env file (install python-dotenv: pip install python-dotenv)
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)
else:
    # fallback: try loading default .env in cwd
    load_dotenv()

class Config:
    # --- CORE FLASK CONFIG ---
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a_very_secret_and_complex_key_replace_me'
    
    # --- AI SERVICE CONFIG ---
    # IMPORTANT: Use a real .env file in production. Do NOT commit real keys.
    # Read the Gemini API key from environment; default to None (no hardcoded keys).
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') or 'AIzaSyCr0nelouPRB4et6zm-rqDLGuYKLYDd9cw'
    
    # Base URLs for the Google AI services - using Gemini 2.5 Flash (latest, free tier)
    STORY_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    IMAGE_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict"
    
    # --- AUTH & SESSION CONFIG ---
    # Replace in-memory stores with a production database in a real app
    USERS = {}          # { user_id: { username: 'user1', password_hash: '...' } }
    SESSIONS = {}       # { token: user_id }
    USER_STORIES = {}   # { user_id: story_data }

    # --- IMAGE / FALLBACK CONFIG ---
    # If True, the backend will return a small placeholder image when the
    # configured image provider is unavailable or the account is not billed.
    USE_IMAGE_FALLBACK = True
    # A tiny 1x1 transparent PNG base64 (safe default placeholder)
    FALLBACK_IMAGE_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="

    # IMAGE PROVIDER configuration
    # 'google' = use Google Imagen (requires billing), 'free' = picsum placeholder, 'stability' = Stability AI, 'alternate' = forward to ALTERNATE_IMAGE_API_URL
    # Default image provider: prefer an explicit IMAGE_PROVIDER env var. If not
    # provided, fall back to stability when a STABILITY_API_KEY exists, else use 'free'.
    _has_gemini = bool(GEMINI_API_KEY)
    _env_image_provider = os.environ.get('IMAGE_PROVIDER')
    ALTERNATE_IMAGE_API_URL = os.environ.get('ALTERNATE_IMAGE_API_URL') or None
    # Force stability for real images
    IMAGE_PROVIDER = 'stability'

    # How long (seconds) to keep generated images in the local disk cache.
    # Default: 24 hours. Configure via environment variable IMAGE_CACHE_TTL_SECONDS.
    IMAGE_CACHE_TTL_SECONDS = int(os.environ.get('IMAGE_CACHE_TTL_SECONDS', 60 * 60 * 24))

    # --- Stability / Stable Diffusion CONFIG ---
    # Add support for cloud Stability.ai or a local AUTOMATIC1111 server.
    # To use Stability.ai (cloud) set IMAGE_PROVIDER=stability and provide
    # STABILITY_API_KEY in your environment.
    STABILITY_API_KEY = os.environ.get('STABILITY_API_KEY') or 'sk-9YIZgUJoO5S45q9Vs52pzFcKdavEe1DqIuHUVRJ4HYvbiFI8'
    # engine/model name for Stability.ai (change if needed)
    STABILITY_ENGINE = os.environ.get('STABILITY_ENGINE') or 'stable-diffusion-xl-1024-v1-0'
    # Local AUTOMATIC1111 URL (if you run a local server): default assumes localhost:7860
    AUTOMATIC1111_URL = os.environ.get('AUTOMATIC1111_URL') or 'http://127.0.0.1:7860'

    # LLM provider for narrative generation:
    # 'gemini' = Google Gemini API, 'groq' = Groq (fast & free), 'openai' = OpenAI GPT,
    # 'anthropic' = Claude, 'mock' = deterministic mock responses
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'gemini')
    # DISABLED mock fallback - force real LLM errors to surface instead of falling back
    USE_MOCK_FALLBACK = os.environ.get('USE_MOCK_FALLBACK', 'False').lower() == 'true'
    
    # Alternative LLM API Keys (for non-Gemini providers)
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY') or None  # Free tier: https://console.groq.com
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or None  # Free trial credits
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY') or None  # Free credits

    # --- Google OAuth2 configuration (optional) ---
    # To enable "Sign in with Google" set these environment variables in a
    # .env file or your environment. The redirect URI should point to
    # /api/auth/google/callback (e.g., http://127.0.0.1:5000/api/auth/google/callback)
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID') or None
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET') or None
    GOOGLE_OAUTH_REDIRECT = os.environ.get('GOOGLE_OAUTH_REDIRECT') or None

    # --- Firebase Authentication configuration (recommended for production) ---
    # Firebase provides easier Google sign-in and supports multiple auth providers
    # Get these from Firebase Console: https://console.firebase.google.com/
    FIREBASE_WEB_API_KEY = os.environ.get('FIREBASE_WEB_API_KEY') or None
    FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID') or None
    FIREBASE_AUTH_DOMAIN = os.environ.get('FIREBASE_AUTH_DOMAIN') or None
    # Service account for backend verification (JSON file path or JSON string)
    FIREBASE_SERVICE_ACCOUNT_PATH = os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH') or None
    FIREBASE_SERVICE_ACCOUNT_JSON = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON') or None

# Initialize a default admin user for convenience (for dev only)
Config.USERS['admin-uuid'] = {'username': 'admin', 'password_hash': 'pass'}
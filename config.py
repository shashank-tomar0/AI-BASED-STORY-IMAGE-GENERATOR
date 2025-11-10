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
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') or None
    
    # Base URLs for the Google AI services
    STORY_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"
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
    # 'google' = use Google Imagen (requires billing), 'free' = picsum placeholder, 'alternate' = forward to ALTERNATE_IMAGE_API_URL
    # Default image provider: use the free Picsum provider by default for
    # local development unless overridden by the IMAGE_PROVIDER env var.
    # If you want to use Google Imagen, set IMAGE_PROVIDER=google and ensure
    # GEMINI_API_KEY is set and billing is enabled for your Google Cloud project.
    _has_gemini = bool(GEMINI_API_KEY)
    IMAGE_PROVIDER = os.environ.get('IMAGE_PROVIDER') or 'free'
    ALTERNATE_IMAGE_API_URL = os.environ.get('ALTERNATE_IMAGE_API_URL') or None

    # --- Stability / Stable Diffusion CONFIG ---
    # Add support for cloud Stability.ai or a local AUTOMATIC1111 server.
    # To use Stability.ai (cloud) set IMAGE_PROVIDER=stability and provide
    # STABILITY_API_KEY in your environment.
    STABILITY_API_KEY = os.environ.get('STABILITY_API_KEY') or None
    # engine/model name for Stability.ai (change if needed)
    STABILITY_ENGINE = os.environ.get('STABILITY_ENGINE') or 'stable-diffusion-xl-1024-v1-0'
    # Local AUTOMATIC1111 URL (if you run a local server): default assumes localhost:7860
    AUTOMATIC1111_URL = os.environ.get('AUTOMATIC1111_URL') or 'http://127.0.0.1:7860'

    # LLM provider for narrative generation. 'gemini' uses the external Gemini API,
    # 'mock' returns deterministic mock responses for local development/testing.
    # Default LLM provider: prefer 'gemini' when a Gemini API key exists, else use 'mock' for local dev.
    # For a simplified local development experience, default to the mock
    # LLM provider and enable mock fallback so the app always produces a
    # narrative + visual prompt even if you don't have a Gemini key.
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER') or ('mock' if not _has_gemini else 'gemini')
    USE_MOCK_FALLBACK = os.environ.get('USE_MOCK_FALLBACK', 'True').lower() in ('1','true','yes')

# Initialize a default admin user for convenience (for dev only)
Config.USERS['admin-uuid'] = {'username': 'admin', 'password_hash': 'pass'}
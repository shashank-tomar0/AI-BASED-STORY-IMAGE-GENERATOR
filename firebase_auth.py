"""
Firebase Authentication Integration

This module provides Firebase Authentication for the Story Generator app.
Firebase handles Google OAuth and other auth providers automatically.

Setup:
1. Create a Firebase project: https://console.firebase.google.com/
2. Enable Google sign-in in Authentication settings
3. Download service account key JSON
4. Add to .env: FIREBASE_SERVICE_ACCOUNT_PATH=path/to/serviceAccountKey.json
5. Get Web API key and project ID from Firebase console
6. Add to .env: FIREBASE_WEB_API_KEY and FIREBASE_PROJECT_ID
"""

import os
import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from flask import current_app
import json

_firebase_initialized = False

def init_firebase():
    """Initialize Firebase Admin SDK (call once at startup)"""
    global _firebase_initialized
    
    if _firebase_initialized:
        return True
    
    # Check if Firebase is configured
    service_account_path = current_app.config.get('FIREBASE_SERVICE_ACCOUNT_PATH')
    service_account_json = current_app.config.get('FIREBASE_SERVICE_ACCOUNT_JSON')
    
    if not service_account_path and not service_account_json:
        current_app.logger.info("Firebase not configured - skipping initialization")
        return False
    
    try:
        if service_account_json:
            # Use JSON string from environment variable
            cred_dict = json.loads(service_account_json)
            cred = credentials.Certificate(cred_dict)
        elif service_account_path and os.path.exists(service_account_path):
            # Use file path
            cred = credentials.Certificate(service_account_path)
        else:
            current_app.logger.warning(f"Firebase service account file not found: {service_account_path}")
            return False
        
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        current_app.logger.info("✓ Firebase Admin SDK initialized successfully")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Failed to initialize Firebase: {e}")
        return False


def verify_firebase_token(id_token):
    """
    Verify a Firebase ID token from the client.
    
    Args:
        id_token: The Firebase ID token string from the client
        
    Returns:
        dict: User info (uid, email, name, picture) if valid
        None: If token is invalid or Firebase not initialized
    """
    if not _firebase_initialized:
        return None
    
    try:
        # Verify the token with Firebase
        decoded_token = firebase_auth.verify_id_token(id_token)
        
        # Extract user information
        user_info = {
            'uid': decoded_token.get('uid'),
            'email': decoded_token.get('email'),
            'email_verified': decoded_token.get('email_verified', False),
            'name': decoded_token.get('name'),
            'picture': decoded_token.get('picture'),
            'firebase_uid': decoded_token.get('uid')
        }
        
        return user_info
        
    except firebase_auth.InvalidIdTokenError:
        current_app.logger.warning("Invalid Firebase ID token")
        return None
    except firebase_auth.ExpiredIdTokenError:
        current_app.logger.warning("Expired Firebase ID token")
        return None
    except Exception as e:
        current_app.logger.error(f"Error verifying Firebase token: {e}")
        return None


def is_firebase_enabled():
    """Check if Firebase is configured and initialized"""
    return _firebase_initialized

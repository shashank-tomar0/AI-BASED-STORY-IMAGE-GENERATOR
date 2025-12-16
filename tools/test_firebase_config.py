"""
Quick test script to verify Firebase configuration.
Checks if Firebase is properly set up for authentication.
"""

import requests
import sys
import os

BASE_URL = "http://127.0.0.1:5000"

def test_firebase_config():
    print("=" * 60)
    print("Firebase Authentication Configuration Test")
    print("=" * 60)
    
    # Test 1: Check server status
    print("\n1. Testing server connection...")
    try:
        resp = requests.get(f"{BASE_URL}/api/ai/status", timeout=5)
        if resp.status_code == 200:
            print("   ✓ Server is responding")
        else:
            print(f"   ✗ Server returned status {resp.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"   ✗ Cannot connect to server: {e}")
        print("   Make sure the Flask server is running: python app.py")
        return False
    
    # Test 2: Check Firebase config endpoint
    print("\n2. Testing Firebase configuration endpoint...")
    try:
        resp = requests.get(f"{BASE_URL}/api/auth/firebase-config", timeout=5)
        
        if resp.status_code == 200:
            config = resp.json()
            print("   ✓ Firebase IS CONFIGURED")
            print(f"   Project ID: {config.get('projectId', 'N/A')}")
            print(f"   Auth Domain: {config.get('authDomain', 'N/A')}")
            print(f"   API Key: {config.get('apiKey', 'N/A')[:20]}...")
            firebase_enabled = True
        elif resp.status_code == 501:
            print("   ⚠ Firebase NOT configured")
            print("   Response:", resp.json().get('error', 'Unknown'))
            print("\n   To enable Firebase:")
            print("   1. See FIREBASE_SETUP.md for instructions")
            print("   2. Add Firebase credentials to .env file")
            print("   3. Restart the server")
            firebase_enabled = False
        else:
            print(f"   ✗ Unexpected status: {resp.status_code}")
            print(f"   Response: {resp.text}")
            firebase_enabled = False
            
    except requests.exceptions.RequestException as e:
        print(f"   ✗ Error: {e}")
        firebase_enabled = False
    
    # Test 3: Check for service account file
    print("\n3. Checking service account configuration...")
    service_account_path = os.path.join(os.path.dirname(__file__), '..', 'firebase-service-account.json')
    
    if os.path.exists(service_account_path):
        print(f"   ✓ Service account file found")
        print(f"   Path: firebase-service-account.json")
    else:
        print("   ⚠ Service account file NOT found")
        print("   Expected path: firebase-service-account.json")
        print("   Alternative: Set FIREBASE_SERVICE_ACCOUNT_JSON in .env")
    
    # Test 4: Check environment variables
    print("\n4. Checking environment variables...")
    try:
        from config import Config
        
        checks = [
            ('FIREBASE_WEB_API_KEY', Config.FIREBASE_WEB_API_KEY),
            ('FIREBASE_PROJECT_ID', Config.FIREBASE_PROJECT_ID),
            ('FIREBASE_AUTH_DOMAIN', Config.FIREBASE_AUTH_DOMAIN),
            ('FIREBASE_SERVICE_ACCOUNT_PATH', Config.FIREBASE_SERVICE_ACCOUNT_PATH),
        ]
        
        all_set = True
        for name, value in checks:
            if value:
                display_value = value[:30] + '...' if len(str(value)) > 30 else value
                print(f"   ✓ {name}: {display_value}")
            else:
                print(f"   ✗ {name}: Not set")
                all_set = False
        
        if not all_set and not firebase_enabled:
            print("\n   To configure Firebase:")
            print("   - Add values to your .env file")
            print("   - See FIREBASE_SETUP.md for step-by-step guide")
    
    except Exception as e:
        print(f"   ✗ Error checking config: {e}")
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    if firebase_enabled:
        print("\n✓ Firebase Authentication is ENABLED")
        print("\n  How it works:")
        print("  1. User clicks 'Sign in with Google'")
        print("  2. Firebase handles Google authentication (popup)")
        print("  3. User signs in with their Google account")
        print("  4. App receives user info (email, name, picture)")
        print("  5. Backend verifies token and creates session")
        print("\n  Test it:")
        print("  - Open http://127.0.0.1:5000")
        print("  - Click 'Sign in with Google'")
        print("  - You should see Firebase Google sign-in popup")
    else:
        print("\n⚠ Firebase Authentication is NOT configured")
        print("\n  Current behavior:")
        print("  - 'Sign in with Google' uses development shortcut")
        print("  - Shows a simple form to enter test email/name")
        print("  - Good for local development without Firebase setup")
        print("\n  To enable Firebase:")
        print("  - Follow guide: FIREBASE_SETUP.md")
        print("  - Takes about 10 minutes to set up")
        print("  - Much simpler than raw OAuth for production")
    
    print("\n" + "=" * 60)
    return firebase_enabled

if __name__ == "__main__":
    print("\nMake sure your Flask server is running first!")
    print("Start it with: python app.py\n")
    
    result = test_firebase_config()
    sys.exit(0 if result else 1)

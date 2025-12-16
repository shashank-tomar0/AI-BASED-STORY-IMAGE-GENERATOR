"""
Quick test script to verify Google OAuth endpoints are configured correctly.
This doesn't test the full OAuth flow (which requires Google credentials),
but verifies the endpoints exist and handle requests appropriately.
"""

import requests
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_oauth_endpoints():
    print("=" * 60)
    print("Google OAuth Configuration Test")
    print("=" * 60)
    
    # Test 1: Check if /api/auth/google endpoint exists
    print("\n1. Testing /api/auth/google endpoint...")
    try:
        resp = requests.get(f"{BASE_URL}/api/auth/google", allow_redirects=False, timeout=5)
        print(f"   Status: {resp.status_code}")
        
        if resp.status_code == 302:
            # Redirect to Google - OAuth is configured!
            location = resp.headers.get('Location', '')
            if 'accounts.google.com' in location:
                print("   ✓ OAuth IS CONFIGURED - Redirects to Google")
                print(f"   Redirect URL: {location[:80]}...")
                print("\n   This means:")
                print("   - GOOGLE_CLIENT_ID is set in your .env file")
                print("   - The OAuth flow will use real Google authentication")
                return True
            else:
                print(f"   Unexpected redirect to: {location}")
        elif resp.status_code == 200:
            # Dev shortcut is being used
            print("   ✓ OAuth NOT configured - Using dev shortcut")
            print("   Response content preview:", resp.text[:200])
            print("\n   This means:")
            print("   - GOOGLE_CLIENT_ID is NOT set (or empty) in your .env file")
            print("   - The app will use the development shortcut")
            print("\n   To enable real Google OAuth:")
            print("   1. Follow instructions in GOOGLE_OAUTH_SETUP.md")
            print("   2. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env")
            print("   3. Restart the server")
            return False
        else:
            print(f"   ✗ Unexpected status code: {resp.status_code}")
            print(f"   Response: {resp.text[:200]}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ✗ Error: {e}")
        print("   Make sure the Flask server is running on http://127.0.0.1:5000")
        return None
    
    print("\n" + "=" * 60)
    return None

def test_status_endpoint():
    """Test the general API status to ensure server is responding"""
    print("\n2. Testing /api/ai/status endpoint...")
    try:
        resp = requests.get(f"{BASE_URL}/api/ai/status", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✓ Server is responding")
            print(f"   LLM Provider: {data.get('llm_provider', 'unknown')}")
            print(f"   Image Provider: {data.get('image_provider', 'unknown')}")
            print(f"   Has Gemini Key: {data.get('has_gemini_key', False)}")
            return True
        else:
            print(f"   ✗ Unexpected status: {resp.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"   ✗ Error: {e}")
        return False

if __name__ == "__main__":
    print("\nStarting OAuth configuration tests...")
    print("Make sure your Flask server is running first!\n")
    
    # Test general server health
    if not test_status_endpoint():
        print("\n✗ Server is not responding. Start the server with: python app.py")
        sys.exit(1)
    
    # Test OAuth configuration
    oauth_configured = test_oauth_endpoints()
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    if oauth_configured is True:
        print("\n✓ Google OAuth is ENABLED and configured")
        print("  When users click 'Sign in with Google', they will:")
        print("  1. See the real Google sign-in page")
        print("  2. Authenticate with their Google account")
        print("  3. Return to your app signed in with their Google profile")
    elif oauth_configured is False:
        print("\n⚠ Google OAuth is NOT configured (using dev shortcut)")
        print("  When users click 'Sign in with Google', they will:")
        print("  1. See a dev email selection form")
        print("  2. Enter a test email and profile info")
        print("  3. Sign in with the test profile")
        print("\n  To enable real Google OAuth, see: GOOGLE_OAUTH_SETUP.md")
    else:
        print("\n✗ Could not determine OAuth configuration status")
        print("  Check the error messages above")
    
    print("\n" + "=" * 60)

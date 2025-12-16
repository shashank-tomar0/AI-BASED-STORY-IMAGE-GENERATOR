#!/usr/bin/env python
"""
Diagnostic script to test LLM narrative generation and image generation.
Run this to identify which part of the pipeline is failing.
"""
import json
import requests
import sys

BASE_URL = "http://127.0.0.1:5000"

# Sample auth token for testing (you need to be logged in)
# Replace with your actual token from localStorage['authToken']
TEST_TOKEN = None  # Will prompt user

def get_test_token():
    """Prompt user for auth token"""
    global TEST_TOKEN
    if not TEST_TOKEN:
        print("\n=== Need Authentication Token ===")
        print("1. Open your browser to http://127.0.0.1:5000")
        print("2. Sign in (Google or local auth)")
        print("3. Open DevTools (F12) → Console")
        print("4. Run: localStorage.getItem('authToken')")
        print("5. Copy the token and paste it here:")
        TEST_TOKEN = input("Auth Token: ").strip()
    return TEST_TOKEN

def test_llm_generation():
    """Test the LLM narrative generation endpoint"""
    print("\n=== Testing LLM Narrative Generation ===")
    token = get_test_token()
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "Write a short story about a robot learning to dance. Keep it to 2-3 sentences."
                    }
                ]
            }
        ],
        "systemInstruction": {
            "parts": [
                {
                    "text": "You are a creative narrative generator. Return a valid JSON with 'narrative', 'image_prompt', and 'summary_point' fields."
                }
            ]
        },
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "narrative": {"type": "STRING"},
                    "image_prompt": {"type": "STRING"},
                    "summary_point": {"type": "STRING"}
                }
            }
        }
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/ai/generate-prompt",
            json={"payload": payload},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=60
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"\nResponse Body:\n{json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('normalized_candidate'):
                print("\n✓ LLM working! Got normalized_candidate")
                print(f"  Narrative: {data['normalized_candidate'].get('narrative', 'N/A')[:100]}...")
                print(f"  Image Prompt: {data['normalized_candidate'].get('image_prompt', 'N/A')[:100]}...")
            elif data.get('candidates'):
                print("\n⚠ Got candidates but no normalized_candidate")
            else:
                print("\n✗ Unexpected response structure")
        else:
            print(f"\n✗ LLM request failed with status {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error: {e}")

def test_image_generation():
    """Test the image generation endpoint"""
    print("\n\n=== Testing Image Generation ===")
    token = get_test_token()
    
    prompt = "A serene forest clearing with soft golden sunlight filtering through tall trees, magical atmosphere, 16:9 cinematic"
    
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "16:9"
        }
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/ai/generate-image",
            json={"payload": payload},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=120
        )
        
        print(f"Status Code: {response.status_code}")
        
        data = response.json()
        print(f"\nResponse keys: {list(data.keys())}")
        
        if response.status_code == 200:
            if data.get('predictions') and len(data['predictions']) > 0:
                pred = data['predictions'][0]
                b64 = pred.get('bytesBase64Encoded', '')
                print(f"\n✓ Image generated successfully!")
                print(f"  Predictions count: {len(data['predictions'])}")
                print(f"  Image size: {len(b64)} bytes of base64 data")
                print(f"  Cached: {data.get('cached', False)}")
            else:
                print(f"\n✗ No predictions in response")
                print(f"Full response: {json.dumps(data, indent=2)[:500]}")
        else:
            print(f"\n✗ Image request failed with status {response.status_code}")
            print(f"Error: {data.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"✗ Error: {e}")

def test_status():
    """Check backend status and configuration"""
    print("\n=== Backend Status ===")
    try:
        response = requests.get(f"{BASE_URL}/api/ai/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Backend is running")
            print(f"  LLM Provider: {data.get('llm_provider')}")
            print(f"  Has Gemini Key: {data.get('has_gemini_key')}")
            print(f"  Image Provider: {data.get('image_provider')}")
            print(f"  Has Stability Key: {data.get('has_stability_key')}")
        else:
            print(f"✗ Status check failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Backend unreachable: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("Story Generator - LLM & Image Generation Diagnostic")
    print("=" * 60)
    
    test_status()
    test_llm_generation()
    test_image_generation()
    
    print("\n" + "=" * 60)
    print("Diagnostic complete!")
    print("=" * 60)

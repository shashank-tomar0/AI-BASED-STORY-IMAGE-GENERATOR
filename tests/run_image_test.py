import requests
import json

BASE = 'http://127.0.0.1:5000'

def register_and_login(username, password):
    reg = requests.post(f"{BASE}/api/auth/register", json={"username":username, "password":password})
    # ignore reg errors if user already exists
    login = requests.post(f"{BASE}/api/auth/login", json={"username":username, "password":password})
    if login.status_code != 200:
        print('Login failed', login.status_code, login.text)
        return None
    data = login.json()
    return data.get('token')

def generate_image(token, prompt):
    url = f"{BASE}/api/ai/generate-image"
    payload = {'payload': {'instances': [{'prompt': prompt}], 'parameters': {'sampleCount': 1, 'aspectRatio': '16:9'}}}
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.post(url, json=payload, headers=headers, timeout=60)
    print('STATUS:', r.status_code)
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)


if __name__ == '__main__':
    token = register_and_login('testuser', 'testpass')
    if not token:
        print('Could not obtain token; exiting')
    else:
        generate_image(token, 'elon musk')

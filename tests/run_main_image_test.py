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


def generate_main_image(token, prompt):
    url = f"{BASE}/api/ai/generate-main-image"
    payload = {'payload': {'instances': [{'prompt': prompt}]}}
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.post(url, json=payload, headers=headers, timeout=60)
    print('STATUS:', r.status_code)
    try:
        js = r.json()
        print('RESPONSE KEYS:', list(js.keys()))
        if 'predictions' in js and isinstance(js['predictions'], list) and len(js['predictions'])>0:
            b64 = js['predictions'][0].get('bytesBase64Encoded')
            if b64:
                print('Image base64 length:', len(b64))
            else:
                print('No bytesBase64Encoded field in predictions[0]')
        else:
            print(json.dumps(js, indent=2))
    except Exception:
        print(r.text)


if __name__ == '__main__':
    token = register_and_login('mainimguser', 'testpass')
    if not token:
        print('Could not obtain token; exiting')
    else:
        generate_main_image(token, 'a fantasy castle on a hill')

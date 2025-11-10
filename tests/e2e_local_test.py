import requests, json, base64
BASE='http://127.0.0.1:5000'
USERNAME='e2e_user'
PASSWORD='e2e_pass'

# Register (ignore errors if user exists)
try:
    r = requests.post(f"{BASE}/api/auth/register", json={'username': USERNAME, 'password': PASSWORD}, timeout=10)
    print('register status', r.status_code, r.text)
except Exception as e:
    print('register error', e)

# Login
r = requests.post(f"{BASE}/api/auth/login", json={'username': USERNAME, 'password': PASSWORD}, timeout=10)
print('login status', r.status_code, r.text)
if r.status_code != 200:
    raise SystemExit('login failed')

token = r.json().get('token')
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# Generate prompt
payload = {
    'payload': {
        'contents': [{'parts': [{'text': 'Idea: A lighthouse on an alien shore at dusk'}]}],
        'systemInstruction': {'parts': [{'text':'Return JSON with narrative, image_prompt, summary_point'}]}
    }
}
print('calling generate-prompt...')
r = requests.post(f"{BASE}/api/ai/generate-prompt", headers=headers, json=payload, timeout=90)
print('generate-prompt status', r.status_code)
print(r.text[:1000])
if r.status_code != 200:
    raise SystemExit('generate-prompt failed')

# extract prompt
try:
    resp = r.json()
    txt = resp['candidates'][0]['content']['parts'][0]['text']
    obj = json.loads(txt)
    image_prompt = obj.get('image_prompt')
    print('image_prompt:', image_prompt)
except Exception as e:
    print('parse error', e)
    raise

# Generate image using the image_prompt
img_payload = {'payload': {'instances':[{'prompt': image_prompt}]}}
r = requests.post(f"{BASE}/api/ai/generate-image", headers=headers, json=img_payload, timeout=90)
print('generate-image status', r.status_code)
try:
    j = r.json()
    b64 = j.get('predictions', [])[0].get('bytesBase64Encoded')
    print('image base64 len', len(b64) if b64 else 'none')
    # save to file
    if b64:
        with open('tests/e2e_output.png','wb') as f:
            f.write(base64.b64decode(b64))
        print('saved tests/e2e_output.png')
except Exception as e:
    print('image parse error', e)
    print(r.text)

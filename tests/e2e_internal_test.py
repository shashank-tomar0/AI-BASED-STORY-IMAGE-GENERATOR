import json, base64, sys, os
# Ensure workspace root is on sys.path so imports like 'app' resolve when running tests directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app

app = create_app()
client = app.test_client()

USERNAME='internal_user'
PASSWORD='internal_pass'

# Register
r = client.post('/api/auth/register', json={'username': USERNAME, 'password': PASSWORD})
print('register status', r.status_code, r.get_data(as_text=True))

# Login
r = client.post('/api/auth/login', json={'username': USERNAME, 'password': PASSWORD})
print('login status', r.status_code, r.get_data(as_text=True))
if r.status_code != 200:
    raise SystemExit('login failed')

token = r.get_json().get('token')
headers = {'Authorization': f'Bearer {token}'}

# Generate prompt
payload = {
    'payload': {
        'contents': [{'parts': [{'text': 'Idea: A lighthouse on an alien shore at dusk'}]}],
        'systemInstruction': {'parts': [{'text':'Return JSON with narrative, image_prompt, summary_point'}]}
    }
}
print('calling generate-prompt...')
r = client.post('/api/ai/generate-prompt', headers=headers, json=payload)
print('generate-prompt status', r.status_code)
print(r.get_data(as_text=True)[:1000])
if r.status_code != 200:
    raise SystemExit('generate-prompt failed')

# extract prompt
resp = r.get_json()
txt = resp['candidates'][0]['content']['parts'][0]['text']
obj = json.loads(txt)
image_prompt = obj.get('image_prompt')
print('image_prompt:', image_prompt)

# Generate image
img_payload = {'payload': {'instances':[{'prompt': image_prompt}]}}
r = client.post('/api/ai/generate-image', headers=headers, json=img_payload)
print('generate-image status', r.status_code)
try:
    j = r.get_json()
    b64 = j.get('predictions', [])[0].get('bytesBase64Encoded')
    print('image base64 len', len(b64) if b64 else 'none')
    if b64:
        with open('tests/e2e_internal_output.png','wb') as f:
            f.write(base64.b64decode(b64))
        print('saved tests/e2e_internal_output.png')
except Exception as e:
    print('image parse error', e)
    print(r.get_data(as_text=True))

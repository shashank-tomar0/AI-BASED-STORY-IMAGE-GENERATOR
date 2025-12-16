import requests
import time
import json

API_BASE = 'http://127.0.0.1:5000/api'

s = requests.Session()

username = 'async_tester'
password = 'testpass'

print('Registering user...')
try:
    r = s.post(f'{API_BASE}/auth/register', json={'username': username, 'password': password}, timeout=10)
    print('Register:', r.status_code, r.text)
except Exception as e:
    print('Register request failed:', e)

print('Logging in...')
r = s.post(f'{API_BASE}/auth/login', json={'username': username, 'password': password}, timeout=10)
if r.status_code != 200:
    print('Login failed:', r.status_code, r.text)
    # try to login with admin if exists
    r = s.post(f'{API_BASE}/auth/login', json={'username': 'admin', 'password': 'pass'}, timeout=10)
    print('Fallback login:', r.status_code, r.text)
    if r.status_code != 200:
        raise SystemExit('Unable to obtain a token for testing')

token = r.json().get('token')
print('Token obtained:', bool(token))
headers = {'Authorization': f'Bearer {token}'}

# Generate prompt
prompt_text = 'A wandering cat on a foggy pier'
payload = { 'payload': { 'contents': [ { 'parts': [ { 'text': prompt_text } ] } ] } }
print('Calling generate-prompt...')
r = s.post(f'{API_BASE}/ai/generate-prompt', json=payload, headers=headers, timeout=20)
print('generate-prompt:', r.status_code)
try:
    jp = r.json()
    print('Normalized candidate keys:', list(jp.get('normalized_candidate', {}).keys()))
    normalized = jp.get('normalized_candidate')
    image_prompt = normalized.get('image_prompt') if normalized else None
except Exception as e:
    print('Failed parse generate-prompt:', e)
    raise

if not image_prompt:
    image_prompt = prompt_text + ' -- photorealistic cinematic'

# Request preview
print('Requesting preview...')
preview_payload = { 'payload': { 'instances': [ { 'prompt': image_prompt } ] } }
r = s.post(f'{API_BASE}/ai/generate-preview', json=preview_payload, headers=headers, timeout=20)
print('preview status:', r.status_code)
try:
    pj = r.json()
    print('preview keys:', pj.keys())
    b64 = pj.get('predictions', [])[0].get('bytesBase64Encoded')
    print('preview length b64:', len(b64) if b64 else 'none')
except Exception as e:
    print('preview parse error', e)

# Enqueue async image generation
print('Enqueue async image generation...')
ai_payload = { 'payload': { 'instances': [ { 'prompt': image_prompt } ], 'parameters': { 'sampleCount': 2 } } }
r = s.post(f'{API_BASE}/ai/generate-image-async', json=ai_payload, headers=headers, timeout=10)
print('enqueue status:', r.status_code, r.text)
if r.status_code != 202:
    print('Failed to enqueue async job, attempting synchronous call as fallback')
    r2 = s.post(f'{API_BASE}/ai/generate-image', json=ai_payload, headers=headers, timeout=60)
    print('sync generate status:', r2.status_code)
    print(r2.text)
    raise SystemExit('Sync fallback executed')

job_id = r.json().get('job_id')
print('Job id:', job_id)

# Poll job
print('Polling job...')
start = time.time()
while time.time() - start < 90:
    rj = s.get(f'{API_BASE}/ai/generate-image-job/{job_id}', headers=headers, timeout=10)
    if rj.status_code == 200:
        jj = rj.json()
        print('Job status:', jj.get('status'))
        if jj.get('status') == 'done':
            print('Job result:', jj.get('result'))
            break
        if jj.get('status') == 'error':
            print('Job error:', jj.get('result'))
            break
    else:
        print('Job poll status code:', rj.status_code, rj.text)
    time.sleep(2)

else:
    print('Job polling timed out')

print('Smoke async test complete')

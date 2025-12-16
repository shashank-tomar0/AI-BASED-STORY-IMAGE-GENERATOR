import sys, os
sys.path.append(os.getcwd())
from app import create_app
import json
import time

app = create_app()
with app.test_client() as client:
    print('Registering test user via test_client...')
    r = client.post('/api/auth/register', json={'username':'tc_async','password':'pw12345'})
    print('register', r.status_code, r.get_data(as_text=True))
    r = client.post('/api/auth/login', json={'username':'tc_async','password':'pw12345'})
    if r.status_code != 200:
        print('login failed', r.status_code, r.get_data(as_text=True))
        r = client.post('/api/auth/login', json={'username':'admin','password':'pass'})
        print('admin login fallback', r.status_code, r.get_data(as_text=True))
    token = r.get_json().get('token')
    headers = {'Authorization': f'Bearer {token}'}

    print('\nCalling generate-prompt...')
    payload = {'payload': {'contents': [ {'parts': [ {'text': 'A lighthouse keeper and a cat at dusk'} ] } ] } }
    rg = client.post('/api/ai/generate-prompt', json=payload, headers=headers)
    print('generate-prompt status', rg.status_code)
    print('body:', rg.get_data(as_text=True)[:500])
    norm = rg.get_json().get('normalized_candidate')
    image_prompt = (norm or {}).get('image_prompt') or 'a cat on a pier'

    print('\nCalling generate-preview...')
    rp = client.post('/api/ai/generate-preview', json={'payload': {'instances':[{'prompt': image_prompt}] } }, headers=headers)
    print('preview status', rp.status_code)
    if rp.status_code == 200:
        pj = rp.get_json()
        print('preview keys', pj.keys())

    print('\nEnqueue async job...')
    ra = client.post('/api/ai/generate-image-async', json={'payload': {'instances':[{'prompt': image_prompt}], 'parameters': {'sampleCount':2}}}, headers=headers)
    print('enqueue status', ra.status_code, ra.get_data(as_text=True))
    if ra.status_code != 202:
        print('Async enqueue not available; calling generate-image directly...')
        rg2 = client.post('/api/ai/generate-image', json={'payload': {'instances':[{'prompt': image_prompt}], 'parameters': {'sampleCount':2}}}, headers=headers)
        print('generate-image status', rg2.status_code)
        print(rg2.get_data(as_text=True)[:500])
    else:
        job_id = ra.get_json().get('job_id')
        print('job id', job_id)
        # Poll job status via test client
        start = time.time()
        while time.time() - start < 10:
            rj = client.get(f'/api/ai/generate-image-job/{job_id}', headers=headers)
            print('poll', rj.status_code, rj.get_data(as_text=True))
            if rj.status_code == 200 and rj.get_json().get('status') == 'done':
                print('job done:', rj.get_json())
                break
            time.sleep(1)
        else:
            print('job polling timed out')

    print('\nTest complete')

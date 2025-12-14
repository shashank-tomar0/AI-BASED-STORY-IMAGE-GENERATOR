import os
import json
import shutil
import sys
# Ensure project root is on sys.path so imports like `from app import create_app` work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
import ai_service


def main():
    app = create_app()
    client = app.test_client()

    # register and login to obtain token
    client.post('/api/auth/register', json={'username': 'testuser', 'password': 'pass'})
    login = client.post('/api/auth/login', json={'username': 'testuser', 'password': 'pass'})
    if login.status_code != 200:
        print('LOGIN_FAILED', login.status_code, login.get_data(as_text=True))
        return 2
    token = login.get_json().get('token')
    if not token:
        print('NO_TOKEN')
        return 2

    uploads_dir = os.path.join(app.static_folder, 'uploads')
    if os.path.exists(uploads_dir):
        shutil.rmtree(uploads_dir)
    os.makedirs(uploads_dir, exist_ok=True)

    # prepare a fake cached image and metadata
    prompt = 'unit test prompt for cache'
    provider = 'free'
    params = {'sampleCount': 1}
    key = ai_service._make_image_cache_key(prompt, provider, params)

    # create fake image file
    b = b'fakepngdata'
    fname = f'img_{key}_0.png'
    path = os.path.join(uploads_dir, fname)
    with open(path, 'wb') as f:
        f.write(b)

    # create metadata json
    meta = {'key': key, 'files': [fname], 'prompt': prompt, 'ts': int(__import__('time').time())}
    meta_path = os.path.join(uploads_dir, f'cache_{key}.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f)

    # ensure files exist
    if not os.path.exists(path) or not os.path.exists(meta_path):
        print('SETUP_FAILED')
        return 2

    # call invalidate endpoint
    headers = {'Authorization': f'Bearer {token}'}
    resp = client.post('/api/ai/cache/invalidate', json={'key': key}, headers=headers)
    if resp.status_code != 200:
        print('INVALIDATE_FAILED', resp.status_code, resp.get_data(as_text=True))
        return 2
    j = resp.get_json()
    if not j.get('success'):
        print('INVALIDATE_RESPONSE_ERROR', j)
        return 2

    # verify files removed
    if os.path.exists(path) or os.path.exists(meta_path):
        print('FILES_NOT_REMOVED')
        return 2

    print('OK')
    return 0

if __name__ == '__main__':
    sys.exit(main())

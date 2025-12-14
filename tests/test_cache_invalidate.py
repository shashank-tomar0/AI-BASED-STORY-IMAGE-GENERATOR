import os
import json
import base64
import shutil
from app import create_app
import ai_service


def test_cache_invalidate_by_key(tmp_path):
    app = create_app()
    client = app.test_client()

    # register and login to obtain token
    client.post('/api/auth/register', json={'username': 'testuser', 'password': 'pass'})
    login = client.post('/api/auth/login', json={'username': 'testuser', 'password': 'pass'})
    assert login.status_code == 200
    token = login.get_json().get('token')
    assert token

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
    assert os.path.exists(path)
    assert os.path.exists(meta_path)

    # call invalidate endpoint
    headers = {'Authorization': f'Bearer {token}'}
    resp = client.post('/api/ai/cache/invalidate', json={'key': key}, headers=headers)
    assert resp.status_code == 200
    j = resp.get_json()
    assert j.get('success') is True
    # removed should at least include the meta file
    assert any(n.startswith('cache_') for n in j.get('removed', []))

    # verify files removed
    assert not os.path.exists(path)
    assert not os.path.exists(meta_path)

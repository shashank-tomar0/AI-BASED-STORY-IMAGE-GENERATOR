import os
import sys
import json
# ensure project root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app


def main():
    app = create_app()
    client = app.test_client()

    # register/login
    client.post('/api/auth/register', json={'username':'tester','password':'p'})
    login = client.post('/api/auth/login', json={'username':'tester','password':'p'})
    if login.status_code != 200:
        print('LOGIN_FAIL', login.status_code)
        return 2
    token = login.get_json().get('token')
    headers = {'Authorization': f'Bearer {token}'}

    # ensure uploads dir exists
    uploads = os.path.join(app.static_folder, 'uploads')
    os.makedirs(uploads, exist_ok=True)

    # call cache list
    resp = client.get('/api/ai/cache/list', headers=headers)
    print('STATUS', resp.status_code)
    print(resp.get_data(as_text=True))
    return 0

if __name__ == '__main__':
    sys.exit(main())

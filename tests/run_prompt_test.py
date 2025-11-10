import requests, json
BASE='http://127.0.0.1:5000'

def login(username, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"username":username, "password":password})
    print('login', r.status_code)
    return r.json().get('token')

if __name__=='__main__':
    token = login('testuser','testpass')
    headers={'Authorization':f'Bearer {token}'}
    ai_payload = {
        'payload':{
            'contents':[{'role':'user','parts':[{'text':'Start a new story about: elon musk'}]}],
            'systemInstruction':{'parts':[{'text':'Return a single valid JSON object with narrative, image_prompt, summary_point.'}]},
            'generationConfig':{'responseMimeType':'application/json'}
        }
    }
    r = requests.post(f"{BASE}/api/ai/generate-prompt", json=ai_payload, headers=headers, timeout=30)
    print('STATUS', r.status_code)
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)

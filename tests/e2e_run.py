import requests, json, sys
BASE='http://127.0.0.1:5000'

s = requests.Session()
# Register (ignore errors if exists)
try:
    r = s.post(BASE+'/auth/register', json={'username':'e2euser','password':'e2epass'}, timeout=10)
    print('register', r.status_code, r.text[:200])
except Exception as e:
    print('register error', e)

# Login
r = s.post(BASE+'/auth/login', json={'username':'e2euser','password':'e2epass'}, timeout=10)
print('login', r.status_code, r.text[:200])
if r.status_code!=200:
    print('login failed, stopping')
    sys.exit(1)
js=r.json()
token=js.get('token')
headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'}

# generate-prompt
payload = {
    'payload':{
        'contents':[{'parts':[{'text':'A lonely lighthouse on an alien shore at dusk'}]}],
        'systemInstruction':{'parts':[{'text':'Return JSON with narrative,image_prompt,summary_point'}]}
    }
}
try:
    r = s.post(BASE+'/api/ai/generate-prompt', json=payload, headers=headers, timeout=120)
    print('generate-prompt', r.status_code)
    print(r.text[:1000])
    if r.status_code!=200:
        sys.exit(1)
    resp = r.json()
    jsstr = resp.get('candidates',[{}])[0].get('content',{}).get('parts',[{}])[0].get('text')
    parsed = json.loads(jsstr)
    prompt = parsed.get('image_prompt')
    print('parsed prompt:', prompt)
except Exception as e:
    print('generate-prompt failed', e)
    sys.exit(1)

# generate-image
img_payload={'payload':{'instances':[{'prompt':prompt}]}}
try:
    r = s.post(BASE+'/api/ai/generate-image', json=img_payload, headers=headers, timeout=120)
    print('generate-image', r.status_code)
    tx = r.text
    print(tx[:200])
    if r.status_code==200:
        j=r.json()
        b64 = j.get('predictions',[{}])[0].get('bytesBase64Encoded')
        if b64:
            print('image len', len(b64))
        else:
            print('no b64 in response')
    else:
        print('image call failed:', tx)
except Exception as e:
    print('generate-image failed', e)
    sys.exit(1)

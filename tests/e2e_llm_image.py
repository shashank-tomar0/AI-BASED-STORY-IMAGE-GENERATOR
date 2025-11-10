import requests, json
BASE='http://127.0.0.1:5000'


def login(username, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"username":username, "password":password})
    if r.status_code != 200:
        print('Login failed', r.status_code, r.text)
        return None
    return r.json().get('token')


def generate_prompt(token, idea, art_style='photorealistic cinematic'):
    headers={'Authorization':f'Bearer {token}'}
    systemPrompt = f"You are a creative narrative generator. Return a single valid JSON object with keys: narrative, image_prompt, summary_point. Style: {art_style}."
    contents = [{
        'role': 'user',
        'parts': [{'text': f'Start a new story about: {idea}'}]
    }]
    payload = {
        'payload': {
            'contents': contents,
            'systemInstruction': {'parts': [{'text': systemPrompt}]},
            'generationConfig': {'responseMimeType': 'application/json'}
        }
    }
    r = requests.post(f"{BASE}/api/ai/generate-prompt", json=payload, headers=headers, timeout=60)
    print('generate-prompt status', r.status_code)
    if r.status_code != 200:
        print(r.text)
        return None
    body = r.json()
    try:
        jsonString = body['candidates'][0]['content']['parts'][0]['text']
        data = json.loads(jsonString)
        return data
    except Exception as e:
        print('Failed to parse LLM response:', e)
        print(body)
        return None


def generate_image(token, prompt, art_style='photorealistic cinematic'):
    headers={'Authorization':f'Bearer {token}'}
    payload = {'payload': {'instances': [{'prompt': f"{prompt}, in the style of {art_style}"}], 'parameters': {'sampleCount': 1, 'aspectRatio': '16:9'}}}
    r = requests.post(f"{BASE}/api/ai/generate-image", json=payload, headers=headers, timeout=120)
    print('generate-image status', r.status_code)
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)
    return r


if __name__ == '__main__':
    token = login('testuser','testpass')
    if not token:
        print('login failed')
    else:
        idea = 'elon musk'
        print('Using idea:', idea)
        res = generate_prompt(token, idea)
        if res:
            print('\nNarrative:\n', res.get('narrative'))
            print('\nImage Prompt:\n', res.get('image_prompt'))
            print('\nSummary:\n', res.get('summary_point'))

            print('\nNow generating image from the LLM prompt...')
            gen = generate_image(token, res.get('image_prompt'))
            # check base64
            try:
                b64 = gen.json()['predictions'][0]['bytesBase64Encoded']
                print('\nReceived base64 image length:', len(b64))
            except Exception as e:
                print('No image data returned', e)

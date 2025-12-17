# ai_service.py

import requests
import json
import base64
import hashlib
import time
import os
import threading
from flask import Blueprint, request, jsonify, current_app
from auth import token_required
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Create a Blueprint for AI routes
ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')

# Create a session with connection pooling and retry strategy for faster API calls
def _create_requests_session():
    """Create a requests session with connection pooling and retries."""
    session = requests.Session()
    retry_strategy = Retry(
        total=0,  # Don't retry at session level, we handle retries manually
        backoff_factor=0,
        status_forcelist=[]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

_session = None

def _get_session():
    """Get or create the global requests session."""
    global _session
    if _session is None:
        _session = _create_requests_session()
    return _session

# Simple in-memory job store for dev async image generation
JOBS = {}  # job_id -> { status: 'pending'|'done'|'error', result: {...} }


def _save_image_b64(b64, prompt_text=None):
    """Save base64 image bytes to static/uploads and return a relative URL.
    Returns None on failure or the relative url like '/static/uploads/abc.png'.
    """
    try:
        if not b64:
            return None
        uploads_dir = os.path.join(current_app.static_folder, 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        # Use a stable filename derived from the prompt when available
        seed = hashlib.sha1((prompt_text or '').encode('utf-8')).hexdigest()[:12]
        filename = f"img_{seed}.png"
        path = os.path.join(uploads_dir, filename)
        img_bytes = base64.b64decode(b64)
        with open(path, 'wb') as f:
            f.write(img_bytes)
        return f"/static/uploads/{filename}"
    except Exception:
        # If saving fails, don't block the response — just return None
        return None


def _picsum_base64_from_prompt(prompt_text: str, width: int = 800, height: int = 450, timeout: int = 20):
    """Return a deterministic Picsum image as base64 for a prompt.
    Uses a short SHA1 seed so the same prompt yields the same image.
    Returns None on failure.
    """
    try:
        seed = hashlib.sha1((prompt_text or 'seed').encode('utf-8')).hexdigest()[:8]
        url = f'https://picsum.photos/seed/{seed}/{width}/{height}'
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            return base64.b64encode(resp.content).decode('utf-8')
    except Exception:
        return None
    return None


def _extract_prompt_from_payload(payload):
    prompt_text = ''
    try:
        if isinstance(payload, dict):
            inst = payload.get('instances') or payload.get('inputs') or payload.get('prompt') or payload.get('inputs')
            if inst and isinstance(inst, list) and len(inst) > 0:
                first = inst[0]
                if isinstance(first, dict):
                    prompt_text = first.get('prompt') or first.get('text') or ''
                else:
                    prompt_text = str(first)
            elif isinstance(inst, dict):
                prompt_text = inst.get('prompt') or inst.get('text') or ''
            elif isinstance(inst, str):
                prompt_text = inst
            else:
                # fallback: try top-level prompt
                prompt_text = str(payload.get('prompt') or payload)
    except Exception:
        prompt_text = str(payload)
    return (prompt_text or '').strip()


def _make_image_cache_key(prompt_text, provider, params=None):
    if params is None:
        params = {}
    try:
        norm = f"prompt:{prompt_text}|provider:{provider}|params:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha1(norm.encode('utf-8')).hexdigest()[:16]
    except Exception:
        return hashlib.sha1((prompt_text + provider).encode('utf-8')).hexdigest()[:16]


def _persist_image_cache(key, base64_list, prompt_text):
    """Persist images and a metadata JSON for a given cache key."""
    try:
        uploads_dir = os.path.join(current_app.static_folder, 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        meta = {'key': key, 'files': [], 'prompt': prompt_text, 'ts': int(time.time())}
        for idx, b64 in enumerate(base64_list):
            filename = f"img_{key}_{idx}.png"
            path = os.path.join(uploads_dir, filename)
            with open(path, 'wb') as f:
                f.write(base64.b64decode(b64))
            meta['files'].append(filename)

        meta_path = os.path.join(uploads_dir, f'cache_{key}.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f)
        return True
    except Exception:
        return False


def _load_image_cache(key, ttl_seconds=86400):
    """Return a list of base64 strings if cache exists and is valid; otherwise None."""
    try:
        uploads_dir = os.path.join(current_app.static_folder, 'uploads')
        meta_path = os.path.join(uploads_dir, f'cache_{key}.json')
        if not os.path.exists(meta_path):
            return None
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        ts = meta.get('ts', 0)
        if ttl_seconds and (int(time.time()) - ts) > ttl_seconds:
            # expired
            return None
        files = meta.get('files', [])
        base64_list = []
        for fname in files:
            path = os.path.join(uploads_dir, fname)
            if not os.path.exists(path):
                return None
            with open(path, 'rb') as f:
                b = f.read()
                base64_list.append(base64.b64encode(b).decode('utf-8'))
        return base64_list
    except Exception:
        return None


def _synthesize_narrative(prompt_text, paragraphs=3):
    """Create a deterministic, multi-paragraph narrative from the prompt_text.
    This is a lightweight local fallback used when a real LLM is not
    available. It is deterministic (based on the prompt) so tests remain
    reproducible.
    """
    try:
        if not prompt_text:
            prompt_text = 'A quiet village at dusk.'
        # Use a hash of the prompt to pick deterministic words
        h = hashlib.sha1(prompt_text.encode('utf-8')).hexdigest()
        # small selection pools
        moods = ['gently', 'ominously', 'brightly', 'softly', 'curiously']
        settings = ['a coastal town', 'an overgrown forest', 'a bustling market', 'an abandoned manor', 'a hidden valley']
        characters = ['an old storyteller', 'a curious child', 'a weary traveler', 'a lonely artist', 'a clever fox']
        events = ['finds an unexpected map', 'uncovers a faded photograph', 'hears a distant melody', 'chases a flicker of light', 'stumbles on a secret door']

        def pick(pool, idx):
            return pool[int(h[idx:idx+6], 16) % len(pool)]

        mood = pick(moods, 0)
        setting = pick(settings, 6)
        character = pick(characters, 12)
        event = pick(events, 18)

        paras = []
        intro = f"{prompt_text.strip()}"
        paras.append(f"{intro} {character.capitalize()} {mood} notices the surroundings of {setting} and {event}.")

        for i in range(1, paragraphs):
            act = pick(events, 18 + i * 6)
            detail = pick(settings, 24 + i * 6)
            paras.append(f"{character.capitalize()} {act} near {detail}. Small, vivid moments unfurl: light, memory, and a choice to be made.")

        # Closing sentence
        paras.append("In time, the scene settles into a new quiet — one shaped by the small acts that came before.")

        return "\n\n".join(paras)
    except Exception:
        return prompt_text


def _extract_user_prompt(payload):
    """Extract the user's prompt text from Gemini-style payload."""
    try:
        contents = payload.get('contents', [])
        if contents and isinstance(contents, list):
            for content in contents:
                if isinstance(content, dict):
                    parts = content.get('parts', [])
                    if parts and isinstance(parts, list):
                        for part in parts:
                            if isinstance(part, dict) and 'text' in part:
                                return part['text']
        return "Continue the story"
    except:
        return "Continue the story"


def _call_groq_llm(payload):
    """Call Groq API for fast, free LLM inference."""
    try:
        from flask import current_app, jsonify
        
        GROQ_API_KEY = current_app.config.get('GROQ_API_KEY')
        if not GROQ_API_KEY:
            return jsonify({'error': 'GROQ_API_KEY not configured'}), 500
        
        # Extract prompt from Gemini-style payload
        user_prompt = _extract_user_prompt(payload)
        system_instruction = payload.get('systemInstruction', {}).get('parts', [{}])[0].get('text', '')
        
        # Groq API (OpenAI-compatible)
        groq_payload = {
            "model": "llama-3.3-70b-versatile",  # Fast, free model
            "messages": [
                {"role": "system", "content": system_instruction or "You are a creative storyteller."},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.8,
            "response_format": {"type": "json_object"}
        }
        
        print(f"[GROQ] Calling Groq API...")
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json=groq_payload,
            timeout=15
        )
        response.raise_for_status()
        
        data = response.json()
        content = data['choices'][0]['message']['content']
        narrative_data = json.loads(content)
        
        # Convert to Gemini-style response
        normalized = {
            'narrative': narrative_data.get('narrative', ''),
            'image_prompt': narrative_data.get('image_prompt', ''),
            'summary_point': narrative_data.get('summary_point', '')
        }
        
        return jsonify({
            'candidates': [{'content': {'parts': [{'text': json.dumps(normalized)}]}}],
            'normalized_candidate': normalized,
            'used_real_llm': True
        }), 200
        
    except Exception as e:
        print(f"[GROQ ERROR] {str(e)}")
        return jsonify({'error': f'Groq API error: {str(e)}'}), 500


def _call_openai_llm(payload):
    """Call OpenAI API (GPT models)."""
    try:
        from flask import current_app, jsonify
        
        OPENAI_API_KEY = current_app.config.get('OPENAI_API_KEY')
        if not OPENAI_API_KEY:
            return jsonify({'error': 'OPENAI_API_KEY not configured'}), 500
        
        user_prompt = _extract_user_prompt(payload)
        system_instruction = payload.get('systemInstruction', {}).get('parts', [{}])[0].get('text', '')
        
        openai_payload = {
            "model": "gpt-3.5-turbo",  # or "gpt-4" if you have access
            "messages": [
                {"role": "system", "content": system_instruction or "You are a creative storyteller."},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.8,
            "response_format": {"type": "json_object"}
        }
        
        print(f"[OPENAI] Calling OpenAI API...")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json=openai_payload,
            timeout=20
        )
        response.raise_for_status()
        
        data = response.json()
        content = data['choices'][0]['message']['content']
        narrative_data = json.loads(content)
        
        normalized = {
            'narrative': narrative_data.get('narrative', ''),
            'image_prompt': narrative_data.get('image_prompt', ''),
            'summary_point': narrative_data.get('summary_point', '')
        }
        
        return jsonify({
            'candidates': [{'content': {'parts': [{'text': json.dumps(normalized)}]}}],
            'normalized_candidate': normalized,
            'used_real_llm': True
        }), 200
        
    except Exception as e:
        print(f"[OPENAI ERROR] {str(e)}")
        return jsonify({'error': f'OpenAI API error: {str(e)}'}), 500


def _call_anthropic_llm(payload):
    """Call Anthropic Claude API."""
    try:
        from flask import current_app, jsonify
        
        ANTHROPIC_API_KEY = current_app.config.get('ANTHROPIC_API_KEY')
        if not ANTHROPIC_API_KEY:
            return jsonify({'error': 'ANTHROPIC_API_KEY not configured'}), 500
        
        user_prompt = _extract_user_prompt(payload)
        system_instruction = payload.get('systemInstruction', {}).get('parts', [{}])[0].get('text', '')
        
        # Add JSON format instruction to the prompt
        enhanced_prompt = f"{user_prompt}\n\nRespond with ONLY a JSON object with these fields: narrative, image_prompt, summary_point"
        
        anthropic_payload = {
            "model": "claude-3-haiku-20240307",  # Fast, cheap model
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": enhanced_prompt}
            ],
            "system": system_instruction or "You are a creative storyteller."
        }
        
        print(f"[ANTHROPIC] Calling Anthropic API...")
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json=anthropic_payload,
            timeout=20
        )
        response.raise_for_status()
        
        data = response.json()
        content = data['content'][0]['text']
        
        # Try to parse JSON from response
        try:
            narrative_data = json.loads(content)
        except:
            # If not JSON, extract from text
            narrative_data = {'narrative': content, 'image_prompt': content[:200], 'summary_point': content[:100]}
        
        normalized = {
            'narrative': narrative_data.get('narrative', ''),
            'image_prompt': narrative_data.get('image_prompt', ''),
            'summary_point': narrative_data.get('summary_point', '')
        }
        
        return jsonify({
            'candidates': [{'content': {'parts': [{'text': json.dumps(normalized)}]}}],
            'normalized_candidate': normalized,
            'used_real_llm': True
        }), 200
        
    except Exception as e:
        print(f"[ANTHROPIC ERROR] {str(e)}")
        return jsonify({'error': f'Anthropic API error: {str(e)}'}), 500


# --- AI ROUTING ENDPOINTS (Protected) ---

@ai_bp.route('/generate-prompt', methods=['POST'])
@token_required
def generate_prompt(user_id):
    """Routes the request to the Gemini LLM to generate narrative and prompt."""
    try:
        data = request.get_json()
        payload = data['payload']

        # Log start of request for debugging (do not print secrets)
        try:
            print(f"GENERATE_PROMPT_START user={user_id} payload_keys={list(payload.keys()) if isinstance(payload, dict) else 'raw'}")
        except Exception:
            pass
        # Support a dev mock LLM provider to return deterministic JSON for local testing
        provider = current_app.config.get('LLM_PROVIDER', 'gemini')
        print(f"[LLM] Using provider: {provider}")

        if provider == 'mock':
            # Try to derive a short prompt text from the payload for better mock outputs
            prompt_text = ''
            try:
                if isinstance(payload, dict):
                    contents = payload.get('contents') or payload.get('messages')
                    if contents and isinstance(contents, list) and len(contents) > 0:
                        first = contents[0]
                        # payload may use parts or text directly
                        if isinstance(first, dict):
                            parts = first.get('parts') or []
                            if parts and isinstance(parts, list) and len(parts) > 0:
                                first_part = parts[0]
                                if isinstance(first_part, dict):
                                    prompt_text = first_part.get('text','')
                                else:
                                    prompt_text = str(first_part)
                            else:
                                prompt_text = first.get('text','') or ''
                        else:
                            prompt_text = str(first)
            except Exception:
                prompt_text = str(payload)

            # Build a richer deterministic narrative for local testing so the
            # frontend receives a believable story even without a real LLM.
            narrative = _synthesize_narrative(prompt_text, paragraphs=4)
            image_prompt = f"{prompt_text[:160]} -- photorealistic cinematic"
            summary_point = narrative.split('\n')[0][:160]

            normalized = {
                'narrative': narrative,
                'image_prompt': image_prompt,
                'summary_point': summary_point
            }
            mock_body = {
                'candidates': [
                    {
                        'content': {
                            'parts': [
                                { 'text': json.dumps(normalized) }
                            ]
                        }
                    }
                ],
                'normalized_candidate': normalized
            }
            # Mark this as mock (not from a real upstream LLM)
            try:
                mock_body['used_real_llm'] = False
            except Exception:
                pass
            return jsonify(mock_body), 200

        # --- Handle alternative LLM providers ---
        if provider == 'groq':
            return _call_groq_llm(payload)
        elif provider == 'openai':
            return _call_openai_llm(payload)
        elif provider == 'anthropic':
            return _call_anthropic_llm(payload)

        # Default: Gemini
        GEMINI_API_KEY = current_app.config['GEMINI_API_KEY']
        STORY_API_URL = current_app.config['STORY_API_URL']

        # Route to external Gemini API. FORCED to use real LLM - NO fallback.
        # Log all requests and responses for debugging.
        print(f"[LLM FORCE] Attempting to call real Gemini API with key: {GEMINI_API_KEY[:20]}...")
        print(f"[LLM FORCE] Story API URL: {STORY_API_URL}")
        try:
            response = None
            session = _get_session()
            # AGGRESSIVE timeout - fail fast if API is slow
            timeout_secs = 8  # Ultra-aggressive 8 second timeout
            print(f"[LLM FORCE] Attempting to call real Gemini API with timeout={timeout_secs}s")
            try:
                print(f"[LLM FORCE] POST to {STORY_API_URL}")
                response = session.post(
                    f"{STORY_API_URL}?key={GEMINI_API_KEY}", 
                    json=payload, 
                    timeout=timeout_secs
                )
                print(f"[LLM FORCE] Response status: {response.status_code}")
                response.raise_for_status()
                print(f"[LLM FORCE] SUCCESS! Got response")
            except requests.exceptions.Timeout as e:
                print(f"[LLM FORCE] TIMEOUT ERROR after {timeout_secs}s: {str(e)}")
                raise Exception(f"Gemini API timeout after {timeout_secs}s - API is not responding in time")
            except requests.exceptions.ConnectionError as e:
                print(f"[LLM FORCE] CONNECTION ERROR: {str(e)}")
                raise Exception(f"Cannot connect to Gemini API: {str(e)}")
            except requests.exceptions.RequestException as e:
                print(f"[LLM FORCE] REQUEST ERROR: {str(e)}")
                raise
            if response is None:
                raise Exception('No response from upstream LLM provider')
            # Post-process the LLM response to ensure we always return a JSON
            # string containing narrative, image_prompt and summary_point in
            # candidates[0].content.parts[0].text. Some LLM providers may return
            # free-form text; normalize it so the frontend never sees undefined
            # for the visual prompt.
            resp_json = response.json()
            # Ensure we always expose a normalized candidate to the client.
            # Some upstream providers return unexpected shapes (no candidates
            # or free-form text). We'll try to normalize below and always set
            # resp_json['normalized_candidate'] so the frontend can rely on it.
            try:
                if not isinstance(resp_json, dict):
                    resp_json = {'raw': resp_json}
            except Exception:
                resp_json = {'raw': str(resp_json)}
            try:
                print('GENERATE_PROMPT_RAW', str(resp_json)[:1000])
            except Exception:
                pass
            try:
                cand = resp_json.get('candidates', [])

                def _synthesize_from_payload(reason='fallback'):
                    prompt_text = ''
                    try:
                        if isinstance(payload, dict):
                            contents = payload.get('contents') or payload.get('messages')
                            if contents and isinstance(contents, list) and len(contents) > 0:
                                first = contents[0]
                                if isinstance(first, dict):
                                    parts_local = first.get('parts') or []
                                    if parts_local and isinstance(parts_local, list) and len(parts_local) > 0:
                                        p0 = parts_local[0]
                                        prompt_text = p0.get('text','') if isinstance(p0, dict) else str(p0)
                                    else:
                                        prompt_text = first.get('text','') or ''
                                else:
                                    prompt_text = str(first)
                        if not prompt_text:
                            prompt_text = str(payload)[:200]
                    except Exception:
                        prompt_text = str(payload)

                    narrative = _synthesize_narrative(prompt_text, paragraphs=4)
                    image_prompt = f"{prompt_text[:160]} -- photorealistic cinematic"
                    summary_point = narrative.split('\n')[0][:160]
                    normalized_local = {
                        'narrative': narrative,
                        'image_prompt': image_prompt,
                        'summary_point': summary_point
                    }
                    resp_json['normalized_candidate'] = normalized_local
                    resp_json['used_real_llm'] = False
                    resp_json['candidates'] = [{
                        'content': {
                            'parts': [{ 'text': json.dumps(normalized_local) }]
                        },
                        'note': f'synthesized because {reason}'
                    }]

                if isinstance(cand, list) and len(cand) > 0:
                    content = cand[0].get('content', {})
                    parts = content.get('parts', [])
                    if not isinstance(parts, list) or len(parts) == 0 or not parts[0].get('text'):
                        _synthesize_from_payload('empty parts from upstream')
                    else:
                        txt = parts[0].get('text', '').strip()

                        # --- Sanitize common LLM artifacts ---
                        try:
                            if txt.startswith('```'):
                                nl = txt.find('\n')
                                if nl != -1:
                                    txt = txt[nl+1:]
                                if txt.endswith('```'):
                                    txt = txt[:-3].strip()
                        except Exception:
                            pass

                        parsed = None
                        try:
                            if '{' in txt and '}' in txt:
                                start = txt.find('{')
                                end = txt.rfind('}')
                                candidate = txt[start:end+1]
                                parsed = json.loads(candidate)
                        except Exception:
                            parsed = None

                        if parsed is None:
                            try:
                                parsed = json.loads(txt)
                            except Exception:
                                parsed = {'narrative': txt}

                        narrative = parsed.get('narrative') or parsed.get('text') or ''
                        image_prompt = parsed.get('image_prompt') or ''
                        summary_point = parsed.get('summary_point') or parsed.get('summary') or ''

                        if not image_prompt:
                            short = ''
                            if narrative:
                                short = narrative.split('\n')[0].split('. ')[0][:180]
                            else:
                                try:
                                    short = str(payload)[:180]
                                except Exception:
                                    short = ''
                            image_prompt = f"{short} -- photorealistic cinematic"

                        normalized = {
                            'narrative': narrative,
                            'image_prompt': image_prompt,
                            'summary_point': summary_point
                        }
                        parts[0]['text'] = json.dumps(normalized)
                        try:
                            print('GENERATE_PROMPT_NORMALIZED', json.dumps(normalized)[:1000])
                        except Exception:
                            pass
                        try:
                            resp_json['normalized_candidate'] = normalized
                            resp_json['used_real_llm'] = True
                        except Exception:
                            pass
                        content['parts'] = parts
                        cand[0]['content'] = content
                        resp_json['candidates'] = cand
                else:
                    _synthesize_from_payload('no candidates returned')
            except Exception:
                # If any post-processing fails, ignore and return original provider response
                pass

            return jsonify(resp_json), 200
        except Exception as upstream_err:
            # Log upstream error on server side (print for now).
            try:
                print('[LLM FORCE ERROR] LLM provider error:', str(upstream_err))
                print('[LLM FORCE ERROR] Full error details:', repr(upstream_err))
            except Exception:
                pass
            
            # FORCE real LLM - NEVER fall back to mock. Always return error.
            print('[LLM FORCE] ABORTING - Mock fallback is disabled. Real LLM is required.')
            return jsonify({'error': str(upstream_err), 'message': 'LLM provider failed. Real LLM is required.'}), 500
            

    except requests.exceptions.HTTPError as e:
        # Better error handling for external API issues
        return jsonify({'error': f"LLM API Error: {e.response.text}"}), e.response.status_code
    except Exception as e:
        return jsonify({'error': f"Internal Server Error during LLM call: {str(e)}"}), 500


@ai_bp.route('/generate-image', methods=['POST'])
@token_required
def generate_image(user_id):
    """Routes the request to the Imagen model to generate the image."""
    try:
        data = request.get_json()
        payload = data['payload']

        print(f"\n[IMAGE] ========== IMAGE GENERATION START ==========")
        print(f"[IMAGE] User: {user_id}")
        print(f"[IMAGE] Payload keys: {list(payload.keys())}")

        GEMINI_API_KEY = current_app.config.get('GEMINI_API_KEY')
        IMAGE_API_URL = current_app.config.get('IMAGE_API_URL')

        # Route to external Imagen API
        # If a 'free' provider is selected, generate a free placeholder image
        # from Picsum (no API key required). We use a deterministic seed based
        # on the prompt so repeated requests for the same prompt return the
        # same image.
        provider = current_app.config.get('IMAGE_PROVIDER', 'google')
        alternate_url = current_app.config.get('ALTERNATE_IMAGE_API_URL')
        
        print(f"[IMAGE] Provider: {provider}")
        print(f"[IMAGE] Stability API Key configured: {bool(current_app.config.get('STABILITY_API_KEY'))}")

        # Determine prompt and requested sample count for caching
        prompt_text = _extract_prompt_from_payload(payload)
        print(f"[IMAGE] Extracted prompt ({len(prompt_text)} chars): {prompt_text[:100]}...")
        params = {}
        try:
            params_obj = payload.get('parameters') if isinstance(payload, dict) else {}
            if isinstance(params_obj, dict):
                params['sampleCount'] = params_obj.get('sampleCount') or params_obj.get('samples') or 1
                params['aspectRatio'] = params_obj.get('aspectRatio')
        except Exception:
            params['sampleCount'] = 1

        cache_key = _make_image_cache_key(prompt_text, provider, params)
        cache_ttl = current_app.config.get('IMAGE_CACHE_TTL_SECONDS', 60 * 60 * 24)
        # Try to serve from cache first
        cached = _load_image_cache(cache_key, ttl_seconds=cache_ttl)
        if cached:
            preds = [{'bytesBase64Encoded': b} for b in cached]
            return jsonify({'predictions': preds, 'cached': True}), 200

        if provider == 'free':
            # Derive a seed from the prompt text for variety
            try:
                seed = hashlib.sha1(prompt_text.encode('utf-8')).hexdigest()[:8]
            except Exception:
                seed = hashlib.sha1(str(time.time()).encode('utf-8')).hexdigest()[:8]
            picsum_url = f'https://picsum.photos/seed/{seed}/800/450'
            pic_resp = requests.get(picsum_url)
            if pic_resp.status_code == 200:
                img_bytes = pic_resp.content
                b64 = base64.b64encode(img_bytes).decode('utf-8')
                # persist small picsum fallback to cache
                try:
                    _persist_image_cache(cache_key, [b64], prompt_text)
                except Exception:
                    pass
                return jsonify({'predictions': [{'bytesBase64Encoded': b64}]}), 200
            # If picsum fails for some reason, fall through to other handlers

        # If an alternate provider is configured, forward the call there instead
        if provider != 'google' and alternate_url:
            # Forward to alternate provider (best-effort: assume compatible request format)
            alt_resp = requests.post(alternate_url, json=payload)
            try:
                alt_resp.raise_for_status()
                return jsonify(alt_resp.json()), 200
            except requests.exceptions.HTTPError:
                # Continue to attempt Google Imagen below if alternate provider fails
                pass

        # Support for cloud Stability.ai and local AUTOMATIC1111 (Stable Diffusion)
        if provider == 'stability':
            # Use Stability.ai REST API (v1) - requires STABILITY_API_KEY and engine/model name
            stability_key = current_app.config.get('STABILITY_API_KEY')
            engine = current_app.config.get('STABILITY_ENGINE')
            if not stability_key:
                return jsonify({'error': 'STABILITY_API_KEY not configured for stability provider.'}), 400

            # attempt to extract a simple prompt string from the payload
            prompt_text = ''
            try:
                if isinstance(payload, dict):
                    inst = payload.get('instances') or payload.get('inputs') or payload.get('prompt')
                    if isinstance(inst, list) and len(inst) > 0:
                        first = inst[0]
                        if isinstance(first, dict):
                            prompt_text = first.get('prompt') or first.get('text') or ''
                        else:
                            prompt_text = str(first)
                    elif isinstance(inst, str):
                        prompt_text = inst
                    else:
                        prompt_text = str(payload)
            except Exception:
                prompt_text = str(payload)

            print(f"[STABILITY] Calling Stability AI...")
            print(f"[STABILITY] Engine: {engine}")
            print(f"[STABILITY] Prompt ({len(prompt_text)} chars): {prompt_text[:150]}...")

            stability_url = f'https://api.stability.ai/v1/generation/{engine}/text-to-image'
            headers = {'Authorization': f'Bearer {stability_key}', 'Content-Type': 'application/json'}
            body = {
                'text_prompts': [{'text': prompt_text}],
                'cfg_scale': 7,
                'height': 1024,
                'width': 1024,
                'samples': 1
            }
            try:
                # if params requested sampleCount override, use it
                if params.get('sampleCount'):
                    body['samples'] = int(params.get('sampleCount') or 1)
                print(f"[STABILITY] POST to {stability_url}")
                st_resp = requests.post(stability_url, headers=headers, json=body, timeout=60)
                print(f"[STABILITY] Response status: {st_resp.status_code}")
                st_resp.raise_for_status()
                print(f"[STABILITY] SUCCESS!")
            except requests.exceptions.HTTPError as e:
                # If Stability returns an API error and fallbacks are enabled, provide Picsum
                print(f"[STABILITY] HTTP Error: {st_resp.status_code}")
                print(f"[STABILITY] Response: {st_resp.text[:200]}")
                if current_app.config.get('USE_IMAGE_FALLBACK', True):
                    print(f"[STABILITY] Falling back to Picsum...")
                    b64 = _picsum_base64_from_prompt(prompt_text)
                    if b64:
                        try:
                            _persist_image_cache(cache_key, [b64], prompt_text)
                        except Exception:
                            pass
                        print(f"[STABILITY] Returned Picsum fallback image")
                        return jsonify({'predictions': [{'bytesBase64Encoded': b64}], 'fallback': 'picsum'}), 200
                try:
                    return jsonify({'error': st_resp.json()}), st_resp.status_code
                except Exception:
                    return jsonify({'error': 'Stability API Error'}), 502
            except Exception as e:
                print(f"[STABILITY] Exception: {str(e)}")
                if current_app.config.get('USE_IMAGE_FALLBACK', True):
                    print(f"[STABILITY] Falling back to Picsum due to exception...")
                    b64 = _picsum_base64_from_prompt(prompt_text)
                    if b64:
                        try:
                            _persist_image_cache(cache_key, [b64], prompt_text)
                        except Exception:
                            pass
                        print(f"[STABILITY] Returned Picsum fallback image")
                        return jsonify({'predictions': [{'bytesBase64Encoded': b64}], 'fallback': 'picsum'}), 200
                return jsonify({'error': f'Stability provider request failed: {str(e)}'}), 502

            # Parse common response shapes for base64 images
            try:
                j = st_resp.json()
                # Check for 'artifacts' or 'images' or 'data'
                b64 = None
                if isinstance(j, dict):
                    if 'artifacts' in j and isinstance(j['artifacts'], list) and len(j['artifacts']) > 0:
                        a = j['artifacts'][0]
                        b64 = a.get('base64') or a.get('b64') or a.get('b64_json')
                    if not b64 and 'images' in j and isinstance(j['images'], list) and len(j['images']) > 0:
                        b64 = j['images'][0].get('b64') if isinstance(j['images'][0], dict) else j['images'][0]
                    if not b64 and 'data' in j and isinstance(j['data'], list) and len(j['data']) > 0:
                        d0 = j['data'][0]
                        if isinstance(d0, dict):
                            b64 = d0.get('b64') or d0.get('base64')
                        else:
                            b64 = d0

                if not b64:
                    if current_app.config.get('USE_IMAGE_FALLBACK', True):
                        fb = _picsum_base64_from_prompt(prompt_text)
                        if fb:
                            try:
                                _persist_image_cache(cache_key, [fb], prompt_text)
                            except Exception:
                                pass
                            return jsonify({'predictions': [{'bytesBase64Encoded': fb}], 'fallback': 'picsum'}), 200
                    return jsonify({'error': 'No image returned by Stability API.'}), 502

                # persist to cache
                try:
                    _persist_image_cache(cache_key, [b64], prompt_text)
                except Exception:
                    pass

                return jsonify({'predictions': [{'bytesBase64Encoded': b64}]}), 200
            except Exception as e:
                if current_app.config.get('USE_IMAGE_FALLBACK', True):
                    fb = _picsum_base64_from_prompt(prompt_text)
                    if fb:
                        try:
                            _persist_image_cache(cache_key, [fb], prompt_text)
                        except Exception:
                            pass
                        return jsonify({'predictions': [{'bytesBase64Encoded': fb}], 'fallback': 'picsum'}), 200
                return jsonify({'error': f'Error parsing Stability response: {str(e)}'}), 500

        if provider == 'local_auto':
            # Forward to a local AUTOMATIC1111 server (assumes /sdapi/v1/txt2img)
            auto_url = current_app.config.get('AUTOMATIC1111_URL') or 'http://127.0.0.1:7860'
            txt2img = f"{auto_url.rstrip('/')}/sdapi/v1/txt2img"
            # derive prompt
            prompt_text = ''
            try:
                if isinstance(payload, dict):
                    inst = payload.get('prompt') or payload.get('prompt_text') or payload.get('inputs') or payload.get('instances')
                    if isinstance(inst, list) and len(inst) > 0:
                        first = inst[0]
                        prompt_text = first.get('prompt') if isinstance(first, dict) else str(first)
                    elif isinstance(inst, str):
                        prompt_text = inst
                if not prompt_text:
                    prompt_text = str(payload)
            except Exception:
                prompt_text = str(payload)

            body = {'prompt': prompt_text, 'steps': 20}
            try:
                auto_resp = requests.post(txt2img, json=body, timeout=60)
                auto_resp.raise_for_status()
            except requests.exceptions.HTTPError:
                try:
                    return jsonify({'error': auto_resp.json()}), auto_resp.status_code
                except Exception:
                    return jsonify({'error': 'Local AUTOMATIC1111 error'}), 502
            except Exception as e:
                return jsonify({'error': f'LOCAL AUTOMATIC1111 request failed: {str(e)}'}), 502

            try:
                j = auto_resp.json()
                # AUTOMATIC1111 returns images as base64 strings in j['images']
                if 'images' in j and isinstance(j['images'], list) and len(j['images']) > 0:
                    b64 = j['images'][0]
                    try:
                        _persist_image_cache(cache_key, [b64], prompt_text)
                    except Exception:
                        pass
                    return jsonify({'predictions': [{'bytesBase64Encoded': b64}]}), 200
                return jsonify({'error': 'No images returned from local AUTOMATIC1111.'}), 502
            except Exception as e:
                return jsonify({'error': f'Error parsing AUTOMATIC1111 response: {str(e)}'}), 500

        response = None
        for attempt in range(3):
            try:
                response = requests.post(f"{IMAGE_API_URL}?key={GEMINI_API_KEY}", json=payload, timeout=60)
                response.raise_for_status()
                break
            except requests.exceptions.RequestException:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        if response is None:
            raise Exception('No response from upstream Image provider')
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            # Attempt to parse API error body and log it for debugging
            try:
                resp_json = response.json()
                resp_text = json.dumps(resp_json)
            except Exception:
                resp_text = response.text or ''

            # Log upstream image provider error to server logs to aid diagnosis
            try:
                print('Image provider error response:', resp_text)
            except Exception:
                pass

            # Detect the common billed-account error and either return a clear
            # actionable 402 or a fallback image depending on config.
            billed_error = 'Imagen API is only accessible to billed users' in resp_text or 'billed' in resp_text
            if billed_error:
                # If configured, fall back to a deterministic Picsum image
                # derived from the visual prompt so the UI still receives a
                # meaningful image rather than a tiny placeholder.
                if current_app.config.get('USE_IMAGE_FALLBACK', False):
                    # Try to extract a prompt to seed Picsum
                    prompt_text = ''
                    try:
                        if isinstance(payload, dict):
                            inst = payload.get('instances') or payload.get('inputs') or payload.get('prompt')
                            if inst and isinstance(inst, list) and len(inst) > 0:
                                first = inst[0]
                                prompt_text = first.get('prompt') if isinstance(first, dict) else str(first)
                            elif isinstance(inst, dict):
                                prompt_text = inst.get('prompt') or inst.get('text') or ''
                            elif isinstance(inst, str):
                                prompt_text = inst
                    except Exception:
                        prompt_text = str(payload)

                    try:
                        seed = hashlib.sha1(prompt_text.encode('utf-8')).hexdigest()[:8]
                        picsum_url = f'https://picsum.photos/seed/{seed}/800/450'
                        pic_resp = requests.get(picsum_url, timeout=20)
                        if pic_resp.status_code == 200:
                            img_bytes = pic_resp.content
                            b64 = base64.b64encode(img_bytes).decode('utf-8')
                            return jsonify({'predictions': [{'bytesBase64Encoded': b64}]}), 200
                    except Exception:
                        # If Picsum fallback fails, return the configured tiny fallback
                        fb = current_app.config.get('FALLBACK_IMAGE_BASE64')
                        return jsonify({'predictions': [{'bytesBase64Encoded': fb}]}), 200

                return jsonify({'error': 'Imagen API requires a billed Google Cloud account. Enable billing or configure an alternative image provider.'}), 402

            # Other API errors: optionally return a Picsum fallback or propagate
            if current_app.config.get('USE_IMAGE_FALLBACK', False):
                # Try to derive a prompt and return a deterministic Picsum image
                prompt_text = ''
                try:
                    if isinstance(payload, dict):
                        inst = payload.get('instances') or payload.get('inputs') or payload.get('prompt')
                        if inst and isinstance(inst, list) and len(inst) > 0:
                            first = inst[0]
                            prompt_text = first.get('prompt') if isinstance(first, dict) else str(first)
                        elif isinstance(inst, dict):
                            prompt_text = inst.get('prompt') or inst.get('text') or ''
                        elif isinstance(inst, str):
                            prompt_text = inst
                except Exception:
                    prompt_text = str(payload)

                try:
                    seed = hashlib.sha1(prompt_text.encode('utf-8')).hexdigest()[:8]
                    picsum_url = f'https://picsum.photos/seed/{seed}/800/450'
                    pic_resp = requests.get(picsum_url, timeout=20)
                    if pic_resp.status_code == 200:
                        img_bytes = pic_resp.content
                        b64 = base64.b64encode(img_bytes).decode('utf-8')
                        return jsonify({'predictions': [{'bytesBase64Encoded': b64}]}), 200
                except Exception:
                    pass

                # As a last resort, return the configured tiny fallback image
                fb = current_app.config.get('FALLBACK_IMAGE_BASE64')
                return jsonify({'predictions': [{'bytesBase64Encoded': fb}]}), 200

            return jsonify({'error': f"Image API Error: {resp_text}"}), response.status_code

        # Attempt to persist returned images if present in response
        try:
            j = response.json()
            # extract base64(s)
            b64_list = []
            if isinstance(j, dict):
                if 'predictions' in j and isinstance(j['predictions'], list):
                    for p in j['predictions']:
                        if isinstance(p, dict) and p.get('bytesBase64Encoded'):
                            b64_list.append(p.get('bytesBase64Encoded'))
                        elif isinstance(p, str):
                            b64_list.append(p)
                # common other shapes
                if 'artifacts' in j and isinstance(j['artifacts'], list):
                    for a in j['artifacts']:
                        if isinstance(a, dict) and a.get('base64'):
                            b64_list.append(a.get('base64'))
                if 'images' in j and isinstance(j['images'], list):
                    for it in j['images']:
                        if isinstance(it, dict) and it.get('b64'):
                            b64_list.append(it.get('b64'))
                        elif isinstance(it, str):
                            b64_list.append(it)
            if b64_list:
                try:
                    _persist_image_cache(cache_key, b64_list, prompt_text)
                except Exception:
                    pass
        except Exception:
            pass

        return jsonify(response.json()), 200
        
    except Exception as e:
        return jsonify({'error': f"Internal Server Error during Image call: {str(e)}"}), 500


@ai_bp.route('/status', methods=['GET'])
def status():
    """Return active provider configuration (safe, non-secret) for UI debugging."""
    cfg = current_app.config
    return jsonify({
        'image_provider': cfg.get('IMAGE_PROVIDER'),
        'llm_provider': cfg.get('LLM_PROVIDER'),
        'use_mock_fallback': cfg.get('USE_MOCK_FALLBACK', False),
        'has_gemini_key': bool(cfg.get('GEMINI_API_KEY'))
    }), 200


@ai_bp.route('/cache/invalidate', methods=['POST'])
@token_required
def cache_invalidate(user_id):
    """Invalidate persisted image cache entries.

    Accepts JSON payloads of the forms:
      { "key": "<cache_key>" }
      { "prompt": "...", "provider": "...", "params": {...} }
      { "all": true }

    Returns which files were removed.
    """
    try:
        data = request.get_json() or {}
        uploads_dir = os.path.join(current_app.static_folder, 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)

        removed = []

        # Remove everything
        if data.get('all'):
            for fname in os.listdir(uploads_dir):
                if fname.startswith('cache_') or fname.startswith('img_'):
                    try:
                        path = os.path.join(uploads_dir, fname)
                        os.remove(path)
                        removed.append(fname)
                    except Exception:
                        pass
            return jsonify({'success': True, 'removed': removed}), 200

        # If key supplied, remove cache_{key}.json and referenced files
        key = data.get('key')
        if key:
            meta_path = os.path.join(uploads_dir, f'cache_{key}.json')
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    for fname in meta.get('files', []):
                        path = os.path.join(uploads_dir, fname)
                        if os.path.exists(path):
                            try:
                                os.remove(path)
                                removed.append(fname)
                            except Exception:
                                pass
                except Exception:
                    pass
                try:
                    os.remove(meta_path)
                    removed.append(os.path.basename(meta_path))
                except Exception:
                    pass
            # Also attempt to remove any imgs matching the key prefix
            for fname in os.listdir(uploads_dir):
                if fname.startswith(f'img_{key}_'):
                    try:
                        os.remove(os.path.join(uploads_dir, fname))
                        removed.append(fname)
                    except Exception:
                        pass
            return jsonify({'success': True, 'removed': removed}), 200

        # If prompt/provider/params provided, compute the cache key and delete
        prompt = data.get('prompt')
        provider = data.get('provider', current_app.config.get('IMAGE_PROVIDER', 'google'))
        params = data.get('params') or {}
        if prompt:
            key = _make_image_cache_key(prompt, provider, params)
            # Recurse into key path removal (reuse above logic)
            meta_path = os.path.join(uploads_dir, f'cache_{key}.json')
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    for fname in meta.get('files', []):
                        path = os.path.join(uploads_dir, fname)
                        if os.path.exists(path):
                            try:
                                os.remove(path)
                                removed.append(fname)
                            except Exception:
                                pass
                except Exception:
                    pass
                try:
                    os.remove(meta_path)
                    removed.append(os.path.basename(meta_path))
                except Exception:
                    pass
            for fname in os.listdir(uploads_dir):
                if fname.startswith(f'img_{key}_'):
                    try:
                        os.remove(os.path.join(uploads_dir, fname))
                        removed.append(fname)
                    except Exception:
                        pass
            return jsonify({'success': True, 'removed': removed, 'key': key}), 200

        return jsonify({'success': False, 'error': 'No valid cache delete parameters provided.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/cache/list', methods=['GET'])
@token_required
def cache_list(user_id):
    """Return a list of cache entries (safe metadata only).

    Each entry includes: key, prompt, ts, files (filenames) and file_urls (relative paths)
    """
    try:
        uploads_dir = os.path.join(current_app.static_folder, 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        entries = []
        for fname in os.listdir(uploads_dir):
            if not fname.startswith('cache_') or not fname.endswith('.json'):
                continue
            meta_path = os.path.join(uploads_dir, fname)
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                key = meta.get('key') or fname.replace('cache_', '').replace('.json', '')
                prompt = meta.get('prompt')
                ts = meta.get('ts')
                files = meta.get('files', [])
                file_urls = [f"/static/uploads/{n}" for n in files]
                entries.append({'key': key, 'prompt': prompt, 'ts': ts, 'files': files, 'file_urls': file_urls})
            except Exception:
                # ignore broken entries
                continue
        # sort by ts desc
        entries.sort(key=lambda e: e.get('ts', 0), reverse=True)
        return jsonify({'entries': entries}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/generate-main-image', methods=['POST'])
@token_required
def generate_main_image(user_id):
    """Generate the main scene image using Picsum (forced free provider).

    This endpoint ignores the configured IMAGE_PROVIDER and always
    returns a Picsum image (deterministic seed derived from the prompt).
    Useful for ensuring the primary scene image is a free placeholder
    regardless of other provider settings.
    """
    try:
        data = request.get_json() or {}
        payload = data.get('payload') or {}

        # Derive a seed from the prompt text for variety (same logic as generate_image free branch)
        prompt_text = ''
        try:
            if isinstance(payload, dict):
                inst = payload.get('instances') or payload.get('inputs') or payload.get('prompt')
                if inst and isinstance(inst, list) and len(inst) > 0:
                    first = inst[0]
                    prompt_text = first.get('prompt') if isinstance(first, dict) else str(first)
                elif isinstance(inst, dict):
                    # direct dict with prompt key
                    prompt_text = inst.get('prompt') or inst.get('text') or ''
                elif isinstance(inst, str):
                    prompt_text = inst
        except Exception:
            prompt_text = str(payload)

        seed = hashlib.sha1(prompt_text.encode('utf-8')).hexdigest()[:8]
        picsum_url = f'https://picsum.photos/seed/{seed}/1200/675'
        pic_resp = requests.get(picsum_url, timeout=20)
        if pic_resp.status_code == 200:
            img_bytes = pic_resp.content
            b64 = base64.b64encode(img_bytes).decode('utf-8')
            return jsonify({'predictions': [{'bytesBase64Encoded': b64}]}), 200

        # If Picsum failed, return configured fallback if available
        if current_app.config.get('USE_IMAGE_FALLBACK', False):
            fb = current_app.config.get('FALLBACK_IMAGE_BASE64')
            return jsonify({'predictions': [{'bytesBase64Encoded': fb}]}), 200

        return jsonify({'error': 'Picsum image fetch failed.'}), 502
    except Exception as e:
        return jsonify({'error': f'Internal Server Error during main image call: {str(e)}'}), 500


@ai_bp.route('/generate-preview', methods=['POST'])
@token_required
def generate_preview(user_id):
    """Return a fast, deterministic low-res preview for a given payload.

    Behavior: Always returns a seeded Picsum image (small size) derived from
    the prompt text so the UI can show an immediate preview while the
    full-resolution generation runs (if requested).
    """
    try:
        data = request.get_json() or {}
        payload = data.get('payload') or data

        prompt_text = _extract_prompt_from_payload(payload)
        if not prompt_text:
            prompt_text = 'preview'

        # Use a short seed derived from the prompt for deterministic previews
        try:
            seed = hashlib.sha1(prompt_text.encode('utf-8')).hexdigest()[:8]
        except Exception:
            seed = hashlib.sha1(str(time.time()).encode('utf-8')).hexdigest()[:8]

        # Small preview size for speed
        width = 512
        height = 288
        picsum_url = f'https://picsum.photos/seed/{seed}/{width}/{height}'
        pic_resp = requests.get(picsum_url, timeout=10)
        if pic_resp.status_code == 200:
            img_bytes = pic_resp.content
            b64 = base64.b64encode(img_bytes).decode('utf-8')
            return jsonify({'predictions': [{'bytesBase64Encoded': b64}], 'preview': True}), 200

        return jsonify({'error': 'Preview fetch failed'}), 502
    except Exception as e:
        return jsonify({'error': f'Internal Server Error during preview generation: {str(e)}'}), 500


def _async_generate_and_cache(job_id, payload, user_id, app_obj=None):
    """Background worker that generates an AI image using Stability API
    or falls back to Picsum. This allows the UI to poll for completion
    via the job endpoints.
    """
    try:
        JOBS[job_id]['status'] = 'running'
        # If an app object was provided, ensure we run inside its application context
        if app_obj:
            ctx = app_obj.app_context()
            ctx.push()
        prompt_text = _extract_prompt_from_payload(payload) or 'async'
        
        print(f"[IMAGE] Starting async image generation for prompt: {prompt_text[:100]}...")

        provider = current_app.config.get('IMAGE_PROVIDER', 'google')
        params = {}
        try:
            params_obj = payload.get('parameters') if isinstance(payload, dict) else {}
            if isinstance(params_obj, dict):
                params['sampleCount'] = params_obj.get('sampleCount') or params_obj.get('samples') or 1
        except Exception:
            params['sampleCount'] = 1

        cache_key = _make_image_cache_key(prompt_text, provider, params)

        # If cache already exists, return that quickly
        cache_ttl = current_app.config.get('IMAGE_CACHE_TTL_SECONDS', 60 * 60 * 24)
        cached = _load_image_cache(cache_key, ttl_seconds=cache_ttl)
        if cached:
            print(f"[IMAGE] Cache hit for key: {cache_key}")
            # build file urls from persisted files
            uploads_dir = os.path.join(current_app.static_folder, 'uploads')
            meta_path = os.path.join(uploads_dir, f'cache_{cache_key}.json')
            files = []
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                    files = meta.get('files', [])
            except Exception:
                files = []

            JOBS[job_id]['status'] = 'done'
            JOBS[job_id]['result'] = {'key': cache_key, 'files': files, 'file_urls': [f"/static/uploads/{n}" for n in files]}
            if app_obj:
                ctx.pop()
            return

        # Try Stability AI first
        img_bytes = None
        if provider == 'stability':
            STABILITY_API_KEY = current_app.config.get('STABILITY_API_KEY')
            STABILITY_ENGINE = current_app.config.get('STABILITY_ENGINE', 'stable-diffusion-xl-1024-v1-0')
            
            if STABILITY_API_KEY:
                print(f"[STABILITY] Calling Stability AI API...")
                try:
                    stability_response = requests.post(
                        f"https://api.stability.ai/v1/generation/{STABILITY_ENGINE}/text-to-image",
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "Authorization": f"Bearer {STABILITY_API_KEY}"
                        },
                        json={
                            "text_prompts": [{"text": prompt_text, "weight": 1.0}],
                            "cfg_scale": 7,
                            "height": 1024,
                            "width": 1024,
                            "samples": 1,
                            "steps": 30
                        },
                        timeout=60
                    )
                    
                    print(f"[STABILITY] Response status: {stability_response.status_code}")
                    
                    if stability_response.status_code == 200:
                        response_data = stability_response.json()
                        artifacts = response_data.get('artifacts', [])
                        if artifacts and 'base64' in artifacts[0]:
                            img_bytes = base64.b64decode(artifacts[0]['base64'])
                            print(f"[STABILITY] ✅ SUCCESS! Image generated ({len(img_bytes)} bytes)")
                        else:
                            print(f"[STABILITY] ⚠️ No artifacts in response")
                    else:
                        error_text = stability_response.text[:200]
                        print(f"[STABILITY] ❌ API Error: {error_text}")
                except Exception as e:
                    print(f"[STABILITY] ❌ Exception: {str(e)}")
            else:
                print(f"[STABILITY] ⚠️ STABILITY_API_KEY not configured")
        
        # Fallback to Picsum if Stability failed
        if img_bytes is None:
            print(f"[IMAGE] Falling back to Picsum...")
            try:
                seed = hashlib.sha1(prompt_text.encode('utf-8')).hexdigest()[:8]
            except Exception:
                seed = hashlib.sha1(str(time.time()).encode('utf-8')).hexdigest()[:8]
            width = 1200
            height = 675
            picsum_url = f'https://picsum.photos/seed/{seed}/{width}/{height}'
            pic_resp = requests.get(picsum_url, timeout=30)
            if pic_resp.status_code == 200:
                img_bytes = pic_resp.content
                print(f"[IMAGE] Picsum fallback success ({len(img_bytes)} bytes)")
            else:
                print(f"[IMAGE] ❌ Picsum also failed")
        
        # If we got an image (from Stability or Picsum), cache it
        if img_bytes:
            b64 = base64.b64encode(img_bytes).decode('utf-8')
            # persist to cache using existing helper
            try:
                _persist_image_cache(cache_key, [b64], prompt_text)
                print(f"[IMAGE] Cached with key: {cache_key}")
            except Exception as e:
                print(f"[IMAGE] Cache persist error: {str(e)}")

            # Read back metadata to report files
            uploads_dir = os.path.join(current_app.static_folder, 'uploads')
            meta_path = os.path.join(uploads_dir, f'cache_{cache_key}.json')
            files = []
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                    files = meta.get('files', [])
            except Exception:
                files = []

            JOBS[job_id]['status'] = 'done'
            JOBS[job_id]['result'] = {'key': cache_key, 'files': files, 'file_urls': [f"/static/uploads/{n}" for n in files]}
            if app_obj:
                ctx.pop()
            return

        # If everything failed, mark job as error
        print(f"[IMAGE] ❌ All image generation methods failed")
        JOBS[job_id]['status'] = 'error'
        JOBS[job_id]['result'] = {'error': 'Failed to generate image from any provider.'}
        if app_obj:
            ctx.pop()
    except Exception as e:
        print(f"[IMAGE] ❌ Fatal error: {str(e)}")
        JOBS[job_id]['status'] = 'error'
        JOBS[job_id]['result'] = {'error': str(e)}
        if app_obj:
            try:
                ctx.pop()
            except Exception:
                pass


@ai_bp.route('/generate-image-async', methods=['POST'])
@token_required
def generate_image_async(user_id):
    """Enqueue an async image generation job. Returns a job id which can be
    polled with /generate-image-job/<job_id>. The background worker will
    create a deterministic high-res Picsum image and persist it to the cache
    so subsequent synchronous requests will hit the cache.
    """
    try:
        data = request.get_json() or {}
        payload = data.get('payload') or data

        prompt_text = _extract_prompt_from_payload(payload) or str(time.time())
        # create a stable job id
        job_id = hashlib.sha1(f"{prompt_text}:{time.time()}".encode('utf-8')).hexdigest()[:16]
        JOBS[job_id] = {'status': 'pending', 'result': None, 'ts': int(time.time()), 'user_id': user_id}

        # start background thread, pass real app object so worker can push app context
        app_obj = current_app._get_current_object()
        t = threading.Thread(target=_async_generate_and_cache, args=(job_id, payload, user_id, app_obj), daemon=True)
        t.start()

        return jsonify({'job_id': job_id, 'status': 'pending'}), 202
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/generate-image-job/<job_id>', methods=['GET'])
@token_required
def generate_image_job_status(user_id, job_id):
    """Return the status and result of an async image generation job."""
    try:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        # For security, ensure the requesting user owns the job (dev scaffold only)
        if job.get('user_id') != user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        return jsonify({'job_id': job_id, 'status': job.get('status'), 'result': job.get('result')}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

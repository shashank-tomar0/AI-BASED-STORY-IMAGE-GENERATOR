# ai_service.py

import requests
import json
import base64
import hashlib
import time
import os
from flask import Blueprint, request, jsonify, current_app
from auth import token_required

# Create a Blueprint for AI routes
ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')


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

        GEMINI_API_KEY = current_app.config['GEMINI_API_KEY']
        STORY_API_URL = current_app.config['STORY_API_URL']

        # Route to external Gemini API. If it fails for any reason (network,
        # provider error, billing, etc.) we fall back to the mock LLM so the
        # frontend receives a usable response instead of an error.
        try:
            response = None
            for attempt in range(3):
                try:
                    response = requests.post(f"{STORY_API_URL}?key={GEMINI_API_KEY}", json=payload, timeout=60)
                    response.raise_for_status()
                    break
                except requests.exceptions.RequestException:
                    if attempt == 2:
                        raise
                    time.sleep(2 ** attempt)
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
                if isinstance(cand, list) and len(cand) > 0:
                    content = cand[0].get('content', {})
                    parts = content.get('parts', [])
                    if isinstance(parts, list) and len(parts) > 0:
                        txt = parts[0].get('text', '').strip()

                        # --- Sanitize common LLM artifacts ---
                        # Some LLMs return JSON wrapped in markdown/code fences
                        # (for example: ```json\n{...}\n```) or include extra
                        # surrounding text. Try to clean those cases so the
                        # frontend always receives a plain JSON string.
                        try:
                            # Remove a leading code fence line such as "```json" or "```"
                            if txt.startswith('```'):
                                # strip the first fence line
                                nl = txt.find('\n')
                                if nl != -1:
                                    txt = txt[nl+1:]
                                # remove trailing fence if present
                                if txt.endswith('```'):
                                    txt = txt[:-3].strip()
                        except Exception:
                            pass

                        # If the text contains an embedded JSON object, try to
                        # extract the first {...} block and parse that. This
                        # handles cases where the model adds commentary around
                        # the JSON or returns extra formatting.
                        parsed = None
                        try:
                            if '{' in txt and '}' in txt:
                                start = txt.find('{')
                                end = txt.rfind('}')
                                candidate = txt[start:end+1]
                                parsed = json.loads(candidate)
                        except Exception:
                            parsed = None

                        # Final attempt: parse the whole string as JSON, else
                        # fall back to treating the text as a narrative string.
                        if parsed is None:
                            try:
                                parsed = json.loads(txt)
                            except Exception:
                                parsed = {'narrative': txt}

                        # Ensure keys exist
                        narrative = parsed.get('narrative') or parsed.get('text') or ''
                        image_prompt = parsed.get('image_prompt') or ''
                        summary_point = parsed.get('summary_point') or parsed.get('summary') or ''

                        # If image_prompt is missing or empty, synthesize one from the narrative
                        if not image_prompt:
                            # Use first sentence or a short extract as the visual prompt
                            short = ''
                            if narrative:
                                short = narrative.split('\n')[0].split('. ')[0][:180]
                            else:
                                # Try to derive from the original request payload
                                try:
                                    short = str(payload)[:180]
                                except Exception:
                                    short = ''
                            image_prompt = f"{short} -- photorealistic cinematic"

                        # Reassemble normalized JSON string back into the response
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
                        # Also expose a normalized_candidate at top-level to
                        # simplify frontend parsing and make the API resilient
                        # to formatting differences from upstream LLMs.
                        try:
                            resp_json['normalized_candidate'] = normalized
                            # Indicate that this response originated from the
                            # upstream LLM provider (even if we synthesized a
                            # normalized candidate from its free-form text).
                            resp_json['used_real_llm'] = True
                        except Exception:
                            pass
                        # write back into structure
                        content['parts'] = parts
                        cand[0]['content'] = content
                        resp_json['candidates'] = cand
                else:
                    # No candidates found in upstream response; synthesize a
                    # minimal normalized candidate from the original payload so
                    # the frontend always receives structured data.
                    try:
                        prompt_text = ''
                        if isinstance(payload, dict):
                            contents = payload.get('contents') or payload.get('messages')
                            if contents and isinstance(contents, list) and len(contents) > 0:
                                first = contents[0]
                                if isinstance(first, dict):
                                    parts = first.get('parts') or []
                                    if parts and isinstance(parts, list) and len(parts) > 0:
                                        p0 = parts[0]
                                        if isinstance(p0, dict):
                                            prompt_text = p0.get('text','')
                                        else:
                                            prompt_text = str(p0)
                                    else:
                                        prompt_text = first.get('text','') or ''
                                else:
                                    prompt_text = str(first)
                        if not prompt_text:
                            prompt_text = str(payload)[:200]
                    except Exception:
                        prompt_text = str(payload)

                    normalized = {
                        'narrative': f"Auto-generated narrative from request: {prompt_text[:200]}",
                        'image_prompt': f"{prompt_text[:160]} -- photorealistic cinematic",
                        'summary_point': f"Auto summary: {prompt_text[:80]}"
                    }
                    try:
                        resp_json['normalized_candidate'] = normalized
                        # Upstream call succeeded; mark that a real LLM was used
                        resp_json['used_real_llm'] = True
                    except Exception:
                        pass
            except Exception:
                # If any post-processing fails, ignore and return original provider response
                pass

            return jsonify(resp_json), 200
        except Exception as upstream_err:
            # Log upstream error on server side (print for now). Always fall
            # back to a deterministic mock response so the frontend can
            # continue working and an image can still be generated from the
            # synthesized visual prompt. This makes the app resilient during
            # network/provider outages and matches the user's expectation of
            # always producing a prompt+image.
            try:
                print('LLM provider error, falling back to mock LLM:', str(upstream_err))
            except Exception:
                pass

            # Build a simple mock body (same format used by LLM_PROVIDER='mock')
            try:
                prompt_text = ''
                if isinstance(payload, dict):
                    contents = payload.get('contents') or payload.get('messages')
                    if contents and isinstance(contents, list) and len(contents) > 0:
                        first = contents[0]
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

            # Synthesize a richer fallback narrative when upstream LLM fails
            narrative = _synthesize_narrative(prompt_text, paragraphs=4)
            image_prompt = f"{prompt_text[:160]} -- photorealistic cinematic"
            summary_point = narrative.split('\n')[0][:160]

            mock_body = {
                'candidates': [
                    {
                        'content': {
                            'parts': [
                                { 'text': json.dumps({
                                    'narrative': narrative,
                                    'image_prompt': image_prompt,
                                    'summary_point': summary_point
                                }) }
                            ]
                        }
                    }
                ]
            }
            # Also expose normalized_candidate for client robustness and
            # indicate that this is a fallback (not generated by a real LLM)
            try:
                mock_body['normalized_candidate'] = {
                    'narrative': narrative,
                    'image_prompt': image_prompt,
                    'summary_point': summary_point
                }
                mock_body['used_real_llm'] = False
            except Exception:
                pass
            return jsonify(mock_body), 200
            

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

        GEMINI_API_KEY = current_app.config.get('GEMINI_API_KEY')
        IMAGE_API_URL = current_app.config.get('IMAGE_API_URL')

        # Route to external Imagen API
        # If a 'free' provider is selected, generate a free placeholder image
        # from Picsum (no API key required). We use a deterministic seed based
        # on the prompt so repeated requests for the same prompt return the
        # same image.
        provider = current_app.config.get('IMAGE_PROVIDER', 'google')
        alternate_url = current_app.config.get('ALTERNATE_IMAGE_API_URL')

        # Determine prompt and requested sample count for caching
        prompt_text = _extract_prompt_from_payload(payload)
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
                st_resp = requests.post(stability_url, headers=headers, json=body, timeout=60)
                st_resp.raise_for_status()
            except requests.exceptions.HTTPError:
                try:
                    return jsonify({'error': st_resp.json()}), st_resp.status_code
                except Exception:
                    return jsonify({'error': 'Stability API Error'}), 502
            except Exception as e:
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
                    return jsonify({'error': 'No image returned by Stability API.'}), 502

                # persist to cache
                try:
                    _persist_image_cache(cache_key, [b64], prompt_text)
                except Exception:
                    pass

                return jsonify({'predictions': [{'bytesBase64Encoded': b64}]}), 200
            except Exception as e:
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
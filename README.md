````markdown
Story Generator - Local Development

This project is a small Flask app that uses an LLM to produce narrative + visual prompts and then generates images. For local development we provide a free Picsum image fallback so you can iterate quickly without paying for image APIs.

Quick goals covered here:
- Use a real LLM (Google Gemini / Generative Language API) to produce narrative and image prompts.
- Use Picsum for image content (free) so images are generated without cloud billing.

Setup (Windows, cmd.exe)
1. Create and activate your virtualenv (if not already):

```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and add your real keys if you want the real LLM/image providers:

```cmd
copy .env.example .env
rem Edit .env and set GEMINI_API_KEY or STABILITY_API_KEY as needed
```

Important env options (you can set them in the terminal or in `.env`):
- GEMINI_API_KEY: your Google Generative Language / Gemini API key (for real narrative generation)
- LLM_PROVIDER: `gemini` (use real LLM) or `mock` (use the deterministic mock LLM)
- IMAGE_PROVIDER: `google` (Imagen), `stability` (Stability.ai), `local_auto` (AUTOMATIC1111), or `free` (Picsum placeholder)
- USE_MOCK_FALLBACK: `False` to force provider errors to surface; `True` to fallback to mock LLM
- USE_IMAGE_FALLBACK: `False` to let image API errors surface; `True` to return a tiny placeholder
 - IMAGE_CACHE_TTL_SECONDS: how long (in seconds) generated images are kept in the local disk cache (default: 86400 = 24 hours). Set this to 0 to disable TTL-based expiration.

Run the app (examples):
- Use real Gemini LLM and Picsum for free images (recommended workflow):

```cmd
set GEMINI_API_KEY=your_gemini_key_here
set LLM_PROVIDER=gemini
set IMAGE_PROVIDER=free
set USE_MOCK_FALLBACK=False
set USE_IMAGE_FALLBACK=False
venv\Scripts\python.exe app.py
```

- Use mock LLM + free Picsum (safe local dev):

```cmd
set LLM_PROVIDER=mock
set IMAGE_PROVIDER=free
set USE_MOCK_FALLBACK=True
set USE_IMAGE_FALLBACK=True
venv\Scripts\python.exe app.py
```

Verify provider status

```cmd
curl http://127.0.0.1:5000/api/ai/status
```
This returns JSON like:

{
  "image_provider": "free",
  "llm_provider": "gemini",
  "use_mock_fallback": false,
  "has_gemini_key": true
}

Notes & troubleshooting
- Imagen image generation requires a billed Google Cloud project. If you set IMAGE_PROVIDER=google and you get billing errors, switch to `free` (Picsum) or `stability`.
- Keep real keys out of source control. Use `.env` for local development and never commit it.
- If you want me to start the server from here with a key you provide in the terminal, paste it into the terminal temporarily and I will start and verify the endpoints; I will not store your secret.

Next steps I can take for you
- Add a UI toggle to choose "Use real LLM" vs "Mock LLM".
- Persist generated images server-side in `static/uploads/` and store metadata in the DB.
- Integrate Google OAuth for login (requires OAuth client config).
- Migrate the in-memory auth/session storage to SQLite (I already prepared SQLAlchemy models earlier — I can finish and enable them once you're ready).

If you want me to start the app now with your Gemini key (paste it into your terminal) say "Run now with my GEMINI key" and paste the key when prompted.

---

## Running locally (quick)

Below is a concise helper you can paste into the README to document the recent provider support and the frontend behavior.

1) Create a virtualenv and install dependencies

```bash
python -m venv venv
# Windows (cmd.exe)
venv\\Scripts\\activate
pip install -r requirements.txt
```

2) Environment variables
Create a `.env` file in the project root with the following keys (examples):

- GEMINI_API_KEY=your_google_gemini_api_key_here
- STORY_API_URL=https://generativelanguage.googleapis.com/v1beta2/models/your-model:generate
- STABILITY_API_KEY=your_stability_api_key_here
- STABILITY_ENGINE=stable-diffusion-v1-5  # or your engine
- IMAGE_PROVIDER=stability  # options: stability, free, local_auto, google
- LLM_PROVIDER=gemini  # options: gemini, mock
- USE_IMAGE_FALLBACK=False  # True to enable deterministic Picsum fallback on image errors
- FALLBACK_IMAGE_BASE64=... (optional tiny base64 image string)
- AUTOMATIC1111_URL=http://127.0.0.1:7860  # when using local_auto provider

Notes:
- If you don't have Gemini/Stability keys you can set `LLM_PROVIDER=mock` and `IMAGE_PROVIDER=free`.
- The app reads `.env` via python-dotenv on startup; restart the server after changing `.env`.

Example `.env` snippet to tune cache TTL (optional):

```env
# Keep cached images for 24 hours (default)
IMAGE_CACHE_TTL_SECONDS=86400

# Set to 0 to disable TTL expiry (cached files will remain until manually removed)
# IMAGE_CACHE_TTL_SECONDS=0
```

3) Start the server (Windows cmd.exe)

```cmd
venv\\Scripts\\python.exe app.py
```

Important: the dev run used here disables Flask's auto-reloader so background runs are stable. If you change `.env`, restart the server.

4) Quick E2E / smoke test

```cmd
venv\\Scripts\\python.exe tools\\run_e2e_local.py
```

5) Frontend notes
- The backend always exposes a `normalized_candidate` (object with `narrative`, `image_prompt`, `summary_point`) in the `/api/ai/generate-prompt` response so the frontend can parse results reliably.
- To prevent automatic image generation after a narrative, the frontend checks localStorage key `AUTO_GENERATE_IMAGE`. Default is off. To enable in the browser console:

```js
localStorage.setItem('AUTO_GENERATE_IMAGE','true')
location.reload()
```
- Generated images are saved to `static/uploads/` with a stable filename derived from the prompt. If saving fails, the API still returns base64 image bytes.

6) Troubleshooting
- If image calls return a billed/account error for Google Imagen, enable `USE_IMAGE_FALLBACK=True` to use deterministic Picsum fallbacks; otherwise configure `IMAGE_PROVIDER=stability` and set `STABILITY_API_KEY`.
- Check `/api/ai/status` for non-secret provider info: `image_provider`, `llm_provider`, `has_gemini_key`.
- Server logs include debug prints like `GENERATE_PROMPT_START`, `GENERATE_PROMPT_RAW`, and `GENERATE_PROMPT_NORMALIZED`.

---

Want me to add this section to the README and push it? I can commit to `main` or create a branch + PR if you prefer.

````
Story Generator - Local Development

This project is a small Flask app that uses an LLM to produce narrative + visual prompts and then generates images. For local development we provide a free Picsum image fallback so you can iterate quickly without paying for image APIs.

Quick goals covered here:
- Use a real LLM (Google Gemini / Generative Language API) to produce narrative and image prompts.
- Use Picsum for image content (free) so images are generated without cloud billing.

Setup (Windows, cmd.exe)
1. Create and activate your virtualenv (if not already):

```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and add your real keys if you want the real LLM/image providers:

```cmd
copy .env.example .env
rem Edit .env and set GEMINI_API_KEY or STABILITY_API_KEY as needed
```

Important env options (you can set them in the terminal or in `.env`):
- GEMINI_API_KEY: your Google Generative Language / Gemini API key (for real narrative generation)
- LLM_PROVIDER: `gemini` (use real LLM) or `mock` (use the deterministic mock LLM)
- IMAGE_PROVIDER: `google` (Imagen), `stability` (Stability.ai), `local_auto` (AUTOMATIC1111), or `free` (Picsum placeholder)
- USE_MOCK_FALLBACK: `False` to force provider errors to surface; `True` to fallback to mock LLM
- USE_IMAGE_FALLBACK: `False` to let image API errors surface; `True` to return a tiny placeholder

Run the app (examples):
- Use real Gemini LLM and Picsum for free images (recommended workflow):

```cmd
set GEMINI_API_KEY=your_gemini_key_here
set LLM_PROVIDER=gemini
set IMAGE_PROVIDER=free
set USE_MOCK_FALLBACK=False
set USE_IMAGE_FALLBACK=False
venv\Scripts\python.exe app.py
```

- Use mock LLM + free Picsum (safe local dev):

```cmd
set LLM_PROVIDER=mock
set IMAGE_PROVIDER=free
set USE_MOCK_FALLBACK=True
set USE_IMAGE_FALLBACK=True
venv\Scripts\python.exe app.py
```

Verify provider status

```cmd
curl http://127.0.0.1:5000/api/ai/status
```
This returns JSON like:

{
  "image_provider": "free",
  "llm_provider": "gemini",
  "use_mock_fallback": false,
  "has_gemini_key": true
}

Notes & troubleshooting
- Imagen image generation requires a billed Google Cloud project. If you set IMAGE_PROVIDER=google and you get billing errors, switch to `free` (Picsum) or `stability`.
- Keep real keys out of source control. Use `.env` for local development and never commit it.
- If you want me to start the server from here with a key you provide in the terminal, paste it into the terminal temporarily and I will start and verify the endpoints; I will not store your secret.

Next steps I can take for you
- Add a UI toggle to choose "Use real LLM" vs "Mock LLM".
- Persist generated images server-side in `static/uploads/` and store metadata in the DB.
- Integrate Google OAuth for login (requires OAuth client config).
- Migrate the in-memory auth/session storage to SQLite (I already prepared SQLAlchemy models earlier — I can finish and enable them once you're ready).

If you want me to start the app now with your Gemini key (paste it into your terminal) say "Run now with my GEMINI key" and paste the key when prompted.
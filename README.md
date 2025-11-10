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
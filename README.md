# 📖 StoryCanvas - AI Narrative & Image Generator

> An intelligent storytelling platform that combines cutting-edge LLM technology with AI-powered image generation to create immersive narrative experiences.

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-2.0%2B-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Stability AI](https://img.shields.io/badge/image-Stability%20AI-blueviolet.svg)](https://stability.ai/)
[![Groq LLM](https://img.shields.io/badge/llm-Groq-orange.svg)](https://groq.com/)

## 🎯 Overview

StoryCanvas is a web-based interactive fiction platform that leverages multiple AI providers to generate compelling narratives and matching visual imagery. The application features a modern cyberpunk UI, real-time LLM processing, and seamless image generation with intelligent fallback mechanisms.

### Key Features

✨ **Multi-Provider LLM Support**
- Groq (llama-3.3-70b) - Fast, free tier available
- Google Gemini (gemini-2.5-flash)
- OpenAI (GPT-3.5/GPT-4)
- Anthropic (Claude)

🎨 **Advanced Image Generation**
- Stability AI (SDXL 1024x1024)
- Intelligent fallback to Picsum Photos
- Editable visual prompts
- Cached results for performance

🔐 **Authentication & Storage**
- Firebase Authentication integration
- Google OAuth Sign-In support
- Persistent story sessions
- User-specific story management

🎭 **Professional UI/UX**
- Cyberpunk-themed responsive design
- Real-time generation feedback
- Visual staging area for review
- Dark mode with accent colors

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Windows/Linux/macOS
- API keys for LLM/image providers (see below)

### Installation

1. **Clone and Setup Environment**

```bash
git clone https://github.com/shashank-tomar0/AI-BASED-STORY-IMAGE-GENERATOR.git
cd story-generator

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/macOS)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

2. **Configure Environment Variables**

```bash
# Copy template
cp .env.example .env

# Edit .env with your API keys
```

### Environment Configuration

Create a `.env` file in the project root:

```env
# LLM Provider Configuration
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Image Generation Configuration
IMAGE_PROVIDER=stability
STABILITY_API_KEY=your_stability_api_key_here
STABILITY_ENGINE=stable-diffusion-xl-1024-v1-0

# Feature Flags
USE_MOCK_FALLBACK=False
USE_IMAGE_FALLBACK=True
IMAGE_CACHE_TTL_SECONDS=86400

# Flask Configuration
SECRET_KEY=your_secret_key_here

# Firebase Configuration (optional)
FIREBASE_API_KEY=your_firebase_api_key_here
FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
FIREBASE_PROJECT_ID=your-project-id

# OAuth Configuration (optional)
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_OAUTH_REDIRECT=http://127.0.0.1:5000/api/auth/google/callback
```

### Running the Application

```bash
# Start Flask development server
python app.py

# Server runs on http://127.0.0.1:5000
```

## 📋 API Providers Guide

### LLM Providers

| Provider | Free Tier | Rate Limit | Speed | Model |
|----------|-----------|-----------|-------|-------|
| **Groq** | ✅ Yes | 30 req/min | ⚡ Fastest | llama-3.3-70b |
| Gemini | ⚠️ Limited | 15 req/min | Fast | gemini-2.5-flash |
| OpenAI | ❌ Paid | Varies | Medium | gpt-3.5-turbo |
| Anthropic | ⚠️ Limited | Varies | Medium | claude-3-haiku |

**Recommended**: Start with Groq for fastest free inference.

### Image Providers

| Provider | Free Tier | Credits | Quality |
|----------|-----------|---------|---------|
| **Stability AI** | ⚠️ $5 free trial | ~25 images | Excellent |
| Picsum (Fallback) | ✅ Yes | Unlimited | Good |
| Google Imagen | ❌ Paid | N/A | Excellent |

**Setup Instructions**:
- [Groq API](https://console.groq.com/)
- [Stability AI API](https://platform.stability.ai/)
- [Google Gemini API](https://aistudio.google.com/apikey)
- [OpenAI API](https://platform.openai.com/api-keys)

## 🏗️ Project Structure

```
story-generator/
├── app.py                          # Flask application entry point
├── ai_service.py                   # LLM & image generation routes
├── auth.py                         # Authentication blueprint
├── story_manager.py                # Story session management
├── config.py                       # Configuration loading
├── models.py                       # Database models (SQLAlchemy)
│
├── templates/
│   └── index.html                  # Main UI template
│
├── static/
│   ├── js/
│   │   ├── main.js                # Frontend logic
│   │   ├── firebase-init.js       # Firebase setup
│   │   └── ui-enhancements.js     # UI utilities
│   ├── css/
│   │   └── prod.css               # Production styles
│   └── uploads/                   # Generated images cache
│
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
└── README.md                       # This file
```

## 🔌 API Endpoints

### Story Generation
- `POST /api/ai/generate-prompt` - Generate narrative from prompt
- `POST /api/ai/generate-image-async` - Async image generation
- `GET /api/ai/generate-image-job/<job_id>` - Check image generation status
- `GET /api/ai/status` - Get provider configuration status

### Story Management
- `GET /api/story/load-session` - Load user's story session
- `POST /api/story/save-session` - Save story progress
- `GET /api/ai/cache/list` - List cached images

### Authentication
- `POST /api/auth/firebase` - Firebase authentication
- `POST /api/auth/logout` - Logout user
- `GET /api/auth/google/callback` - Google OAuth callback

## 💡 Usage Examples

### Generate a Story

```bash
curl -X POST http://127.0.0.1:5000/api/ai/generate-prompt \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "payload": {
      "contents": [{
        "parts": [{"text": "A robot discovering humanity"}]
      }],
      "generationConfig": {"temperature": 0.8}
    }
  }'
```

### Generate Image from Narration

```bash
curl -X POST http://127.0.0.1:5000/api/ai/generate-image-async \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "payload": {
      "contents": [{
        "parts": [{"text": "Visual prompt describing the scene"}]
      }]
    }
  }'
```

### Check Generation Status

```bash
curl http://127.0.0.1:5000/api/ai/generate-image-job/JOB_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🧪 Testing

### Run E2E Tests

```bash
python tests/e2e_run.py
```

### Test LLM Integration

```bash
python test_groq.py
python test_stability_key.py
```

### Verify Configuration

```bash
python verify_config.py
```

## 🛠️ Development

### Code Structure

- **Frontend**: Vanilla JavaScript with modern ES6+ features
- **Backend**: Flask blueprints for modular organization
- **Database**: SQLAlchemy ORM with optional SQLite
- **Async Operations**: Threading for background image generation

### Adding New LLM Providers

1. Add provider to `config.py`
2. Create `_call_provider_name()` function in `ai_service.py`
3. Update `generate_prompt()` router logic
4. Test with `test_provider.py`

### Performance Optimization

- Image caching with TTL (24h default)
- Async job processing for image generation
- Groq LLM optimized for speed (70B+ inference ~2-3s)
- Stability AI with automatic Picsum fallback

## 🐛 Troubleshooting

### Rate Limit Errors

```
[GROQ ERROR] Max retries exceeded
```

**Solution**: Wait 1-2 minutes or switch to Gemini provider
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
```

### Image Generation Failures

```
[STABILITY] ❌ API Error
```

**Solution**: Check Stability API credits and fallback is enabled
```env
USE_IMAGE_FALLBACK=True  # Falls back to Picsum
```

### Authentication Issues

Check Firebase configuration and ensure credentials are valid:
```bash
python test_firebase_config.py
```

## 📊 Logs & Debugging

Server logs include debug prefixes:
- `[LLM]` - Language model operations
- `[GROQ]` - Groq API calls
- `[STABILITY]` - Stability AI calls
- `[IMAGE]` - Image generation workflow

Enable verbose logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### License Summary

- ✅ Commercial use
- ✅ Modification
- ✅ Distribution
- ✅ Private use
- ⚠️ Liability: Provided as-is
- ⚠️ Warranty: None provided

## 👥 Authors

- **Shashank Tomar** - Lead Developer
- Project initiated: December 2025

## 🔗 Links & Resources

- [Groq API Documentation](https://console.groq.com/docs)
- [Stability AI API](https://platform.stability.ai/docs)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Firebase Documentation](https://firebase.google.com/docs)

## 📞 Support

For issues, questions, or suggestions:
- 🐛 Issues: [GitHub Issues](https://github.com/shashank-tomar0/AI-BASED-STORY-IMAGE-GENERATOR/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/shashank-tomar0/AI-BASED-STORY-IMAGE-GENERATOR/discussions)

## 🎉 Acknowledgments

- Groq for fast, free LLM inference
- Stability AI for high-quality image generation
- Firebase for authentication infrastructure
- Flask community for excellent web framework

---

**Made with ❤️ by Shashank Tomar**

⭐ If you find this project helpful, please give it a star!

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
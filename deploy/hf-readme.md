---
title: NEXUS AI
emoji: 🪄
colorFrom: purple
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: AI presentation generator — research-driven slide decks
---

# NEXUS AI — backend

FastAPI + Celery slide-generation backend. Single-container Hugging Face
Space: Redis broker + Celery worker + uvicorn, SQLite persistence.

The React frontend is hosted separately (Vercel) and calls this Space's
`/api/*` endpoints.

## Configuration

Set these as **Space secrets** (Settings → Repository secrets):

- `NEXUS_SECRETS_KEY` — Fernet master key; decrypts the committed `.env.enc`
  containing all provider keys at boot. (Recommended — one secret.)

…or set each key individually instead of using `.env.enc`:

- `GROQ_API_KEY`, `NVIDIA_NIM_API_KEY`, `SAMBANOVA_API_KEY`
- `SECRET_KEY`, `NEXUS_API_KEY`
- `FRONTEND_URL` (the Vercel URL, for CORS)
- optional: `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `SERPER_API_KEY`

Health check: `GET /api/health`.

Configuration reference: https://huggingface.co/docs/hub/spaces-config-reference

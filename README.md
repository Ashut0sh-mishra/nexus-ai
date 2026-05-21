# NEXUS

Production-grade AI slide generator — same stack as Manus AI.

## 🚀 Live

| | URL |
| --- | --- |
| **Frontend (app)** | https://nexus-ai-alpha-jade.vercel.app |
| **Backend (API)** | https://ashu010-nexus-ai.hf.space |
| **API health** | https://ashu010-nexus-ai.hf.space/api/health |

- **Frontend** is hosted on **Vercel** (static Vite build).
- **Backend** runs on a **Hugging Face Space** (Docker: FastAPI + in-process
  Celery + Redis + SQLite). See [`DEPLOY.md`](DEPLOY.md) for the full free-tier
  deploy guide, plus [`render.yaml`](render.yaml) / [`fly.toml`](fly.toml) for
  alternative hosts.

> The free Hugging Face Space sleeps when idle, so the first request may
> cold-start (~30s). Generated decks live in ephemeral storage — set a free
> Neon Postgres `DATABASE_URL` for persistence.

---

## Stack

- **Frontend** — React 18 + Vite + Tailwind (Manus-style dark UI)
- **Backend** — FastAPI + Celery + PostgreSQL + Redis
- **AI** — multi-provider chain (Groq / NVIDIA NIM / SambaNova; Anthropic/OpenAI optional)
- **Search** — Tavily (primary) + Serper (fallback)
- **Browser** — Playwright (Chromium, opt-in via `BROWSER_ENABLED=true`)
- **Storage** — Cloudflare R2 (with local fallback)
- **Auth** — JWT + Google OAuth; shared-key + per-IP rate-limit lock-down for public deploys

---

## Quick Start

### 1. Clone & configure

```bash
git clone <this-repo> nexus
cd nexus
cp .env.example .env
```

Edit `.env` and fill in at minimum:

| key | required | where |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | ✅ yes | console.anthropic.com/settings/keys |
| `SECRET_KEY` | ✅ yes | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `TAVILY_API_KEY` | optional | app.tavily.com (research step is skipped without it) |
| everything else | optional | only needed for production deploys |

### 2. One-command boot (Docker)

```bash
# Linux / macOS
./start.sh
# Windows
start.bat
```

This runs `docker compose up -d postgres redis backend worker` then `npm run dev` for the frontend.

Open <http://localhost:5173>.

### 3. Manual / dev workflow

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
alembic upgrade head
uvicorn main:app --reload
```

**Worker** (separate terminal)
```bash
cd backend
celery -A workers.celery_app.celery worker --loglevel=info
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

---

## Architecture

```
        ┌─────────────┐    POST /api/generate     ┌──────────────┐
        │  Frontend   │ ─────────────────────────▶│   FastAPI    │
        │  (Vite)     │ ◀────── SSE /api/status   │   backend    │
        └─────────────┘                           └──────┬───────┘
                                                         │ enqueue
                                                         ▼
                                                  ┌──────────────┐
                                                  │ Celery / Redis│
                                                  └──────┬───────┘
                                                         │
                                                         ▼
                          ┌──────────────────────────────────────────┐
                          │  Agent Loop (CodeAct, 6 steps)           │
                          │  analyze → search → plan → generate      │
                          │           → assemble → save              │
                          └──────────┬───────────────────┬───────────┘
                                     │                   │
                            Claude (Anthropic)     Tavily / Serper / browser-use
```

### 6-step agent loop (Manus-style)

1. **ANALYZE** — understand topic
2. **SEARCH** — Tavily → Serper fallback (skipped if no keys)
3. **PLAN** — Claude builds `todo.md`-style outline
4. **GENERATE** — Claude writes each slide (`claude-sonnet-4-6`)
5. **ASSEMBLE** — combine to final JSON
6. **SAVE** — persist to Postgres, mark task `done`

Each step pushes an SSE event with progress `%` and message.

### Slide layouts (6)

`title`, `bullets`, `two-col`, `quote`, `stats`, `closing`.

### API

| method | path | purpose |
| --- | --- | --- |
| `POST` | `/api/generate` | enqueue generation task |
| `GET`  | `/api/status/{id}` | SSE progress stream |
| `GET`  | `/api/slides/{id}` | full slide JSON |
| `POST` | `/api/export/pptx` | download .pptx |
| `POST` | `/api/export/pdf`  | download .pdf |
| `POST` | `/api/share` | create share token |
| `GET`  | `/api/share/{token}` | public deck view |
| `POST` | `/api/auth/register` | email signup |
| `POST` | `/api/auth/login` | JWT login |
| `GET`  | `/api/auth/google` | Google OAuth start |

Full OpenAPI docs at <http://localhost:8000/docs>.

---

## Project Layout

```
nexus/
├── .env / .env.example
├── docker-compose.yml
├── start.sh / start.bat
├── frontend/          React + Vite + Tailwind
└── backend/           FastAPI + Celery
    ├── api/routes/    generate, status, slides, export, share, auth
    ├── agent/         loop, planner, tools, memory, prompts
    ├── services/      claude, search, browser, export, storage, auth
    ├── database/      models + Alembic migrations
    ├── workers/       Celery tasks
    └── sandbox/       Docker code-execution sandbox
```

---

## Production notes

- Set `ENVIRONMENT=production` to switch Claude routing to `claude-sonnet-4-6`.
- Configure Cloudflare R2 to enable cloud-hosted exports (otherwise files live in `backend/storage/`).
- Set `SENTRY_DSN` for error tracking.
- Run Alembic migrations on deploy: `alembic upgrade head`.

---

## Workspace & test commands (truthful)

This folder is `D:\nexus-ai-1\nexus-ai`. A sibling clone at `D:\nexus-ai-gh`
or similar uses a different Docker Compose project name and will NOT see
edits made here. To verify which workspace your containers belong to:

```powershell
pwsh ./scripts/doctor.ps1
```

The compose project is pinned to `nexus-ai-1` via the top-level `name:` key in
`docker-compose.yml`.

### Backend tests

```powershell
pwsh ./scripts/test-backend.ps1
```

Builds `nexus-ai-backend:latest` and `nexus-ai-backend:dev` if missing, then
runs `pytest -q` against the local `backend/` mount with an in-memory SQLite
database. Dev-only deps live in `backend/requirements-dev.txt` and are NOT
installed in the production image.

### Frontend layout verification

```powershell
cd frontend
npm run verify:layouts
```

### Frontend build

```powershell
cd frontend
npm run build
```


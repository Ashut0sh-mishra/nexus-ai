# NEXUS

Production-grade AI slide generator — same stack as Manus AI.

- **Frontend** — React 18 + Vite + Tailwind (Manus-style dark UI)
- **Backend** — FastAPI + Celery + PostgreSQL + Redis
- **AI** — Claude `claude-sonnet-4-6` (prod) / `claude-opus-4-7` (dev)
- **Search** — Tavily (primary) + Serper (fallback)
- **Browser** — `browser-use` + Playwright (CodeAct sandbox)
- **Storage** — Cloudflare R2 (with local fallback)
- **Auth** — JWT + Google OAuth

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

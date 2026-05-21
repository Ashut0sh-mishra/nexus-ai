# NEXUS — Free Production Deploy Guide

## ⭐ Chosen path: Hugging Face Spaces (backend) + Vercel (frontend)

Same setup as agri-analyze: a GitHub Action pushes the backend to a HF Space
on every push to `main`; the frontend deploys to Vercel. **Validated locally** —
the HF container (Redis + Celery + uvicorn + SQLite, port 7860) boots green and
the security gate works (health 200, generate 403 without key / 202 with key).

### One-time setup (you do this once — ~5 min)

**A. Create the HF Space**
1. https://huggingface.co/new-space → Owner `ashu010`, Space name **`nexus-ai`**,
   **SDK: Docker**, visibility your choice → Create.
2. (It starts empty; the GitHub Action fills it.)

**B. Add your HF token to this repo's GitHub secrets**
1. Get/confirm your token: https://huggingface.co/settings/tokens (write access).
   (You already have one — it powers agri-analyze's deploy.)
2. GitHub → `Ashut0sh-mishra/nexus-ai` → Settings → Secrets and variables →
   Actions → New repository secret:
   - Name: `HF_TOKEN`  ·  Value: your HF write token.
3. Also create a GitHub **Environment** named `production` (Settings →
   Environments → New) — the workflow references it. No protection rules needed.

**C. Set the Space's runtime secrets** (HF Space → Settings → Repository secrets)

Recommended (one secret unlocks everything via the committed `.env.enc`):
- `NEXUS_SECRETS_KEY` = your Fernet master key (see § Encrypted secrets below).

…or set each individually instead:
- `SECRET_KEY`, `NEXUS_API_KEY`, `GROQ_API_KEY`, `NVIDIA_NIM_API_KEY`,
  `SAMBANOVA_API_KEY`, and `FRONTEND_URL` (your Vercel URL, for CORS).
- optional: `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `SERPER_API_KEY`.

### Deploy

- **Backend:** push to `main` (or run the *Deploy backend to HuggingFace
  Spaces* workflow manually) → the Action syncs `backend/` into the Space →
  HF builds the Docker image → live at `https://ashu010-nexus-ai.hf.space`.
  Verify: `curl https://ashu010-nexus-ai.hf.space/api/health`.
- **Frontend (Vercel):** import `Ashut0sh-mishra/nexus-ai`, Root Directory
  `frontend`. Env vars:
  - `VITE_BACKEND_URL = https://ashu010-nexus-ai.hf.space`
  - `VITE_NEXUS_KEY = ` (same value as the backend's `NEXUS_API_KEY`)
  Deploy → `https://<app>.vercel.app`. Then set the Space secret
  `FRONTEND_URL` to that Vercel URL and restart the Space (CORS).

### Encrypted secrets (the "encrypt everything" part)

All keys can live in the repo **encrypted** — only the master key is a host
secret. From `backend/`:

```bash
python -m scripts.secrets_crypt keygen                 # -> MASTER_KEY (save it)
# put your rotated keys in backend/.env, then:
python -m scripts.secrets_crypt encrypt --key MASTER_KEY   # -> backend/.env.enc
git add backend/.env.enc && git commit -m "add encrypted secrets" && git push
```

Then set `NEXUS_SECRETS_KEY=MASTER_KEY` as the only Space secret. On boot,
`secrets_loader` decrypts `.env.enc` into the environment (Fernet / AES). A
host env var always wins over the file, so you can still override any single
value from the Space dashboard. Wrong key → fails closed, no plaintext leak.

### HF free-tier caveats
- SQLite storage is **ephemeral** — decks reset when the Space rebuilds/sleeps.
  Fine for a demo; for persistence point `DATABASE_URL` at a free Neon Postgres.
- Spaces sleep after inactivity → first request cold-starts.

---

## Other free paths

Two more options if you'd rather not use HF:

- **Render Blueprint (FASTEST — recommended, ~5 min, no CLI)** — one repo
  connect provisions backend+worker, frontend, Postgres, and Redis from the
  committed `render.yaml`. See **§ Render fast path** immediately below.
- **Fly.io + Vercel** (always-on, no cold starts, needs CLI) — see § A onward.

---

## ⚡ Render fast path (do this)

Everything is committed (`render.yaml`, `backend/start-render.sh`). You only
sign in and paste secrets — no CLI, no Docker, no local tooling.

### Step 1 — rotate keys, then have these ready

The exposed keys MUST be rotated first (see § 0 below). Then keep these values
to paste in step 3. Your freshly generated app secrets (use these as-is):

```
SECRET_KEY=ff5166ea92051af656852b40ff658d7dbc3f186303d20b8aeff5501059c89811
NEXUS_API_KEY=WCifgvDIHcCpeqGqjXyiD--ZCtbrMpiaHjlnV2wYC6RgRnm3WmyoLp_vmjqX0EmI
```

(If you'd rather not reuse secrets printed in a doc, regenerate with
`python -c "import secrets;print(secrets.token_urlsafe(48))"` — just use the
SAME `NEXUS_API_KEY` for both the backend env var and the frontend
`VITE_NEXUS_KEY`.)

### Step 2 — create the Blueprint

1. Sign up at https://render.com with your GitHub account.
2. Dashboard → **New +** → **Blueprint**.
3. Pick the repo **`Ashut0sh-mishra/nexus-ai`** → **Apply**.
4. Render reads `render.yaml` and creates 4 things: `nexus-backend`,
   `nexus-frontend`, `nexus-db` (Postgres), `nexus-redis`. `DATABASE_URL`
   and `REDIS_URL` are wired automatically.

### Step 3 — paste the secrets

When prompted (or under each service → Environment), set the `sync: false`
vars on **nexus-backend**:

| Key | Value |
|---|---|
| `SECRET_KEY` | (from step 1) |
| `NEXUS_API_KEY` | (from step 1) |
| `GROQ_API_KEY` | your **rotated** key |
| `NVIDIA_NIM_API_KEY` | your **rotated** key |
| `SAMBANOVA_API_KEY` | your key |
| `ANTHROPIC_API_KEY` | optional (paid fallback) |
| `TAVILY_API_KEY` | optional (web research) |
| `SERPER_API_KEY` | optional |

### Step 4 — connect the two URLs

After the first deploy Render shows your hostnames
(`https://nexus-backend.onrender.com`, `https://nexus-frontend.onrender.com`).

- On **nexus-backend** set: `FRONTEND_URL = https://nexus-frontend.onrender.com`
- On **nexus-frontend** set:
  - `VITE_BACKEND_URL = https://nexus-backend.onrender.com`
  - `VITE_NEXUS_KEY = ` (the same `NEXUS_API_KEY` value)
- Click **Manual Deploy → Clear cache & deploy** on both (so the frontend
  bundle bakes in the key, and CORS picks up the frontend origin).

### Step 5 — verify

```
curl https://nexus-backend.onrender.com/api/health     # {"status":"ok",...}
open  https://nexus-frontend.onrender.com              # the app
```

Done. `git push main` now auto-redeploys both (autoDeploy: true).

**Render free-tier caveats (acceptable for a demo / invite-only):**
- Backend spins down after ~15 min idle → first request after sleep cold-starts
  in ~30–60s. Fine for dogfooding; annoying for a public launch.
- Free Postgres expires after the trial window — migrate to **Neon** (free
  forever, § 1 below) when it does: just swap `DATABASE_URL`.
- 512MB RAM cap → Celery runs at concurrency=1 (set in `start-render.sh`).

For always-on with no cold starts, use the Fly.io path below instead.

---

# (Alternative) Fly.io + Vercel

100% free for low traffic. Backend + worker on **Fly.io** ($5/mo free credit),
frontend on **Vercel** (free), Postgres on **Neon** (free), Redis on
**Upstash** (free). Auto-deploys on every push to `main`.

---

## 0. URGENT — rotate exposed keys FIRST

`.env` was committed to the public repo (commit `dfafd37`). Every key below
is **compromised** and must be regenerated at its provider dashboard before
you deploy. Removing `.env` going forward does NOT purge git history — bots
have already scraped the old values.

| Key | Where to rotate |
|---|---|
| `GROQ_API_KEY` | https://console.groq.com/keys → revoke old, create new |
| `NVIDIA_NIM_API_KEY` | https://build.nvidia.com/ → API keys |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `OPENROUTER_API_KEY` | https://openrouter.ai/keys |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/settings/keys |
| `TAVILY_API_KEY` | https://app.tavily.com/ |
| `SERPER_API_KEY` | https://serper.dev/api-key |
| `UNFILTERED_API_KEY` | provider dashboard |
| `SECRET_KEY` | regenerate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` password | rotate when you provision Neon (new DB = new creds) |

After rotating, put the NEW values only in: your local `.env`, Fly secrets,
and Vercel env vars. Never in git.

### Optional: purge `.env` from git history

Cosmetic after the leak (rotation is what actually secures you), but if you
want a clean history:

```bash
pip install git-filter-repo
git filter-repo --path .env --invert-paths --force
git push origin main --force
```

⚠️ This rewrites every commit hash and force-pushes. Anyone who cloned must
re-clone. Do this only if you understand the consequences.

---

## 1. Provision the free datastores (~10 min)

### Neon (Postgres)
1. Sign up at https://neon.tech (GitHub login).
2. Create project → copy the **connection string** (looks like
   `postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require`).
3. Convert the scheme for async SQLAlchemy: replace `postgresql://` with
   `postgresql+asyncpg://` and drop `?sslmode=require` (asyncpg uses `ssl=`
   differently — Neon works without it on the pooled endpoint).

### Upstash (Redis)
1. Sign up at https://upstash.com.
2. Create a Redis database → copy the **`rediss://` URL** (TLS).

---

## 2. Deploy backend + worker to Fly.io (~15 min)

```bash
# Install the CLI (once)
curl -L https://fly.io/install.sh | sh        # macOS/Linux
# Windows PowerShell: iwr https://fly.io/install.ps1 -useb | iex

fly auth login
cd D:/nexus-ai-1/nexus-ai

# Create the app (uses the committed fly.toml). Pick your region in fly.toml
# first — primary_region = "iad" by default.
fly launch --no-deploy --copy-config --name nexus-ai

# Set ALL secrets (these never touch git). Use your ROTATED keys.
fly secrets set \
  SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')" \
  NEXUS_API_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  DATABASE_URL="postgresql+asyncpg://USER:PASS@ep-xxx.neon.tech/neondb" \
  REDIS_URL="rediss://default:PASS@xxx.upstash.io:6379" \
  GROQ_API_KEY="new-key" \
  NVIDIA_NIM_API_KEY="new-key" \
  SAMBANOVA_API_KEY="new-key" \
  ANTHROPIC_API_KEY="new-key" \
  TAVILY_API_KEY="new-key" \
  SERPER_API_KEY="new-key" \
  FRONTEND_URL="https://YOUR-APP.vercel.app"

# IMPORTANT: copy the NEXUS_API_KEY value you just generated — you need the
# exact same string for Vercel in step 3. Retrieve it any time with:
#   fly secrets list           (shows digests only, not values)
# So save it now when you generate it.

fly deploy
fly status            # confirm both 'app' and 'worker' machines are running
curl https://nexus-ai.fly.dev/api/health   # should return {"status":"ok",...}
```

Your backend is now at `https://nexus-ai.fly.dev` (or your chosen app name).

---

## 3. Deploy frontend to Vercel (~5 min)

1. Sign up at https://vercel.com (GitHub login).
2. **Add New Project** → import `Ashut0sh-mishra/nexus-ai`.
3. Set **Root Directory** = `frontend`.
4. Framework preset auto-detects Vite (the committed `frontend/vercel.json`
   pins build settings).
5. Add **Environment Variables**:
   | Name | Value |
   |---|---|
   | `VITE_BACKEND_URL` | `https://nexus-ai.fly.dev` |
   | `VITE_NEXUS_KEY` | the exact `NEXUS_API_KEY` from step 2 |
6. Deploy. You get `https://YOUR-APP.vercel.app`.
7. Go back and update the Fly secret so CORS matches:
   ```bash
   fly secrets set FRONTEND_URL="https://YOUR-APP.vercel.app"
   ```

Now only your Vercel frontend (carrying the matching key + allowed origin)
can call the backend. Random callers get 403; abusers hit the 20/hr rate cap.

---

## 4. Wire auto-deploy (~5 min)

The committed `.github/workflows/ci.yml` already:
- runs the backend test gate + frontend build + layout parity on every push/PR,
- deploys the backend to Fly.io on push to `main` (after gates pass).

To enable the Fly deploy step, add one GitHub secret:

1. Generate a Fly deploy token:
   ```bash
   fly tokens create deploy -x 999999h
   ```
2. GitHub repo → Settings → Secrets and variables → Actions → New secret:
   - Name: `FLY_API_TOKEN`
   - Value: the token from above.

Vercel's GitHub integration auto-deploys the frontend on every push to `main`
— no secret needed for that.

**Result:** `git push main` → tests run → backend deploys to Fly + frontend
deploys to Vercel. Fully automatic, fully free.

---

## 5. Custom domain (optional, ~10 min)

- **Frontend:** Vercel → Project → Settings → Domains → add `app.yourdomain.com`
  (free TLS, auto-renew).
- **Backend:** `fly certs add api.yourdomain.com` then add the shown CNAME at
  your DNS provider. Update `VITE_BACKEND_URL` in Vercel + redeploy.

---

## What's protected vs what's still open

**Protected now:**
- `.env` no longer tracked; secrets only in Fly/Vercel stores.
- Shared-key gate + CORS lock + per-IP rate limit (Phase 6AL `SecurityMiddleware`).

**Still open (acceptable for invite-only, fix before public launch):**
- The `VITE_NEXUS_KEY` is readable in the frontend JS bundle — it stops random
  scanners, not a determined attacker. Real per-user auth (Clerk free tier:
  https://clerk.com, or Supabase Auth) is the next upgrade.
- No paid AI fallback billing controls — set per-user quotas before opening up.
- Free tiers sleep / rate-limit under load — fine for dogfooding, not a launch.

---

## Cost summary

| Stage | Monthly |
|---|---|
| Invite-only dogfooding | **$0** (Fly $5 credit + Vercel/Neon/Upstash free tiers) |
| Public, paid AI fallback on | ~$30–90 (Fly + Anthropic usage; charge users to cover) |

# NEXUS — Free Production Deploy Guide

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

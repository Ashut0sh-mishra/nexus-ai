# syntax=docker/dockerfile:1.6
# ─── Stage 1: build wheels in an isolated layer ──────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps only — discarded after the wheel build.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libffi-dev \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip wheel --wheel-dir=/wheels -r requirements.txt


# ─── Stage 2: lean runtime image ─────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Runtime libs only — no compilers, no -dev headers.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libcairo2 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-liberation \
        fonts-dejavu-core \
        curl \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user. UID/GID pinned so bind-mounts don't permission-bomb.
RUN groupadd --system --gid 1001 nexus \
    && useradd  --system --uid 1001 --gid 1001 --home-dir /app --shell /usr/sbin/nologin nexus

WORKDIR /app

# Install pre-built wheels from stage 1.
COPY --from=builder /wheels /wheels
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-index --find-links=/wheels -r /tmp/requirements.txt \
    && rm -rf /wheels /tmp/requirements.txt

# Copy application source and pre-create writable dirs.
COPY --chown=nexus:nexus . /app
RUN mkdir -p /app/storage /app/storage/exports /app/.memory \
    && chown -R nexus:nexus /app/storage /app/.memory

USER nexus

EXPOSE 8000

# Health: hit FastAPI's /api/health route. Fails container if backend is unresponsive.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent --show-error http://127.0.0.1:8000/api/health || exit 1

# tini reaps zombies and forwards signals (uvicorn, celery).
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

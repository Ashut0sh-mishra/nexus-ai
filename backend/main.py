"""NEXUS FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from api.middleware import RequestContextMiddleware, configure_logging
from api.routes import (
    api_keys,
    assets,
    audit_logs,
    auth,
    brand_kits,
    export,
    generate,
    share,
    slides,
    status,
    upload,
    versions,
    webhooks,
    workspaces,
)
from database.connection import close_engine, init_models

logger = logging.getLogger("nexus.main")


@asynccontextmanager
async def lifespan(app: FastAPI):  # pragma: no cover - exercised at runtime
    configure_logging(settings.LOG_LEVEL)
    settings.assert_required_for_runtime()
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=0.1,
        )
    await init_models()
    # Load Manus-style local design references for the planner.
    try:
        from services.reference_service import load_local_references
        n_refs = load_local_references()
        logger.info("nexus.references_loaded", extra={"count": n_refs})
    except Exception as exc:  # noqa: BLE001
        logger.warning("nexus.references_load_failed", extra={"err": str(exc)})
    logger.info("nexus.startup", extra={"env": settings.ENVIRONMENT})
    try:
        yield
    finally:
        await close_engine()
        logger.info("nexus.shutdown")


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    summary="AI-powered presentation generator \u2014 backend API.",
    description=(
        "REST + SSE API powering the NEXUS AI presentation platform. "
        "The typical flow is:\n\n"
        "1. `POST /api/upload` (optional) \u2014 attach context files.\n"
        "2. `POST /api/generate` \u2014 create a deck task; receive a `task_id`.\n"
        "3. `GET /api/status/{task_id}` (SSE) \u2014 stream live progress.\n"
        "4. `GET /api/slides/{task_id}` \u2014 fetch the finished deck.\n"
        "5. `PUT/DELETE/POST /api/slides/...` \u2014 edit, reorder, or regenerate.\n"
        "6. `GET /api/export/{task_id}/{format}` \u2014 download as PPTX / PDF / HTML.\n\n"
        "A first-class TypeScript client (`@nexus-ai/react-sdk`) wraps every "
        "endpoint listed below \u2014 see the SDK README for examples."
    ),
    contact={"name": "NEXUS", "url": "https://github.com/nexus-ai"},
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "generate", "description": "Create generation tasks."},
        {"name": "status", "description": "Live progress via Server-Sent Events."},
        {"name": "slides", "description": "Read, edit, reorder, regenerate, and delete slides."},
        {"name": "export", "description": "Download the deck as PPTX / PDF / HTML / JSON."},
        {"name": "share", "description": "Public read-only share links."},
        {"name": "upload", "description": "Attach CSV / XLSX / PDF / DOCX context files."},
        {"name": "auth", "description": "Email-password registration and login."},
    ],
    servers=[
        {"url": "/", "description": "Current host"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)

# Static files for local-storage exports (used when R2 is not configured).
# Mount under /api/files so the Vite dev proxy (/api) forwards download links.
settings.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
settings.ASSET_DIR.mkdir(parents=True, exist_ok=True)
# More-specific mount first so /api/files/assets/* hits the asset dir,
# not the export dir.
app.mount("/api/files/assets", StaticFiles(directory=str(settings.ASSET_DIR)), name="assets")
app.mount("/api/files", StaticFiles(directory=str(settings.EXPORT_DIR)), name="files")
app.mount("/files", StaticFiles(directory=str(settings.EXPORT_DIR)), name="files-legacy")

app.include_router(generate.router, prefix="/api", tags=["generate"])
app.include_router(status.router, prefix="/api", tags=["status"])
app.include_router(slides.router, prefix="/api", tags=["slides"])
app.include_router(export.router, prefix="/api", tags=["export"])
app.include_router(share.router, prefix="/api", tags=["share"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(workspaces.router, prefix="/api", tags=["workspaces"])
app.include_router(brand_kits.router, prefix="/api", tags=["brand-kits"])
app.include_router(assets.router, prefix="/api", tags=["assets"])
app.include_router(api_keys.router, prefix="/api", tags=["api-keys"])
app.include_router(webhooks.router, prefix="/api", tags=["webhooks"])
app.include_router(audit_logs.router, prefix="/api", tags=["audit-logs"])
app.include_router(versions.router, prefix="/api", tags=["versions"])


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
    }


@app.get("/api/health")
async def health():
    from services.ai_service import AIService
    ai = AIService()
    provider = ai.active_provider
    model = ai.active_model
    # Friendly label for the marketing badge.
    labels = {
        "anthropic": ("Claude Sonnet", "Anthropic"),
        "groq": ("Llama 3.3 70B", "Groq"),
        "gemini": ("Gemini 2.0 Flash", "Google"),
        "openrouter": ("Llama 3.3 70B", "OpenRouter"),
        "nvidia_nim": ("Llama 3.3 70B", "NVIDIA NIM"),
        "openai": ("GPT-4.1", "OpenAI"),
        "unfiltered": ("GPT-4o", "Unfiltered"),
    }
    label_model, label_vendor = labels.get(provider, (model, provider))
    return {
        "status": "ok",
        "provider": provider,
        "model": model,
        "label": f"Powered by {label_model} ({label_vendor})",
        "env": settings.ENVIRONMENT,
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):  # pragma: no cover - safety net
    logger.exception("unhandled.exception", extra={"path": str(request.url)})
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_type": exc.__class__.__name__},
    )

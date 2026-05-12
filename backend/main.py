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
    agent,
    auth,
    export,
    generate,
    import_json,
    import_pptx,
    lifecycle,
    runs,
    share,
    slides,
    status,
    themes,
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
    logger.info("nexus.startup", extra={"env": settings.ENVIRONMENT})
    try:
        yield
    finally:
        # Cleanly stop Playwright if it was ever started.
        if getattr(settings, "BROWSER_ENABLED", False):
            try:
                from services.browser_service import BrowserService

                await BrowserService().shutdown()
            except Exception:  # pragma: no cover - best-effort
                logger.exception("nexus.browser_shutdown_failed")
        await close_engine()
        logger.info("nexus.shutdown")


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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
app.mount("/api/files", StaticFiles(directory=str(settings.EXPORT_DIR)), name="files")
app.mount("/files", StaticFiles(directory=str(settings.EXPORT_DIR)), name="files-legacy")

app.include_router(generate.router, prefix="/api", tags=["generate"])
app.include_router(status.router, prefix="/api", tags=["status"])
app.include_router(lifecycle.router, prefix="/api", tags=["lifecycle"])
app.include_router(slides.router, prefix="/api", tags=["slides"])
app.include_router(import_pptx.router, prefix="/api", tags=["import"])
app.include_router(import_json.router, prefix="/api", tags=["import"])
app.include_router(themes.router, prefix="/api", tags=["themes"])
app.include_router(export.router, prefix="/api", tags=["export"])
app.include_router(share.router, prefix="/api", tags=["share"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(runs.router, prefix="/api", tags=["runs"])


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
        "cerebras": ("Llama 3.3 70B", "Cerebras"),
        "sambanova": ("Llama 3.3 70B", "SambaNova"),
        "mistral": ("Mistral Small", "Mistral"),
        "github_models": ("GPT-4o-mini", "GitHub Models"),
    }
    label_model, label_vendor = labels.get(provider, (model, provider))

    # Phase 6W: report all 10 providers (configured / active / model / base_url).
    # Does not call any remote API.
    provider_specs: list[tuple[str, str, str, str]] = [
        ("groq", settings.GROQ_API_KEY, settings.GROQ_MODEL, settings.GROQ_BASE_URL),
        ("gemini", settings.GEMINI_API_KEY, settings.GEMINI_MODEL, ""),
        ("openrouter", settings.OPENROUTER_API_KEY, settings.OPENROUTER_MODEL, settings.OPENROUTER_BASE_URL),
        ("nvidia_nim", settings.NVIDIA_NIM_API_KEY, settings.NVIDIA_NIM_MODEL, settings.NVIDIA_NIM_BASE_URL),
        ("anthropic", settings.ANTHROPIC_API_KEY, settings.active_anthropic_model, ""),
        ("openai", settings.OPENAI_API_KEY, settings.OPENAI_MODEL_FALLBACK, "https://api.openai.com/v1"),
        ("cerebras", settings.CEREBRAS_API_KEY, settings.CEREBRAS_MODEL, settings.CEREBRAS_BASE_URL),
        ("sambanova", settings.SAMBANOVA_API_KEY, settings.SAMBANOVA_MODEL, settings.SAMBANOVA_BASE_URL),
        ("mistral", settings.MISTRAL_API_KEY, settings.MISTRAL_MODEL, settings.MISTRAL_BASE_URL),
        ("github_models", settings.GITHUB_MODELS_API_KEY, settings.GITHUB_MODELS_MODEL, settings.GITHUB_MODELS_BASE_URL),
    ]
    providers: dict[str, dict[str, object]] = {}
    for name, key, mdl, base in provider_specs:
        providers[name] = {
            "configured": bool(key),
            "active": name == provider,
            "model": mdl,
            "base_url": base,
        }

    return {
        "status": "ok",
        "provider": provider,
        "model": model,
        "label": f"Powered by {label_model} ({label_vendor})",
        "env": settings.ENVIRONMENT,
        "providers": providers,
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):  # pragma: no cover - safety net
    logger.exception("unhandled.exception", extra={"path": str(request.url)})
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_type": exc.__class__.__name__},
    )

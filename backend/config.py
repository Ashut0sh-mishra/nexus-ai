"""Centralized application settings.

All environment variables for NEXUS are loaded **only** here. Other modules
must `from config import settings` rather than reading os.environ directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """All NEXUS env vars. Defaults are dev-friendly; secrets default to empty."""

    model_config = SettingsConfigDict(
        env_file=[str(PROJECT_ROOT / ".env"), str(BACKEND_DIR / ".env")],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── AI MODEL CHAIN ─────────────────────────
    # Primary: Groq Llama 3.3 70B (FREE, fastest, OpenAI-compat) — verified working
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Secondary: Gemini 2.0 Flash (FREE 1500/day)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Tertiary: OpenRouter — Llama 3.3 70B Instruct (free tier as of late 2025)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"

    # Quaternary: NVIDIA NIM (Llama 3.3 70B Instruct on integrate.api.nvidia.com)
    NVIDIA_NIM_API_KEY: str = ""
    NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_NIM_MODEL: str = "meta/llama-3.3-70b-instruct"

    # Final fallback: Claude Sonnet 4.6 (paid)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL_PROD: str = "claude-sonnet-4-6"
    ANTHROPIC_MODEL_DEV: str = "claude-opus-4-7"

    # OpenAI (extra fallback)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_FALLBACK: str = "gpt-4.1"

    # Unfiltered (community OpenAI-compatible endpoint)
    UNFILTERED_API_KEY: str = ""
    UNFILTERED_BASE_URL: str = "https://api.unfiltered.ai/v1"
    UNFILTERED_MODEL: str = "gpt-4o"

    # ── Priority-1 free / low-cost providers (Phase 6W) ───────────────────
    # Cerebras inference (fast Llama 3.3 70B, OpenAI-compatible).
    CEREBRAS_API_KEY: str = ""
    CEREBRAS_BASE_URL: str = "https://api.cerebras.ai/v1"
    CEREBRAS_MODEL: str = "qwen-3-235b-a22b-instruct-2507"

    # SambaNova Cloud (free tier; OpenAI-compatible).
    SAMBANOVA_API_KEY: str = ""
    SAMBANOVA_BASE_URL: str = "https://api.sambanova.ai/v1"
    SAMBANOVA_MODEL: str = "Meta-Llama-3.3-70B-Instruct"

    # Mistral AI (low-cost; OpenAI-compatible).
    MISTRAL_API_KEY: str = ""
    MISTRAL_BASE_URL: str = "https://api.mistral.ai/v1"
    MISTRAL_MODEL: str = "mistral-small-latest"

    # GitHub Models (free tier via Azure inference; OpenAI-compatible).
    GITHUB_MODELS_API_KEY: str = ""
    GITHUB_MODELS_BASE_URL: str = "https://models.inference.ai.azure.com"
    GITHUB_MODELS_MODEL: str = "gpt-4o-mini"

    # ── Token / context pruning ───────────────────────────────────────────
    MAX_CONTEXT_TOKENS: int = 6000
    KEEP_LAST_MESSAGES: int = 5

    # Order of providers to try. Override via env to disable any tier.
    # Phase 6W-stable: only providers with verified-working credentials
    # are listed by default. Gemini / OpenRouter / Cerebras are supported
    # but excluded due to free-tier 429 risk; Mistral / GitHub Models are
    # supported but excluded until valid inference credentials exist.
    # All 10 providers remain visible in /api/health.
    AI_PROVIDER_CHAIN: str = "groq,nvidia_nim,sambanova"

    # ── SEARCH & BROWSER ───────────────────────
    TAVILY_API_KEY: str = ""
    SERPER_API_KEY: str = ""
    BROWSERLESS_API_KEY: str = ""

    # Phase 6I — runtime-driven /api/generate (feature flag, default OFF).
    # When false, /api/generate behaves exactly as before. When true, the
    # route additionally persists an AgentRun + AgentStep dispatch trail
    # (still enqueueing Celery; the runtime does not yet execute the
    # generation pipeline). See audits/REFERENCE_INTELLIGENCE_BLUEPRINT.md
    # § Phase 6I.
    NEXUS_RUNTIME_DRIVES_GENERATE: bool = False

    # Browser automation (Playwright). Disabled by default so CI/local
    # baseline stays stable. Enable with BROWSER_ENABLED=true once Chromium
    # has been installed via `python -m playwright install chromium`.
    BROWSER_ENABLED: bool = False
    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT_MS: int = 10000
    BROWSER_NAV_TIMEOUT_MS: int = 30000
    BROWSER_VIEWPORT_WIDTH: int = 1280
    BROWSER_VIEWPORT_HEIGHT: int = 720

    # ── DATABASE ───────────────────────────────
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/nexus"
    REDIS_URL: str = "redis://localhost:6379"

    # ── FILE STORAGE (Cloudflare R2) ───────────
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = "nexus-exports"
    R2_ENDPOINT: str = ""
    R2_PUBLIC_URL: str = ""

    # ── AUTH & SECURITY ────────────────────────
    # `SECRET_KEY` is the canonical name; `JWT_SECRET` kept as alias.
    SECRET_KEY: str = "change-me-in-production"
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # ── APP ────────────────────────────────────
    APP_NAME: str = "NEXUS"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"
    DEBUG: bool = True

    # ── MONITORING ─────────────────────────────
    SENTRY_DSN: str = ""
    LOG_LEVEL: str = "INFO"

    # ── PAYMENTS ───────────────────────────────
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # ── INTERNAL ───────────────────────────────
    STORAGE_DIR: Path = Field(default=BACKEND_DIR / "storage")
    EXPORT_DIR: Path = Field(default=BACKEND_DIR / "storage" / "exports")
    MEMORY_DIR: Path = Field(default=BACKEND_DIR / ".memory")

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        return v

    # ── derived helpers ────────────────────────
    @property
    def is_dev(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_prod(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def active_anthropic_model(self) -> str:
        return self.ANTHROPIC_MODEL_DEV if self.is_dev else self.ANTHROPIC_MODEL_PROD

    # Phase 6W — role-based model routing. Maps a generation role to a
    # (provider, model) pair. ``complete_for_role`` consults this map first
    # and falls back to the normal provider_chain on failure or missing key.
    @property
    def ROLE_MODEL_MAP(self) -> dict[str, tuple[str, str]]:
        # Phase 6W-stable: every role is pinned to a provider whose key is
        # currently verified-working (groq / nvidia_nim / sambanova). The
        # other 7 providers remain wired in code and visible in /api/health
        # but are not routed to until their credentials are operational.
        return {
            "planner":   ("sambanova",  self.SAMBANOVA_MODEL),
            "writer":    ("groq",       self.GROQ_MODEL),
            "critic":    ("nvidia_nim", self.NVIDIA_NIM_MODEL),
            "research":  ("sambanova",  self.SAMBANOVA_MODEL),
            "vision":    ("groq",       self.GROQ_MODEL),
            "repair":    ("nvidia_nim", self.NVIDIA_NIM_MODEL),
            "summarize": ("sambanova",  self.SAMBANOVA_MODEL),
            "json_fix":  ("groq",       self.GROQ_MODEL),
        }

    @property
    def provider_chain(self) -> list[str]:
        # Normalize aliases: `nvidia` -> `nvidia_nim`, `claude` -> `anthropic`.
        aliases = {"nvidia": "nvidia_nim", "claude": "anthropic", "unfiltered": "unfiltered"}
        out: list[str] = []
        for raw in self.AI_PROVIDER_CHAIN.split(","):
            p = raw.strip().lower()
            if not p:
                continue
            out.append(aliases.get(p, p))

        # Auto-promote Anthropic to the front when a real key is set.
        # Manus uses Claude Sonnet directly; users who paid for a key get the
        # quality jump for free without editing AI_PROVIDER_CHAIN.
        if self.ANTHROPIC_API_KEY and self.ANTHROPIC_API_KEY.startswith("sk-ant-"):
            out = ["anthropic"] + [p for p in out if p != "anthropic"]
        return out

    @property
    def jwt_secret(self) -> str:
        return self.JWT_SECRET or self.SECRET_KEY

    @property
    def has_r2(self) -> bool:
        return bool(
            self.R2_ACCESS_KEY_ID
            and self.R2_SECRET_ACCESS_KEY
            and self.R2_ENDPOINT
            and self.R2_BUCKET
        )

    @property
    def has_google_oauth(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    def ensure_directories(self) -> None:
        for d in (self.STORAGE_DIR, self.EXPORT_DIR, self.MEMORY_DIR):
            d.mkdir(parents=True, exist_ok=True)

    def assert_required_for_runtime(self) -> None:
        """Fail fast on startup if no AI provider key is configured."""
        keys = (
            self.OPENROUTER_API_KEY,
            self.NVIDIA_NIM_API_KEY,
            self.GEMINI_API_KEY,
            self.GROQ_API_KEY,
            self.ANTHROPIC_API_KEY,
            self.OPENAI_API_KEY,
            self.CEREBRAS_API_KEY,
            self.SAMBANOVA_API_KEY,
            self.MISTRAL_API_KEY,
            self.GITHUB_MODELS_API_KEY,
        )
        if not any(keys):
            raise RuntimeError(
                "No AI provider configured. Set at least one of: "
                "OPENROUTER_API_KEY, NVIDIA_NIM_API_KEY, GEMINI_API_KEY, "
                "GROQ_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, "
                "CEREBRAS_API_KEY, SAMBANOVA_API_KEY, MISTRAL_API_KEY, "
                "GITHUB_MODELS_API_KEY in .env"
            )
        if self.jwt_secret in ("", "change-me-in-production") and self.is_prod:
            raise RuntimeError(
                "SECRET_KEY must be set in production. "
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_directories()
    return s


settings: Settings = get_settings()

"""Smoke-test every configured AI provider with a tiny prompt.

Usage (from repo root):
    python test_providers.py

Skips providers without keys. Exit code 0 if at least one configured provider
responds OK; non-zero if every configured provider fails. Never prints secrets.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Make backend importable without installing the package.
ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# Defer imports so sys.path tweak applies first.
from config import settings  # noqa: E402
from services.ai_service import AIService  # noqa: E402


PROVIDERS: list[tuple[str, str]] = [
    ("groq", "GROQ_API_KEY"),
    ("gemini", "GEMINI_API_KEY"),
    ("openrouter", "OPENROUTER_API_KEY"),
    ("nvidia_nim", "NVIDIA_NIM_API_KEY"),
    ("anthropic", "ANTHROPIC_API_KEY"),
    ("openai", "OPENAI_API_KEY"),
    ("cerebras", "CEREBRAS_API_KEY"),
    ("sambanova", "SAMBANOVA_API_KEY"),
    ("mistral", "MISTRAL_API_KEY"),
    ("github_models", "GITHUB_MODELS_API_KEY"),
]


async def _ping(ai: AIService, provider: str) -> tuple[str, str]:
    """Return (status, detail). status in {OK, FAIL, SKIP}."""
    handler = ai._handler_for(provider)  # noqa: SLF001 — internal but stable
    if handler is None:
        return "SKIP", "no key configured"
    try:
        result = await handler(
            "You are a terse health-check responder.",
            "Reply OK only.",
            32,
            0.0,
        )
        snippet = (result.text or "").strip().splitlines()[0][:40] if result.text else ""
        return "OK", f"model={result.model} reply={snippet!r}"
    except Exception as exc:  # noqa: BLE001 — we report the error string
        return "FAIL", f"{type(exc).__name__}: {str(exc)[:160]}"


async def main() -> int:
    ai = AIService()
    print(f"NEXUS provider smoke test  env={settings.ENVIRONMENT}")
    print(f"Active provider chain: {settings.provider_chain}")
    print("-" * 72)
    print(f"{'PROVIDER':<16} {'STATUS':<6} DETAIL")
    print("-" * 72)
    configured = 0
    ok = 0
    for provider, _env in PROVIDERS:
        status, detail = await _ping(ai, provider)
        if status != "SKIP":
            configured += 1
        if status == "OK":
            ok += 1
        print(f"{provider:<16} {status:<6} {detail}")
    print("-" * 72)
    print(f"summary: ok={ok} configured={configured} total={len(PROVIDERS)}")
    if configured == 0:
        print("WARNING: no providers configured. Set at least one *_API_KEY in .env")
        return 0
    return 0 if ok > 0 else 2


if __name__ == "__main__":
    # Ensure unbuffered prints when piped.
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    sys.exit(asyncio.run(main()))

"""Unified AI service with FREE-first fallback chain.

Order (configurable via AI_PROVIDER_CHAIN):

  1. OpenRouter   — Kimi K2 (FREE)
  2. NVIDIA NIM   — Kimi K2.5 (FREE)
  3. Gemini       — gemini-2.0-flash (FREE 1000/day)
  4. Groq         — Llama 3.3 70B (FREE, fastest)
  5. Anthropic    — Claude Sonnet 4.6 (paid fallback)
  6. OpenAI       — gpt-4.1 (paid fallback)

All providers expose the same interface:

    text, tokens, cost = await ai.complete(system, user, max_tokens=8096)

The first provider whose key is configured is tried; on failure the chain
falls through to the next. Free providers report cost = 0.0.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from config import settings

logger = logging.getLogger("nexus.services.ai")


# Pricing per 1M tokens (input, output) — used only for paid providers.
_PRICING: dict[str, tuple[float, float]] = {
    "anthropic-opus": (15.0, 75.0),
    "anthropic-sonnet": (3.0, 15.0),
    "anthropic-haiku": (0.80, 4.0),
    "openai": (2.0, 8.0),
}


@dataclass
class CompletionResult:
    text: str
    tokens: int
    cost_usd: float
    provider: str
    model: str


class AIService:
    """Multi-provider LLM client. Drop-in replacement for the old ClaudeService."""

    def __init__(self) -> None:
        self._anthropic = None
        self._openai = None
        self._openrouter = None
        self._nvidia = None
        self._groq = None
        self._gemini_ready = False

    # ── public surface ────────────────────────────────────────────────────
    @property
    def active_model(self) -> str:
        for p in settings.provider_chain:
            m = self._model_for(p)
            if m:
                return m
        return settings.active_anthropic_model

    @property
    def active_provider(self) -> str:
        for p in settings.provider_chain:
            if self._model_for(p):
                return p
        return "anthropic"

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 8096,
        temperature: float = 0.7,
    ) -> tuple[str, int, float]:
        """Try each configured provider until one succeeds.

        Returns (text, total_tokens, cost_usd) for compatibility with callers.
        """
        return await self._complete_with_chain(
            settings.provider_chain, system, user, max_tokens, temperature
        )

    async def complete_writing(
        self,
        system: str,
        user: str,
        max_tokens: int = 8096,
        temperature: float = 0.7,
    ) -> tuple[str, int, float]:
        """High-quality pass for slide-content generation.

        Routes to the configured WRITING_MODEL_PROVIDER first (defaults to a
        priority order: anthropic \u2192 openai \u2192 gemini \u2192 openrouter \u2192 nvidia_nim
        \u2192 groq). Falls back to the standard chain if that provider has no
        key. Cheap utility passes (classifier, critic, planning) keep using
        :meth:`complete` so we don't burn budget on structure.
        """
        chain = self._writing_chain()
        return await self._complete_with_chain(
            chain, system, user, max_tokens, temperature
        )

    def _writing_chain(self) -> list[str]:
        """Build a provider chain biased toward the strongest available model."""
        preferred = (getattr(settings, "WRITING_MODEL_PROVIDER", "auto") or "auto").lower()
        # Quality-first default order. We pick the FIRST that has a key.
        quality_order = ["anthropic", "openai", "gemini", "openrouter", "nvidia_nim", "groq"]
        if preferred != "auto" and preferred in quality_order:
            head = [preferred]
        else:
            head = []
            for p in quality_order:
                if self._handler_for(p) is not None:
                    head = [p]
                    break
        # Always append the standard chain as fallback (de-duped).
        seen = set(head)
        for p in settings.provider_chain:
            if p not in seen:
                head.append(p)
                seen.add(p)
        return head

    async def _complete_with_chain(
        self,
        chain: list[str],
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, int, float]:
        last_exc: Exception | None = None
        for provider in chain:
            handler = self._handler_for(provider)
            if handler is None:
                continue
            try:
                result = await handler(system, user, max_tokens, temperature)
                logger.info(
                    "ai.ok",
                    extra={
                        "provider": result.provider,
                        "model": result.model,
                        "tokens": result.tokens,
                        "cost_usd": round(result.cost_usd, 6),
                    },
                )
                return result.text, result.tokens, result.cost_usd
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "ai.provider_failed",
                    extra={"provider": provider, "err": str(exc)[:200]},
                )
                continue

        raise RuntimeError(
            f"All AI providers failed. Last error: {last_exc}. "
            "Verify at least one provider key is set in .env"
        )

    # ── provider routing ──────────────────────────────────────────────────
    def _handler_for(
        self, provider: str
    ) -> Callable[[str, str, int, float], Awaitable[CompletionResult]] | None:
        if provider == "openrouter" and settings.OPENROUTER_API_KEY:
            return self._call_openrouter
        if provider == "nvidia_nim" and settings.NVIDIA_NIM_API_KEY:
            return self._call_nvidia_nim
        if provider == "gemini" and settings.GEMINI_API_KEY:
            return self._call_gemini
        if provider == "groq" and settings.GROQ_API_KEY:
            return self._call_groq
        if provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            return self._call_anthropic
        if provider == "openai" and settings.OPENAI_API_KEY:
            return self._call_openai
        if provider == "unfiltered" and settings.UNFILTERED_API_KEY:
            return self._call_unfiltered
        return None

    def _model_for(self, provider: str) -> str | None:
        mapping = {
            "openrouter": (settings.OPENROUTER_API_KEY, settings.OPENROUTER_MODEL),
            "nvidia_nim": (settings.NVIDIA_NIM_API_KEY, settings.NVIDIA_NIM_MODEL),
            "gemini": (settings.GEMINI_API_KEY, settings.GEMINI_MODEL),
            "groq": (settings.GROQ_API_KEY, settings.GROQ_MODEL),
            "anthropic": (settings.ANTHROPIC_API_KEY, settings.active_anthropic_model),
            "openai": (settings.OPENAI_API_KEY, settings.OPENAI_MODEL_FALLBACK),
            "unfiltered": (settings.UNFILTERED_API_KEY, settings.UNFILTERED_MODEL),
        }
        key, model = mapping.get(provider, ("", ""))
        return model if key else None

    # ── OpenAI-compatible providers (OpenRouter / NIM / Groq / OpenAI) ────
    async def _openai_compat(
        self,
        *,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
        cost_key: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> CompletionResult:
        from openai import OpenAI

        def _call() -> Any:
            client_kwargs: dict[str, Any] = {"api_key": api_key, "base_url": base_url}
            if extra_headers:
                client_kwargs["default_headers"] = extra_headers
            client = OpenAI(**client_kwargs)
            return client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )

        response = await asyncio.to_thread(_call)
        text = (response.choices[0].message.content or "").strip()
        usage = getattr(response, "usage", None)
        in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
        out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
        cost = 0.0
        if cost_key and cost_key in _PRICING:
            ip, op = _PRICING[cost_key]
            cost = (in_tok * ip + out_tok * op) / 1_000_000
        return CompletionResult(text, in_tok + out_tok, cost, provider, model)

    async def _call_openrouter(self, system: str, user: str, mt: int, t: float) -> CompletionResult:
        return await self._openai_compat(
            provider="openrouter",
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            model=settings.OPENROUTER_MODEL,
            system=system, user=user, max_tokens=mt, temperature=t,
            extra_headers={
                "HTTP-Referer": settings.FRONTEND_URL,
                "X-Title": settings.APP_NAME,
            },
        )

    async def _call_nvidia_nim(self, system: str, user: str, mt: int, t: float) -> CompletionResult:
        return await self._openai_compat(
            provider="nvidia_nim",
            api_key=settings.NVIDIA_NIM_API_KEY,
            base_url=settings.NVIDIA_NIM_BASE_URL,
            model=settings.NVIDIA_NIM_MODEL,
            system=system, user=user, max_tokens=mt, temperature=t,
        )

    async def _call_groq(self, system: str, user: str, mt: int, t: float) -> CompletionResult:
        return await self._openai_compat(
            provider="groq",
            api_key=settings.GROQ_API_KEY,
            base_url=settings.GROQ_BASE_URL,
            model=settings.GROQ_MODEL,
            system=system, user=user, max_tokens=mt, temperature=t,
        )

    async def _call_openai(self, system: str, user: str, mt: int, t: float) -> CompletionResult:
        return await self._openai_compat(
            provider="openai",
            api_key=settings.OPENAI_API_KEY,
            base_url="https://api.openai.com/v1",
            model=settings.OPENAI_MODEL_FALLBACK,
            system=system, user=user, max_tokens=mt, temperature=t,
            cost_key="openai",
        )

    async def _call_unfiltered(self, system: str, user: str, mt: int, t: float) -> CompletionResult:
        return await self._openai_compat(
            provider="unfiltered",
            api_key=settings.UNFILTERED_API_KEY,
            base_url=settings.UNFILTERED_BASE_URL,
            model=settings.UNFILTERED_MODEL,
            system=system, user=user, max_tokens=mt, temperature=t,
        )

    # ── Gemini (native) ───────────────────────────────────────────────────
    async def _call_gemini(self, system: str, user: str, mt: int, t: float) -> CompletionResult:
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "google-generativeai is not installed. Run: pip install google-generativeai"
            ) from exc

        if not self._gemini_ready:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._gemini_ready = True

        def _call() -> Any:
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                system_instruction=system,
            )
            return model.generate_content(
                user,
                generation_config={
                    "max_output_tokens": mt,
                    "temperature": t,
                },
            )

        response = await asyncio.to_thread(_call)
        text = ""
        try:
            text = (response.text or "").strip()
        except Exception:
            try:
                text = "".join(
                    p.text for c in response.candidates for p in c.content.parts if hasattr(p, "text")
                ).strip()
            except Exception:
                text = ""

        usage = getattr(response, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", 0) if usage else 0
        out_tok = getattr(usage, "candidates_token_count", 0) if usage else 0
        return CompletionResult(text, in_tok + out_tok, 0.0, "gemini", settings.GEMINI_MODEL)

    # ── Anthropic (native SDK, mirrors Manus call shape) ──────────────────
    async def _call_anthropic(self, system: str, user: str, mt: int, t: float) -> CompletionResult:
        import anthropic

        if self._anthropic is None:
            self._anthropic = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        model = settings.active_anthropic_model

        def _call() -> Any:
            return self._anthropic.messages.create(
                model=model,
                max_tokens=mt,
                temperature=t,
                system=system,
                messages=[{"role": "user", "content": user}],
            )

        response = await asyncio.to_thread(_call)
        parts: list[str] = []
        for b in response.content or []:
            if hasattr(b, "text") and isinstance(b.text, str):
                parts.append(b.text)
            elif isinstance(b, dict) and isinstance(b.get("text"), str):
                parts.append(b["text"])
        text = "".join(parts).strip()

        in_tok = getattr(response.usage, "input_tokens", 0) or 0
        out_tok = getattr(response.usage, "output_tokens", 0) or 0
        cost_key = "anthropic-opus" if "opus" in model else "anthropic-sonnet"
        ip, op = _PRICING[cost_key]
        cost = (in_tok * ip + out_tok * op) / 1_000_000
        return CompletionResult(text, in_tok + out_tok, cost, "anthropic", model)


# Backwards compatibility — older modules still import ClaudeService.
ClaudeService = AIService

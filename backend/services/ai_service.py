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
        last_exc: Exception | None = None
        for provider in settings.provider_chain:
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
        if provider == "cerebras" and settings.CEREBRAS_API_KEY:
            return self._call_cerebras
        if provider == "sambanova" and settings.SAMBANOVA_API_KEY:
            return self._call_sambanova
        if provider == "mistral" and settings.MISTRAL_API_KEY:
            return self._call_mistral
        if provider == "github_models" and settings.GITHUB_MODELS_API_KEY:
            return self._call_github_models
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
            "cerebras": (settings.CEREBRAS_API_KEY, settings.CEREBRAS_MODEL),
            "sambanova": (settings.SAMBANOVA_API_KEY, settings.SAMBANOVA_MODEL),
            "mistral": (settings.MISTRAL_API_KEY, settings.MISTRAL_MODEL),
            "github_models": (settings.GITHUB_MODELS_API_KEY, settings.GITHUB_MODELS_MODEL),
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

    async def _call_openrouter(
        self, system: str, user: str, mt: int, t: float, *, model: str | None = None
    ) -> CompletionResult:
        return await self._openai_compat(
            provider="openrouter",
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            model=model or settings.OPENROUTER_MODEL,
            system=system, user=user, max_tokens=mt, temperature=t,
            extra_headers={
                "HTTP-Referer": settings.FRONTEND_URL,
                "X-Title": settings.APP_NAME,
            },
        )

    async def _call_nvidia_nim(
        self, system: str, user: str, mt: int, t: float, *, model: str | None = None
    ) -> CompletionResult:
        return await self._openai_compat(
            provider="nvidia_nim",
            api_key=settings.NVIDIA_NIM_API_KEY,
            base_url=settings.NVIDIA_NIM_BASE_URL,
            model=model or settings.NVIDIA_NIM_MODEL,
            system=system, user=user, max_tokens=mt, temperature=t,
        )

    async def _call_groq(
        self, system: str, user: str, mt: int, t: float, *, model: str | None = None
    ) -> CompletionResult:
        return await self._openai_compat(
            provider="groq",
            api_key=settings.GROQ_API_KEY,
            base_url=settings.GROQ_BASE_URL,
            model=model or settings.GROQ_MODEL,
            system=system, user=user, max_tokens=mt, temperature=t,
        )

    async def _call_openai(
        self, system: str, user: str, mt: int, t: float, *, model: str | None = None
    ) -> CompletionResult:
        return await self._openai_compat(
            provider="openai",
            api_key=settings.OPENAI_API_KEY,
            base_url="https://api.openai.com/v1",
            model=model or settings.OPENAI_MODEL_FALLBACK,
            system=system, user=user, max_tokens=mt, temperature=t,
            cost_key="openai",
        )

    async def _call_unfiltered(
        self, system: str, user: str, mt: int, t: float, *, model: str | None = None
    ) -> CompletionResult:
        return await self._openai_compat(
            provider="unfiltered",
            api_key=settings.UNFILTERED_API_KEY,
            base_url=settings.UNFILTERED_BASE_URL,
            model=model or settings.UNFILTERED_MODEL,
            system=system, user=user, max_tokens=mt, temperature=t,
        )

    # ── Phase 6W: Cerebras / SambaNova / Mistral / GitHub Models ──────────────
    async def _call_cerebras(
        self, system: str, user: str, mt: int, t: float, *, model: str | None = None
    ) -> CompletionResult:
        return await self._openai_compat(
            provider="cerebras",
            api_key=settings.CEREBRAS_API_KEY,
            base_url=settings.CEREBRAS_BASE_URL,
            model=model or settings.CEREBRAS_MODEL,
            system=system, user=user, max_tokens=mt, temperature=t,
        )

    async def _call_sambanova(
        self, system: str, user: str, mt: int, t: float, *, model: str | None = None
    ) -> CompletionResult:
        return await self._openai_compat(
            provider="sambanova",
            api_key=settings.SAMBANOVA_API_KEY,
            base_url=settings.SAMBANOVA_BASE_URL,
            model=model or settings.SAMBANOVA_MODEL,
            system=system, user=user, max_tokens=mt, temperature=t,
        )

    async def _call_mistral(
        self, system: str, user: str, mt: int, t: float, *, model: str | None = None
    ) -> CompletionResult:
        return await self._openai_compat(
            provider="mistral",
            api_key=settings.MISTRAL_API_KEY,
            base_url=settings.MISTRAL_BASE_URL,
            model=model or settings.MISTRAL_MODEL,
            system=system, user=user, max_tokens=mt, temperature=t,
        )

    async def _call_github_models(
        self, system: str, user: str, mt: int, t: float, *, model: str | None = None
    ) -> CompletionResult:
        return await self._openai_compat(
            provider="github_models",
            api_key=settings.GITHUB_MODELS_API_KEY,
            base_url=settings.GITHUB_MODELS_BASE_URL,
            model=model or settings.GITHUB_MODELS_MODEL,
            system=system, user=user, max_tokens=mt, temperature=t,
        )

    # ── Gemini (native) ───────────────────────────────────────────────────
    async def _call_gemini(
        self, system: str, user: str, mt: int, t: float, *, model: str | None = None
    ) -> CompletionResult:
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "google-generativeai is not installed. Run: pip install google-generativeai"
            ) from exc

        if not self._gemini_ready:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._gemini_ready = True

        model_name = model or settings.GEMINI_MODEL

        def _call() -> Any:
            gmodel = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system,
            )
            return gmodel.generate_content(
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
        return CompletionResult(text, in_tok + out_tok, 0.0, "gemini", model_name)

    # ── Anthropic (native SDK, mirrors Manus call shape) ──────────────────
    async def _call_anthropic(
        self, system: str, user: str, mt: int, t: float, *, model: str | None = None
    ) -> CompletionResult:
        import anthropic

        if self._anthropic is None:
            self._anthropic = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        active_model = model or settings.active_anthropic_model

        def _call() -> Any:
            return self._anthropic.messages.create(
                model=active_model,
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
        cost_key = "anthropic-opus" if "opus" in active_model else "anthropic-sonnet"
        ip, op = _PRICING[cost_key]
        cost = (in_tok * ip + out_tok * op) / 1_000_000
        return CompletionResult(text, in_tok + out_tok, cost, "anthropic", active_model)

    # ── Phase 6W: role-based routing ──────────────────────────────────────
    async def complete_for_role(
        self,
        role: str,
        system: str,
        user: str,
        max_tokens: int = 8096,
        temperature: float = 0.7,
    ) -> tuple[str, int, float]:
        """Complete using the preferred provider/model for a generation role.

        Roles (see ``settings.ROLE_MODEL_MAP``):
        - ``planner``: deck outline and strategy decisions
        - ``writer``: slide writing
        - ``critic``: quality critique and rewrite
        - ``research``: research analysis/summarization
        - ``vision``: image/visual reasoning prompts
        - ``repair``: schema/layout repair
        - ``summarize``: compression of long text
        - ``json_fix``: cheap JSON/schema fixing

        If the role-preferred provider is unconfigured or fails, falls back
        to the normal :meth:`complete` chain. Always returns the same
        ``(text, tokens, cost)`` tuple as :meth:`complete`.
        """
        # Apply token pruning to the user payload before any expensive call.
        user = _prune_user_text(user)

        mapping = settings.ROLE_MODEL_MAP
        choice = mapping.get(role)
        if choice is not None:
            provider, model = choice
            handler = self._handler_for(provider)
            logger.info(
                "ai.role_dispatch",
                extra={
                    "role": role,
                    "preferred_provider": provider,
                    "preferred_model": model,
                    "configured": handler is not None,
                },
            )
            if handler is not None:
                try:
                    # All provider handlers accept ``model=`` (keyword-only)
                    # so the role's exact model is honored, not the env default.
                    result = await handler(
                        system, user, max_tokens, temperature, model=model
                    )
                    logger.info(
                        "ai.role_ok",
                        extra={
                            "role": role,
                            "provider": result.provider,
                            "model": result.model,
                            "tokens": result.tokens,
                        },
                    )
                    return result.text, result.tokens, result.cost_usd
                except Exception as exc:
                    logger.warning(
                        "ai.role_failed_falling_back",
                        extra={
                            "role": role,
                            "provider": provider,
                            "model": model,
                            "err": str(exc)[:200],
                        },
                    )

        # Fallback: existing provider chain.
        return await self.complete(system, user, max_tokens, temperature)


# ── Phase 6W: token / context pruning ─────────────────────────────────────
def prune_messages(
    messages: list[dict[str, str]],
    max_tokens: int | None = None,
    keep_last: int | None = None,
) -> list[dict[str, str]]:
    """Approximate, dependency-free message pruning.

    Strategy (preserves the most important parts):
    1. System messages are always kept (de-duplicated, first occurrence wins).
    2. The last ``keep_last`` non-system messages are always kept verbatim.
       These typically contain the most recent user request and the output
       contract — never trim them.
    3. If still over budget, the OLDEST middle messages are dropped first
       (FIFO), and a single placeholder is inserted noting the elision.
    4. As a final safeguard, if a single very long message still exceeds the
       budget, that one message is middle-truncated (head + tail kept).

    Budget is approximated as ``max_tokens * 4`` chars. Always returns a new
    list; never mutates the input messages in place.
    """
    if not messages:
        return []

    max_tok = max_tokens if max_tokens is not None else settings.MAX_CONTEXT_TOKENS
    keep_n = keep_last if keep_last is not None else settings.KEEP_LAST_MESSAGES
    char_budget = max(1000, max_tok * 4)

    system_msgs: list[dict[str, str]] = []
    other_msgs: list[dict[str, str]] = []
    seen_system_content: set[str] = set()
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role", "")
        content = m.get("content", "") or ""
        if role == "system":
            if content not in seen_system_content:
                seen_system_content.add(content)
                system_msgs.append({"role": "system", "content": content})
        else:
            other_msgs.append({"role": role, "content": content})

    # Always keep the last ``keep_n`` non-system messages verbatim.
    if keep_n > 0 and len(other_msgs) > keep_n:
        protected_tail = other_msgs[-keep_n:]
        middle = other_msgs[:-keep_n]
    else:
        protected_tail = other_msgs[:]
        middle = []

    pruned = system_msgs + middle + protected_tail

    def total() -> int:
        return sum(len(m.get("content", "")) for m in pruned)

    # Drop oldest middle messages first until under budget.
    dropped = 0
    while total() > char_budget and middle:
        middle.pop(0)
        dropped += 1
        pruned = system_msgs + middle + protected_tail
    if dropped:
        pruned = (
            system_msgs
            + [{"role": "system", "content": f"[...{dropped} earlier message(s) elided for context budget...]"}]
            + middle
            + protected_tail
        )

    # Final safeguard: if still over budget, middle-truncate the single
    # longest message (preserving its head and tail).
    if total() > char_budget:
        idx = max(range(len(pruned)), key=lambda i: len(pruned[i].get("content", "")))
        content = pruned[idx].get("content", "") or ""
        overflow = total() - char_budget
        if len(content) > overflow + 400:
            keep = len(content) - overflow - 200
            tail_n = int(keep * 0.30)
            head_n = keep - tail_n
            new_content = (
                content[:head_n]
                + f"\n\n[...truncated {overflow + 200} chars from middle for context budget...]\n\n"
                + content[-tail_n:]
            )
            pruned[idx] = {"role": pruned[idx].get("role", "user"), "content": new_content}
    return pruned


def _prune_user_text(user: str) -> str:
    """Middle-truncate a long user prompt while preserving head and tail.

    The end of NEXUS prompts always contains the output contract / format
    instructions ("Return ONLY a JSON array...", etc.). Naive end-truncation
    silently drops these and produces malformed output. Middle-truncation
    keeps both the question framing (head) and the output contract (tail)
    and only sacrifices the long research/context block in between.
    """
    if not user:
        return user
    char_budget = max(1000, settings.MAX_CONTEXT_TOKENS * 4)
    if len(user) <= char_budget:
        return user
    # Reserve ~30% for tail (output contract), ~55% for head, ~15% sacrificed.
    keep = char_budget - 200  # marker overhead
    tail_chars = int(keep * 0.30)
    head_chars = keep - tail_chars
    head = user[:head_chars]
    tail = user[-tail_chars:]
    return f"{head}\n\n[...truncated {len(user) - keep} chars from middle for context budget...]\n\n{tail}"


# Backwards compatibility — older modules still import ClaudeService.
ClaudeService = AIService

"""Compatibility shim — `ClaudeService` was renamed to `AIService`.

New code should import from `services.ai_service` directly.
"""

from services.ai_service import AIService, ClaudeService, CompletionResult

__all__ = ["AIService", "ClaudeService", "CompletionResult"]

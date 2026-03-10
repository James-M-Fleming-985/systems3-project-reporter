"""
AI Chat Service - Claude API wrapper for project management chat
Handles message sending, token counting, and staleness detection.
"""
import os
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Claude model context windows
MODEL_CONTEXT_WINDOWS = {
    "claude-sonnet-4-20250514": 200000,
    "claude-opus-4-20250514": 200000,
    "claude-3-5-sonnet-20241022": 200000,
    "claude-3-opus-20240229": 200000,
    "claude-3-sonnet-20240229": 200000,
    "claude-3-haiku-20240307": 200000,
}

STALENESS_WARNING_THRESHOLD = 0.75
STALENESS_CRITICAL_THRESHOLD = 0.90


class AIChatService:
    """Wraps the Anthropic Claude API for context-aware PM chat."""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = os.getenv("AI_CHAT_MODEL", "claude-sonnet-4-20250514")
        self.max_tokens_response = int(os.getenv("AI_CHAT_MAX_TOKENS", "4096"))
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise RuntimeError(
                    "anthropic package not installed. Install with: pip install anthropic"
                )
        return self._client

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def send_message(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Send a message to Claude and return the response with token usage.

        Args:
            system_prompt: Context-aware system prompt
            messages: Conversation history [{role, content}, ...]

        Returns:
            {reply, input_tokens, output_tokens}
        """
        if not self.is_configured():
            raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens_response,
            system=system_prompt,
            messages=messages,
        )

        reply = response.content[0].text if response.content else ""
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        return {
            "reply": reply,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate (1 token ≈ 4 chars for English text)."""
        return max(1, len(text) // 4)

    def get_context_window(self) -> int:
        return MODEL_CONTEXT_WINDOWS.get(self.model, 200000)

    def check_staleness(self, total_tokens_used: int) -> Dict[str, Any]:
        """Check conversation staleness based on token usage."""
        context_window = self.get_context_window()
        ratio = total_tokens_used / context_window if context_window else 0

        return {
            "tokens_used": total_tokens_used,
            "context_window": context_window,
            "context_remaining": context_window - total_tokens_used,
            "usage_ratio": round(ratio, 3),
            "staleness_warning": ratio >= STALENESS_WARNING_THRESHOLD,
            "suggest_new_conversation": ratio >= STALENESS_CRITICAL_THRESHOLD,
        }

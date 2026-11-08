"""LLM access layer. The production implementation uses the Anthropic Claude API from the backend only.

All calls return schema-constrained JSON (structured outputs) so model output can be validated before use.
Case documents are passed as untrusted data; see engine/prompts.py for the injection guard.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..config import get_settings

log = logging.getLogger(__name__)


class LLMError(Exception):
    pass


@dataclass
class LLMResult:
    data: dict
    model: str
    usage: dict = field(default_factory=dict)


class LLMClient(Protocol):
    def structured(self, *, purpose: str, system: str, content: list[dict], schema: dict,
                   model: str | None = None, max_tokens: int = 32000) -> LLMResult: ...


class AnthropicLLM:
    def __init__(self) -> None:
        import anthropic

        s = get_settings()
        self._anthropic = anthropic
        kwargs: dict[str, Any] = {"max_retries": 4, "timeout": 900}
        if s.anthropic_api_key:
            kwargs["api_key"] = s.anthropic_api_key
        self.client = anthropic.Anthropic(**kwargs)

    def structured(self, *, purpose: str, system: str, content: list[dict], schema: dict,
                   model: str | None = None, max_tokens: int = 32000) -> LLMResult:
        s = get_settings()
        model = model or s.ai_model
        params: dict[str, Any] = dict(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
            thinking={"type": "adaptive"},
            output_config={"effort": s.ai_effort, "format": {"type": "json_schema", "schema": schema}},
        )
        try:
            if s.ai_server_fallback:
                with self.client.beta.messages.stream(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params
                ) as stream:
                    msg = stream.get_final_message()
            else:
                with self.client.messages.stream(**params) as stream:
                    msg = stream.get_final_message()
        except self._anthropic.RateLimitError as e:
            raise LLMError("AI service is rate-limited; the job will be retried") from e
        except self._anthropic.APIStatusError as e:
            raise LLMError(f"AI service error {e.status_code}: {e.message}") from e
        except self._anthropic.APIConnectionError as e:
            raise LLMError("Could not reach the AI service; the job will be retried") from e

        if msg.stop_reason == "refusal":
            raise LLMError(f"AI declined the request during {purpose}")
        if msg.stop_reason == "max_tokens":
            raise LLMError(f"AI output was cut off during {purpose}; increase max_tokens or reduce scope")
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError(f"AI returned invalid JSON during {purpose}") from e
        usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens,
                 "cache_read_input_tokens": getattr(msg.usage, "cache_read_input_tokens", 0) or 0}
        log.info("llm %s model=%s usage=%s", purpose, msg.model, usage)
        return LLMResult(data=data, model=msg.model, usage=usage)


_override: LLMClient | None = None
_default: LLMClient | None = None


def set_llm(client: LLMClient | None) -> None:
    """Inject an alternative client (used by the automated test-suite)."""
    global _override
    _override = client


def get_llm() -> LLMClient:
    global _default
    if _override is not None:
        return _override
    if _default is None:
        _default = AnthropicLLM()
    return _default

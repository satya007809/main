"""Exercises the production AnthropicLLM through the real SDK with a mocked HTTP transport (no network)."""
import json

import httpx2 as httpx
import pytest

from app.llm.client import AnthropicLLM, LLMError


def _sse(events: list[dict]) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def _stream_events(text: str, stop_reason: str = "end_turn") -> list[dict]:
    return [
        {"type": "message_start", "message": {"id": "msg_1", "type": "message", "role": "assistant",
                                              "model": "claude-opus-5-5", "content": [], "stop_reason": None,
                                              "stop_sequence": None,
                                              "usage": {"input_tokens": 120, "output_tokens": 1}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
         "usage": {"output_tokens": 42}},
        {"type": "message_stop"},
    ]


def _client(handler) -> AnthropicLLM:
    import anthropic

    llm = AnthropicLLM.__new__(AnthropicLLM)
    llm._anthropic = anthropic
    llm.client = anthropic.Anthropic(api_key="test-key", base_url="https://api.test",
                                     http_client=httpx.Client(transport=httpx.MockTransport(handler)), max_retries=0)
    return llm


SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}


def test_request_shape_and_parsing():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        seen["beta"] = req.headers.get("anthropic-beta", "")
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              content=_sse(_stream_events('{"ok": true}')))

    res = _client(handler).structured(purpose="t", system="SYS", content=[{"type": "text", "text": "hi"}], schema=SCHEMA)
    assert res.data == {"ok": True} and res.usage["output_tokens"] == 42
    b = seen["body"]
    assert b["model"] == "claude-opus-5-5" and b["stream"] is True
    assert b["thinking"] == {"type": "adaptive"}
    assert b["output_config"]["format"] == {"type": "json_schema", "schema": SCHEMA}
    assert b["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert b["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in seen["beta"]


def test_refusal_and_truncation_raise():
    for stop in ("refusal", "max_tokens"):
        llm = _client(lambda req, s=stop: httpx.Response(200, headers={"content-type": "text/event-stream"},
                                                        content=_sse(_stream_events('{"ok"', s))))
        with pytest.raises(LLMError):
            llm.structured(purpose="t", system="S", content=[{"type": "text", "text": "x"}], schema=SCHEMA)


def test_api_error_maps_to_llm_error():
    llm = _client(lambda req: httpx.Response(529, json={"type": "error", "error": {"type": "overloaded_error",
                                                                                     "message": "Overloaded"}}))
    with pytest.raises(LLMError):
        llm.structured(purpose="t", system="S", content=[{"type": "text", "text": "x"}], schema=SCHEMA)

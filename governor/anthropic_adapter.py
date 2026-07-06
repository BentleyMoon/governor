"""Adapter that translates between OpenAI chat-completion format and Anthropic Messages API.

Anthropic's API differs from OpenAI's in several ways:
  - Endpoint: /v1/messages (not /v1/chat/completions)
  - Auth: x-api-key header (not Authorization: Bearer)
  - Version: anthropic-version header is required
  - Request: system messages go in a top-level `system` field, not in `messages`
  - Request: max_tokens is required (not optional)
  - Response: `content` is a list of typed blocks, not a string
  - Response: usage keys are input_tokens/output_tokens (not prompt_/completion_)

Streaming translation is NOT implemented yet — streaming requests against an
Anthropic backend will be downgraded to non-streaming with a warning.
"""

from __future__ import annotations

from typing import Any

ANTHROPIC_VERSION = "2023-06-01"


def is_anthropic_backend(base_url: str) -> bool:
    return "anthropic.com" in base_url


def to_anthropic_request(openai_payload: dict[str, Any]) -> dict[str, Any]:
    """Translate an OpenAI chat-completion request to Anthropic Messages format."""
    messages = openai_payload.get("messages", [])

    # Anthropic requires system messages outside the messages array
    system_messages = [m for m in messages if m.get("role") == "system"]
    chat_messages = [m for m in messages if m.get("role") != "system"]

    request: dict[str, Any] = {
        "model": openai_payload["model"],
        "messages": chat_messages,
        # max_tokens is REQUIRED on Anthropic; default to a reasonable value
        "max_tokens": openai_payload.get("max_tokens") or 1024,
    }

    if system_messages:
        # Concatenate multiple system messages with double newline
        request["system"] = "\n\n".join(
            m.get("content", "") for m in system_messages if m.get("content")
        )

    if "temperature" in openai_payload and openai_payload["temperature"] is not None:
        request["temperature"] = openai_payload["temperature"]

    return request


def to_anthropic_headers(api_key: str) -> dict[str, str]:
    return {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }


def to_anthropic_url(base_url: str) -> str:
    """Anthropic uses /v1/messages, not /v1/chat/completions."""
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


_FINISH_REASON_MAP = {
    "end_turn": "stop",
    "max_tokens": "length",
    "stop_sequence": "stop",
    "tool_use": "tool_calls",
}


def from_anthropic_response(anthropic_body: dict[str, Any], requested_model: str) -> dict[str, Any]:
    """Translate an Anthropic Messages response to OpenAI chat-completion format."""
    text_parts: list[str] = []
    for block in anthropic_body.get("content", []):
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))
    text = "".join(text_parts)

    anthropic_usage = anthropic_body.get("usage", {}) or {}
    input_tokens = int(anthropic_usage.get("input_tokens", 0))
    output_tokens = int(anthropic_usage.get("output_tokens", 0))

    finish_reason = _FINISH_REASON_MAP.get(
        anthropic_body.get("stop_reason") or "", "stop"
    )

    return {
        "id": anthropic_body.get("id", "msg-unknown"),
        "object": "chat.completion",
        "model": anthropic_body.get("model", requested_model),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    }

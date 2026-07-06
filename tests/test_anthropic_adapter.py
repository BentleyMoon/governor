"""Tests for the Anthropic adapter.

These don't hit the network — they validate request/response translation only.
"""

from governor.anthropic_adapter import (
    from_anthropic_response,
    is_anthropic_backend,
    to_anthropic_headers,
    to_anthropic_request,
    to_anthropic_url,
)


def test_is_anthropic_backend():
    assert is_anthropic_backend("https://api.anthropic.com/v1")
    assert is_anthropic_backend("https://api.anthropic.com")
    assert not is_anthropic_backend("https://api.openai.com/v1")
    assert not is_anthropic_backend("http://localhost:8000")


def test_to_anthropic_url_appends_messages():
    assert to_anthropic_url("https://api.anthropic.com/v1") == "https://api.anthropic.com/v1/messages"
    assert to_anthropic_url("https://api.anthropic.com") == "https://api.anthropic.com/v1/messages"
    # Trailing slash tolerated
    assert to_anthropic_url("https://api.anthropic.com/v1/") == "https://api.anthropic.com/v1/messages"


def test_to_anthropic_headers_uses_x_api_key():
    h = to_anthropic_headers("sk-ant-fake")
    assert h["x-api-key"] == "sk-ant-fake"
    assert h["anthropic-version"] == "2023-06-01"
    assert h["Content-Type"] == "application/json"
    assert "Authorization" not in h


def test_to_anthropic_request_basic():
    r = to_anthropic_request({
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert r["model"] == "claude-sonnet-4-6"
    assert r["messages"] == [{"role": "user", "content": "hi"}]
    # max_tokens must be defaulted (Anthropic requires it)
    assert r["max_tokens"] == 1024


def test_to_anthropic_request_extracts_system_messages():
    r = to_anthropic_request({
        "model": "claude-sonnet-4-6",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "hi"},
        ],
    })
    assert r["system"] == "You are a helpful assistant."
    assert r["messages"] == [{"role": "user", "content": "hi"}]


def test_to_anthropic_request_concatenates_multiple_system_messages():
    r = to_anthropic_request({
        "model": "claude-sonnet-4-6",
        "messages": [
            {"role": "system", "content": "Be helpful."},
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "hi"},
        ],
    })
    assert r["system"] == "Be helpful.\n\nBe concise."


def test_to_anthropic_request_preserves_temperature_and_max_tokens():
    r = to_anthropic_request({
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.7,
        "max_tokens": 256,
    })
    assert r["temperature"] == 0.7
    assert r["max_tokens"] == 256


def test_from_anthropic_response_basic():
    body = {
        "id": "msg_01ABC",
        "model": "claude-sonnet-4-6",
        "content": [{"type": "text", "text": "Hello!"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    r = from_anthropic_response(body, "claude-sonnet-4-6")
    assert r["object"] == "chat.completion"
    assert r["id"] == "msg_01ABC"
    assert r["choices"][0]["message"]["content"] == "Hello!"
    assert r["choices"][0]["finish_reason"] == "stop"
    assert r["usage"]["prompt_tokens"] == 10
    assert r["usage"]["completion_tokens"] == 5
    assert r["usage"]["total_tokens"] == 15


def test_from_anthropic_response_handles_multiple_text_blocks():
    body = {
        "id": "msg_01",
        "model": "claude-sonnet-4-6",
        "content": [
            {"type": "text", "text": "Part 1. "},
            {"type": "text", "text": "Part 2."},
        ],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 5, "output_tokens": 10},
    }
    r = from_anthropic_response(body, "claude-sonnet-4-6")
    assert r["choices"][0]["message"]["content"] == "Part 1. Part 2."


def test_from_anthropic_response_max_tokens_maps_to_length():
    body = {
        "id": "msg_01",
        "content": [{"type": "text", "text": "..."}],
        "stop_reason": "max_tokens",
        "usage": {"input_tokens": 10, "output_tokens": 1024},
    }
    r = from_anthropic_response(body, "claude-sonnet-4-6")
    assert r["choices"][0]["finish_reason"] == "length"


def test_from_anthropic_response_handles_missing_usage():
    body = {
        "id": "msg_01",
        "content": [{"type": "text", "text": "hi"}],
        "stop_reason": "end_turn",
    }
    r = from_anthropic_response(body, "claude-sonnet-4-6")
    assert r["usage"]["prompt_tokens"] == 0
    assert r["usage"]["completion_tokens"] == 0

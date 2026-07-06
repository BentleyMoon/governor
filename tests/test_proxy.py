"""End-to-end proxy tests with mocked upstream HTTP.

These validate that the routing decision dispatches to the correct backend URL
+ model, that usage tracking accumulates correctly per tier, and that the
shape of the /v1/usage response matches what billing logic will consume.

We mock httpx.AsyncClient.post and httpx.AsyncClient.stream so no real network
call goes out.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from governor.proxy import create_app
from governor.router import ProxyConfig


def _fake_response(model: str, content: str, prompt_tokens: int, completion_tokens: int) -> dict[str, Any]:
    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


@contextmanager
def _set_env(**kwargs: str):
    saved = {k: os.environ.get(k) for k in kwargs}
    try:
        for k, v in kwargs.items():
            os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _mock_post(captured: dict[str, Any], response_json: dict[str, Any]):
    """Build a mock for httpx.AsyncClient context manager + .post()."""
    response = MagicMock()
    response.status_code = 200
    response.json = MagicMock(return_value=response_json)
    response.text = ""
    client = MagicMock()
    async def _post(url, json=None, headers=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return response
    client.post = _post
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=cm)


def test_healthz():
    with TestClient(create_app()) as c:
        r = c.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "version": "0.1.0"}


def test_usage_starts_empty():
    with TestClient(create_app()) as c:
        r = c.get("/v1/usage")
        assert r.status_code == 200
        body = r.json()
        assert body["per_tier"] == []
        assert body["total_savings_usd"] == 0
        assert body["savings_pct"] == 0.0


def test_coding_request_dispatches_to_standard():
    config = ProxyConfig(
        standard_base_url="https://standard.test/v1",
        standard_model="gpt-4o",
    )
    captured: dict[str, Any] = {}
    with _set_env(GOVERNOR_OPENAI_KEY="sk-test"):
        with patch("governor.proxy.httpx.AsyncClient", _mock_post(captured, _fake_response("gpt-4o", "ok", 100, 50))):
            with TestClient(create_app(config)) as c:
                r = c.post("/v1/chat/completions", json={
                    "messages": [{"role": "user", "content": "fix the bug in main.py"}]
                })
    assert r.status_code == 200
    body = r.json()
    assert body["_governor"]["tier"] == "standard"
    assert body["_governor"]["model"] == "gpt-4o"
    assert captured["url"] == "https://standard.test/v1/chat/completions"
    assert captured["json"]["model"] == "gpt-4o"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"


def test_architecture_request_dispatches_to_frontier():
    config = ProxyConfig(
        frontier_base_url="https://frontier.test/v1",
        frontier_model="claude-sonnet-4-6",
    )
    captured: dict[str, Any] = {}
    with _set_env(GOVERNOR_OPENAI_KEY="sk-test"):
        with patch("governor.proxy.httpx.AsyncClient", _mock_post(captured, _fake_response("claude-sonnet-4-6", "ok", 200, 100))):
            with TestClient(create_app(config)) as c:
                r = c.post("/v1/chat/completions", json={
                    "messages": [{"role": "user", "content": "redesign the auth system from scratch"}]
                })
    assert r.status_code == 200
    assert r.json()["_governor"]["tier"] == "frontier"
    assert captured["url"] == "https://frontier.test/v1/chat/completions"


def test_simple_request_dispatches_to_economy():
    config = ProxyConfig(
        economy_base_url="https://economy.test/v1",
        economy_model="gpt-4o-mini",
    )
    captured: dict[str, Any] = {}
    with _set_env(GOVERNOR_OPENAI_KEY="sk-test"):
        with patch("governor.proxy.httpx.AsyncClient", _mock_post(captured, _fake_response("gpt-4o-mini", "ok", 20, 10))):
            with TestClient(create_app(config)) as c:
                r = c.post("/v1/chat/completions", json={
                    "messages": [{"role": "user", "content": "thanks"}]
                })
    assert r.status_code == 200
    assert r.json()["_governor"]["tier"] == "economy"
    assert captured["url"] == "https://economy.test/v1/chat/completions"


def test_usage_accumulates_across_requests():
    config = ProxyConfig()
    captured: dict[str, Any] = {}
    with _set_env(GOVERNOR_OPENAI_KEY="sk-test"):
        with patch("governor.proxy.httpx.AsyncClient", _mock_post(captured, _fake_response("gpt-4o-mini", "ok", 1000, 500))):
            with TestClient(create_app(config)) as c:
                # 3 simple requests, all routed to economy
                for _ in range(3):
                    r = c.post("/v1/chat/completions", json={
                        "messages": [{"role": "user", "content": "thanks"}]
                    })
                    assert r.status_code == 200
                usage = c.get("/v1/usage").json()
    assert len(usage["per_tier"]) == 1
    economy = usage["per_tier"][0]
    assert economy["tier"] == "economy"
    assert economy["request_count"] == 3
    assert economy["input_tokens"] == 3000
    assert economy["output_tokens"] == 1500
    # Per request: 1000 input + 500 output. Per request cost on gpt-4o-mini:
    #   1000 * $0.15/1M + 500 * $0.60/1M = $0.00015 + $0.00030 = $0.00045
    # Per request cost on counterfactual sonnet:
    #   1000 * $3.00/1M + 500 * $15.00/1M = $0.00300 + $0.00750 = $0.01050
    assert abs(economy["did_cost_usd"] - 0.00045 * 3) < 1e-6
    assert abs(economy["would_have_cost_usd"] - 0.01050 * 3) < 1e-6
    assert usage["savings_pct"] > 90.0  # economy vs frontier should save 95%+


def test_missing_api_key_returns_500():
    """No API key in any env var should raise 500 with the expected env-var name."""
    # Make sure no governor keys are set
    saved = {k: os.environ.pop(k, None) for k in [
        "GOVERNOR_OPENAI_KEY", "GOVERNOR_ECONOMY_KEY",
        "GOVERNOR_STANDARD_KEY", "GOVERNOR_FRONTIER_KEY",
    ]}
    try:
        with TestClient(create_app(), raise_server_exceptions=False) as c:
            r = c.post("/v1/chat/completions", json={
                "messages": [{"role": "user", "content": "thanks"}]
            })
        assert r.status_code == 500
        assert "GOVERNOR_ECONOMY_KEY" in r.json()["detail"]
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_malformed_payload_returns_422():
    with TestClient(create_app()) as c:
        r = c.post("/v1/chat/completions", json={"bad": "payload"})
    assert r.status_code == 422


def test_anthropic_backend_full_roundtrip():
    """Validate the complete Anthropic flow: classify → adapt request → mock
    upstream Anthropic response → adapt response back to OpenAI format → record
    usage. This proves the adapter works end-to-end without needing a real key.
    """
    config = ProxyConfig(
        standard_base_url="https://api.anthropic.com/v1",
        standard_model="claude-sonnet-4-6",
    )
    captured: dict[str, Any] = {}
    # Build an Anthropic-shaped fake response (note: NOT OpenAI shape)
    anthropic_response = {
        "id": "msg_01TEST",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-4-6",
        "content": [{"type": "text", "text": "Reverse with lst[::-1]"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 12, "output_tokens": 8},
    }
    with _set_env(GOVERNOR_ANTHROPIC_KEY="sk-ant-fake-test"):
        with patch("governor.proxy.httpx.AsyncClient", _mock_post(captured, anthropic_response)):
            with TestClient(create_app(config)) as c:
                r = c.post("/v1/chat/completions", json={
                    "messages": [{"role": "user", "content": "fix the bug in main.py"}]
                })
    # 1. Response is OpenAI-shaped (translation worked)
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "Reverse with lst[::-1]"
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["usage"]["prompt_tokens"] == 12
    assert body["usage"]["completion_tokens"] == 8
    # 2. Request was sent to /v1/messages, NOT /v1/chat/completions
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    # 3. Anthropic-style headers (NOT Bearer)
    assert captured["headers"]["x-api-key"] == "sk-ant-fake-test"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert "Authorization" not in captured["headers"]
    # 4. Request body is in Anthropic format with required max_tokens
    assert captured["json"]["max_tokens"] == 1024
    assert captured["json"]["model"] == "claude-sonnet-4-6"
    # 5. Governor metadata is attached
    assert body["_governor"]["tier"] == "standard"
    assert body["_governor"]["model"] == "claude-sonnet-4-6"


def test_anthropic_backend_extracts_system_message():
    """System messages must be extracted to top-level `system` field."""
    config = ProxyConfig(
        economy_base_url="https://api.anthropic.com/v1",
        economy_model="claude-haiku-4-5",
    )
    captured: dict[str, Any] = {}
    response = {
        "id": "msg_01",
        "content": [{"type": "text", "text": "hi"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 5, "output_tokens": 1},
    }
    with _set_env(GOVERNOR_ANTHROPIC_KEY="sk-ant-fake"):
        with patch("governor.proxy.httpx.AsyncClient", _mock_post(captured, response)):
            with TestClient(create_app(config)) as c:
                c.post("/v1/chat/completions", json={
                    "messages": [
                        {"role": "system", "content": "You are concise."},
                        {"role": "user", "content": "thanks"},
                    ]
                })
    # System message extracted to top-level
    assert captured["json"]["system"] == "You are concise."
    # And NOT in the messages array
    roles_sent = [m["role"] for m in captured["json"]["messages"]]
    assert "system" not in roles_sent
    assert "user" in roles_sent


def test_anthropic_backend_streaming_is_downgraded():
    """Streaming requests against Anthropic are silently downgraded to non-streaming."""
    config = ProxyConfig(
        standard_base_url="https://api.anthropic.com/v1",
        standard_model="claude-sonnet-4-6",
    )
    captured: dict[str, Any] = {}
    response = {
        "id": "msg_01",
        "content": [{"type": "text", "text": "ok"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 5, "output_tokens": 1},
    }
    with _set_env(GOVERNOR_ANTHROPIC_KEY="sk-ant-fake"):
        with patch("governor.proxy.httpx.AsyncClient", _mock_post(captured, response)):
            with TestClient(create_app(config)) as c:
                r = c.post("/v1/chat/completions", json={
                    "messages": [{"role": "user", "content": "fix the bug"}],
                    "stream": True,
                })
    # Got a JSON response, not a stream
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/json")
    body = r.json()
    # Marker tells the caller they got a non-streamed result
    assert body["_governor"]["stream_downgraded"] is True
    # The upstream payload to Anthropic does NOT have stream=True
    assert captured["json"].get("stream") is not True

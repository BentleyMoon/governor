"""OpenAI-compatible proxy that routes via the governor classifier.

Drop-in: point your client's `base_url` at `http://localhost:8000/v1` and set
GOVERNOR_OPENAI_KEY (or per-tier keys) in your environment.

Supports:
  - /v1/chat/completions  — non-streaming and streaming (SSE)
  - /v1/usage             — per-tier token counts and estimated savings
  - /healthz              — liveness check

Backends:
  - OpenAI-compatible (default)
  - Anthropic Messages API (auto-detected by `anthropic.com` in base_url;
    streaming not yet implemented for Anthropic backends — falls back to
    non-streaming with a header note).
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from governor.anthropic_adapter import (
    from_anthropic_response,
    is_anthropic_backend,
    to_anthropic_headers,
    to_anthropic_request,
    to_anthropic_url,
)
from governor.pricing import estimate_savings
from governor.router import GovernorDecision, ModelTier, ProxyConfig, SessionState, classify_turn


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool | None = False


def _last_user_text(messages: list[ChatMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.content
    return ""


def _backend_for(tier: ModelTier, config: ProxyConfig) -> tuple[str, str, str]:
    if tier == ModelTier.ECONOMY:
        return config.economy_base_url, config.economy_model, "GOVERNOR_ECONOMY_KEY"
    if tier == ModelTier.STANDARD:
        return config.standard_base_url, config.standard_model, "GOVERNOR_STANDARD_KEY"
    return config.frontier_base_url, config.frontier_model, "GOVERNOR_FRONTIER_KEY"


def _resolve_api_key(key_env: str, base_url: str) -> str:
    """Find the right key for this backend in env vars."""
    fallback_envs = ["GOVERNOR_OPENAI_KEY"]
    if is_anthropic_backend(base_url):
        fallback_envs = ["GOVERNOR_ANTHROPIC_KEY", "ANTHROPIC_API_KEY"]
    candidates = [key_env, *fallback_envs]
    for env in candidates:
        v = os.environ.get(env)
        if v:
            return v
    raise HTTPException(
        status_code=500,
        detail=f"No API key found in {', '.join(candidates)}",
    )


def _build_upstream_request(
    base_url: str, model: str, api_key: str, openai_payload: dict[str, Any], stream: bool,
) -> tuple[str, dict[str, Any], dict[str, str]]:
    """Return (url, payload, headers) ready to POST upstream."""
    if is_anthropic_backend(base_url):
        anthropic_payload = to_anthropic_request({**openai_payload, "model": model})
        if stream:
            # Streaming translation not yet implemented; warning is via response header.
            anthropic_payload["stream"] = False
        url = to_anthropic_url(base_url)
        headers = to_anthropic_headers(api_key)
        return url, anthropic_payload, headers

    payload = {**openai_payload, "model": model}
    if stream:
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return url, payload, headers


def _record_usage(
    store: dict[str, dict[str, Any]],
    decision: GovernorDecision,
    model: str,
    usage_block: dict[str, Any] | None,
    counterfactual_model: str,
) -> None:
    if not usage_block:
        return
    input_tokens = int(usage_block.get("prompt_tokens", 0))
    output_tokens = int(usage_block.get("completion_tokens", 0))
    would, did, saved = estimate_savings(
        model, input_tokens, output_tokens, counterfactual_model=counterfactual_model,
    )
    bucket = store.setdefault(decision.model_tier.value, {
        "tier": decision.model_tier.value,
        "model": model,
        "input_tokens": 0,
        "output_tokens": 0,
        "would_have_cost_usd": 0.0,
        "did_cost_usd": 0.0,
        "savings_usd": 0.0,
        "request_count": 0,
    })
    bucket["input_tokens"] += input_tokens
    bucket["output_tokens"] += output_tokens
    bucket["would_have_cost_usd"] += would
    bucket["did_cost_usd"] += did
    bucket["savings_usd"] += saved
    bucket["request_count"] += 1


def create_app(config: ProxyConfig | None = None) -> FastAPI:
    config = config or ProxyConfig()
    app = FastAPI(title="Governor", version="0.1.0")
    sessions: dict[str, SessionState] = {}
    usage_store: dict[str, dict[str, Any]] = defaultdict(dict)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/v1/usage")
    def usage() -> dict[str, Any]:
        per_tier = list(usage_store.values())
        total_would = sum(b.get("would_have_cost_usd", 0.0) for b in per_tier)
        total_did = sum(b.get("did_cost_usd", 0.0) for b in per_tier)
        total_saved = total_would - total_did
        savings_pct = (total_saved / total_would * 100.0) if total_would else 0.0
        return {
            "per_tier": per_tier,
            "total_would_have_cost_usd": round(total_would, 4),
            "total_did_cost_usd": round(total_did, 4),
            "total_savings_usd": round(total_saved, 4),
            "savings_pct": round(savings_pct, 2),
        }

    async def _proxy_stream(
        url: str, payload: dict[str, Any], headers: dict[str, str],
    ) -> AsyncIterator[bytes]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as r:
                if r.status_code >= 400:
                    body = await r.aread()
                    yield body
                    return
                async for chunk in r.aiter_raw():
                    yield chunk

    @app.post("/v1/chat/completions")
    async def chat(req: ChatRequest, raw: Request) -> Any:
        session_id = raw.headers.get("x-governor-session", "default")
        session = sessions.setdefault(session_id, SessionState())

        user_text = _last_user_text(req.messages)
        decision = classify_turn(user_text, session=session, config=config)
        session.turn_history.append(decision.turn_kind)

        base_url, model, key_env = _backend_for(decision.model_tier, config)
        api_key = _resolve_api_key(key_env, base_url)

        openai_payload: dict[str, Any] = {
            "model": model,
            "messages": [m.model_dump() for m in req.messages],
        }
        if req.temperature is not None:
            openai_payload["temperature"] = req.temperature
        if req.max_tokens is not None:
            openai_payload["max_tokens"] = req.max_tokens

        # Streaming on Anthropic backends is downgraded to non-streaming.
        will_stream = bool(req.stream) and not is_anthropic_backend(base_url)

        url, upstream_payload, headers = _build_upstream_request(
            base_url, model, api_key, openai_payload, will_stream,
        )

        if will_stream:
            return StreamingResponse(
                _proxy_stream(url, upstream_payload, headers),
                media_type="text/event-stream",
                headers={"x-governor-tier": decision.model_tier.value},
            )

        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, json=upstream_payload, headers=headers)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)

        body = r.json()
        if is_anthropic_backend(base_url):
            body = from_anthropic_response(body, model)

        _record_usage(
            usage_store, decision, model, body.get("usage"),
            counterfactual_model=config.frontier_model,
        )
        body["_governor"] = {
            "tier": decision.model_tier.value,
            "model": model,
            "reason": decision.reason,
            "workload_class": decision.workload_class,
            "stream_downgraded": bool(req.stream) and is_anthropic_backend(base_url),
        }
        return body

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

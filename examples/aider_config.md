# Using Governor with Aider

Aider is a CLI coding agent that works with any OpenAI-compatible endpoint. Pointing it at Governor takes one environment variable.

## Setup

```bash
# Server side: real OpenAI key, governor serving
export GOVERNOR_OPENAI_KEY=sk-your-real-openai-key
governor serve

# Client side: tell Aider to use the proxy
export OPENAI_API_BASE=http://localhost:8000/v1
export OPENAI_API_KEY=not-used

aider
```

## What Aider sends, and how Governor classifies it

Aider's first turn typically includes test output, file content, and a question. That's a long coding request — Governor will likely route it to STANDARD or FRONTIER depending on length.

| Aider turn type | Likely Governor tier | Why |
|---|---|---|
| Initial fix request with file context | STANDARD | "fix" + file references hit CODING_TERMS |
| Long initial request (>200 words with code) | FRONTIER | Long-coding rule promotes to frontier |
| "/run tests" | STANDARD | "tests" + "fail" hit failure-language CODING_TERMS |
| `/ask` (read-only Q&A) | varies | Depends on the question phrasing |
| `/help` | ECONOMY | Short, no coding keywords |

## Watching the routing

```bash
# In a third terminal:
watch -n 1 'curl -s http://localhost:8000/v1/usage | python -m json.tool'
```

You'll see request_count tick up per tier as you work in Aider.

## Recommended Aider flags

```bash
aider --no-stream    # Easier to debug initial setup; remove once it works
aider --map-tokens 1024  # Smaller repo map = shorter requests = more chances for STANDARD vs FRONTIER routing
```

## When NOT to put Aider behind Governor

- You're working on architecture-grade refactors all day. Governor will route everything to FRONTIER and you'll see ~0% savings. Skip Governor for those sessions.
- You're using a custom Aider model config that already negotiates between models. Two layers of routing fight each other.
- Your Aider workload is small (<100 turns/day). The Governor-side complexity isn't worth it under that volume.

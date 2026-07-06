# Using Governor with Cursor

Cursor lets you point at a custom OpenAI-compatible base URL. Governor is one.

## Setup (5 minutes)

1. **Run Governor locally** with a real OpenAI key:
   ```bash
   export GOVERNOR_OPENAI_KEY=sk-your-real-openai-key
   governor serve
   ```
   (or use `python -m uvicorn governor.proxy:app --port 8000`)

2. **In Cursor**, open Settings → Models → "Custom OpenAI-compatible endpoint"
   - Base URL: `http://localhost:8000/v1`
   - API key: anything (Governor uses the server-side key)
   - Model name: leave blank — Governor selects per request

3. **That's it.** Cursor's chat panel now routes through Governor.

## What you'll see

Cursor doesn't surface the `_governor` metadata, so to verify routing:

- In another terminal: `watch -n 2 'curl -s http://localhost:8000/v1/usage | python -m json.tool'`
- The per-tier counts will tick up as you use Cursor

You should see:
- "thanks" / "got it" follow-ups → ECONOMY
- Most edit-and-debug turns → STANDARD
- "refactor the entire auth module" turns → FRONTIER

## Caveats

- **Cursor's tab-complete** uses a separate fast model and doesn't route through Cursor's chat backend, so Governor doesn't see those calls. Savings are on chat/edit, not tab-complete.
- **Custom prompts in Cursor** that include "production" or other FRONTIER keywords will route to FRONTIER even if the actual ask is small. Tune the keyword list in `governor/router.py` if you have a workload pattern that systematically over-tiers.
- **Fast-edit-mode (Cmd-K)** sends short coding-context turns. These typically route to STANDARD, which is the right tier for most fast-edit work.

## Killing the proxy

When you stop using Governor, point Cursor back at the default endpoint and stop the `governor serve` process. Cursor reverts to direct OpenAI within seconds.

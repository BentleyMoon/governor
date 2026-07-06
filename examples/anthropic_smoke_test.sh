#!/usr/bin/env bash
# Anthropic-backed smoke test for Governor.
#
# Total expected cost: under $0.05 USD (5 cents).
# Configures Haiku 4.5 / Sonnet 4.6 / Opus 4.7 across the 3 tiers.
#
# PREREQUISITE: you have rotated the leaked key and stored the NEW key in
# the ANTHROPIC_API_KEY environment variable. Do NOT paste the key into
# this script. Do NOT echo it. Do NOT share it in any chat or screenshot.
#
# Usage:
#   1. export ANTHROPIC_API_KEY=<your-new-key>   # in your shell, locally
#   2. bash examples/anthropic_smoke_test.sh
#
# The script will refuse to run if ANTHROPIC_API_KEY isn't set.

set -euo pipefail

# --- 1. Verify key is set without printing it ---
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ERROR: ANTHROPIC_API_KEY is not set in your environment."
  echo "Set it with: export ANTHROPIC_API_KEY=<your-key>"
  echo "Then re-run this script. The key never enters this script's source."
  exit 1
fi

# Show only that the key is set, never the value:
echo "ANTHROPIC_API_KEY is set (length: ${#ANTHROPIC_API_KEY} chars). Not printing the value."

# --- 2. Configure Governor for Anthropic-only deployment ---
# These env vars are read by governor.proxy at request time. They tell each
# tier which model + base_url to use and where to find the key.
export GOVERNOR_ECONOMY_MODEL="${GOVERNOR_ECONOMY_MODEL:-claude-haiku-4-5-20251001}"
export GOVERNOR_STANDARD_MODEL="${GOVERNOR_STANDARD_MODEL:-claude-sonnet-4-6}"
export GOVERNOR_FRONTIER_MODEL="${GOVERNOR_FRONTIER_MODEL:-claude-opus-4-7}"

# Override the default base URLs by writing a tiny config-local file. The
# proxy picks up ProxyConfig defaults from governor/router.py; for this
# smoke test we'll use Python's -c to instantiate the app with overrides.
# (Cleaner approach is to refactor ProxyConfig to read env vars; for now
# we'll use a shim.)

# --- 3. Start governor with Anthropic config ---
GOVERNOR_PORT=8765
echo ""
echo "Starting Governor with all 3 tiers pointed at api.anthropic.com..."

python - <<'PYEOF' &
import os
import uvicorn
from governor.router import ProxyConfig
from governor.proxy import create_app

config = ProxyConfig(
    economy_model=os.environ.get("GOVERNOR_ECONOMY_MODEL", "claude-haiku-4-5-20251001"),
    economy_base_url="https://api.anthropic.com/v1",
    standard_model=os.environ.get("GOVERNOR_STANDARD_MODEL", "claude-sonnet-4-6"),
    standard_base_url="https://api.anthropic.com/v1",
    frontier_model=os.environ.get("GOVERNOR_FRONTIER_MODEL", "claude-opus-4-7"),
    frontier_base_url="https://api.anthropic.com/v1",
)
app = create_app(config)
uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
PYEOF

SERVER_PID=$!
trap "kill $SERVER_PID 2>/dev/null || true" EXIT

# --- 4. Wait for server ---
for i in {1..15}; do
  if curl -sf "http://127.0.0.1:${GOVERNOR_PORT}/healthz" > /dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -sf "http://127.0.0.1:${GOVERNOR_PORT}/healthz" > /dev/null 2>&1; then
  echo "ERROR: Server did not start within 15 seconds."
  exit 1
fi
echo "Server up on :${GOVERNOR_PORT}"

# --- 5. Run 4 small test calls. Total expected cost: ~$0.01-0.05. ---

run_call() {
  local prompt="$1"
  local label="$2"
  echo ""
  echo "=== $label ==="
  echo "Prompt: $prompt"
  RESPONSE=$(curl -sf -X POST "http://127.0.0.1:${GOVERNOR_PORT}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":[{\"role\":\"user\",\"content\":\"$prompt\"}],\"max_tokens\":50}" \
    || echo '{"error":"call failed"}')
  echo "$RESPONSE" | python -c "
import sys, json
try:
    body = json.loads(sys.stdin.read())
    if 'error' in body:
        print(f'FAILED: {body}')
        sys.exit(1)
    gov = body.get('_governor', {})
    text = body.get('choices', [{}])[0].get('message', {}).get('content', '')
    usage = body.get('usage', {})
    print(f'  Tier:    {gov.get(\"tier\")}')
    print(f'  Model:   {gov.get(\"model\")}')
    print(f'  Reason:  {gov.get(\"reason\")}')
    print(f'  Tokens:  {usage.get(\"prompt_tokens\")} in / {usage.get(\"completion_tokens\")} out')
    print(f'  Reply:   {text[:80]}')
except Exception as e:
    print(f'PARSE FAILED: {e}')
    print(sys.stdin.read())
"
}

# 1. Greeting → ECONOMY (Haiku)
run_call "Say hello in one word." "Test 1: greeting → ECONOMY"

# 2. Bounded coding → STANDARD (Sonnet)
run_call "Write a Python one-liner to reverse a list." "Test 2: bounded coding → STANDARD"

# 3. Architecture → FRONTIER (Opus)
run_call "Briefly describe how to redesign an auth system to support SSO across tenants." "Test 3: architecture → FRONTIER"

# 4. Production false-positive regression: should NOT route to FRONTIER
run_call "In production we use postgres, just so you know." "Test 4: false-positive regression"

# --- 6. Show cumulative usage ---
echo ""
echo "=== Cumulative usage (saved data) ==="
curl -sf "http://127.0.0.1:${GOVERNOR_PORT}/v1/usage" | python -m json.tool

echo ""
echo "=== Done ==="
echo ""
echo "Expected total spend: \$0.01 - \$0.05 USD."
echo "Verify in https://console.anthropic.com/settings/billing"
echo ""
echo "If all 4 tests showed correct tier routing, Governor works on Anthropic."
echo "Server will be killed when this script exits."

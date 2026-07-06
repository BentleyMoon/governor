#!/usr/bin/env bash
# Minimal Governor smoke test using just curl.
# Requires: governor serve running on :8000, GOVERNOR_OPENAI_KEY exported on the server.

set -euo pipefail

GOVERNOR_URL="${GOVERNOR_URL:-http://localhost:8000}"

echo "=== Health check ==="
curl -s "$GOVERNOR_URL/healthz"
echo
echo

echo "=== Simple turn (expect ECONOMY tier) ==="
curl -s -X POST "$GOVERNOR_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"thanks"}]}' | python -m json.tool | grep -E '"(tier|reason|content)"' | head -6
echo

echo "=== Coding turn (expect STANDARD tier) ==="
curl -s -X POST "$GOVERNOR_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"fix the bug in main.py"}]}' | python -m json.tool | grep -E '"(tier|reason|content)"' | head -6
echo

echo "=== Architecture turn (expect FRONTIER tier) ==="
curl -s -X POST "$GOVERNOR_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"redesign the auth system from scratch"}]}' | python -m json.tool | grep -E '"(tier|reason|content)"' | head -6
echo

echo "=== Cumulative savings ==="
curl -s "$GOVERNOR_URL/v1/usage" | python -m json.tool

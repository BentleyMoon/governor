# Anthropic Smoke Test — Run Me

This is the test for your $20 Anthropic credit. **Run this AFTER rotating the leaked key.**

## Prerequisites checklist

Before you run anything:

- [ ] You've deleted the leaked key at https://console.anthropic.com/settings/keys (the one starting `sk-ant-api03-Urp6au2mSJQK...`)
- [ ] You've issued a NEW key
- [ ] You've stored the new key **only** in your shell environment (NOT in any file in this repo, NOT in a screenshot, NOT pasted in any chat)
- [ ] You're at a terminal in `C:\governor` with Python 3.10+ available
- [ ] Governor is installed (`pip install -e ".[dev]"` from earlier)

## Step 1 — Set your key in the shell

In **PowerShell**:
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."   # paste your NEW key
```

In **Git Bash / WSL**:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Verify it's set without printing the value:
```bash
echo "Length: ${#ANTHROPIC_API_KEY}"   # should print "Length: 108" or similar
```

## Step 2 — Run the smoke test

From `C:\governor`:

```bash
bash examples/anthropic_smoke_test.sh
```

(In PowerShell, you can also use `wsl bash examples/anthropic_smoke_test.sh` or just `bash` if Git Bash is installed.)

**Expected runtime: ~30 seconds**
**Expected cost: $0.01 – $0.05 (1–5 cents)**

## Step 3 — What "passing" looks like

The script runs 4 test calls. Each one should show:

```
=== Test 1: greeting → ECONOMY ===
Prompt: Say hello in one word.
  Tier:    economy
  Model:   claude-haiku-4-5-20251001
  Reason:  Simple greeting or acknowledgment
  Tokens:  10 in / 1 out
  Reply:   Hello

=== Test 2: bounded coding → STANDARD ===
Prompt: Write a Python one-liner to reverse a list.
  Tier:    standard
  Model:   claude-sonnet-4-6
  Reason:  Bounded coding task detected
  Tokens:  15 in / 8 out
  Reply:   `lst[::-1]`

=== Test 3: architecture → FRONTIER ===
Prompt: Briefly describe how to redesign an auth system to support SSO across tenants.
  Tier:    frontier
  Model:   claude-opus-4-7
  Reason:  Architecture, redesign, or multi-file signals detected
  Tokens:  20 in / 50 out
  Reply:   To redesign auth for SSO across tenants...

=== Test 4: false-positive regression ===
Prompt: In production we use postgres, just so you know.
  Tier:    economy             ← MUST be economy, not frontier!
  Model:   claude-haiku-4-5-20251001
  Reason:  No coding signals; handled by economy path
```

Then the cumulative usage block:

```
=== Cumulative usage ===
{
    "per_tier": [
        {"tier": "economy", "request_count": 2, "input_tokens": ..., ...},
        {"tier": "standard", "request_count": 1, ...},
        {"tier": "frontier", "request_count": 1, ...}
    ],
    "total_savings_usd": 0.0XX,
    "savings_pct": XX.X
}
```

## What to report back to me

After the script runs, copy back ONLY the following information:

1. The 4 tier classifications (economy / standard / frontier / economy)
2. The total `savings_pct` from the usage block
3. Any error messages

**Do NOT paste:**
- The API key
- The full response bodies (they may include unique IDs or other data)
- Any environment-variable values

## What to do if a test fails

| Failure | Diagnosis | Fix |
|---|---|---|
| `401 Unauthorized` | Key didn't propagate to the proxy | Verify `echo $ANTHROPIC_API_KEY` shows a non-empty length, then restart the script |
| `404 Not Found` | Anthropic adapter URL routing bug | Tell me; I'll debug |
| Tier mismatch (Test 4 routes to frontier) | Router false-positive regressed | Tell me; I'll fix the keyword list |
| Server didn't start | Port 8765 in use | `taskkill //F //PID $(netstat -ano | grep :8765 | awk '{print $5}' | head -1)` then retry |
| Cost > $0.10 | Something is wrong; investigate before running again | Stop, tell me |

## After the test

Verify the actual spend at https://console.anthropic.com/settings/billing — it should show $0.01–$0.05. If it shows much more, something looped; tell me immediately.

When done, you can kill the server (the script does this automatically on exit) and we move on.

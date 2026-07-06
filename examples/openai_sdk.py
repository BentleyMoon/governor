"""Use Governor with the OpenAI Python SDK.

Setup:
    pip install openai
    export GOVERNOR_OPENAI_KEY=sk-your-real-openai-key
    governor serve  # in another terminal

Then run this file:
    python examples/openai_sdk.py
"""

from openai import OpenAI

# Single line to switch from direct OpenAI to Governor:
#   client = OpenAI()                                       # before
client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-used")
# (api_key here is consumed by the SDK but Governor reads from GOVERNOR_*_KEY
#  on the server side, so any non-empty placeholder works.)


# Example 1: simple acknowledgment → routes to ECONOMY
r1 = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "thanks!"}],
)
print("Example 1 (ECONOMY):", r1.choices[0].message.content[:80])
# The proxy adds a `_governor` field to the response describing the tier,
# model, and routing reason. Inspect via the underlying response dict:
print("  routed via:", r1.model_dump().get("_governor"))


# Example 2: bounded coding → routes to STANDARD
r2 = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "fix the bug in main.py where the list reverses twice"}],
)
print("Example 2 (STANDARD):", r2.choices[0].message.content[:80])
print("  routed via:", r2.model_dump().get("_governor"))


# Example 3: architecture → routes to FRONTIER
r3 = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "redesign the auth system to support SSO across tenants"}],
)
print("Example 3 (FRONTIER):", r3.choices[0].message.content[:80])
print("  routed via:", r3.model_dump().get("_governor"))


# Example 4: streaming
print("\nExample 4 (streaming):")
stream = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "write a python function to reverse a list"}],
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta.content if chunk.choices else None
    if delta:
        print(delta, end="", flush=True)
print()


# Show the cumulative savings for this session
import httpx
usage = httpx.get("http://localhost:8000/v1/usage").json()
print(f"\nCumulative usage across {sum(b['request_count'] for b in usage['per_tier'])} requests:")
print(f"  Would have cost: ${usage['total_would_have_cost_usd']:.4f}")
print(f"  Did cost:        ${usage['total_did_cost_usd']:.4f}")
print(f"  Saved:           ${usage['total_savings_usd']:.4f}  ({usage['savings_pct']}%)")

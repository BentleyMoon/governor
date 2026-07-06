"""Start Governor with all 3 tiers pointed at Anthropic.

Run from C:/governor:
    python examples/anthropic_serve.py

Reads ANTHROPIC_API_KEY from the environment. Listens on 127.0.0.1:8765.
Press Ctrl+C to stop.
"""

from __future__ import annotations

import os
import sys

import uvicorn

from governor.proxy import create_app
from governor.router import ProxyConfig


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set in this process's environment.")
        print("Set it in your shell first, then re-run this script.")
        return 1

    config = ProxyConfig(
        economy_model="claude-haiku-4-5-20251001",
        economy_base_url="https://api.anthropic.com/v1",
        standard_model="claude-sonnet-4-6",
        standard_base_url="https://api.anthropic.com/v1",
        frontier_model="claude-opus-4-7",
        frontier_base_url="https://api.anthropic.com/v1",
    )
    app = create_app(config)

    port = int(os.environ.get("GOVERNOR_PORT", "8765"))
    print(f"Governor up on http://127.0.0.1:{port}")
    print(f"  ECONOMY  -> {config.economy_model}")
    print(f"  STANDARD -> {config.standard_model}")
    print(f"  FRONTIER -> {config.frontier_model}")
    print("Press Ctrl+C to stop.")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Command-line entry point: `governor serve`, `governor classify "..."`."""

from __future__ import annotations

import argparse
import json
import os
import sys

from governor.router import classify_turn


def main() -> int:
    parser = argparse.ArgumentParser(prog="governor")
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="Run the proxy server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))

    classify = sub.add_parser("classify", help="Classify a single request and print the decision")
    classify.add_argument("text", help="The request text to classify")

    args = parser.parse_args()

    if args.cmd == "serve":
        import uvicorn
        from governor.proxy import app
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    if args.cmd == "classify":
        decision = classify_turn(args.text)
        print(json.dumps({
            "tier": decision.model_tier.value,
            "objective": decision.objective,
            "turn_kind": decision.turn_kind,
            "workload_class": decision.workload_class,
            "reason": decision.reason,
        }, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())

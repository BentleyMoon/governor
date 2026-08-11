# Governor

**Cut your LLM bill ~49% on coding workloads with a 200-line keyword router.** Drop-in OpenAI-compatible proxy. MIT-licensed.

> **Evidence status, 2026-08-11.** The savings figures below come from 35 hand-rated turns against
> simulated pricing, and the turn-level data is not published. Governor is a working, tested reference
> implementation whose numbers are **indicative, not a validated benchmark**. The headline previously
> read "30-60%", a range that appears in no measurement in this repository; the measured mixed-coding
> figure is 49%.

This is the production code from §5 ("Governor Routing") of [a research synthesis on boundary mechanisms in AI systems](PAPER.md). It's open source, no strings attached. Use forever.

## How it works

```
ECONOMY    →  greetings, acks, simple lookups, follow-ups   → cheap fast model
STANDARD   →  bounded coding, implementation, reasoning      → capable model
FRONTIER   →  architecture, multi-file refactor, security    → strongest model
```

Classification is keyword-based (~200 lines of Python). The argument is a hypothesis from the parent research program, not a benchmark result: the decision-relevant signal for tier selection is observable in the prompt itself.

**No learned classifier was ever tested against it.** There is no head-to-head, so nothing here shows keywords beating a learned router. `MASTER_RESEARCH_PAPER.md` §7 records "N/A (no internal model tested)" for this domain. Earlier versions of this README claimed internal models "didn't improve routing accuracy in my testing"; that claim was not supported by any experiment and has been removed.

## Quickstart

```bash
pip install -e ".[dev]"

# Set keys for the backends you want to use:
export GOVERNOR_OPENAI_KEY=sk-...           # for OpenAI tiers
export GOVERNOR_ANTHROPIC_KEY=sk-ant-...    # for Anthropic tiers

# Start the proxy
governor serve  # or: python -m uvicorn governor.proxy:app --port 8000
```

Then in your client:

```python
from openai import OpenAI

# Single line to swap from OpenAI direct to Governor:
client = OpenAI(base_url="http://localhost:8000/v1", api_key="anything")
```

## Measured savings

| Workload | Flat, single model† | Routed | Savings | Quality |
|---|---:|---:|---:|---:|
| Mixed coding session | $0.194 | $0.100 | **49%** | 95% |
| Debugging session | $0.156 | $0.055 | **65%** | 96% |
| Research / Q&A | $0.052 | $0.004 | **92%*** | 100% |
| Customer support | $0.040 | $0.003 | **93%*** | 100% |

*Q&A and support savings depend on the routing fraction (most turns route to ECONOMY). Coding/debugging are the conservative numbers.

† The baseline is every turn, greetings included, routed to a single model, which is the most favourable
comparator available. Our own documents disagree on which tier it was: this repo's PAPER.md said
"frontier", the parent synthesis says "all capable model". Stated as unconfirmed until the data is out.

**Source and its limits.** §5 of [PAPER.md](PAPER.md), 35 measured turns across scripted and real
sessions, simulated cloud pricing. The turn-level data, the prompts and the rating protocol are **not
published**, in this repo or the parent paper, so these figures cannot currently be checked by anyone.
Quality is hand-rated by the author with no second rater.

## Backends

- **OpenAI-compatible** (default): any provider speaking OpenAI's chat-completion API
- **Anthropic**: detected by `anthropic.com` in base_url; auto-translates to Anthropic's Messages API; streaming downgrades to non-streaming with a marker

## Status

- ✅ Classifier (`governor/router.py`) — 50 unit + integration tests pass
- ✅ FastAPI proxy with OpenAI + Anthropic backends
- ✅ Per-tier usage tracking + savings math
- ✅ Streaming on OpenAI; non-streaming on Anthropic (translation pending)
- ✅ End-to-end validated on real Anthropic API (4-test smoke run)

## What this is not

- **Not a paid product.** Governor is open-source MIT, no commercial tier. The competitive landscape (CodeRouter, RouteLLM, Martian, OpenRouter) is mature; Governor is published as a clean, research-backed reference implementation, not a business.
- **Not a marketplace.** No model arbitrage, no price-based routing. Routing picks by *workload classification*, not provider availability.
- **Not a fine-tuned classifier.** The whole pitch is that you don't need one for this decision.

## What this is

- A clean, working, tested implementation of workload-classifying LLM routing
- The production code from a documented research finding (986+ trials of related work, this one ~35 turns)
- A teaching artifact for engineers thinking about boundary mechanisms vs. internal-model approaches

## If you want a hosted tool

For hosted LLM cost routing: [CodeRouter](https://www.coderouter.io/), [OpenRouter](https://openrouter.ai/), [Portkey](https://portkey.ai/), [Martian](https://withmartian.com/).

Related, same author: [lattice-commit](https://github.com/bentleymoon/lattice-commit) — open-source, git-native checkpointing for multi-file LLM code repair (`pip install lattice-commit`). Different problem: correctness rather than cost.

## Files

- [PAPER.md](PAPER.md) — public §5 extract
- [governor/](governor/) — package source
- [tests/](tests/) — 50 tests
- [examples/](examples/) — copy-paste integrations
- [site/](site/) — static project page

## License

MIT. Use it, fork it, don't ask permission.

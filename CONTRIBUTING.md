# Contributing to Governor

Thanks for considering a contribution. Honest expectations up front:

**This is a one-person project.** Bentley Moon reviews PRs personally. Response time is "within 1 week most weeks, occasionally longer."

## What's in scope

- **Keyword list extensions** — adding terms for non-English workloads, or for domain-specific patterns (medical, legal, finance, gaming, etc.). Tag the PR `keywords:<domain>`.
- **Backend integrations** — getting Governor working cleanly in front of new model providers (Cohere, Mistral, local Ollama, vLLM, etc.).
- **Better cost models** — input/output pricing changes, tier-specific surcharges, batch-mode pricing.
- **Streaming usage accounting** — the current code under-counts streamed-call costs because the upstream `usage` block isn't always emitted at end-of-stream. A robust fix here is welcome.
- **Examples** — IDE plugins, CLI agents, framework integrations.

## What's out of scope (for now)

- **Replacing the keyword classifier with a learned model.** The whole pitch of Governor rests on keyword sufficiency. PRs adding embeddings, fine-tuning, or active-learning on the routing decision will be closed unless they include statistical evidence (>30 turns, blind quality rating) showing meaningful improvement over keywords on the same workload.
- **Generic LLM features** that would make Governor a frontier proxy with everything (image generation, voice, vector stores, agentic loops). This stays a routing proxy. Other tools do those.
- **Frontend or hosted-dashboard work** until there are paying customers asking for it.

## Process

1. Open an issue describing the change before writing code, especially for anything beyond "add a keyword."
2. Fork, branch, push.
3. PR against `main` with a description that includes:
   - What changed
   - Why
   - How you tested it
   - Whether tests were added (they should be, except for trivial doc changes)
4. Run `pytest tests/ && ruff check governor/ tests/` locally.
5. Wait. CI runs on push. If CI is green and the PR is in scope, expect a review within ~1 week.

## Ground rules

- New keywords need at least one new test case (positive or negative).
- New endpoints need at least one mocked-httpx integration test in `tests/test_proxy.py`.
- Cost-model changes need at least one direct math test in the relevant test file.
- Don't add dependencies that aren't already in `pyproject.toml` without a clear case.

## License

By contributing, you agree your contribution is licensed under MIT (the repo license).

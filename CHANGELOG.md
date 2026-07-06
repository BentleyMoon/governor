# Changelog

All notable changes to Governor will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-04-30

Initial public release. Alpha — interfaces may change.

### Added
- Workload classifier (`governor.router.classify_turn`) implementing the 3-tier
  ECONOMY / STANDARD / FRONTIER routing described in §5 of the boundary-mechanisms
  research synthesis.
- OpenAI-compatible FastAPI proxy (`governor.proxy`) with non-streaming and
  streaming `/v1/chat/completions`, `/v1/usage`, and `/healthz` endpoints.
- Per-request cost estimation and per-tier usage accumulation
  (`governor.pricing`). Counterfactual cost defaults to `claude-sonnet-4-6`.
- CLI: `governor serve` and `governor classify "..."`.
- 25 tests covering router edge cases (false-positive regression for "production"
  in passing context, error/test-failure language, empty/whitespace input,
  session-aware corrections) and proxy dispatch (mocked-httpx integration tests
  validating tier→URL routing and usage accumulation).
- Examples for OpenAI Python SDK, raw curl, Cursor, and Aider.
- GitHub Actions CI matrix (Ubuntu/Windows/macOS × Python 3.10/3.11/3.12) plus
  a server-boot smoke job.

### Known limitations
- Streaming responses don't always include the upstream `usage` block, so
  per-tier cost on streamed calls may be undercounted.
- Keyword list is English-coding-centric. Non-English workloads will need
  keyword extension.
- Cost figures use published list prices; customers with negotiated rates will
  see different savings.
- Quality measurement (95–96% retention claim) is from 35 hand-rated turns.
  Re-validate per deployment.

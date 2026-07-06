"""Tests for cost estimation, including Anthropic-snapshot prefix matching."""

from governor.pricing import (
    DEFAULT_PRICES,
    TokenPrice,
    _resolve_price,
    estimate_cost,
    estimate_savings,
)


def test_exact_model_match():
    p = _resolve_price("claude-haiku-4-5", DEFAULT_PRICES)
    assert p is not None
    assert p.input_per_million == 1.00


def test_anthropic_snapshot_resolves_to_base_model():
    """Bug 3 (live): claude-haiku-4-5-20251001 returned 0.0 cost because
    the date suffix wasn't in the price table. Prefix-match fixes this."""
    p = _resolve_price("claude-haiku-4-5-20251001", DEFAULT_PRICES)
    assert p is not None
    assert p.input_per_million == 1.00
    assert p.output_per_million == 5.00


def test_unknown_model_returns_none():
    assert _resolve_price("nonexistent-model-x", DEFAULT_PRICES) is None


def test_estimate_cost_uses_prefix_match_for_snapshot():
    # 1000 input + 500 output on claude-haiku-4-5-20251001
    # Should resolve to claude-haiku-4-5 prices: $1.00/$5.00 per 1M
    cost = estimate_cost("claude-haiku-4-5-20251001", 1000, 500)
    expected = (1000 / 1e6) * 1.00 + (500 / 1e6) * 5.00  # $0.001 + $0.0025 = $0.0035
    assert abs(cost - expected) < 1e-9


def test_estimate_savings_with_explicit_counterfactual():
    """Counterfactual should be passable; default should be Opus (frontier-class)."""
    would, did, saved = estimate_savings(
        routed_model="claude-haiku-4-5",
        input_tokens=1000,
        output_tokens=500,
        counterfactual_model="claude-opus-4-7",
    )
    # Haiku: 1000*1.00/1M + 500*5.00/1M = 0.001 + 0.0025 = 0.0035
    # Opus:  1000*15/1M  + 500*75/1M  = 0.015 + 0.0375 = 0.0525
    assert abs(did - 0.0035) < 1e-9
    assert abs(would - 0.0525) < 1e-9
    assert abs(saved - (would - did)) < 1e-9
    assert saved > 0


def test_estimate_savings_negative_when_routed_more_expensive_than_counterfactual():
    """If a request routes to FRONTIER and counterfactual is STANDARD, saved is negative."""
    would, did, saved = estimate_savings(
        routed_model="claude-opus-4-7",
        input_tokens=100,
        output_tokens=100,
        counterfactual_model="claude-sonnet-4-6",
    )
    assert did > would
    assert saved < 0


def test_estimate_savings_default_counterfactual_is_opus():
    """If counterfactual not specified, default is opus (the most expensive
    realistic frontier model the customer would otherwise be paying for)."""
    would_default, _, _ = estimate_savings("claude-haiku-4-5", 1000, 500)
    would_explicit, _, _ = estimate_savings(
        "claude-haiku-4-5", 1000, 500, counterfactual_model="claude-opus-4-7",
    )
    assert would_default == would_explicit

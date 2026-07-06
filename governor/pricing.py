"""Per-request cost estimation.

Used by the proxy to compute "would-have-cost" (flat counterfactual) vs
"did-cost" (routed). The difference is the customer's measured savings — the
basis for percent-of-savings billing.

Prices are USD per 1M tokens, as of 2026-04. Override per deployment.

Model-name resolution: Anthropic snapshots include date suffixes like
`claude-haiku-4-5-20251001`. We resolve those by prefix-match against the
pricing table — `claude-haiku-4-5-20251001` resolves to the `claude-haiku-4-5`
price entry.
"""

from __future__ import annotations

from dataclasses import dataclass

from governor.router import ModelTier


@dataclass(frozen=True)
class TokenPrice:
    input_per_million: float
    output_per_million: float


# Approximate published list prices, USD per 1M tokens. Intentionally
# conservative — actual contracts vary.
DEFAULT_PRICES: dict[str, TokenPrice] = {
    "gpt-4o-mini":       TokenPrice(0.15, 0.60),
    "gpt-4o":            TokenPrice(2.50, 10.00),
    "claude-haiku-4-5":  TokenPrice(1.00, 5.00),
    "claude-sonnet-4-6": TokenPrice(3.00, 15.00),
    "claude-opus-4-7":   TokenPrice(15.00, 75.00),
}

# Tier defaults — what each tier costs if no model-specific price is set.
TIER_DEFAULTS: dict[ModelTier, TokenPrice] = {
    ModelTier.ECONOMY:  TokenPrice(1.00, 5.00),
    ModelTier.STANDARD: TokenPrice(3.00, 15.00),
    ModelTier.FRONTIER: TokenPrice(15.00, 75.00),
}


def _resolve_price(model: str, prices: dict[str, TokenPrice]) -> TokenPrice | None:
    """Resolve a model name to a price entry, with prefix-match for snapshots.

    `claude-haiku-4-5-20251001` matches `claude-haiku-4-5`.
    Order: exact match first, then longest matching prefix.
    """
    if model in prices:
        return prices[model]
    candidates = sorted(
        (k for k in prices if model.startswith(k)),
        key=len,
        reverse=True,
    )
    if candidates:
        return prices[candidates[0]]
    return None


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    prices: dict[str, TokenPrice] | None = None,
) -> float:
    """Estimate cost in USD for one completion."""
    table = prices if prices is not None else DEFAULT_PRICES
    price = _resolve_price(model, table)
    if price is None:
        return 0.0
    return (
        (input_tokens / 1_000_000) * price.input_per_million
        + (output_tokens / 1_000_000) * price.output_per_million
    )


def estimate_savings(
    routed_model: str,
    input_tokens: int,
    output_tokens: int,
    counterfactual_model: str = "claude-opus-4-7",
    prices: dict[str, TokenPrice] | None = None,
) -> tuple[float, float, float]:
    """
    Return (would_have_cost, did_cost, savings) in USD.

    `would_have_cost` is what the customer would pay with no routing — the
    counterfactual model (typically the FRONTIER tier model in your config).
    `did_cost` is what they paid after Governor's routing. `savings` is the
    difference.

    Note: savings can be NEGATIVE if a request was routed to a tier *more*
    expensive than the counterfactual. This is the correct accounting and
    you should investigate any negative savings (typically means a request
    was over-tiered to FRONTIER when it didn't need to be).
    """
    did = estimate_cost(routed_model, input_tokens, output_tokens, prices)
    would = estimate_cost(counterfactual_model, input_tokens, output_tokens, prices)
    return would, did, would - did

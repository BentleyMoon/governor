"""Workload classification and tier routing.

Standalone version of the classifier described in MASTER_RESEARCH_PAPER.md §5.
Three tiers: ECONOMY (chat/acks), STANDARD (bounded coding), FRONTIER
(architecture/multi-file/security). Classification uses keyword detection at
the request boundary — no learned classifier, no embeddings.

Measured savings (35 turns, simulated cloud pricing):
  - Coding session:    49% savings, 95% quality retention
  - Debugging session: 65% savings, 96% quality retention
  - Q&A / lookups:     92-93% savings, 100% quality retention
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


def _has_word(text: str, terms) -> bool:
    """Word-boundary substring match — avoids 'now' matching inside 'know'."""
    for term in terms:
        # If the term itself contains spaces, treat it as a phrase (substring OK).
        # If it's a single word, require word boundaries.
        if " " in term:
            if term in text:
                return True
        else:
            if re.search(rf"\b{re.escape(term)}\b", text):
                return True
    return False


class ModelTier(str, Enum):
    ECONOMY = "economy"
    STANDARD = "standard"
    FRONTIER = "frontier"


@dataclass
class ProxyConfig:
    """Maps tiers to backend models. Override per deployment."""
    economy_model: str = "gpt-4o-mini"
    standard_model: str = "gpt-4o"
    frontier_model: str = "claude-sonnet-4-6"
    economy_base_url: str = "https://api.openai.com/v1"
    standard_base_url: str = "https://api.openai.com/v1"
    frontier_base_url: str = "https://api.anthropic.com/v1"


@dataclass
class SessionState:
    """Minimal session memory for follow-up classification."""
    turn_history: list[str] = field(default_factory=list)


@dataclass
class GovernorDecision:
    objective: str
    model_tier: ModelTier
    turn_kind: str
    workload_class: str
    reason: str


SIMPLE_TERMS = frozenset({
    "thanks", "thank you", "ok", "okay", "got it",
    "sounds good", "yes", "no", "sure", "great",
    "hello", "hi", "hey", "bye", "goodbye", "cheers",
})

CODING_TERMS = (
    "fix the bug", "fix bug", "fix this", "write code", "add function",
    "add method", "update function", "update method", "write a function",
    "write a test", "add feature", "create file", "edit file",
    "refactor", "debug", "patch", "lint error", "compile error", "build error",
    "implement", "add endpoint", "add api", "database migration",
    "write a class", "deploy", "commit", "pull request", "git push",
    "git merge", "branch ", "module", "the code", "my code", "this code",
    "the function", "the method", "the class", "the file", "source code",
    "codebase", "repository", "repo", "main.py", ".py", ".js", ".ts",
    # Failure / error language — common in coding sessions
    "test fail", "tests fail", "tests are failing", "test is failing",
    "stack trace", "stacktrace", "traceback", "throws", "raises",
    "throwing an error", "getting an error", "an exception",
    "type error", "syntax error", "import error", "null pointer",
    "segfault", "infinite loop", "memory leak",
    # General "write code" phrasings
    "one-liner", "one liner", "snippet", "code snippet",
    "list comprehension", "regex", "regular expression",
    "function to ", "method to ", "script to ", "program to ",
    " python ", "in python", "javascript ", "typescript ",
    "shell script", "bash script", "powershell ",
    "loop through", "iterate over", "parse json", "parse the",
    "return value", "function that ", "algorithm",
)

FRONTIER_TERMS = (
    "architect this", "redesign", "design the", "design a system",
    "refactor entire", "refactor the entire", "multi-file",
    "rewrite the", "overhaul", "restructure the", "migrate the",
    "security audit", "scalab", "system design",
    "entire codebase", "from scratch", "ground up",
    # Note: "production" and "infrastructure" removed from this list because
    # they're frequently used in passing ("in production we use X") and produced
    # false positives. If you need them, add them back per-deployment.
)

CLARIFICATION_TERMS = (
    "i mean", "more specifically", "specifically",
    "focus on", "only", "narrow it",
)

CORRECTION_TERMS = (
    "actually", "instead", "correction", "turn that",
    "change that", "not a", "rather than",
)

FRESHNESS_TERMS = (
    "today", "latest", "current", "now", "this week",
    "this month", "recent", "refresh", "updated",
)


def _has_code_signals(text: str) -> bool:
    return any(term in text for term in CODING_TERMS)


def _has_frontier_signals(text: str) -> bool:
    return any(term in text for term in FRONTIER_TERMS)


def classify_turn(
    request_text: str,
    session: SessionState | None = None,
    config: ProxyConfig | None = None,
) -> GovernorDecision:
    """Classify a turn into ECONOMY / STANDARD / FRONTIER."""
    session = session or SessionState()
    config = config or ProxyConfig()

    text_lower = request_text.lower().strip()
    word_count = len(text_lower.split())
    clean_words = set(re.sub(r"[^\w\s]", "", text_lower).split())

    if word_count <= 10 and any(term in clean_words for term in SIMPLE_TERMS):
        return GovernorDecision(
            objective="ECONOMY",
            model_tier=ModelTier.ECONOMY,
            turn_kind="simple",
            workload_class="CHAT_SIMPLE",
            reason="Simple greeting or acknowledgment",
        )

    if _has_frontier_signals(text_lower):
        return GovernorDecision(
            objective="FRONTIER",
            model_tier=ModelTier.FRONTIER,
            turn_kind="frontier",
            workload_class="CODE_ARCH",
            reason="Architecture, redesign, or multi-file signals detected",
        )

    if word_count > 200 and _has_code_signals(text_lower):
        return GovernorDecision(
            objective="FRONTIER",
            model_tier=ModelTier.FRONTIER,
            turn_kind="frontier",
            workload_class="CODE_ARCH",
            reason=f"Long complex coding request ({word_count} words)",
        )

    if _has_code_signals(text_lower):
        return GovernorDecision(
            objective="STANDARD",
            model_tier=ModelTier.STANDARD,
            turn_kind="coding",
            workload_class="CODE_PATCH",
            reason="Bounded coding task detected",
        )

    # Word-boundary match — prevents "now" matching inside "know", etc.
    has_correction = _has_word(text_lower, CORRECTION_TERMS)
    has_freshness = _has_word(text_lower, FRESHNESS_TERMS)
    session_has_code = any(
        kind in ("coding", "frontier") for kind in session.turn_history
    )

    if (has_correction or has_freshness) and session_has_code:
        return GovernorDecision(
            objective="STANDARD",
            model_tier=ModelTier.STANDARD,
            turn_kind="correction" if has_correction else "freshness",
            workload_class="CODE_FOLLOWUP",
            reason="Correction or freshness follow-up inside a coding session",
        )

    if has_correction or has_freshness:
        return GovernorDecision(
            objective="ECONOMY",
            model_tier=ModelTier.ECONOMY,
            turn_kind="correction" if has_correction else "freshness",
            workload_class="CHAT_FOLLOWUP",
            reason="Non-coding correction or freshness follow-up",
        )

    if _has_word(text_lower, CLARIFICATION_TERMS):
        return GovernorDecision(
            objective="ECONOMY",
            model_tier=ModelTier.ECONOMY,
            turn_kind="clarification",
            workload_class="CHAT_FOLLOWUP",
            reason="Clarification follow-up",
        )

    return GovernorDecision(
        objective="ECONOMY",
        model_tier=ModelTier.ECONOMY,
        turn_kind="default",
        workload_class="CHAT_SIMPLE",
        reason="No coding signals; handled by economy path",
    )

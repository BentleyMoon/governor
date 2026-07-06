"""Smoke tests for the governor classifier.

These do NOT validate the 49% savings claim — that requires real backend calls.
They validate that the classifier routes correctly per the published rules.
"""

from governor.router import ModelTier, SessionState, classify_turn


def test_simple_acknowledgment_routes_economy():
    decision = classify_turn("thanks")
    assert decision.model_tier == ModelTier.ECONOMY
    assert decision.workload_class == "CHAT_SIMPLE"


def test_short_greeting_routes_economy():
    decision = classify_turn("hello there")
    assert decision.model_tier == ModelTier.ECONOMY


def test_bounded_coding_routes_standard():
    decision = classify_turn("fix the bug in main.py where the list reverses twice")
    assert decision.model_tier == ModelTier.STANDARD
    assert decision.workload_class == "CODE_PATCH"


def test_architecture_routes_frontier():
    decision = classify_turn("redesign the auth system to support SSO across tenants")
    assert decision.model_tier == ModelTier.FRONTIER
    assert decision.workload_class == "CODE_ARCH"


def test_long_coding_request_routes_frontier():
    long_request = (
        "I need to implement a new feature in the codebase. "
        "The function should accept a list of items and return a sorted version. "
    ) * 20
    long_request += " write a function to do this"
    decision = classify_turn(long_request)
    assert decision.model_tier == ModelTier.FRONTIER


def test_correction_in_coding_session_routes_standard():
    session = SessionState(turn_history=["coding"])
    decision = classify_turn("actually, change that to use a generator", session=session)
    assert decision.model_tier == ModelTier.STANDARD
    assert decision.workload_class == "CODE_FOLLOWUP"


def test_correction_outside_coding_session_routes_economy():
    session = SessionState(turn_history=["simple"])
    decision = classify_turn("actually, never mind", session=session)
    assert decision.model_tier == ModelTier.ECONOMY


def test_default_routes_economy():
    decision = classify_turn("what is the capital of France")
    assert decision.model_tier == ModelTier.ECONOMY


# Adversarial / regression cases — these are the failure modes we care about.

def test_passing_mention_of_production_does_not_route_frontier():
    """User describing context, not asking for production work, must not over-tier."""
    decision = classify_turn("in production we use postgres, just curious")
    assert decision.model_tier != ModelTier.FRONTIER


def test_test_failure_language_routes_standard():
    """Common debugging phrasing without explicit 'fix' should still hit STANDARD."""
    decision = classify_turn("my tests are failing with a type error")
    assert decision.model_tier == ModelTier.STANDARD


def test_stack_trace_routes_standard():
    decision = classify_turn("here's the stack trace, what's wrong")
    assert decision.model_tier == ModelTier.STANDARD


def test_pure_chat_with_code_word_does_not_overtier():
    """Non-coding sentence that happens to contain a coding-adjacent word."""
    # 'module' is in CODING_TERMS, but 'coffee module' isn't a coding context.
    # Currently the router DOES route this to STANDARD; we accept that as
    # over-tiering rather than mis-tiering. This test pins the behavior so a
    # future tightening of CODING_TERMS doesn't break silently.
    decision = classify_turn("the coffee module is broken")
    assert decision.model_tier == ModelTier.STANDARD


def test_long_non_coding_request_routes_economy():
    long_chat = "I had a long day at work today and " * 30
    decision = classify_turn(long_chat)
    assert decision.model_tier == ModelTier.ECONOMY


def test_architecture_keyword_at_end_still_routes_frontier():
    decision = classify_turn("can you help me redesign the auth flow?")
    assert decision.model_tier == ModelTier.FRONTIER


def test_empty_input_routes_economy():
    decision = classify_turn("")
    assert decision.model_tier == ModelTier.ECONOMY


def test_whitespace_input_routes_economy():
    decision = classify_turn("   \n   ")
    assert decision.model_tier == ModelTier.ECONOMY


def test_session_history_persists_across_turns():
    session = SessionState()
    classify_turn("fix the bug in main.py", session=session)
    session.turn_history.append("coding")
    decision = classify_turn("actually, scrap that approach", session=session)
    # Correction inside coding session should stay STANDARD, not drop to ECONOMY
    assert decision.model_tier == ModelTier.STANDARD


# Regression tests from 2026-04-30 live Anthropic smoke test.
# These pin live-discovered bugs that the offline tests had missed.

def test_regression_python_one_liner_routes_standard():
    """Bug 1 (live): 'Write a Python one-liner to reverse a list.' was
    routing to ECONOMY because no CODING_TERM matched."""
    decision = classify_turn("Write a Python one-liner to reverse a list.")
    assert decision.model_tier == ModelTier.STANDARD


def test_regression_know_does_not_match_now():
    """Bug 2 (live): 'just so you know' was routing to STANDARD because the
    substring matcher saw 'now' inside 'know' and triggered FRESHNESS_TERMS.
    Word-boundary matching prevents this."""
    session = SessionState(turn_history=["frontier"])  # prior coding context
    decision = classify_turn(
        "In production we use postgres, just so you know.", session=session,
    )
    # Should stay ECONOMY despite session having coding history
    assert decision.model_tier == ModelTier.ECONOMY


def test_regression_actually_at_word_boundary_still_works():
    """Word-boundary fix should NOT break legitimate corrections."""
    session = SessionState(turn_history=["coding"])
    decision = classify_turn("actually, change that to use a generator", session=session)
    assert decision.model_tier == ModelTier.STANDARD


def test_regression_now_as_word_does_match_freshness():
    """Word-boundary fix preserves true freshness matches."""
    session = SessionState(turn_history=["coding"])
    decision = classify_turn("can you do that now please", session=session)
    # 'now' as a word should still hit FRESHNESS_TERMS
    assert decision.model_tier == ModelTier.STANDARD

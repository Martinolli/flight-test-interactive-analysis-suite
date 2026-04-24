"""Tests for P3.1 prompt-to-mode routing quality guard heuristics."""

from app.prompt_mode_guard import (
    MismatchSeverity,
    PromptIntent,
    evaluate_prompt_mode_guard,
    infer_prompt_intent,
)


def test_infer_prompt_intent_detects_handling_qualities_keywords():
    intent, matched = infer_prompt_intent(
        "Assess aileron deflection, stick position, and roll response quality."
    )
    assert intent == PromptIntent.HANDLING_QUALITIES
    assert "aileron" in matched
    assert "stick" in matched
    assert "roll response" in matched


def test_evaluate_prompt_mode_guard_marks_strong_mismatch_for_takeoff_vs_handling():
    guard = evaluate_prompt_mode_guard(
        selected_mode_key="takeoff",
        user_prompt="Analyze stick input and aileron control response during roll capture.",
    )
    assert guard.inferred_intent == PromptIntent.HANDLING_QUALITIES.value
    assert guard.mismatch_severity == MismatchSeverity.STRONG
    assert guard.guarded_execution is True
    suggested_keys = [item.key for item in guard.suggested_modes]
    assert "handling_qualities" in suggested_keys
    assert "general" in suggested_keys


def test_evaluate_prompt_mode_guard_marks_soft_mismatch_for_general_with_takeoff_prompt():
    guard = evaluate_prompt_mode_guard(
        selected_mode_key="general",
        user_prompt="Estimate takeoff ground roll and liftoff speed.",
    )
    assert guard.inferred_intent == PromptIntent.TAKEOFF.value
    assert guard.mismatch_severity == MismatchSeverity.SOFT
    assert guard.guarded_execution is False
    assert any(item.key == "takeoff" for item in guard.suggested_modes)


def test_evaluate_prompt_mode_guard_returns_none_for_empty_prompt():
    guard = evaluate_prompt_mode_guard(selected_mode_key="takeoff", user_prompt="")
    assert guard.inferred_intent == PromptIntent.UNKNOWN.value
    assert guard.mismatch_severity == MismatchSeverity.NONE
    assert guard.guarded_execution is False


def test_infer_prompt_intent_detects_air_data_performance_keywords():
    intent, matched = infer_prompt_intent(
        "Cross-check Mach, CAS, TAS and density altitude consistency for this segment."
    )
    assert intent == PromptIntent.PERFORMANCE
    assert "mach" in matched
    assert "cas" in matched
    assert "tas" in matched

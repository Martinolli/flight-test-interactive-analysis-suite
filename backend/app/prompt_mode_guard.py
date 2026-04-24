"""
Prompt-to-mode routing quality guard.

P3.1 goal:
- detect obvious prompt intent vs selected mode mismatch
- provide explicit mismatch severity and suggested modes
- support guarded execution behavior for strong mismatches
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.analysis_modes import (
    analysis_mode_status,
    get_analysis_mode_definition,
    resolve_analysis_mode,
)
from app.capabilities import CapabilityImplementationStatus


class PromptIntent(str, Enum):
    TAKEOFF = "takeoff"
    LANDING = "landing"
    PERFORMANCE = "performance"
    BUFFET_VIBRATION = "buffet_vibration"
    HANDLING_QUALITIES = "handling_qualities"
    GENERAL = "general"
    UNKNOWN = "unknown"


class MismatchSeverity(str, Enum):
    NONE = "none"
    SOFT = "soft"
    STRONG = "strong"


class PromptModeSuggestion(BaseModel):
    key: str
    label: str
    capability_status: str
    available_now: bool
    reason: str


class PromptModeGuardSnapshot(BaseModel):
    selected_mode: str
    inferred_intent: str
    matched_keywords: List[str] = Field(default_factory=list)
    mismatch_severity: MismatchSeverity = MismatchSeverity.NONE
    reason_key: Optional[str] = None
    message: str = "Prompt/mode alignment looks acceptable."
    suggested_modes: List[PromptModeSuggestion] = Field(default_factory=list)
    proceeded_with_selected_mode: bool = True
    execution_mode: str
    guarded_execution: bool = False
    auto_downgraded: bool = False


_INTENT_KEYWORDS: Dict[PromptIntent, List[str]] = {
    PromptIntent.TAKEOFF: [
        "takeoff",
        "rotation",
        "ground roll",
        "liftoff",
        "vr",
    ],
    PromptIntent.LANDING: [
        "landing",
        "touchdown",
        "rollout",
        "deceleration",
        "approach speed",
    ],
    PromptIntent.PERFORMANCE: [
        "climb",
        "rate of climb",
        "climb gradient",
        "performance",
        "altitude gain",
        "acceleration trend",
        "mach",
        "cas",
        "tas",
        "air data",
        "air-data",
        "density altitude",
        "pressure altitude",
        "isa",
    ],
    PromptIntent.BUFFET_VIBRATION: [
        "vibration",
        "buffet",
        "load",
        "loads",
        "frequency",
        "flutter",
        "rms",
    ],
    PromptIntent.HANDLING_QUALITIES: [
        "aileron",
        "stick",
        "rudder",
        "elevator",
        "handling",
        "control input",
        "control response",
        "roll response",
        "pitch response",
        "yaw response",
    ],
    PromptIntent.GENERAL: [
        "summary",
        "overview",
        "general",
        "recommendations",
        "cross-check",
    ],
}


_INTENT_TO_MODE: Dict[PromptIntent, str] = {
    PromptIntent.TAKEOFF: "takeoff",
    PromptIntent.LANDING: "landing",
    PromptIntent.PERFORMANCE: "performance",
    PromptIntent.BUFFET_VIBRATION: "buffet_vibration",
    PromptIntent.HANDLING_QUALITIES: "handling_qualities",
    PromptIntent.GENERAL: "general",
    PromptIntent.UNKNOWN: "general",
}

_STRICT_DETERMINISTIC_MODES = {
    "takeoff",
    "landing",
    "performance",
    "buffet_vibration",
    "handling_qualities",
}

_INTENT_PRIORITY: List[PromptIntent] = [
    PromptIntent.HANDLING_QUALITIES,
    PromptIntent.BUFFET_VIBRATION,
    PromptIntent.LANDING,
    PromptIntent.TAKEOFF,
    PromptIntent.PERFORMANCE,
    PromptIntent.GENERAL,
]


def infer_prompt_intent(user_prompt: Optional[str]) -> Tuple[PromptIntent, List[str]]:
    text = (user_prompt or "").strip().lower()
    if not text:
        return PromptIntent.UNKNOWN, []

    matches_by_intent: Dict[PromptIntent, List[str]] = {
        intent: [] for intent in _INTENT_KEYWORDS.keys()
    }
    for intent, keywords in _INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                matches_by_intent[intent].append(keyword)

    best_intent = PromptIntent.UNKNOWN
    best_count = 0
    for intent in _INTENT_PRIORITY:
        count = len(matches_by_intent.get(intent, []))
        if count > best_count:
            best_count = count
            best_intent = intent

    if best_count == 0:
        return PromptIntent.UNKNOWN, []

    matched_keywords = sorted(set(matches_by_intent[best_intent]))
    return best_intent, matched_keywords


def _mode_status_payload(mode_key: str) -> Tuple[str, str, bool]:
    mode = get_analysis_mode_definition(mode_key)
    if mode is None:
        return mode_key, "unknown", False
    status = analysis_mode_status(mode)
    available_now = status == CapabilityImplementationStatus.IMPLEMENTED
    return mode.label, status.value, available_now


def _build_suggestions(
    *,
    selected_mode_key: str,
    inferred_intent: PromptIntent,
) -> List[PromptModeSuggestion]:
    suggestions: List[PromptModeSuggestion] = []
    primary_mode_key = _INTENT_TO_MODE.get(inferred_intent, "general")
    label, status, available_now = _mode_status_payload(primary_mode_key)

    if inferred_intent != PromptIntent.UNKNOWN:
        reason = (
            "Best mode fit for detected prompt intent."
            if available_now
            else "Detected intent points here, but this capability is not fully implemented yet."
        )
        suggestions.append(
            PromptModeSuggestion(
                key=primary_mode_key,
                label=label,
                capability_status=status,
                available_now=available_now,
                reason=reason,
            )
        )

    if primary_mode_key != "general":
        general_label, general_status, general_available = _mode_status_payload("general")
        suggestions.append(
            PromptModeSuggestion(
                key="general",
                label=general_label,
                capability_status=general_status,
                available_now=general_available,
                reason=(
                    "Safer fallback when selected deterministic mode is mismatched or target capability is limited."
                ),
            )
        )

    # Deduplicate while preserving order.
    dedup: Dict[str, PromptModeSuggestion] = {}
    for item in suggestions:
        if item.key not in dedup:
            dedup[item.key] = item
    return list(dedup.values())


def evaluate_prompt_mode_guard(
    *,
    selected_mode_key: str,
    user_prompt: Optional[str],
) -> PromptModeGuardSnapshot:
    normalized_selected_mode = resolve_analysis_mode(selected_mode_key).key
    inferred_intent, matched_keywords = infer_prompt_intent(user_prompt)
    inferred_mode_key = _INTENT_TO_MODE.get(inferred_intent, "general")

    if inferred_intent in {PromptIntent.UNKNOWN}:
        return PromptModeGuardSnapshot(
            selected_mode=normalized_selected_mode,
            inferred_intent=inferred_intent.value,
            matched_keywords=[],
            mismatch_severity=MismatchSeverity.NONE,
            reason_key=None,
            message="No strong prompt intent cues detected; using selected mode.",
            suggested_modes=[],
            proceeded_with_selected_mode=True,
            execution_mode=normalized_selected_mode,
            guarded_execution=False,
            auto_downgraded=False,
        )

    severity = MismatchSeverity.NONE
    reason_key = None
    message = "Prompt intent aligns with selected mode."

    if inferred_mode_key == normalized_selected_mode:
        severity = MismatchSeverity.NONE
    elif normalized_selected_mode == "general":
        severity = MismatchSeverity.SOFT
        reason_key = "general_selected_with_specific_prompt_intent"
        message = (
            "Prompt appears to target a specific analysis mode; selected mode is general guidance."
        )
    elif inferred_mode_key == "general":
        severity = MismatchSeverity.SOFT
        reason_key = "specific_mode_selected_with_general_prompt_intent"
        message = (
            "Prompt appears broad/general while selected mode is specific."
        )
    elif normalized_selected_mode in _STRICT_DETERMINISTIC_MODES:
        severity = MismatchSeverity.STRONG
        reason_key = "strong_prompt_mode_mismatch"
        message = (
            "Prompt intent strongly differs from selected deterministic mode. "
            "Deterministic execution is guarded to avoid misleading mode fit."
        )
    else:
        severity = MismatchSeverity.SOFT
        reason_key = "soft_prompt_mode_mismatch"
        message = "Prompt intent differs from selected mode; review suggested modes."

    suggestions = _build_suggestions(
        selected_mode_key=normalized_selected_mode,
        inferred_intent=inferred_intent,
    )
    guarded_execution = (
        severity == MismatchSeverity.STRONG
        and normalized_selected_mode in _STRICT_DETERMINISTIC_MODES
    )

    return PromptModeGuardSnapshot(
        selected_mode=normalized_selected_mode,
        inferred_intent=inferred_intent.value,
        matched_keywords=matched_keywords,
        mismatch_severity=severity,
        reason_key=reason_key,
        message=message,
        suggested_modes=suggestions,
        proceeded_with_selected_mode=True,
        execution_mode=normalized_selected_mode,
        guarded_execution=guarded_execution,
        auto_downgraded=False,
    )


def parse_prompt_mode_guard(
    raw: Any,
    *,
    selected_mode_key: str = "takeoff",
) -> PromptModeGuardSnapshot:
    if isinstance(raw, PromptModeGuardSnapshot):
        return raw
    payload: Dict[str, Any] = raw if isinstance(raw, dict) else {}
    if not payload:
        return PromptModeGuardSnapshot(
            selected_mode=selected_mode_key,
            inferred_intent=PromptIntent.UNKNOWN.value,
            matched_keywords=[],
            mismatch_severity=MismatchSeverity.NONE,
            reason_key=None,
            message="Prompt/mode guard snapshot unavailable for this artifact.",
            suggested_modes=[],
            proceeded_with_selected_mode=True,
            execution_mode=selected_mode_key,
            guarded_execution=False,
            auto_downgraded=False,
        )
    try:
        parsed = PromptModeGuardSnapshot.model_validate(payload)
        if not parsed.selected_mode:
            parsed.selected_mode = selected_mode_key
        if not parsed.execution_mode:
            parsed.execution_mode = parsed.selected_mode or selected_mode_key
        return parsed
    except Exception:
        return PromptModeGuardSnapshot(
            selected_mode=selected_mode_key,
            inferred_intent=PromptIntent.UNKNOWN.value,
            matched_keywords=[],
            mismatch_severity=MismatchSeverity.NONE,
            reason_key="prompt_mode_guard_parse_failed",
            message="Prompt/mode guard snapshot could not be parsed.",
            suggested_modes=[],
            proceeded_with_selected_mode=True,
            execution_mode=selected_mode_key,
            guarded_execution=False,
            auto_downgraded=False,
        )

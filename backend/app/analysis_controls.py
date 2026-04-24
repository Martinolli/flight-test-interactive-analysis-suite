"""
Structured confidence / coverage / applicability controls for AI analysis outputs.

P2.4 goal:
- provide a bounded, explainable control layer for deterministic + RAG analysis
- persist control snapshot in analysis jobs for immutable reopen/report flows
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, Field

from app.capabilities import (
    CapabilityAuthority,
    CapabilityEvaluation,
    CapabilityOutcome,
)


class DeterministicConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNAVAILABLE = "unavailable"


class RetrievalCoverage(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


class ApplicabilityStatus(str, Enum):
    FULLY_APPLICABLE = "fully_applicable"
    PARTIALLY_APPLICABLE = "partially_applicable"
    ADVISORY_ONLY = "advisory_only"
    NOT_APPLICABLE = "not_applicable"


class WarningLevel(str, Enum):
    NONE = "none"
    INFO = "info"
    CAUTION = "caution"
    HIGH = "high"


class ResultStrength(str, Enum):
    AUTHORITATIVE = "authoritative"
    BOUNDED = "bounded"
    ADVISORY = "advisory"
    BLOCKED = "blocked"


class AnalysisControlSnapshot(BaseModel):
    deterministic_confidence: DeterministicConfidence
    retrieval_coverage: RetrievalCoverage
    applicability_status: ApplicabilityStatus
    warning_level: WarningLevel
    result_strength: ResultStrength
    blocking_or_downgrade_reason: Optional[str] = None
    warning_messages: List[str] = Field(default_factory=list)
    deterministic_available: bool = False
    retrieved_sources_count: int = 0
    cited_sources_count: int = 0
    mode_filter_fallback_used: bool = False
    metadata_coverage_ratio: float = 0.0


def _is_deterministic_authority(authority: CapabilityAuthority) -> bool:
    return authority in {
        CapabilityAuthority.DETERMINISTIC_PRIMARY,
        CapabilityAuthority.DETERMINISTIC_WITH_RAG_CROSSCHECK,
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _evaluate_deterministic_confidence(
    *,
    mode_key: str,
    capability_eval: CapabilityEvaluation,
    deterministic_metrics: Optional[dict],
) -> DeterministicConfidence:
    if not deterministic_metrics:
        return DeterministicConfidence.UNAVAILABLE
    if not bool(deterministic_metrics.get("available")):
        return DeterministicConfidence.UNAVAILABLE
    if capability_eval.outcome == CapabilityOutcome.PARTIAL_ESTIMATE:
        return DeterministicConfidence.MEDIUM

    sample_intervals = _safe_int(deterministic_metrics.get("sample_intervals_used"), -1)
    samples_used = _safe_int(deterministic_metrics.get("samples_used"), -1)
    handling_pairings = _safe_int(deterministic_metrics.get("pairings_analyzed"), -1)
    handling_samples = _safe_int(deterministic_metrics.get("total_pairing_samples"), -1)
    buffet_channels = _safe_int(deterministic_metrics.get("channels_screened"), -1)
    buffet_events = len(deterministic_metrics.get("anomaly_windows") or [])
    buffet_samples = _safe_int(deterministic_metrics.get("samples_used"), -1)
    run_time_s = _safe_float(
        deterministic_metrics.get("run_time_s", deterministic_metrics.get("rollout_time_s")),
        -1.0,
    )

    if mode_key == "handling_qualities":
        if handling_pairings >= 3 and handling_samples >= 120:
            return DeterministicConfidence.HIGH
        if handling_pairings >= 1 and handling_samples >= 40:
            return DeterministicConfidence.MEDIUM
        if handling_pairings >= 1:
            return DeterministicConfidence.LOW
        return DeterministicConfidence.UNAVAILABLE

    if mode_key == "buffet_vibration":
        if buffet_channels < 0 and buffet_samples >= 120:
            return DeterministicConfidence.HIGH
        if buffet_channels < 0 and buffet_samples >= 40:
            return DeterministicConfidence.MEDIUM
        if buffet_channels >= 4 and buffet_samples >= 120:
            return DeterministicConfidence.HIGH
        if buffet_channels >= 2 and buffet_samples >= 60:
            return DeterministicConfidence.MEDIUM
        if buffet_channels >= 1 and (buffet_events > 0 or buffet_samples >= 20):
            return DeterministicConfidence.LOW
        return DeterministicConfidence.UNAVAILABLE

    if sample_intervals >= 25 or samples_used >= 120:
        return DeterministicConfidence.HIGH
    if sample_intervals >= 8 or samples_used >= 40:
        return DeterministicConfidence.MEDIUM
    if run_time_s > 0 and run_time_s < 2.0 and mode_key in {"takeoff", "landing"}:
        return DeterministicConfidence.LOW
    if sample_intervals >= 0 or samples_used >= 0:
        return DeterministicConfidence.LOW
    if mode_key in {"buffet_vibration", "performance"}:
        return DeterministicConfidence.MEDIUM
    return DeterministicConfidence.LOW


def _evaluate_retrieval_coverage(
    *,
    retrieved_sources_count: int,
    cited_sources_count: int,
    retrieval_debug: Optional[Dict[str, Any]],
) -> RetrievalCoverage:
    if retrieved_sources_count <= 0:
        return RetrievalCoverage.NONE

    debug = retrieval_debug or {}
    score = 0.0
    if retrieved_sources_count >= 8:
        score += 2.0
    elif retrieved_sources_count >= 4:
        score += 1.0

    if cited_sources_count >= 4:
        score += 2.0
    elif cited_sources_count >= 2:
        score += 1.0
    elif cited_sources_count >= 1:
        score += 0.5

    metadata_coverage_ratio = _safe_float(debug.get("metadata_coverage_ratio"), 0.0)
    if metadata_coverage_ratio >= 0.7:
        score += 1.0
    elif metadata_coverage_ratio >= 0.35:
        score += 0.5

    if bool(debug.get("mode_filter_enabled")) and _safe_int(
        debug.get("mode_filter_matched_chunks"), 0
    ) > 0:
        score += 0.5

    if bool(debug.get("mode_filter_fallback_used")):
        score -= 0.5

    if retrieved_sources_count <= 2 and cited_sources_count == 0:
        score -= 0.5

    if score >= 3.0:
        return RetrievalCoverage.STRONG
    if score >= 1.5:
        return RetrievalCoverage.MODERATE
    return RetrievalCoverage.WEAK


def _evaluate_applicability_status(
    *,
    capability_eval: CapabilityEvaluation,
) -> ApplicabilityStatus:
    if capability_eval.outcome == CapabilityOutcome.BLOCKED:
        return ApplicabilityStatus.NOT_APPLICABLE
    if capability_eval.outcome == CapabilityOutcome.STANDARDS_ONLY_GUIDANCE:
        return ApplicabilityStatus.ADVISORY_ONLY
    if capability_eval.authority in {
        CapabilityAuthority.RAG_GUIDANCE_ONLY,
        CapabilityAuthority.NOT_SUPPORTED,
    }:
        return ApplicabilityStatus.ADVISORY_ONLY
    if capability_eval.outcome in {
        CapabilityOutcome.ALLOW_WITH_LIMITATIONS,
        CapabilityOutcome.PARTIAL_ESTIMATE,
    }:
        return ApplicabilityStatus.PARTIALLY_APPLICABLE
    if capability_eval.outcome == CapabilityOutcome.ALLOWED:
        return ApplicabilityStatus.FULLY_APPLICABLE
    return ApplicabilityStatus.PARTIALLY_APPLICABLE


def _evaluate_warning_level(
    *,
    capability_eval: CapabilityEvaluation,
    deterministic_confidence: DeterministicConfidence,
    retrieval_coverage: RetrievalCoverage,
    applicability_status: ApplicabilityStatus,
) -> WarningLevel:
    if capability_eval.outcome == CapabilityOutcome.BLOCKED:
        return WarningLevel.HIGH
    if (
        deterministic_confidence == DeterministicConfidence.UNAVAILABLE
        and _is_deterministic_authority(capability_eval.authority)
    ):
        return WarningLevel.HIGH
    if capability_eval.outcome == CapabilityOutcome.PARTIAL_ESTIMATE:
        return WarningLevel.CAUTION
    if deterministic_confidence == DeterministicConfidence.LOW:
        return WarningLevel.CAUTION
    if retrieval_coverage in {RetrievalCoverage.NONE, RetrievalCoverage.WEAK}:
        if capability_eval.authority in {
            CapabilityAuthority.RAG_GUIDANCE_ONLY,
            CapabilityAuthority.DETERMINISTIC_WITH_RAG_CROSSCHECK,
        }:
            return WarningLevel.CAUTION
        return WarningLevel.INFO
    if applicability_status == ApplicabilityStatus.ADVISORY_ONLY:
        return WarningLevel.INFO
    return WarningLevel.NONE


def _evaluate_result_strength(
    *,
    deterministic_confidence: DeterministicConfidence,
    retrieval_coverage: RetrievalCoverage,
    applicability_status: ApplicabilityStatus,
    warning_level: WarningLevel,
) -> ResultStrength:
    if applicability_status == ApplicabilityStatus.NOT_APPLICABLE:
        return ResultStrength.BLOCKED
    if applicability_status == ApplicabilityStatus.ADVISORY_ONLY:
        return ResultStrength.ADVISORY
    if warning_level == WarningLevel.HIGH:
        return ResultStrength.BLOCKED
    if deterministic_confidence in {
        DeterministicConfidence.UNAVAILABLE,
        DeterministicConfidence.LOW,
    }:
        return ResultStrength.BOUNDED
    if applicability_status == ApplicabilityStatus.FULLY_APPLICABLE:
        if retrieval_coverage in {RetrievalCoverage.STRONG, RetrievalCoverage.MODERATE}:
            return ResultStrength.AUTHORITATIVE
        return ResultStrength.BOUNDED
    return ResultStrength.BOUNDED


def evaluate_analysis_controls(
    *,
    mode_key: str,
    capability_eval: CapabilityEvaluation,
    deterministic_metrics: Optional[dict],
    retrieved_sources: Iterable[dict],
    cited_source_ids: Iterable[str],
    retrieval_debug: Optional[Dict[str, Any]] = None,
) -> AnalysisControlSnapshot:
    retrieved_count = len(list(retrieved_sources or []))
    cited_count = len({str(item) for item in cited_source_ids if item})
    debug = retrieval_debug or {}

    deterministic_confidence = _evaluate_deterministic_confidence(
        mode_key=mode_key,
        capability_eval=capability_eval,
        deterministic_metrics=deterministic_metrics,
    )
    retrieval_coverage = _evaluate_retrieval_coverage(
        retrieved_sources_count=retrieved_count,
        cited_sources_count=cited_count,
        retrieval_debug=debug,
    )
    applicability_status = _evaluate_applicability_status(
        capability_eval=capability_eval,
    )
    warning_level = _evaluate_warning_level(
        capability_eval=capability_eval,
        deterministic_confidence=deterministic_confidence,
        retrieval_coverage=retrieval_coverage,
        applicability_status=applicability_status,
    )
    result_strength = _evaluate_result_strength(
        deterministic_confidence=deterministic_confidence,
        retrieval_coverage=retrieval_coverage,
        applicability_status=applicability_status,
        warning_level=warning_level,
    )

    reason = capability_eval.reason_key
    if not reason and retrieval_coverage == RetrievalCoverage.NONE:
        if applicability_status == ApplicabilityStatus.ADVISORY_ONLY:
            reason = "retrieval_coverage_none_advisory"
        elif mode_key in {
            "takeoff",
            "landing",
            "performance",
            "buffet_vibration",
            "handling_qualities",
        }:
            reason = "retrieval_coverage_none"

    warning_messages: List[str] = []
    if capability_eval.outcome == CapabilityOutcome.BLOCKED:
        warning_messages.append(
            "Requested capability is blocked for the available data and cannot produce an engineering result."
        )
    if capability_eval.outcome == CapabilityOutcome.PARTIAL_ESTIMATE:
        warning_messages.append(
            "Output is downgraded to a partial estimate due to missing correction inputs."
        )
    if deterministic_confidence in {
        DeterministicConfidence.UNAVAILABLE,
        DeterministicConfidence.LOW,
    } and _is_deterministic_authority(capability_eval.authority):
        warning_messages.append(
            "Deterministic confidence is limited for this mode/data combination."
        )
    if retrieval_coverage in {RetrievalCoverage.NONE, RetrievalCoverage.WEAK}:
        warning_messages.append(
            "Document-retrieval support is weak; standards/context conclusions should be interpreted cautiously."
        )

    return AnalysisControlSnapshot(
        deterministic_confidence=deterministic_confidence,
        retrieval_coverage=retrieval_coverage,
        applicability_status=applicability_status,
        warning_level=warning_level,
        result_strength=result_strength,
        blocking_or_downgrade_reason=reason,
        warning_messages=warning_messages,
        deterministic_available=bool(deterministic_metrics and deterministic_metrics.get("available")),
        retrieved_sources_count=retrieved_count,
        cited_sources_count=cited_count,
        mode_filter_fallback_used=bool(debug.get("mode_filter_fallback_used", False)),
        metadata_coverage_ratio=max(0.0, min(1.0, _safe_float(debug.get("metadata_coverage_ratio"), 0.0))),
    )


def parse_analysis_controls(raw: Any) -> AnalysisControlSnapshot:
    """Backward-safe parser for persisted snapshots (legacy jobs may not have this field)."""
    if isinstance(raw, AnalysisControlSnapshot):
        return raw
    if isinstance(raw, dict):
        payload = raw
    else:
        payload = {}
    try:
        return AnalysisControlSnapshot.model_validate(payload)
    except Exception:
        return AnalysisControlSnapshot(
            deterministic_confidence=DeterministicConfidence.UNAVAILABLE,
            retrieval_coverage=RetrievalCoverage.NONE,
            applicability_status=ApplicabilityStatus.ADVISORY_ONLY,
            warning_level=WarningLevel.INFO,
            result_strength=ResultStrength.ADVISORY,
            blocking_or_downgrade_reason="controls_unavailable",
            warning_messages=["Analysis control snapshot was unavailable for this artifact."],
            deterministic_available=False,
            retrieved_sources_count=0,
            cited_sources_count=0,
            mode_filter_fallback_used=False,
            metadata_coverage_ratio=0.0,
        )

"""Focused tests for P2.4 confidence / coverage / applicability controls."""

from app.analysis_controls import (
    ApplicabilityStatus,
    DeterministicConfidence,
    ResultStrength,
    RetrievalCoverage,
    WarningLevel,
    evaluate_analysis_controls,
)
from app.capabilities import evaluate_capability_request


def test_takeoff_controls_show_bounded_strong_engineering_state():
    capability_eval = evaluate_capability_request(
        "takeoff",
        available_signals=["ground_speed", "weight_on_wheels"],
        has_dataset=True,
        has_time_series_continuity=True,
        data_coverage_ok=True,
        event_detection_ok=True,
        has_standards_context=True,
    )
    controls = evaluate_analysis_controls(
        mode_key="takeoff",
        capability_eval=capability_eval,
        deterministic_metrics={
            "available": True,
            "sample_intervals_used": 42,
            "run_time_s": 11.1,
        },
        retrieved_sources=[{"source_id": "S1"} for _ in range(8)],
        cited_source_ids=["S1", "S2", "S3", "S4"],
        retrieval_debug={
            "mode_filter_enabled": True,
            "mode_filter_matched_chunks": 4,
            "mode_filter_fallback_used": False,
            "metadata_coverage_ratio": 0.82,
        },
    )

    assert controls.deterministic_confidence == DeterministicConfidence.HIGH
    assert controls.retrieval_coverage == RetrievalCoverage.STRONG
    assert controls.applicability_status == ApplicabilityStatus.PARTIALLY_APPLICABLE
    assert controls.result_strength == ResultStrength.BOUNDED


def test_general_controls_are_advisory_with_info_warning():
    capability_eval = evaluate_capability_request(
        "general_standards_query",
        has_dataset=True,
        has_standards_context=True,
    )
    controls = evaluate_analysis_controls(
        mode_key="general",
        capability_eval=capability_eval,
        deterministic_metrics=None,
        retrieved_sources=[{"source_id": "S1"}, {"source_id": "S2"}, {"source_id": "S3"}],
        cited_source_ids=["S1", "S2"],
        retrieval_debug={
            "mode_filter_enabled": False,
            "mode_filter_fallback_used": False,
            "metadata_coverage_ratio": 0.5,
        },
    )

    assert controls.applicability_status == ApplicabilityStatus.ADVISORY_ONLY
    assert controls.result_strength == ResultStrength.ADVISORY
    assert controls.warning_level in {WarningLevel.INFO, WarningLevel.CAUTION}


def test_buffet_controls_mark_retrieval_none_explicitly():
    capability_eval = evaluate_capability_request(
        "buffet_vibration",
        available_signals=["accelerometers"],
        has_dataset=True,
        has_time_series_continuity=True,
        data_coverage_ok=True,
    )
    controls = evaluate_analysis_controls(
        mode_key="buffet_vibration",
        capability_eval=capability_eval,
        deterministic_metrics={
            "available": True,
            "samples_used": 96,
        },
        retrieved_sources=[],
        cited_source_ids=[],
        retrieval_debug={},
    )

    assert controls.retrieval_coverage == RetrievalCoverage.NONE
    assert controls.warning_level in {WarningLevel.INFO, WarningLevel.CAUTION}
    assert controls.result_strength == ResultStrength.BOUNDED


def test_blocked_takeoff_controls_escalate_to_high_and_blocked():
    capability_eval = evaluate_capability_request(
        "takeoff",
        available_signals=["ground_speed"],  # WOW missing on purpose
        has_dataset=True,
        has_standards_context=True,
    )
    controls = evaluate_analysis_controls(
        mode_key="takeoff",
        capability_eval=capability_eval,
        deterministic_metrics=None,
        retrieved_sources=[],
        cited_source_ids=[],
        retrieval_debug={},
    )

    assert controls.applicability_status == ApplicabilityStatus.NOT_APPLICABLE
    assert controls.warning_level == WarningLevel.HIGH
    assert controls.result_strength == ResultStrength.BLOCKED
    assert controls.blocking_or_downgrade_reason == "missing_required_signals"

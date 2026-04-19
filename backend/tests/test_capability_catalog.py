"""Tests for backend capability catalog and rule evaluation."""

from app.capabilities import (
    CapabilityAuthority,
    CapabilityImplementationStatus,
    CapabilityOutcome,
    evaluate_capability_request,
    get_capability_definition,
)


def test_takeoff_capability_definition_resolves_with_expected_authority():
    cap = get_capability_definition("takeoff")
    assert cap is not None
    assert cap.key == "takeoff"
    assert cap.status == CapabilityImplementationStatus.IMPLEMENTED
    assert cap.authority == CapabilityAuthority.DETERMINISTIC_WITH_RAG_CROSSCHECK
    assert "ground_speed" in cap.required_inputs.required_signals
    assert "weight_on_wheels" in cap.required_inputs.required_signals


def test_takeoff_missing_required_signal_is_blocked():
    evaluation = evaluate_capability_request(
        "takeoff",
        available_signals=["ground_speed"],
        has_dataset=True,
    )
    assert evaluation.outcome == CapabilityOutcome.BLOCKED
    assert evaluation.reason_key == "missing_required_signals"
    assert "weight_on_wheels" in evaluation.missing_required_signals


def test_takeoff_certification_request_without_corrections_is_downgraded_partial():
    evaluation = evaluate_capability_request(
        "takeoff",
        available_signals=["ground_speed", "weight_on_wheels", "longitudinal_acceleration"],
        has_dataset=True,
        has_time_series_continuity=True,
        data_coverage_ok=True,
        event_detection_ok=True,
        request_certification_result=True,
        correction_inputs_available=False,
    )
    assert evaluation.outcome == CapabilityOutcome.PARTIAL_ESTIMATE
    assert evaluation.reason_key == "certification_corrections_missing"


def test_unsupported_capability_returns_not_supported_state():
    evaluation = evaluate_capability_request("not_a_real_capability")
    assert evaluation.authority == CapabilityAuthority.NOT_SUPPORTED
    assert evaluation.outcome == CapabilityOutcome.BLOCKED
    assert evaluation.reason_key == "capability_not_supported"


def test_takeoff_applicability_statements_are_stable_and_explicit():
    evaluation = evaluate_capability_request(
        "takeoff",
        available_signals=["ground_speed", "weight_on_wheels"],
        has_dataset=True,
        has_time_series_continuity=True,
        data_coverage_ok=True,
        event_detection_ok=True,
    )
    assert evaluation.outcome == CapabilityOutcome.ALLOW_WITH_LIMITATIONS
    combined = " ".join(evaluation.applicability_boundaries)
    assert "estimated ground roll to liftoff" in combined.lower()
    assert "not equivalent to corrected certification takeoff distance" in combined.lower()


def test_landing_capability_is_implemented_and_deterministic():
    cap = get_capability_definition("landing")
    assert cap is not None
    assert cap.status == CapabilityImplementationStatus.IMPLEMENTED
    assert cap.authority == CapabilityAuthority.DETERMINISTIC_WITH_RAG_CROSSCHECK
    assert "ground_speed" in cap.required_inputs.required_signals
    assert "weight_on_wheels" in cap.required_inputs.required_signals


def test_performance_general_capability_is_bounded_deterministic():
    cap = get_capability_definition("performance_general")
    assert cap is not None
    assert cap.status == CapabilityImplementationStatus.IMPLEMENTED
    assert cap.authority == CapabilityAuthority.DETERMINISTIC_PRIMARY

    evaluation = evaluate_capability_request(
        "performance_general",
        available_signals=["ground_speed", "altitude"],
        has_dataset=True,
        has_time_series_continuity=True,
        data_coverage_ok=True,
    )
    assert evaluation.outcome == CapabilityOutcome.ALLOW_WITH_LIMITATIONS
    assert "certification" in " ".join(evaluation.applicability_boundaries).lower()


def test_buffet_vibration_capability_is_deterministic_screening_only():
    cap = get_capability_definition("buffet_vibration")
    assert cap is not None
    assert cap.status == CapabilityImplementationStatus.IMPLEMENTED
    assert cap.authority == CapabilityAuthority.DETERMINISTIC_PRIMARY

    evaluation = evaluate_capability_request(
        "buffet_vibration",
        available_signals=["accelerometers"],
        has_dataset=True,
        has_time_series_continuity=True,
        data_coverage_ok=True,
    )
    assert evaluation.outcome == CapabilityOutcome.ALLOW_WITH_LIMITATIONS
    assert "not sufficient for formal loads substantiation" in " ".join(
        evaluation.applicability_boundaries
    ).lower()

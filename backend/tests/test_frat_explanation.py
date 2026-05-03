"""Tests for P4.1 FRAT no-go explanation and export availability."""

import json

from fastapi import status

from app.models import AnalysisJob, DatasetVersion, FlightTest
from app.routers import frat as frat_router


def _create_flight_test(db_session, user_id: int, name: str = "FRAT Explanation") -> FlightTest:
    flight_test = FlightTest(
        test_name=name,
        aircraft_type="F-16",
        created_by_id=user_id,
    )
    db_session.add(flight_test)
    db_session.commit()
    db_session.refresh(flight_test)
    return flight_test


def _create_dataset(db_session, flight_test: FlightTest, user_id: int) -> DatasetVersion:
    dataset = DatasetVersion(
        flight_test_id=flight_test.id,
        version_number=1,
        label="v1 scored evidence",
        status="success",
        row_count=10,
        data_points_count=50,
        created_by_id=user_id,
    )
    db_session.add(dataset)
    db_session.commit()
    db_session.refresh(dataset)
    return dataset


def _create_analysis_job(
    db_session, flight_test: FlightTest, user_id: int, dataset_id: int | None = None
) -> AnalysisJob:
    controls = {
        "deterministic_confidence": "low",
        "retrieval_coverage": "weak",
        "applicability_status": "partially_applicable",
        "warning_level": "caution",
        "result_strength": "bounded",
        "blocking_or_downgrade_reason": "limited_evidence",
        "warning_messages": ["Evidence is bounded and should be reviewed."],
        "deterministic_available": True,
        "retrieved_sources_count": 1,
        "cited_sources_count": 0,
        "mode_filter_fallback_used": False,
        "metadata_coverage_ratio": 0.2,
    }
    job = AnalysisJob(
        flight_test_id=flight_test.id,
        created_by_id=user_id,
        dataset_version_id=dataset_id,
        status="completed",
        model_name="gpt-4o-mini",
        model_version="2026-04-01",
        parameters_analysed=2,
        parameter_stats_snapshot_json="[]",
        analysis_controls_json=json.dumps(controls),
        prompt_text="[analysis_mode:takeoff] Review takeoff evidence",
        retrieved_source_ids_json="[]",
        retrieved_sources_snapshot_json="[]",
        output_sha256="e" * 64,
        analysis_text="Bounded takeoff evidence.",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def _create_assessment(client, headers, flight_test_id: int, inputs: dict, **extra) -> int:
    response = client.post(
        "/api/frat/assessments",
        json={
            "flight_test_id": flight_test_id,
            "assessment_name": extra.pop("assessment_name", "P4.1 assessment"),
            "analysis_job_ids": extra.pop("analysis_job_ids", []),
            "dataset_version_id": extra.pop("dataset_version_id", None),
            "inputs": inputs,
        },
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["id"]


def _score(client, headers, assessment_id: int) -> dict:
    response = client.post(f"/api/frat/assessments/{assessment_id}/score", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def test_low_risk_approved_assessment_can_export_with_explanation(
    client, db_session, test_user, auth_headers, monkeypatch
):
    flight_test = _create_flight_test(db_session, test_user["id"], "FRAT Low Export")
    captured = {}

    def fake_build_pdf(*, report_snapshot, generated_by):
        captured["report_snapshot"] = report_snapshot
        captured["generated_by"] = generated_by
        return b"%PDF-1.4\n%mock\n"

    monkeypatch.setattr(frat_router, "_build_frat_pdf", fake_build_pdf)
    assessment_id = _create_assessment(
        client,
        auth_headers,
        flight_test.id,
        {
            "requested_decision_authority": "advisory",
            "categories": {
                "mission_profile": {"score": 1},
                "weather_environment": {"score": 1},
                "runway_operational": {"score": 1},
                "aircraft_system_status": {"score": 1},
                "crew_readiness": {"score": 1},
            },
        },
    )
    scored = _score(client, auth_headers, assessment_id)
    assert scored["decision_explanation"]["score_composition"]["recommendation"] == "go"

    approved = client.post(
        f"/api/frat/assessments/{assessment_id}/approve",
        json={"notes": "Approved low-risk case"},
        headers=auth_headers,
    )
    assert approved.status_code == status.HTTP_200_OK, approved.text

    exported = client.get(f"/api/frat/assessments/{assessment_id}/report.pdf", headers=auth_headers)
    assert exported.status_code == status.HTTP_200_OK, exported.text
    assert captured["report_snapshot"]["decision_explanation"]["decision"]["is_acceptable"] is True

    finalized = client.post(
        f"/api/frat/assessments/{assessment_id}/finalize",
        json={"notes": "Finalized low-risk case"},
        headers=auth_headers,
    )
    assert finalized.status_code == status.HTTP_200_OK, finalized.text
    finalized_export = client.get(
        f"/api/frat/assessments/{assessment_id}/report.pdf",
        headers=auth_headers,
    )
    assert finalized_export.status_code == status.HTTP_200_OK, finalized_export.text
    assert captured["report_snapshot"]["summary"]["status"] == "finalized"


def test_rejected_no_go_unacceptable_scored_assessment_can_export(
    client, db_session, test_user, auth_headers, monkeypatch
):
    flight_test = _create_flight_test(db_session, test_user["id"], "FRAT No Go Export")
    captured = {}

    def fake_build_pdf(*, report_snapshot, generated_by):
        captured["report_snapshot"] = report_snapshot
        return b"%PDF-1.4\n%mock\n"

    monkeypatch.setattr(frat_router, "_build_frat_pdf", fake_build_pdf)
    assessment_id = _create_assessment(
        client,
        auth_headers,
        flight_test.id,
        {
            "requested_decision_authority": "advisory",
            "categories": {
                "mission_profile": {"score": 18},
                "weather_environment": {"score": 18},
                "runway_operational": {"score": 16},
                "aircraft_system_status": {"score": 16},
                "crew_readiness": {"score": 14},
            },
            "reviewer_notes": "Weather and mission profile exceed normal risk envelope.",
        },
    )
    scored = _score(client, auth_headers, assessment_id)
    assert scored["status"] == "needs_review"
    assert scored["score_snapshot"]["risk_band"] == "unacceptable"
    assert scored["score_snapshot"]["recommendation"] == "no_go"

    rejected = client.post(
        f"/api/frat/assessments/{assessment_id}/reject",
        json={"notes": "Rejected pending mitigation"},
        headers=auth_headers,
    )
    assert rejected.status_code == status.HTTP_200_OK, rejected.text

    exported = client.get(f"/api/frat/assessments/{assessment_id}/report.pdf", headers=auth_headers)
    assert exported.status_code == status.HTTP_200_OK, exported.text
    explanation = captured["report_snapshot"]["decision_explanation"]
    assert explanation["lifecycle_state"] == "rejected"
    assert "score_band" in explanation["decision"]["driver_types"]
    assert any(
        "Mitigate and rescore" in item
        for item in explanation["decision"]["recommended_next_actions"]
    )


def test_hard_stop_assessment_can_export_and_includes_reasons(
    client, db_session, test_user, auth_headers, monkeypatch
):
    flight_test = _create_flight_test(db_session, test_user["id"], "FRAT Hard Stop Export")
    captured = {}

    def fake_build_pdf(*, report_snapshot, generated_by):
        captured["report_snapshot"] = report_snapshot
        return b"%PDF-1.4\n%mock\n"

    monkeypatch.setattr(frat_router, "_build_frat_pdf", fake_build_pdf)
    assessment_id = _create_assessment(
        client,
        auth_headers,
        flight_test.id,
        {
            "requested_decision_authority": "advisory",
            "critical_flags": {"crew_unfit": True},
            "categories": {
                "mission_profile": {"score": 1},
                "weather_environment": {"score": 1},
                "runway_operational": {"score": 1},
                "aircraft_system_status": {"score": 1},
                "crew_readiness": {"score": 1},
            },
        },
    )
    scored = _score(client, auth_headers, assessment_id)
    assert scored["decision_explanation"]["hard_stops"]["triggered"] is True
    assert (
        "Crew readiness indicates unfit status."
        in scored["decision_explanation"]["hard_stops"]["reasons"]
    )

    exported = client.get(f"/api/frat/assessments/{assessment_id}/report.pdf", headers=auth_headers)
    assert exported.status_code == status.HTTP_200_OK, exported.text
    assert (
        "crew_unfit" in captured["report_snapshot"]["decision_explanation"]["hard_stops"]["flags"]
    )


def test_no_linked_analysis_explanation_and_unscored_draft_export_block(
    client, db_session, test_user, auth_headers
):
    flight_test = _create_flight_test(db_session, test_user["id"], "FRAT No Analysis")
    assessment_id = _create_assessment(
        client,
        auth_headers,
        flight_test.id,
        {
            "requested_decision_authority": "advisory",
            "categories": {
                "mission_profile": {"score": 8},
                "weather_environment": {"score": 8},
                "runway_operational": {"score": 8},
                "aircraft_system_status": {"score": 4},
                "crew_readiness": {"score": 4},
            },
        },
    )

    draft_export = client.get(
        f"/api/frat/assessments/{assessment_id}/report.pdf", headers=auth_headers
    )
    assert draft_export.status_code == status.HTTP_400_BAD_REQUEST
    assert "must be scored before export" in draft_export.json()["detail"]

    scored = _score(client, auth_headers, assessment_id)
    explanation = scored["decision_explanation"]
    assert explanation["linked_analysis"]["available"] is False
    assert (
        "No linked analysis job is available"
        in explanation["linked_analysis"]["no_linked_analysis_statement"]
    )
    assert explanation["linked_analysis"]["warning"] == (
        "Review required: score is moderate or higher and no linked analysis evidence is attached."
    )

    reopened = client.get(f"/api/frat/assessments/{assessment_id}", headers=auth_headers)
    assert reopened.status_code == status.HTTP_200_OK, reopened.text
    assert reopened.json()["decision_explanation"]["linked_analysis"]["available"] is False


def test_linked_analysis_penalty_appears_in_score_composition_and_explanation(
    client, db_session, test_user, auth_headers, monkeypatch
):
    flight_test = _create_flight_test(db_session, test_user["id"], "FRAT Linked Penalty")
    dataset = _create_dataset(db_session, flight_test, test_user["id"])
    job = _create_analysis_job(db_session, flight_test, test_user["id"], dataset.id)
    captured = {}

    def fake_build_pdf(*, report_snapshot, generated_by):
        captured["report_snapshot"] = report_snapshot
        return b"%PDF-1.4\n%mock\n"

    monkeypatch.setattr(frat_router, "_build_frat_pdf", fake_build_pdf)

    assessment_id = _create_assessment(
        client,
        auth_headers,
        flight_test.id,
        {
            "requested_decision_authority": "advisory",
            "categories": {
                "mission_profile": {"score": 1},
                "weather_environment": {"score": 1},
                "runway_operational": {"score": 1},
                "aircraft_system_status": {"score": 1},
                "crew_readiness": {"score": 1},
            },
        },
        dataset_version_id=dataset.id,
        analysis_job_ids=[job.id],
    )
    scored = _score(client, auth_headers, assessment_id)
    explanation = scored["decision_explanation"]
    assert scored["score_snapshot"]["analysis_indicator_score"] > 0
    assert (
        explanation["score_composition"]["analysis_indicator_score"]
        == scored["score_snapshot"]["analysis_indicator_score"]
    )
    assert explanation["linked_analysis"]["available"] is True
    assert explanation["linked_analysis"]["controls_summary"][0]["analysis_job_id"] == job.id
    assert explanation["dataset_version"]["label"] == "v1 scored evidence"

    exported = client.get(f"/api/frat/assessments/{assessment_id}/report.pdf", headers=auth_headers)
    assert exported.status_code == status.HTTP_200_OK, exported.text
    assert (
        captured["report_snapshot"]["decision_explanation"]["linked_analysis"]["controls_summary"][
            0
        ]["analysis_job_id"]
        == job.id
    )

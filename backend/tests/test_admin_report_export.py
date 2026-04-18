"""Tests for immutable admin PDF export from persisted analysis jobs."""

from datetime import datetime
import json

from fastapi import status

from app.models import AnalysisJob, DataPoint, DatasetVersion, FlightTest, TestParameter
from app.routers import admin as admin_router


def _create_flight_test(db_session, user_id: int, name: str = "Admin Report Test") -> FlightTest:
    flight_test = FlightTest(
        test_name=name,
        aircraft_type="F-16",
        created_by_id=user_id,
    )
    db_session.add(flight_test)
    db_session.commit()
    db_session.refresh(flight_test)
    return flight_test


def test_admin_pdf_export_uses_persisted_analysis_job(client, db_session, admin_user, admin_headers, monkeypatch):
    flight_test = _create_flight_test(db_session, admin_user["id"])
    job = AnalysisJob(
        flight_test_id=flight_test.id,
        created_by_id=admin_user["id"],
        status="completed",
        model_name="gpt-4o-mini",
        model_version=None,
        prompt_text="Prompt",
        retrieved_source_ids_json='["S1"]',
        retrieved_sources_snapshot_json='[{"source_id":"S1"}]',
        output_sha256="b" * 64,
        analysis_text="Persisted analysis text",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    captured = {}

    def fake_build_pdf(*, flight_test, stats_snapshot, analysis_text, generated_by, analysis_job=None):
        captured["analysis_text"] = analysis_text
        captured["analysis_job_id"] = analysis_job.id if analysis_job else None
        captured["stats_snapshot"] = stats_snapshot
        return b"%PDF-1.4\n%mock\n"

    monkeypatch.setattr(admin_router, "_build_pdf", fake_build_pdf)

    response = client.post(
        f"/api/admin/flight-tests/{flight_test.id}/report.pdf",
        json={"analysis_job_id": job.id},
        headers=admin_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/pdf"
    assert captured["analysis_text"] == "Persisted analysis text"
    assert captured["analysis_job_id"] == job.id
    assert captured["stats_snapshot"] == []


def test_admin_pdf_export_rejects_unknown_analysis_job(client, db_session, admin_user, admin_headers):
    flight_test = _create_flight_test(db_session, admin_user["id"], name="Missing Analysis Job")

    response = client.post(
        f"/api/admin/flight-tests/{flight_test.id}/report.pdf",
        json={"analysis_job_id": 99999},
        headers=admin_headers,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Analysis job not found" in response.json()["detail"]


def test_admin_pdf_export_uses_persisted_stats_snapshot_after_data_changes(
    client, db_session, admin_user, admin_headers, monkeypatch
):
    flight_test = _create_flight_test(db_session, admin_user["id"], name="Snapshot Immutable")
    persisted_snapshot = [
        {
            "name": "SNAP_PARAM",
            "unit": "kt",
            "min_val": 1.0,
            "max_val": 2.0,
            "avg_val": 1.5,
            "std_val": 0.5,
            "sample_count": 2,
        }
    ]
    job = AnalysisJob(
        flight_test_id=flight_test.id,
        created_by_id=admin_user["id"],
        status="completed",
        model_name="gpt-4o-mini",
        model_version=None,
        parameters_analysed=1,
        parameter_stats_snapshot_json=json.dumps(persisted_snapshot),
        prompt_text="Prompt",
        retrieved_source_ids_json="[]",
        retrieved_sources_snapshot_json="[]",
        output_sha256="d" * 64,
        analysis_text="Persisted analysis text",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    # Mutable live data diverges later.
    live_param = TestParameter(name="LIVE_REPORT_PARAM", unit="g")
    db_session.add(live_param)
    db_session.commit()
    db_session.refresh(live_param)
    db_session.add(
        DataPoint(
            flight_test_id=flight_test.id,
            parameter_id=live_param.id,
            timestamp=datetime(2026, 4, 11, 13, 0, 0),
            value=999.0,
        )
    )
    db_session.commit()

    captured = {}

    def fake_build_pdf(*, flight_test, stats_snapshot, analysis_text, generated_by, analysis_job=None):
        captured["stats_snapshot"] = stats_snapshot
        return b"%PDF-1.4\n%mock\n"

    monkeypatch.setattr(admin_router, "_build_pdf", fake_build_pdf)

    response = client.post(
        f"/api/admin/flight-tests/{flight_test.id}/report.pdf",
        json={"analysis_job_id": job.id},
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert captured["stats_snapshot"] == persisted_snapshot


def test_build_pdf_contains_professional_sections_and_provenance_block(db_session, admin_user):
    flight_test = _create_flight_test(db_session, admin_user["id"], name="Professional Report")
    dataset_version = DatasetVersion(
        flight_test_id=flight_test.id,
        version_number=3,
        label="v3",
        status="active",
        row_count=1234,
        data_points_count=4321,
        created_by_id=admin_user["id"],
    )
    db_session.add(dataset_version)
    db_session.commit()
    db_session.refresh(dataset_version)

    job = AnalysisJob(
        flight_test_id=flight_test.id,
        created_by_id=admin_user["id"],
        dataset_version_id=dataset_version.id,
        status="completed",
        model_name="gpt-4o-mini",
        model_version="2026-04-01",
        parameters_analysed=2,
        parameter_stats_snapshot_json=json.dumps(
            [
                {
                    "name": "IAS",
                    "unit": "kt",
                    "min_val": 80.0,
                    "max_val": 210.0,
                    "avg_val": 140.0,
                    "std_val": 9.5,
                    "sample_count": 320,
                },
                {
                    "name": "AOA",
                    "unit": "deg",
                    "min_val": 2.1,
                    "max_val": 14.4,
                    "avg_val": 6.9,
                    "std_val": 1.2,
                    "sample_count": 310,
                },
            ]
        ),
        prompt_text="Prompt",
        retrieved_source_ids_json='["S1","S2"]',
        retrieved_sources_snapshot_json=json.dumps(
            [
                {
                    "source_id": "S1",
                    "filename": "MIL-HDBK-1763.pdf",
                    "title": "MIL-HDBK-1763",
                    "page_numbers": "33-34",
                    "section_title": "Separation Analysis",
                    "similarity": 0.83,
                }
            ]
        ),
        output_sha256="f" * 64,
        analysis_text=(
            "## Findings\n"
            "Finding: Separation envelope remains constrained at high alpha.\n\n"
            "## Recommendations\n"
            "Recommendation: Expand instrumentation for release transient capture."
        ),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    # Warm relationship for deterministic provenance rendering in helper.
    _ = job.dataset_version

    pdf_bytes = admin_router._build_pdf(
        flight_test=flight_test,
        stats_snapshot=json.loads(job.parameter_stats_snapshot_json),
        analysis_text=job.analysis_text,
        generated_by=admin_user["username"],
        analysis_job=job,
    )

    assert b"FTIAS Engineering Analysis Report" in pdf_bytes
    assert b"1. Flight Test Metadata Summary" in pdf_bytes
    assert b"2. Dataset Provenance Summary" in pdf_bytes
    assert b"4. Key Charts / Figures" in pdf_bytes
    assert b"5. Parameter Statistics Summary" in pdf_bytes
    assert b"6. Engineering Assessment Narrative" in pdf_bytes
    assert b"7. Sources / Provenance / References" in pdf_bytes
    assert b"Provenance statement: This PDF reflects persisted analysis job artifacts." in pdf_bytes
    assert b"Dataset Label" in pdf_bytes
    assert dataset_version.label.encode() in pdf_bytes


def test_build_pdf_takeoff_context_includes_result_classification_and_limitations(
    db_session, admin_user
):
    flight_test = _create_flight_test(db_session, admin_user["id"], name="Takeoff Wording Hardening")
    job = AnalysisJob(
        flight_test_id=flight_test.id,
        created_by_id=admin_user["id"],
        status="completed",
        model_name="gpt-4o-mini",
        model_version="2026-04-01",
        parameters_analysed=1,
        parameter_stats_snapshot_json=json.dumps(
            [
                {
                    "name": "GS",
                    "unit": "kt",
                    "min_val": 0.0,
                    "max_val": 83.0,
                    "avg_val": 42.0,
                    "std_val": 5.0,
                    "sample_count": 250,
                }
            ]
        ),
        prompt_text=(
            "Provide an approximate takeoff distance calculation using WOW and ground speed data."
        ),
        retrieved_source_ids_json='["S1"]',
        retrieved_sources_snapshot_json='[{"source_id":"S1","title":"MIL-HDBK-1763","similarity":0.8}]',
        output_sha256="e" * 64,
        analysis_text=(
            "## Deterministic Calculation (Flight Data) [DATA]\n"
            "Estimated takeoff ground roll to liftoff from WOW transition.\n\n"
            "## Standards Cross-Check\n"
            "Relevant release standards require careful envelope definition [S1].\n\n"
            "## Recommendations\n"
            "Recommendation: validate event-detection sensitivity before campaign release."
        ),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    pdf_bytes = admin_router._build_pdf(
        flight_test=flight_test,
        stats_snapshot=json.loads(job.parameter_stats_snapshot_json),
        analysis_text=job.analysis_text,
        generated_by=admin_user["username"],
        analysis_job=job,
    )

    assert b"6.1 Deterministic Computed Result" in pdf_bytes
    assert b"Estimated takeoff ground roll to liftoff" in pdf_bytes
    assert b"Deterministic data-derived estimate" in pdf_bytes
    assert b"Certification-corrected takeoff distance was not computed in this report." in pdf_bytes
    assert b"6.3 Assumptions and Limitations" in pdf_bytes
    assert b"Wind correction not applied." in pdf_bytes
    assert b"6.5 Applicability Boundaries" in pdf_bytes
    assert b"Not equivalent to corrected certification takeoff distance unless explicit corrections are applied." in pdf_bytes

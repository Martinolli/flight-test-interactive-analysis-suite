"""Tests for immutable admin PDF export from persisted analysis jobs."""

from datetime import datetime
import json

from fastapi import status

from app.models import AnalysisJob, DataPoint, FlightTest, TestParameter
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

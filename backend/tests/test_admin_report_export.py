"""Tests for immutable admin PDF export from persisted analysis jobs."""

from fastapi import status

from app.models import AnalysisJob, FlightTest
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

    def fake_build_pdf(*, flight_test, stats_rows, analysis_text, generated_by, analysis_job=None):
        captured["analysis_text"] = analysis_text
        captured["analysis_job_id"] = analysis_job.id if analysis_job else None
        return b"%PDF-1.4\n%mock\n"

    monkeypatch.setattr(admin_router.func, "stddev", lambda col: admin_router.func.avg(col))
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


def test_admin_pdf_export_rejects_unknown_analysis_job(client, db_session, admin_user, admin_headers):
    flight_test = _create_flight_test(db_session, admin_user["id"], name="Missing Analysis Job")

    response = client.post(
        f"/api/admin/flight-tests/{flight_test.id}/report.pdf",
        json={"analysis_job_id": 99999},
        headers=admin_headers,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Analysis job not found" in response.json()["detail"]

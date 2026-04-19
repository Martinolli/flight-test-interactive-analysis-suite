"""API routing tests for P2.1 analysis_mode architecture."""

from datetime import datetime

from fastapi import status

from app.models import AnalysisJob, DataPoint, FlightTest, TestParameter
from app.routers import documents as documents_router


def _create_flight_test_with_single_datapoint(db_session, owner_id: int) -> FlightTest:
    flight_test = FlightTest(
        test_name="Mode Routing Test",
        aircraft_type="F-16",
        created_by_id=owner_id,
    )
    db_session.add(flight_test)
    db_session.commit()
    db_session.refresh(flight_test)

    parameter = TestParameter(name="TEST_MODE_SPEED", unit="kt")
    db_session.add(parameter)
    db_session.commit()
    db_session.refresh(parameter)

    db_session.add(
        DataPoint(
            flight_test_id=flight_test.id,
            parameter_id=parameter.id,
            timestamp=datetime(2026, 4, 19, 10, 0, 0),
            value=120.0,
        )
    )
    db_session.commit()
    return flight_test


def test_get_analysis_modes_returns_catalog_backed_modes(client, auth_headers):
    response = client.get("/api/documents/analysis-modes", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    keys = {item["key"] for item in payload}
    assert keys == {
        "takeoff",
        "landing",
        "performance",
        "handling_qualities",
        "buffet_vibration",
        "flutter",
        "propulsion_systems",
        "electrical_systems",
        "general",
    }
    takeoff = next(item for item in payload if item["key"] == "takeoff")
    assert takeoff["capability_key"] == "takeoff"
    assert takeoff["capability_status"] == "implemented"
    assert takeoff["authority"] == "deterministic_with_rag_crosscheck"
    assert takeoff["default"] is True
    landing = next(item for item in payload if item["key"] == "landing")
    assert landing["capability_status"] == "implemented"
    assert landing["authority"] == "deterministic_with_rag_crosscheck"
    performance = next(item for item in payload if item["key"] == "performance")
    assert performance["capability_status"] == "implemented"
    assert performance["authority"] == "deterministic_primary"
    buffet = next(item for item in payload if item["key"] == "buffet_vibration")
    assert buffet["capability_status"] == "implemented"
    assert buffet["authority"] == "deterministic_primary"


def test_ai_analysis_defaults_to_takeoff_mode_and_persists_mode_tag(
    client, db_session, test_user, auth_headers, monkeypatch
):
    flight_test = _create_flight_test_with_single_datapoint(db_session, test_user["id"])

    def fake_retrieve_hybrid_sources(*, db, question, requested_top_k, owner_user_id):
        return (
            [
                {
                    "source_id": "S1",
                    "filename": "std.pdf",
                    "title": "Standard",
                    "page_numbers": "12",
                    "section_title": "Takeoff",
                    "similarity": 0.98,
                    "text": "sample standards chunk",
                }
            ],
            "[S1] sample context",
        )

    class _FakeMessage:
        content = "Standards cross-check result [S1]"

    class _FakeChoice:
        message = _FakeMessage()

    class _FakeCompletion:
        choices = [_FakeChoice()]

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            return _FakeCompletion()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    monkeypatch.setattr(documents_router, "_require_ai_packages", lambda: None)
    monkeypatch.setattr(documents_router, "_retrieve_hybrid_sources", fake_retrieve_hybrid_sources)
    monkeypatch.setattr(documents_router, "get_openai_client", lambda: _FakeClient())
    monkeypatch.setattr(documents_router.func, "stddev", lambda col: documents_router.func.avg(col))
    monkeypatch.setattr(
        documents_router,
        "_compute_takeoff_metrics",
        lambda db, flight_test_id, dataset_version_id=None, request_certification_result=False: {
            "distance_ft": 1234.5,
            "distance_m": 376.3,
            "dataset_version_id": dataset_version_id,
            "capability_key": "takeoff",
            "capability_outcome": "allow_with_limitations",
        },
    )
    monkeypatch.setattr(
        documents_router,
        "_build_deterministic_takeoff_section",
        lambda metrics: "### Deterministic Takeoff Computation\n- value [DATA]",
    )

    response = client.post(
        f"/api/documents/flight-tests/{flight_test.id}/ai-analysis",
        json={"user_prompt": "Analyse takeoff performance"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["analysis_mode"] == "takeoff"
    assert body["capability_key"] == "takeoff"
    assert isinstance(body.get("retrieved_sources_snapshot"), list)
    assert len(body["retrieved_sources_snapshot"]) == 1
    assert body["retrieved_sources_snapshot"][0]["source_id"] == "S1"

    persisted_job = (
        db_session.query(AnalysisJob)
        .filter(AnalysisJob.id == body["analysis_job_id"])
        .first()
    )
    assert persisted_job is not None
    assert persisted_job.prompt_text.startswith("[analysis_mode:takeoff]")

    job_response = client.get(
        f"/api/documents/flight-tests/{flight_test.id}/ai-analysis/jobs/{persisted_job.id}",
        headers=auth_headers,
    )
    assert job_response.status_code == status.HTTP_200_OK
    reopened = job_response.json()
    assert reopened["analysis_mode"] == "takeoff"
    assert reopened["capability_key"] == "takeoff"
    assert not reopened["prompt_text"].startswith("[analysis_mode:")


def test_ai_analysis_landing_mode_returns_deterministic_landing_section_with_guardrails(
    client, db_session, test_user, auth_headers, monkeypatch
):
    flight_test = _create_flight_test_with_single_datapoint(db_session, test_user["id"])
    monkeypatch.setattr(documents_router, "_require_ai_packages", lambda: None)
    monkeypatch.setattr(documents_router.func, "stddev", lambda col: documents_router.func.avg(col))

    response = client.post(
        f"/api/documents/flight-tests/{flight_test.id}/ai-analysis",
        json={
            "analysis_mode": "landing",
            "user_prompt": "Assess landing performance boundaries",
        },
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["analysis_mode"] == "landing"
    assert body["capability_key"] == "landing"
    assert "Deterministic Calculation (Landing Data) [DATA]" in body["analysis"]
    assert "Weight-on-wheels parameter not found." in body["analysis"]
    assert "Routing outcome" in body["analysis"]


def test_ai_analysis_performance_mode_runs_mode_specific_deterministic_metrics(
    client, db_session, test_user, auth_headers, monkeypatch
):
    flight_test = FlightTest(
        test_name="Performance Deterministic Test",
        aircraft_type="F-16",
        created_by_id=test_user["id"],
    )
    db_session.add(flight_test)
    db_session.commit()
    db_session.refresh(flight_test)

    gs_param = TestParameter(name="GROUND SPEED", unit="kt")
    alt_param = TestParameter(name="PRESSURE ALTITUDE", unit="ft")
    db_session.add(gs_param)
    db_session.add(alt_param)
    db_session.commit()
    db_session.refresh(gs_param)
    db_session.refresh(alt_param)

    samples = [
        (datetime(2026, 4, 19, 10, 0, 0), 120.0, 5000.0),
        (datetime(2026, 4, 19, 10, 0, 5), 135.0, 5125.0),
        (datetime(2026, 4, 19, 10, 0, 10), 150.0, 5260.0),
    ]
    for ts, gs, alt in samples:
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=gs_param.id,
                timestamp=ts,
                value=gs,
            )
        )
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=alt_param.id,
                timestamp=ts,
                value=alt,
            )
        )
    db_session.commit()

    monkeypatch.setattr(documents_router, "_require_ai_packages", lambda: None)
    monkeypatch.setattr(documents_router.func, "stddev", lambda col: documents_router.func.avg(col))
    monkeypatch.setattr(
        documents_router,
        "_compute_takeoff_metrics",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("takeoff calculator must not run")),
    )

    response = client.post(
        f"/api/documents/flight-tests/{flight_test.id}/ai-analysis",
        json={"analysis_mode": "performance", "user_prompt": "Provide deterministic performance trends"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["analysis_mode"] == "performance"
    assert body["capability_key"] == "performance_general"
    assert "Deterministic Calculation (Performance Trends) [DATA]" in body["analysis"]
    assert "Mean climb rate" in body["analysis"]


def test_ai_analysis_buffet_mode_returns_screening_metrics(
    client, db_session, test_user, auth_headers, monkeypatch
):
    flight_test = FlightTest(
        test_name="Buffet Screening Test",
        aircraft_type="F-16",
        created_by_id=test_user["id"],
    )
    db_session.add(flight_test)
    db_session.commit()
    db_session.refresh(flight_test)

    vib_param = TestParameter(name="AIRFRAME VIBRATION X", unit="g")
    db_session.add(vib_param)
    db_session.commit()
    db_session.refresh(vib_param)

    values = [0.02, 0.03, 0.09, 0.12, 0.2, 0.18, 0.05, 0.04]
    for idx, value in enumerate(values):
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=vib_param.id,
                timestamp=datetime(2026, 4, 19, 11, 0, idx),
                value=value,
            )
        )
    db_session.commit()

    monkeypatch.setattr(documents_router, "_require_ai_packages", lambda: None)
    monkeypatch.setattr(documents_router.func, "stddev", lambda col: documents_router.func.avg(col))
    monkeypatch.setattr(
        documents_router,
        "_compute_takeoff_metrics",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("takeoff calculator must not run")),
    )

    response = client.post(
        f"/api/documents/flight-tests/{flight_test.id}/ai-analysis",
        json={"analysis_mode": "buffet_vibration", "user_prompt": "Screen vibration channels"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["analysis_mode"] == "buffet_vibration"
    assert body["capability_key"] == "buffet_vibration"
    assert "Deterministic Calculation (Buffet/Vibration Screening) [DATA]" in body["analysis"]
    assert "Channels screened" in body["analysis"]


def test_ai_analysis_general_mode_routes_without_takeoff_calculator(
    client, db_session, test_user, auth_headers, monkeypatch
):
    flight_test = _create_flight_test_with_single_datapoint(db_session, test_user["id"])

    def fake_retrieve_hybrid_sources(*, db, question, requested_top_k, owner_user_id):
        return (
            [
                {
                    "source_id": "S1",
                    "filename": "std.pdf",
                    "title": "General Standard",
                    "page_numbers": "9",
                    "section_title": "General",
                    "similarity": 0.97,
                    "text": "general guidance chunk",
                }
            ],
            "[S1] general guidance context",
        )

    class _FakeMessage:
        content = "General engineering guidance [S1]"

    class _FakeChoice:
        message = _FakeMessage()

    class _FakeCompletion:
        choices = [_FakeChoice()]

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            return _FakeCompletion()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    monkeypatch.setattr(documents_router, "_require_ai_packages", lambda: None)
    monkeypatch.setattr(documents_router, "_retrieve_hybrid_sources", fake_retrieve_hybrid_sources)
    monkeypatch.setattr(documents_router, "get_openai_client", lambda: _FakeClient())
    monkeypatch.setattr(documents_router.func, "stddev", lambda col: documents_router.func.avg(col))
    monkeypatch.setattr(
        documents_router,
        "_compute_takeoff_metrics",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("takeoff calculator must not run")),
    )

    response = client.post(
        f"/api/documents/flight-tests/{flight_test.id}/ai-analysis",
        json={"analysis_mode": "general", "user_prompt": "Provide a general engineering summary"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["analysis_mode"] == "general"
    assert body["capability_key"] == "general_standards_query"
    assert "Deterministic Takeoff Computation" not in body["analysis"]
    assert "analysis_mode=general" in body["analysis"]


def test_ai_analysis_rejects_unknown_analysis_mode(
    client, db_session, test_user, auth_headers, monkeypatch
):
    flight_test = _create_flight_test_with_single_datapoint(db_session, test_user["id"])
    monkeypatch.setattr(documents_router, "_require_ai_packages", lambda: None)
    monkeypatch.setattr(documents_router.func, "stddev", lambda col: documents_router.func.avg(col))

    response = client.post(
        f"/api/documents/flight-tests/{flight_test.id}/ai-analysis",
        json={"analysis_mode": "unknown_mode"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsupported analysis_mode 'unknown_mode'" in response.json()["detail"]

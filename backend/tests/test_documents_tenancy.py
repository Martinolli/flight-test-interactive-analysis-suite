"""Tests for document tenancy isolation on /api/documents endpoints."""

from datetime import datetime
import json

from fastapi import status

from app.auth import get_password_hash
from app.models import (
    AnalysisJob,
    DataPoint,
    DatasetVersion,
    Document,
    FlightTest,
    TestParameter,
    User,
)
from app.routers import documents as documents_router


def _create_user(db_session, email: str, username: str, password: str, *, is_superuser: bool = False) -> User:
    user = User(
        email=email,
        username=username,
        full_name=username,
        hashed_password=get_password_hash(password),
        is_active=True,
        is_superuser=is_superuser,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_document(db_session, owner_id: int, filename: str) -> Document:
    doc = Document(
        filename=filename,
        title=filename,
        status="ready",
        uploaded_by_id=owner_id,
        total_chunks=1,
        total_pages=1,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


def test_list_documents_scoped_to_current_user(client, db_session, test_user, auth_headers):
    """GET /api/documents should return only the caller's documents."""
    other_user = _create_user(
        db_session,
        email="other-docs@test.com",
        username="otherdocs",
        password="otherpass123",
    )
    own_doc = _create_document(db_session, test_user["id"], "own.pdf")
    _create_document(db_session, other_user.id, "other.pdf")

    response = client.get("/api/documents/", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    returned_ids = {item["id"] for item in payload}
    assert own_doc.id in returned_ids
    assert all(item["filename"] != "other.pdf" for item in payload)


def test_delete_document_cannot_delete_other_users_document(client, db_session, auth_headers):
    """DELETE /api/documents/{id} should not allow cross-user deletion."""
    owner = _create_user(
        db_session,
        email="owner@test.com",
        username="ownerdocs",
        password="ownerpass123",
    )
    foreign_doc = _create_document(db_session, owner.id, "foreign.pdf")

    response = client.delete(f"/api/documents/{foreign_doc.id}", headers=auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    still_exists = db_session.query(Document).filter(Document.id == foreign_doc.id).first()
    assert still_exists is not None


def test_query_documents_passes_current_user_scope(client, test_user, auth_headers, monkeypatch):
    """POST /api/documents/query should pass current user scope into retrieval."""
    captured = {}

    def fake_retrieve_hybrid_sources(*, db, question, requested_top_k, owner_user_id):
        captured["question"] = question
        captured["top_k"] = requested_top_k
        captured["owner_user_id"] = owner_user_id
        return (
            [
                {
                    "source_id": "S1",
                    "filename": "owned.pdf",
                    "title": "Owned Standard",
                    "page_numbers": "3",
                    "section_title": "Takeoff",
                    "similarity": 0.99,
                    "text": "source chunk",
                }
            ],
            "[S1] sample context",
        )

    class _FakeMessage:
        content = "Answer with citation [S1]\nUSED_SOURCES: S1"

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

    response = client.post(
        "/api/documents/query",
        json={"question": "test question", "top_k": 4},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert captured["owner_user_id"] == test_user["id"]
    body = response.json()
    assert body["sources"][0]["source_id"] == "S1"
    assert "text" not in body["sources"][0]
    assert body["answer_type"] == "technical_explanation"
    assert "coverage" in body
    assert "retrieval_metadata" in body
    assert isinstance(body.get("recommended_next_queries"), list)


def test_query_documents_empty_retrieval_returns_structured_response(client, auth_headers, monkeypatch):
    """Empty retrieval should still return full structured response contract."""

    def fake_retrieve_hybrid_sources(*, db, question, requested_top_k, owner_user_id):
        return [], ""

    monkeypatch.setattr(documents_router, "_require_ai_packages", lambda: None)
    monkeypatch.setattr(documents_router, "_retrieve_hybrid_sources", fake_retrieve_hybrid_sources)

    response = client.post(
        "/api/documents/query",
        json={"question": "test no sources", "top_k": 4},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["answer_type"] == "insufficient_evidence"
    assert body["sources"] == []
    assert "coverage" in body
    assert body["coverage"]["retrieved_sources_count"] == 0
    assert "retrieval_metadata" in body


def test_ai_analysis_persists_analysis_job_and_returns_job_id(
    client, db_session, test_user, auth_headers, monkeypatch
):
    """POST ai-analysis should persist immutable analysis artifact and return job metadata."""

    flight_test = FlightTest(
        test_name="AI Job Test",
        aircraft_type="F-16",
        created_by_id=test_user["id"],
    )
    db_session.add(flight_test)
    db_session.commit()
    db_session.refresh(flight_test)

    parameter = TestParameter(name="TEST_SPEED", unit="kt")
    db_session.add(parameter)
    db_session.commit()
    db_session.refresh(parameter)

    db_session.add(
        DataPoint(
            flight_test_id=flight_test.id,
            parameter_id=parameter.id,
            timestamp=datetime(2026, 4, 11, 10, 0, 0),
            value=100.0,
        )
    )
    db_session.commit()

    def fake_retrieve_hybrid_sources(*, db, question, requested_top_k, owner_user_id):
        return (
            [
                {
                    "source_id": "S1",
                    "filename": "std.pdf",
                    "title": "Standard",
                    "page_numbers": "12",
                    "section_title": "Section A",
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
        lambda db, flight_test_id, dataset_version_id=None: {
            "distance_ft": 1234.5,
            "distance_m": 376.3,
            "dataset_version_id": dataset_version_id,
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
    assert body["analysis_job_id"] > 0
    assert body["model_name"]
    assert body["output_sha256"]
    assert body["retrieved_source_ids"] == ["S1"]

    persisted_job = (
        db_session.query(AnalysisJob)
        .filter(AnalysisJob.id == body["analysis_job_id"])
        .first()
    )
    assert persisted_job is not None
    assert persisted_job.flight_test_id == flight_test.id
    assert persisted_job.created_by_id == test_user["id"]
    assert persisted_job.output_sha256 == body["output_sha256"]
    assert persisted_job.parameters_analysed == 1
    stats_snapshot = json.loads(persisted_job.parameter_stats_snapshot_json)
    assert len(stats_snapshot) == 1
    assert stats_snapshot[0]["name"] == "TEST_SPEED"
    assert stats_snapshot[0]["sample_count"] == 1
    assert stats_snapshot[0]["avg_val"] == 100.0


def test_ai_analysis_uses_requested_dataset_version_and_persists_dataset_version_id(
    client, db_session, test_user, auth_headers, monkeypatch
):
    flight_test = FlightTest(
        test_name="AI Dataset Version Test",
        aircraft_type="F-16",
        created_by_id=test_user["id"],
    )
    db_session.add(flight_test)
    db_session.commit()
    db_session.refresh(flight_test)

    v1 = DatasetVersion(
        flight_test_id=flight_test.id,
        version_number=1,
        label="v1",
        status="success",
        created_by_id=test_user["id"],
    )
    v2 = DatasetVersion(
        flight_test_id=flight_test.id,
        version_number=2,
        label="v2",
        status="success",
        created_by_id=test_user["id"],
    )
    db_session.add(v1)
    db_session.add(v2)
    db_session.commit()
    db_session.refresh(v1)
    db_session.refresh(v2)
    flight_test.active_dataset_version_id = v2.id
    db_session.add(flight_test)
    db_session.commit()

    parameter = TestParameter(name="TEST_SPEED_DATASET", unit="kt")
    db_session.add(parameter)
    db_session.commit()
    db_session.refresh(parameter)

    db_session.add(
        DataPoint(
            flight_test_id=flight_test.id,
            dataset_version_id=v1.id,
            parameter_id=parameter.id,
            timestamp=datetime(2026, 4, 11, 10, 0, 0),
            value=111.0,
        )
    )
    db_session.add(
        DataPoint(
            flight_test_id=flight_test.id,
            dataset_version_id=v2.id,
            parameter_id=parameter.id,
            timestamp=datetime(2026, 4, 11, 10, 0, 1),
            value=222.0,
        )
    )
    db_session.commit()

    def fake_retrieve_hybrid_sources(*, db, question, requested_top_k, owner_user_id):
        return (
            [
                {
                    "source_id": "S1",
                    "filename": "std.pdf",
                    "title": "Standard",
                    "page_numbers": "12",
                    "section_title": "Section A",
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
        lambda db, flight_test_id, dataset_version_id=None: {
            "distance_ft": 1234.5,
            "distance_m": 376.3,
            "dataset_version_id": dataset_version_id,
        },
    )
    monkeypatch.setattr(
        documents_router,
        "_build_deterministic_takeoff_section",
        lambda metrics: "### Deterministic Takeoff Computation\n- value [DATA]",
    )

    response = client.post(
        f"/api/documents/flight-tests/{flight_test.id}/ai-analysis",
        json={
            "user_prompt": "Analyse dataset specific performance",
            "dataset_version_id": v1.id,
        },
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["dataset_version_id"] == v1.id

    persisted_job = (
        db_session.query(AnalysisJob)
        .filter(AnalysisJob.id == payload["analysis_job_id"])
        .first()
    )
    assert persisted_job is not None
    assert persisted_job.dataset_version_id == v1.id
    stats_snapshot = json.loads(persisted_job.parameter_stats_snapshot_json)
    assert stats_snapshot[0]["avg_val"] == 111.0


def test_get_ai_analysis_job_is_tenant_scoped(client, db_session, test_user, auth_headers):
    """GET saved ai-analysis job should be denied for non-owner regular users."""

    owner = User(
        email="owner-ai@test.com",
        username="ownerai",
        full_name="Owner AI",
        hashed_password=get_password_hash("ownerpass123"),
        is_active=True,
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    flight_test = FlightTest(
        test_name="Tenant Scope Job",
        aircraft_type="F-18",
        created_by_id=owner.id,
    )
    db_session.add(flight_test)
    db_session.commit()
    db_session.refresh(flight_test)

    analysis_job = AnalysisJob(
        flight_test_id=flight_test.id,
        created_by_id=owner.id,
        status="completed",
        model_name="gpt-4o-mini",
        model_version=None,
        prompt_text="prompt",
        retrieved_source_ids_json='["S1"]',
        retrieved_sources_snapshot_json="[]",
        output_sha256="a" * 64,
        analysis_text="analysis text",
    )
    db_session.add(analysis_job)
    db_session.commit()
    db_session.refresh(analysis_job)

    response = client.get(
        f"/api/documents/flight-tests/{flight_test.id}/ai-analysis/jobs/{analysis_job.id}",
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_ai_analysis_job_returns_persisted_snapshot_not_live_recompute(
    client, db_session, test_user, auth_headers
):
    flight_test = FlightTest(
        test_name="Snapshot Persisted",
        aircraft_type="F-16",
        created_by_id=test_user["id"],
    )
    db_session.add(flight_test)
    db_session.commit()
    db_session.refresh(flight_test)

    # Persisted job says 2 parameters with predefined snapshot values.
    persisted_snapshot = [
        {
            "name": "PARAM_A",
            "unit": "kt",
            "min_val": 10.0,
            "max_val": 20.0,
            "avg_val": 15.0,
            "std_val": 5.0,
            "sample_count": 2,
        }
    ]
    analysis_job = AnalysisJob(
        flight_test_id=flight_test.id,
        created_by_id=test_user["id"],
        status="completed",
        model_name="gpt-4o-mini",
        model_version=None,
        parameters_analysed=1,
        parameter_stats_snapshot_json=json.dumps(persisted_snapshot),
        prompt_text="prompt",
        retrieved_source_ids_json='["S1"]',
        retrieved_sources_snapshot_json="[]",
        output_sha256="c" * 64,
        analysis_text="analysis text",
    )
    db_session.add(analysis_job)
    db_session.commit()
    db_session.refresh(analysis_job)

    # Add mutable datapoints that do not match persisted snapshot.
    param_live = TestParameter(name="LIVE_PARAM_001", unit="g")
    db_session.add(param_live)
    db_session.commit()
    db_session.refresh(param_live)
    db_session.add(
        DataPoint(
            flight_test_id=flight_test.id,
            parameter_id=param_live.id,
            timestamp=datetime(2026, 4, 11, 12, 0, 0),
            value=999.0,
        )
    )
    db_session.commit()

    response = client.get(
        f"/api/documents/flight-tests/{flight_test.id}/ai-analysis/jobs/{analysis_job.id}",
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["parameters_analysed"] == 1
    assert body["parameter_stats_snapshot"] == persisted_snapshot

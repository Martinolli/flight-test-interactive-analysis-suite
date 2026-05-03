"""
Focused tests for FRAT / mission-risk workflow (P2.5).
"""

from fastapi import status

from app.models import AnalysisJob, DatasetVersion, FlightTest, FratAssessment, User


def _create_flight_test(client, auth_headers, name: str = "FRAT Test Flight") -> int:
    response = client.post(
        "/api/flight-tests/",
        json={
            "test_name": name,
            "aircraft_type": "F-16",
            "test_date": "2026-04-24",
            "description": "FRAT workflow test flight",
        },
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["id"]


def test_frat_create_and_list_assessments(client, auth_headers):
    flight_test_id = _create_flight_test(client, auth_headers, "FRAT Create/List")

    create = client.post(
        "/api/frat/assessments",
        json={
            "flight_test_id": flight_test_id,
            "assessment_name": "Mission Risk Draft A",
            "analysis_job_ids": [],
            "inputs": {
                "requested_decision_authority": "advisory",
                "categories": {
                    "mission_profile": {"score": 6, "notes": "New profile"},
                    "weather_environment": {"score": 4, "notes": "Moderate wind"},
                },
            },
        },
        headers=auth_headers,
    )
    assert create.status_code == status.HTTP_201_CREATED, create.text
    payload = create.json()
    assert payload["status"] == "draft"
    assert payload["assessment_name"] == "Mission Risk Draft A"
    assert payload["input_snapshot"]["categories"]["mission_profile"]["score"] == 6

    listed = client.get(
        f"/api/frat/flight-tests/{flight_test_id}/assessments",
        headers=auth_headers,
    )
    assert listed.status_code == status.HTTP_200_OK, listed.text
    items = listed.json()
    assert len(items) == 1
    assert items[0]["id"] == payload["id"]
    assert items[0]["assessment_name"] == "Mission Risk Draft A"


def test_frat_hard_stop_overrides_scoring_and_blocks_approval(client, auth_headers):
    flight_test_id = _create_flight_test(client, auth_headers, "FRAT Hard Stop")

    create = client.post(
        "/api/frat/assessments",
        json={
            "flight_test_id": flight_test_id,
            "assessment_name": "Hard Stop Assessment",
            "inputs": {
                "requested_decision_authority": "advisory",
                "critical_flags": {"mandatory_data_missing": True},
                "categories": {
                    "mission_profile": {"score": 2},
                    "weather_environment": {"score": 2},
                    "runway_operational": {"score": 2},
                    "aircraft_system_status": {"score": 2},
                    "crew_readiness": {"score": 2},
                },
            },
        },
        headers=auth_headers,
    )
    assessment_id = create.json()["id"]

    scored = client.post(
        f"/api/frat/assessments/{assessment_id}/score",
        headers=auth_headers,
    )
    assert scored.status_code == status.HTTP_200_OK, scored.text
    score_payload = scored.json()
    assert score_payload["status"] == "needs_review"
    assert score_payload["score_snapshot"]["hard_stop_triggered"] is True
    assert score_payload["score_snapshot"]["recommendation"] == "no_go"

    approve = client.post(
        f"/api/frat/assessments/{assessment_id}/approve",
        json={"notes": "Attempt should fail"},
        headers=auth_headers,
    )
    assert approve.status_code == status.HTTP_400_BAD_REQUEST


def test_frat_approve_finalize_and_immutability(client, auth_headers):
    flight_test_id = _create_flight_test(client, auth_headers, "FRAT Finalize")

    create = client.post(
        "/api/frat/assessments",
        json={
            "flight_test_id": flight_test_id,
            "assessment_name": "Finalize Candidate",
            "inputs": {
                "requested_decision_authority": "advisory",
                "categories": {
                    "mission_profile": {"score": 1},
                    "weather_environment": {"score": 1},
                    "runway_operational": {"score": 1},
                    "aircraft_system_status": {"score": 1},
                    "crew_readiness": {"score": 1},
                },
            },
        },
        headers=auth_headers,
    )
    assert create.status_code == status.HTTP_201_CREATED, create.text
    assessment_id = create.json()["id"]

    scored = client.post(
        f"/api/frat/assessments/{assessment_id}/score",
        headers=auth_headers,
    )
    assert scored.status_code == status.HTTP_200_OK, scored.text
    assert scored.json()["status"] == "scored"
    assert scored.json()["score_snapshot"]["recommendation"] == "go"

    approved = client.post(
        f"/api/frat/assessments/{assessment_id}/approve",
        json={"notes": "Approved for mission rehearsal"},
        headers=auth_headers,
    )
    assert approved.status_code == status.HTTP_200_OK, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by_id"] is not None

    finalized = client.post(
        f"/api/frat/assessments/{assessment_id}/finalize",
        json={"notes": "Finalized snapshot"},
        headers=auth_headers,
    )
    assert finalized.status_code == status.HTTP_200_OK, finalized.text
    assert finalized.json()["status"] == "finalized"
    assert finalized.json()["finalized_by_id"] is not None

    mutate_after_finalize = client.put(
        f"/api/frat/assessments/{assessment_id}",
        json={"assessment_name": "Should not change"},
        headers=auth_headers,
    )
    assert mutate_after_finalize.status_code == status.HTTP_400_BAD_REQUEST
    assert "immutable" in mutate_after_finalize.json()["detail"].lower()


def test_frat_analysis_job_reference_endpoint_decodes_analysis_mode(
    client, test_user, auth_headers, db_session
):
    flight_test = FlightTest(
        test_name="FRAT Analysis Ref Flight",
        aircraft_type="F-16",
        created_by_id=test_user["id"],
    )
    db_session.add(flight_test)
    db_session.flush()

    dataset = DatasetVersion(
        flight_test_id=flight_test.id,
        version_number=1,
        label="v1",
        status="success",
        row_count=100,
        data_points_count=1000,
        created_by_id=test_user["id"],
    )
    db_session.add(dataset)
    db_session.flush()

    analysis = AnalysisJob(
        flight_test_id=flight_test.id,
        created_by_id=test_user["id"],
        dataset_version_id=dataset.id,
        status="completed",
        model_name="gpt-4o",
        model_version="2026-04-01",
        parameters_analysed=3,
        parameter_stats_snapshot_json="[]",
        analysis_controls_json="{}",
        prompt_text="[analysis_mode:landing] Assess landing rollout quality",
        retrieved_source_ids_json="[]",
        retrieved_sources_snapshot_json="[]",
        output_sha256="c" * 64,
        analysis_text="Landing deterministic summary.",
    )
    db_session.add(analysis)
    db_session.commit()

    response = client.get(
        f"/api/frat/flight-tests/{flight_test.id}/analysis-jobs",
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == analysis.id
    assert items[0]["analysis_mode"] == "landing"
    assert items[0]["dataset_version_id"] == dataset.id


def test_frat_delete_flight_test_removes_assessments(client, test_user, auth_headers, db_session):
    owner = db_session.query(User).filter(User.id == test_user["id"]).first()
    assert owner is not None

    flight_test = FlightTest(
        test_name="FRAT Delete Cascade Flight",
        aircraft_type="F-16",
        created_by_id=owner.id,
    )
    db_session.add(flight_test)
    db_session.flush()

    assessment = FratAssessment(
        flight_test_id=flight_test.id,
        created_by_id=owner.id,
        status="draft",
        assessment_name="Delete Me",
        analysis_reference_ids_json="[]",
        input_snapshot_json="{}",
        score_snapshot_json="{}",
        hard_stop_snapshot_json="[]",
        finalized_snapshot_json="{}",
    )
    db_session.add(assessment)
    db_session.commit()

    delete = client.delete(f"/api/flight-tests/{flight_test.id}", headers=auth_headers)
    assert delete.status_code == status.HTTP_204_NO_CONTENT, delete.text

    remaining = (
        db_session.query(FratAssessment)
        .filter(FratAssessment.flight_test_id == flight_test.id)
        .count()
    )
    assert remaining == 0

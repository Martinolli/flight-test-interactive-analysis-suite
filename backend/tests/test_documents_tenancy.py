"""Tests for document tenancy isolation on /api/documents endpoints."""

from fastapi import status

from app.auth import get_password_hash
from app.models import Document, User
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

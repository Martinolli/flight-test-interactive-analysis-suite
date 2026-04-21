"""Tests for retrieval metadata inference and mode-aware ranking helpers."""

from app.retrieval_metadata import (
    build_retrieval_mode_profile,
    derive_document_retrieval_metadata,
    rerank_candidates_with_metadata,
)


def test_derive_document_retrieval_metadata_infers_authority_and_tags():
    metadata = derive_document_retrieval_metadata(
        filename="MIL-HDBK-1763_takeoff_revB.pdf",
        title="Aircraft Stores Compatibility Handbook - Takeoff and Landing",
        doc_type="handbook",
        description="Includes takeoff and landing compatibility procedures.",
    )
    assert metadata["authority_type"] == "handbook"
    assert "takeoff" in metadata["domain_tags"]
    assert "landing" in metadata["domain_tags"]
    assert "takeoff" in metadata["capability_tags"]
    assert metadata["source_priority"] >= 60


def test_derive_document_retrieval_metadata_falls_back_safely_for_generic_docs():
    metadata = derive_document_retrieval_metadata(
        filename="notes.pdf",
        title="General Flight Notes",
        doc_type=None,
        description=None,
    )
    assert metadata["authority_type"] in {
        "regulation",
        "advisory",
        "handbook",
        "internal_reference",
        "derived_note",
    }
    assert len(metadata["domain_tags"]) >= 1
    assert len(metadata["capability_tags"]) >= 1


def test_mode_aware_reranking_prefers_mode_matching_high_authority_sources():
    profile = build_retrieval_mode_profile("takeoff", "takeoff")
    candidates = [
        {
            "id": 1,
            "base_score": 0.4,
            "row": {"id": 1},
            "metadata": {
                "authority_type": "handbook",
                "domain_tags": ["landing"],
                "capability_tags": ["landing"],
                "source_priority": 70,
            },
        },
        {
            "id": 2,
            "base_score": 0.35,
            "row": {"id": 2},
            "metadata": {
                "authority_type": "regulation",
                "domain_tags": ["takeoff", "performance"],
                "capability_tags": ["takeoff"],
                "source_priority": 100,
            },
        },
    ]
    ranked, debug = rerank_candidates_with_metadata(candidates=candidates, profile=profile)
    assert ranked[0]["id"] == 2
    assert debug["mode_filter_enabled"] is True
    assert debug["mode_filter_matched_chunks"] >= 1


def test_mode_aware_reranking_falls_back_when_metadata_is_sparse():
    profile = build_retrieval_mode_profile("landing", "landing")
    candidates = [
        {"id": 1, "base_score": 0.5, "row": {"id": 1}, "metadata": {"domain_tags": [], "capability_tags": []}},
        {"id": 2, "base_score": 0.45, "row": {"id": 2}, "metadata": {"domain_tags": [], "capability_tags": []}},
    ]
    ranked, debug = rerank_candidates_with_metadata(candidates=candidates, profile=profile)
    assert len(ranked) == 2
    assert debug["mode_filter_enabled"] is True
    assert debug["mode_filter_fallback_used"] is True
    assert debug["metadata_coverage_ratio"] == 0.0


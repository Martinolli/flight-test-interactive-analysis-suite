"""
Retrieval metadata schema, inference, and mode-aware ranking helpers.

P2.3 goals:
- persist structured metadata for document retrieval
- derive sane defaults for legacy/unclassified docs
- enable explainable mode-aware soft filtering/ranking with safe fallback
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_AUTHORITY_TYPE = "handbook"
DEFAULT_SOURCE_PRIORITY = 60
VALID_AUTHORITY_TYPES = {
    "regulation",
    "advisory",
    "handbook",
    "internal_reference",
    "derived_note",
}

AUTHORITY_PRIORITY_BASE = {
    "regulation": 100,
    "advisory": 85,
    "handbook": 75,
    "internal_reference": 60,
    "derived_note": 40,
}

AUTHORITY_RANK_BONUS = {
    "regulation": 0.09,
    "advisory": 0.06,
    "handbook": 0.04,
    "internal_reference": 0.02,
    "derived_note": 0.0,
}

DOMAIN_KEYWORD_MAP: Dict[str, Sequence[str]] = {
    "takeoff": ("takeoff", "rotation", "liftoff", "ground roll"),
    "landing": ("landing", "touchdown", "rollout", "flare"),
    "performance": ("performance", "climb", "cruise", "acceleration", "deceleration"),
    "handling_qualities": ("handling", "flying qualities", "controllability", "stability"),
    "buffet_vibration": ("buffet", "vibration", "loads", "accelerometer"),
    "flutter": ("flutter", "aeroelastic", "modal", "eigenvalue"),
    "systems": ("systems", "engine", "propulsion", "electrical", "hydraulic", "avionics"),
    "risk": ("risk", "hazard", "frat", "assessment", "mitigation"),
}

DOMAIN_TO_CAPABILITY = {
    "takeoff": "takeoff",
    "landing": "landing",
    "performance": "performance_general",
    "handling_qualities": "handling_qualities",
    "buffet_vibration": "buffet_vibration",
    "flutter": "flutter_support",
    "systems": "systems_monitoring",
    "risk": "risk_assessment",
}

MODE_DOMAIN_PREFERENCES: Dict[str, Sequence[str]] = {
    "takeoff": ("takeoff", "performance"),
    "landing": ("landing", "performance"),
    "performance": ("performance", "takeoff", "landing"),
    "handling_qualities": ("handling_qualities", "performance"),
    "buffet_vibration": ("buffet_vibration", "performance", "flutter"),
    "flutter": ("flutter", "buffet_vibration"),
    "propulsion_systems": ("systems", "performance"),
    "electrical_systems": ("systems",),
    "general": (),
}

MODE_CAPABILITY_PREFERENCES: Dict[str, Sequence[str]] = {
    "takeoff": ("takeoff", "performance_general"),
    "landing": ("landing", "performance_general"),
    "performance": ("performance_general", "takeoff", "landing"),
    "handling_qualities": ("handling_qualities",),
    "buffet_vibration": ("buffet_vibration", "flutter_support"),
    "flutter": ("flutter_support", "buffet_vibration"),
    "propulsion_systems": ("systems_monitoring", "performance_general"),
    "electrical_systems": ("systems_monitoring",),
    "general": (),
}


def _normalize_tag(tag: str) -> str:
    normalized = (tag or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized == "vibration":
        return "buffet_vibration"
    if normalized == "loads":
        return "buffet_vibration"
    if normalized == "system":
        return "systems"
    return normalized


def normalize_tags(tags: Optional[Iterable[str]]) -> List[str]:
    if not tags:
        return []
    result: List[str] = []
    for raw in tags:
        normalized = _normalize_tag(str(raw))
        if not normalized:
            continue
        if normalized not in result:
            result.append(normalized)
    return result


def _safe_json_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return normalize_tags([str(item) for item in raw if item is not None])
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return normalize_tags([str(item) for item in parsed if item is not None])
        except Exception:
            # Comma-separated fallback.
            return normalize_tags([piece for piece in text.split(",") if piece.strip()])
    return []


def normalize_authority_type(authority_type: Optional[str]) -> str:
    value = (authority_type or "").strip().lower()
    if value not in VALID_AUTHORITY_TYPES:
        return DEFAULT_AUTHORITY_TYPE
    return value


def coerce_source_priority(priority: Optional[Any], authority_type: str) -> int:
    if priority is not None:
        try:
            value = int(priority)
            return max(0, min(100, value))
        except Exception:
            pass
    return AUTHORITY_PRIORITY_BASE.get(authority_type, DEFAULT_SOURCE_PRIORITY)


def _infer_authority_type(text_blob: str, doc_type: Optional[str]) -> str:
    candidate = (doc_type or "").strip().lower()
    if candidate in VALID_AUTHORITY_TYPES:
        return candidate
    if any(token in text_blob for token in ("far ", "cs-25", "regulation", "mil-std", "mil-")):
        return "regulation"
    if any(token in text_blob for token in ("advisory", "ac ", "circular")):
        return "advisory"
    if any(token in text_blob for token in ("handbook", "hdbk", "manual", "guide")):
        return "handbook"
    if any(token in text_blob for token in ("internal", "company", "org procedure")):
        return "internal_reference"
    if any(token in text_blob for token in ("derived", "summary note", "analysis note")):
        return "derived_note"
    return DEFAULT_AUTHORITY_TYPE


def _infer_document_revision(text_blob: str) -> Optional[str]:
    rev_match = re.search(r"\brev(?:ision)?[\s\-_]*([a-z0-9\.\-]+)\b", text_blob, flags=re.IGNORECASE)
    if rev_match:
        return f"rev {rev_match.group(1)}"
    date_match = re.search(r"\b(20\d{2}[-_/]\d{2}[-_/]\d{2})\b", text_blob)
    if date_match:
        return date_match.group(1)
    year_match = re.search(r"\b(20\d{2})\b", text_blob)
    if year_match:
        return year_match.group(1)
    return None


def _infer_domain_tags(text_blob: str) -> List[str]:
    tags: List[str] = []
    for domain_tag, keywords in DOMAIN_KEYWORD_MAP.items():
        if any(keyword in text_blob for keyword in keywords):
            tags.append(domain_tag)
    if not tags:
        tags.append("performance")
    return normalize_tags(tags)


def _infer_capability_tags(domain_tags: Iterable[str]) -> List[str]:
    capability_tags: List[str] = []
    for domain_tag in normalize_tags(domain_tags):
        capability = DOMAIN_TO_CAPABILITY.get(domain_tag)
        if capability and capability not in capability_tags:
            capability_tags.append(capability)
    if not capability_tags:
        capability_tags.append("general_standards_query")
    return capability_tags


def _infer_aircraft_scope(text_blob: str) -> Optional[str]:
    match = re.search(r"\b([A-Z]{1,2}-\d{1,3}[A-Z]?)\b", text_blob)
    return match.group(1) if match else None


def _infer_system_scope(text_blob: str) -> Optional[str]:
    if any(token in text_blob for token in ("electrical", "generator", "battery", "bus")):
        return "electrical"
    if any(token in text_blob for token in ("engine", "propulsion", "thrust", "fuel")):
        return "propulsion"
    if any(token in text_blob for token in ("hydraulic", "actuator")):
        return "hydraulic"
    if any(token in text_blob for token in ("avionics", "navigation", "communication")):
        return "avionics"
    return None


def derive_document_retrieval_metadata(
    *,
    filename: str,
    title: Optional[str],
    doc_type: Optional[str],
    description: Optional[str],
    authority_type: Optional[str] = None,
    document_revision: Optional[str] = None,
    domain_tags: Optional[Iterable[str]] = None,
    capability_tags: Optional[Iterable[str]] = None,
    aircraft_scope: Optional[str] = None,
    system_scope: Optional[str] = None,
    source_priority: Optional[int] = None,
) -> Dict[str, Any]:
    text_blob = " ".join(
        [
            (filename or ""),
            (title or ""),
            (doc_type or ""),
            (description or ""),
        ]
    ).lower()
    resolved_authority = normalize_authority_type(authority_type or _infer_authority_type(text_blob, doc_type))
    resolved_domain_tags = normalize_tags(domain_tags) or _infer_domain_tags(text_blob)
    resolved_capability_tags = normalize_tags(capability_tags) or _infer_capability_tags(resolved_domain_tags)
    resolved_revision = (document_revision or "").strip() or _infer_document_revision(text_blob)
    resolved_aircraft_scope = (aircraft_scope or "").strip() or _infer_aircraft_scope(" ".join([filename or "", title or ""]))
    resolved_system_scope = (system_scope or "").strip() or _infer_system_scope(text_blob)
    resolved_priority = coerce_source_priority(source_priority, resolved_authority)

    return {
        "authority_type": resolved_authority,
        "document_revision": resolved_revision,
        "domain_tags": resolved_domain_tags,
        "capability_tags": resolved_capability_tags,
        "aircraft_scope": resolved_aircraft_scope or None,
        "system_scope": resolved_system_scope or None,
        "source_priority": resolved_priority,
    }


@dataclass(frozen=True)
class RetrievalModeProfile:
    mode_key: str
    capability_key: Optional[str]
    preferred_domain_tags: Tuple[str, ...]
    preferred_capability_tags: Tuple[str, ...]
    is_general: bool = False


def build_retrieval_mode_profile(mode_key: Optional[str], capability_key: Optional[str] = None) -> RetrievalModeProfile:
    normalized_mode = (mode_key or "general").strip().lower()
    if normalized_mode not in MODE_DOMAIN_PREFERENCES:
        normalized_mode = "general"
    preferred_domain_tags = tuple(normalize_tags(MODE_DOMAIN_PREFERENCES.get(normalized_mode, ())))
    preferred_capability_tags = tuple(
        normalize_tags(MODE_CAPABILITY_PREFERENCES.get(normalized_mode, ()))
    )
    if capability_key:
        normalized_capability = capability_key.strip().lower()
        if normalized_capability and normalized_capability not in preferred_capability_tags:
            preferred_capability_tags = tuple([*preferred_capability_tags, normalized_capability])
    return RetrievalModeProfile(
        mode_key=normalized_mode,
        capability_key=capability_key,
        preferred_domain_tags=preferred_domain_tags,
        preferred_capability_tags=preferred_capability_tags,
        is_general=(normalized_mode == "general"),
    )


def extract_row_retrieval_metadata(row: Any) -> Dict[str, Any]:
    authority_type = normalize_authority_type(getattr(row, "authority_type", None))
    document_revision = getattr(row, "document_revision", None)
    domain_tags = _safe_json_list(getattr(row, "domain_tags_json", None))
    capability_tags = _safe_json_list(getattr(row, "capability_tags_json", None))
    aircraft_scope = (getattr(row, "aircraft_scope", None) or None)
    system_scope = (getattr(row, "system_scope", None) or None)
    source_priority = coerce_source_priority(getattr(row, "source_priority", None), authority_type)
    return {
        "authority_type": authority_type,
        "document_revision": document_revision,
        "domain_tags": domain_tags,
        "capability_tags": capability_tags,
        "aircraft_scope": aircraft_scope,
        "system_scope": system_scope,
        "source_priority": source_priority,
    }


def _revision_recency_bonus(document_revision: Optional[str]) -> float:
    if not document_revision:
        return 0.0
    year_match = re.search(r"(20\d{2})", document_revision)
    if not year_match:
        return 0.0
    year = int(year_match.group(1))
    if year < 2000:
        return 0.0
    # Bounded soft bonus.
    return min(0.02, max(0.0, (year - 2000) * 0.0008))


def metadata_rank_signal(
    metadata: Dict[str, Any],
    profile: RetrievalModeProfile,
) -> Dict[str, Any]:
    domain_tags = set(normalize_tags(metadata.get("domain_tags")))
    capability_tags = set(normalize_tags(metadata.get("capability_tags")))
    has_metadata_tags = bool(domain_tags or capability_tags)
    mode_domain_match = bool(domain_tags.intersection(profile.preferred_domain_tags))
    mode_capability_match = bool(capability_tags.intersection(profile.preferred_capability_tags))

    bonus = 0.0
    authority_type = normalize_authority_type(metadata.get("authority_type"))
    bonus += AUTHORITY_RANK_BONUS.get(authority_type, 0.0)
    source_priority = coerce_source_priority(metadata.get("source_priority"), authority_type)
    bonus += (source_priority / 100.0) * 0.04
    bonus += _revision_recency_bonus(metadata.get("document_revision"))

    if not profile.is_general:
        if mode_domain_match:
            bonus += 0.07
        if mode_capability_match:
            bonus += 0.1
        if mode_domain_match and mode_capability_match:
            bonus += 0.03
        if has_metadata_tags and not (mode_domain_match or mode_capability_match):
            bonus -= 0.02

    return {
        "bonus": round(bonus, 6),
        "mode_domain_match": mode_domain_match,
        "mode_capability_match": mode_capability_match,
        "mode_match": mode_domain_match or mode_capability_match,
        "has_metadata_tags": has_metadata_tags,
        "authority_type": authority_type,
        "source_priority": source_priority,
    }


def rerank_candidates_with_metadata(
    *,
    candidates: Sequence[Dict[str, Any]],
    profile: RetrievalModeProfile,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    metadata_covered = 0
    mode_matches = 0

    for item in candidates:
        metadata = item.get("metadata") or {}
        signal = metadata_rank_signal(metadata, profile)
        final_score = float(item.get("base_score", 0.0)) + float(signal["bonus"])
        if signal["has_metadata_tags"]:
            metadata_covered += 1
        if signal["mode_match"]:
            mode_matches += 1
        enriched.append(
            {
                **item,
                "metadata": metadata,
                "metadata_signal": signal,
                "final_score": final_score,
            }
        )

    ranked = sorted(enriched, key=lambda item: item["final_score"], reverse=True)
    mode_filter_enabled = not profile.is_general
    minimum_matches_for_soft_filter = 2
    mode_filter_fallback_used = False

    if mode_filter_enabled:
        matched = [item for item in ranked if item["metadata_signal"]["mode_match"]]
        if len(matched) >= minimum_matches_for_soft_filter:
            unmatched = [item for item in ranked if not item["metadata_signal"]["mode_match"]]
            ranked = matched + unmatched
        else:
            mode_filter_fallback_used = True

    debug = {
        "analysis_mode": profile.mode_key,
        "capability_key": profile.capability_key,
        "mode_filter_enabled": mode_filter_enabled,
        "mode_filter_matched_chunks": mode_matches,
        "mode_filter_fallback_used": mode_filter_fallback_used,
        "metadata_coverage_ratio": round(
            (metadata_covered / len(enriched)) if enriched else 0.0,
            3,
        ),
        "authority_weighting_enabled": True,
    }
    return ranked, debug


"""
FTIAS analysis-mode registry and resolver.

P2.1 goal:
- define explicit mode keys and metadata
- map mode keys to capability-catalog entries
- provide stable routing resolution for analysis requests
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.capabilities import (
    CapabilityAuthority,
    CapabilityImplementationStatus,
    get_capability_definition,
)


@dataclass(frozen=True)
class AnalysisModeDefinition:
    key: str
    label: str
    description: str
    capability_key: str
    default: bool = False


_ANALYSIS_MODES: Dict[str, AnalysisModeDefinition] = {
    "takeoff": AnalysisModeDefinition(
        key="takeoff",
        label="Takeoff",
        description="Deterministic takeoff ground-roll/liftoff analysis with standards cross-check.",
        capability_key="takeoff",
        default=True,
    ),
    "landing": AnalysisModeDefinition(
        key="landing",
        label="Landing",
        description="Landing-performance analysis routing (planned/partial behavior in current release).",
        capability_key="landing",
    ),
    "performance": AnalysisModeDefinition(
        key="performance",
        label="Performance",
        description="General performance analysis routing.",
        capability_key="performance_general",
    ),
    "handling_qualities": AnalysisModeDefinition(
        key="handling_qualities",
        label="Handling Qualities",
        description="Handling qualities mode routing.",
        capability_key="handling_qualities",
    ),
    "buffet_vibration": AnalysisModeDefinition(
        key="buffet_vibration",
        label="Buffet and Vibration",
        description="Buffet/vibration mode routing.",
        capability_key="buffet_vibration",
    ),
    "flutter": AnalysisModeDefinition(
        key="flutter",
        label="Flutter",
        description="Flutter-support mode routing.",
        capability_key="flutter_support",
    ),
    "propulsion_systems": AnalysisModeDefinition(
        key="propulsion_systems",
        label="Propulsion Systems",
        description="Propulsion-systems analysis routed through systems-monitoring capability.",
        capability_key="systems_monitoring",
    ),
    "electrical_systems": AnalysisModeDefinition(
        key="electrical_systems",
        label="Electrical Systems",
        description="Electrical-systems analysis routed through systems-monitoring capability.",
        capability_key="systems_monitoring",
    ),
    "general": AnalysisModeDefinition(
        key="general",
        label="General",
        description="General technical interpretation and standards guidance mode.",
        capability_key="general_standards_query",
    ),
}


def list_analysis_modes() -> List[AnalysisModeDefinition]:
    return [_ANALYSIS_MODES[key] for key in sorted(_ANALYSIS_MODES.keys())]


def get_analysis_mode_definition(mode_key: str) -> Optional[AnalysisModeDefinition]:
    if not mode_key:
        return None
    return _ANALYSIS_MODES.get(mode_key.strip().lower())


def resolve_analysis_mode(requested_mode: Optional[str]) -> AnalysisModeDefinition:
    if requested_mode and requested_mode.strip():
        mode = get_analysis_mode_definition(requested_mode)
        if mode:
            return mode
    default_mode = next((m for m in _ANALYSIS_MODES.values() if m.default), None)
    if default_mode is None:
        # Defensive fallback; registry always defines a default.
        return _ANALYSIS_MODES["takeoff"]
    return default_mode


def analysis_mode_status(mode: AnalysisModeDefinition) -> CapabilityImplementationStatus:
    capability = get_capability_definition(mode.capability_key)
    if capability is None:
        return CapabilityImplementationStatus.BLOCKED
    return capability.status


def analysis_mode_authority(mode: AnalysisModeDefinition) -> CapabilityAuthority:
    capability = get_capability_definition(mode.capability_key)
    if capability is None:
        return CapabilityAuthority.NOT_SUPPORTED
    return capability.authority

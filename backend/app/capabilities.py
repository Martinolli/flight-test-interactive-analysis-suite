"""
FTIAS capability catalog and rule evaluation.

This module is the backend source of truth for:
- supported analysis capability families
- required inputs
- authority classification (deterministic vs RAG)
- blocked/downgrade rules
- applicability boundaries and output contract intent
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Set


class CapabilityImplementationStatus(str, Enum):
    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    PLANNED = "planned"
    BLOCKED = "blocked"


class CapabilityAuthority(str, Enum):
    DETERMINISTIC_PRIMARY = "deterministic_primary"
    DETERMINISTIC_WITH_RAG_CROSSCHECK = "deterministic_with_rag_crosscheck"
    RAG_GUIDANCE_ONLY = "rag_guidance_only"
    NOT_SUPPORTED = "not_supported"


class CapabilityOutcome(str, Enum):
    ALLOWED = "allowed"
    ALLOW_WITH_LIMITATIONS = "allow_with_limitations"
    PARTIAL_ESTIMATE = "partial_estimate"
    STANDARDS_ONLY_GUIDANCE = "standards_only_guidance"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class BlockedConditionRule:
    reason_key: str
    description: str
    user_message: str
    outcome: CapabilityOutcome


@dataclass(frozen=True)
class CapabilityRequiredInputs:
    required_signals: List[str] = field(default_factory=list)
    required_dataset_conditions: List[str] = field(default_factory=list)
    optional_signals: List[str] = field(default_factory=list)
    required_provenance_state: List[str] = field(default_factory=list)
    certification_correction_inputs: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CapabilityOutputContract:
    deterministic_metrics: List[str] = field(default_factory=list)
    includes_assumptions: bool = True
    includes_limitations: bool = True
    includes_applicability_statement: bool = True
    includes_warnings: bool = True
    includes_recommendations: bool = True
    standards_crosscheck_allowed: bool = True


@dataclass(frozen=True)
class CapabilityDefinition:
    key: str
    label: str
    description: str
    status: CapabilityImplementationStatus
    authority: CapabilityAuthority
    required_inputs: CapabilityRequiredInputs
    blocked_rules: List[BlockedConditionRule]
    applicability_boundaries: List[str]
    default_limitations: List[str]
    output_contract: CapabilityOutputContract


@dataclass(frozen=True)
class CapabilityEvaluation:
    capability_key: str
    label: str
    status: CapabilityImplementationStatus
    authority: CapabilityAuthority
    outcome: CapabilityOutcome
    reason_key: Optional[str]
    user_message: str
    missing_required_signals: List[str]
    applicability_boundaries: List[str]
    limitations: List[str]


def _capability_registry() -> Dict[str, CapabilityDefinition]:
    takeoff_blocked_rules = [
        BlockedConditionRule(
            reason_key="missing_required_signals",
            description="Required deterministic takeoff signals are missing.",
            user_message=(
                "Takeoff deterministic analysis requires Ground Speed and Weight-on-Wheels signals."
            ),
            outcome=CapabilityOutcome.BLOCKED,
        ),
        BlockedConditionRule(
            reason_key="no_dataset_data",
            description="No usable flight-test dataset is available.",
            user_message="No flight-test dataset is available for deterministic takeoff analysis.",
            outcome=CapabilityOutcome.BLOCKED,
        ),
        BlockedConditionRule(
            reason_key="insufficient_data_coverage",
            description="Time-series continuity/coverage is insufficient for deterministic estimate.",
            user_message=(
                "Insufficient time-series continuity or coverage for a deterministic takeoff estimate."
            ),
            outcome=CapabilityOutcome.BLOCKED,
        ),
        BlockedConditionRule(
            reason_key="invalid_event_detection",
            description="WOW-based event boundaries are invalid or could not be resolved.",
            user_message=(
                "Could not reliably detect valid WOW event boundaries for takeoff segment estimation."
            ),
            outcome=CapabilityOutcome.BLOCKED,
        ),
        BlockedConditionRule(
            reason_key="certification_corrections_missing",
            description="Certification-corrected request lacks required correction inputs.",
            user_message=(
                "Requested certification-style takeoff distance, but correction inputs are unavailable. "
                "Returning deterministic ground-roll estimate with explicit limitations."
            ),
            outcome=CapabilityOutcome.PARTIAL_ESTIMATE,
        ),
    ]

    return {
        "takeoff": CapabilityDefinition(
            key="takeoff",
            label="Takeoff Analysis",
            description=(
                "Deterministic takeoff ground-roll to liftoff estimation from flight-test time-series data, "
                "with optional standards cross-check support."
            ),
            status=CapabilityImplementationStatus.IMPLEMENTED,
            authority=CapabilityAuthority.DETERMINISTIC_WITH_RAG_CROSSCHECK,
            required_inputs=CapabilityRequiredInputs(
                required_signals=["ground_speed", "weight_on_wheels"],
                required_dataset_conditions=[
                    "time_series_continuity",
                    "sufficient_sample_coverage",
                    "resolvable_wow_transition",
                ],
                optional_signals=["longitudinal_acceleration"],
                required_provenance_state=["dataset_version_selected_or_active"],
                certification_correction_inputs=[
                    "wind_component",
                    "runway_slope",
                    "atmosphere_corrections",
                    "screen_height_profile",
                ],
            ),
            blocked_rules=takeoff_blocked_rules,
            applicability_boundaries=[
                "Valid for estimated ground roll to liftoff from available WOW and ground-speed data.",
                "Not equivalent to corrected certification takeoff distance unless explicit corrections are applied.",
                "Sensitive to WOW event-detection quality and ground-speed signal integrity.",
            ],
            default_limitations=[
                "Wind correction not applied.",
                "Runway slope correction not applied.",
                "Non-standard atmosphere correction not applied.",
                "WOW event-definition timing can shift the estimated liftoff boundary.",
                "Sampling frequency and sensor quality can materially affect estimate precision.",
            ],
            output_contract=CapabilityOutputContract(
                deterministic_metrics=[
                    "estimated_ground_roll_distance_ft",
                    "estimated_ground_roll_distance_m",
                    "start_to_liftoff_time_s",
                    "start_speed_kt",
                    "liftoff_speed_kt",
                    "mean_acceleration",
                ],
                standards_crosscheck_allowed=True,
            ),
        ),
        "landing": CapabilityDefinition(
            key="landing",
            label="Landing Analysis",
            description="Landing distance/performance capability scaffold; deterministic implementation pending.",
            status=CapabilityImplementationStatus.PLANNED,
            authority=CapabilityAuthority.NOT_SUPPORTED,
            required_inputs=CapabilityRequiredInputs(
                required_signals=["ground_speed", "weight_on_wheels"],
                optional_signals=["brake_pressure", "pitch_angle", "flap_setting"],
            ),
            blocked_rules=[],
            applicability_boundaries=[
                "Landing deterministic computation is not yet implemented in this release."
            ],
            default_limitations=["Current output is limited to standards guidance only."],
            output_contract=CapabilityOutputContract(
                deterministic_metrics=[],
                standards_crosscheck_allowed=True,
            ),
        ),
        "performance_general": CapabilityDefinition(
            key="performance_general",
            label="General Performance Assessment",
            description=(
                "Cross-parameter performance interpretation with contextual standards support."
            ),
            status=CapabilityImplementationStatus.PARTIAL,
            authority=CapabilityAuthority.RAG_GUIDANCE_ONLY,
            required_inputs=CapabilityRequiredInputs(
                required_signals=[],
                required_dataset_conditions=["minimum_relevant_parameters_available"],
            ),
            blocked_rules=[],
            applicability_boundaries=[
                "Provides contextual interpretation; no authoritative deterministic certification metric."
            ],
            default_limitations=["Output is advisory and depends on source coverage quality."],
            output_contract=CapabilityOutputContract(
                deterministic_metrics=[],
                standards_crosscheck_allowed=True,
            ),
        ),
        "handling_qualities": CapabilityDefinition(
            key="handling_qualities",
            label="Handling Qualities",
            description="Handling qualities assessment scaffold; deterministic scoring not yet implemented.",
            status=CapabilityImplementationStatus.PARTIAL,
            authority=CapabilityAuthority.RAG_GUIDANCE_ONLY,
            required_inputs=CapabilityRequiredInputs(
                optional_signals=["control_surface_positions", "attitude_rates", "pilot_inputs"],
            ),
            blocked_rules=[],
            applicability_boundaries=[
                "Current output is guidance-only and not a formal handling-qualities rating."
            ],
            default_limitations=["Formal rating methods are outside current implemented scope."],
            output_contract=CapabilityOutputContract(
                deterministic_metrics=[],
                standards_crosscheck_allowed=True,
            ),
        ),
        "trajectory_kinematics": CapabilityDefinition(
            key="trajectory_kinematics",
            label="Trajectory Kinematics",
            description="Kinematic trend interpretation; dedicated deterministic module planned.",
            status=CapabilityImplementationStatus.PARTIAL,
            authority=CapabilityAuthority.DETERMINISTIC_PRIMARY,
            required_inputs=CapabilityRequiredInputs(
                required_signals=["time_reference"],
                optional_signals=["position", "velocity", "acceleration"],
            ),
            blocked_rules=[],
            applicability_boundaries=[
                "Only partial support is available until dedicated trajectory module is introduced."
            ],
            default_limitations=["Use outputs as exploratory engineering cues only."],
            output_contract=CapabilityOutputContract(
                deterministic_metrics=["trend_descriptors"],
                standards_crosscheck_allowed=False,
            ),
        ),
        "systems_monitoring": CapabilityDefinition(
            key="systems_monitoring",
            label="Systems Monitoring",
            description="System-parameter trend and anomaly review with standards/context guidance.",
            status=CapabilityImplementationStatus.PARTIAL,
            authority=CapabilityAuthority.RAG_GUIDANCE_ONLY,
            required_inputs=CapabilityRequiredInputs(
                required_signals=[],
                optional_signals=["electrical_parameters", "hydraulic_parameters", "engine_parameters"],
            ),
            blocked_rules=[],
            applicability_boundaries=[
                "Provides trend/anomaly screening, not authoritative fault isolation."
            ],
            default_limitations=["Requires domain-specific deterministic modules for authoritative conclusions."],
            output_contract=CapabilityOutputContract(
                deterministic_metrics=[],
                standards_crosscheck_allowed=True,
            ),
        ),
        "buffet_vibration": CapabilityDefinition(
            key="buffet_vibration",
            label="Buffet and Vibration Support",
            description="Pre-screening support for buffet/vibration trends; formal methods pending.",
            status=CapabilityImplementationStatus.PLANNED,
            authority=CapabilityAuthority.NOT_SUPPORTED,
            required_inputs=CapabilityRequiredInputs(
                optional_signals=["accelerometers", "frequency_features"],
            ),
            blocked_rules=[],
            applicability_boundaries=[
                "Not sufficient for formal buffet/vibration clearance determination."
            ],
            default_limitations=["Dedicated spectral/dynamic methods are not yet implemented."],
            output_contract=CapabilityOutputContract(
                deterministic_metrics=[],
                standards_crosscheck_allowed=True,
            ),
        ),
        "flutter_support": CapabilityDefinition(
            key="flutter_support",
            label="Flutter Support",
            description="Flutter-support pre-assessment scaffold; clearance computation not implemented.",
            status=CapabilityImplementationStatus.BLOCKED,
            authority=CapabilityAuthority.NOT_SUPPORTED,
            required_inputs=CapabilityRequiredInputs(
                optional_signals=["flutter_test_instrumentation", "modal_features"],
            ),
            blocked_rules=[],
            applicability_boundaries=[
                "Not sufficient for flutter clearance or formal aeroelastic certification."
            ],
            default_limitations=["Current release does not implement flutter determination logic."],
            output_contract=CapabilityOutputContract(
                deterministic_metrics=[],
                standards_crosscheck_allowed=True,
            ),
        ),
        "risk_assessment": CapabilityDefinition(
            key="risk_assessment",
            label="Risk Assessment",
            description="Qualitative/structured risk assessment support; deterministic FRAT scoring pending P2.",
            status=CapabilityImplementationStatus.PARTIAL,
            authority=CapabilityAuthority.RAG_GUIDANCE_ONLY,
            required_inputs=CapabilityRequiredInputs(
                optional_signals=["campaign_context", "hazard_catalog", "operational_constraints"],
            ),
            blocked_rules=[],
            applicability_boundaries=[
                "Supports structured preliminary risk framing, not final authorized risk acceptance."
            ],
            default_limitations=["Formal FRAT deterministic scoring workflow is not yet enabled."],
            output_contract=CapabilityOutputContract(
                deterministic_metrics=[],
                standards_crosscheck_allowed=True,
            ),
        ),
        "general_standards_query": CapabilityDefinition(
            key="general_standards_query",
            label="General Standards Query",
            description="RAG-first standards/regulatory evidence query without deterministic flight-data computation.",
            status=CapabilityImplementationStatus.IMPLEMENTED,
            authority=CapabilityAuthority.RAG_GUIDANCE_ONLY,
            required_inputs=CapabilityRequiredInputs(
                required_signals=[],
                required_dataset_conditions=[],
            ),
            blocked_rules=[],
            applicability_boundaries=[
                "Standards interpretation only; does not compute deterministic flight-test metrics."
            ],
            default_limitations=[
                "Output quality depends on retrieved document coverage and citation relevance."
            ],
            output_contract=CapabilityOutputContract(
                deterministic_metrics=[],
                standards_crosscheck_allowed=True,
            ),
        ),
    }


CAPABILITY_REGISTRY: Dict[str, CapabilityDefinition] = _capability_registry()


def list_capabilities() -> List[CapabilityDefinition]:
    return [CAPABILITY_REGISTRY[key] for key in sorted(CAPABILITY_REGISTRY.keys())]


def get_capability_definition(capability_key: str) -> Optional[CapabilityDefinition]:
    return CAPABILITY_REGISTRY.get((capability_key or "").strip().lower())


def _normalize_signal_key(raw_signal: str) -> str:
    s = (raw_signal or "").strip().lower()
    if not s:
        return s
    if any(token in s for token in ["ground_speed", "ground speed", "gs"]):
        return "ground_speed"
    if any(token in s for token in ["weight_on_wheels", "weight on wheels", "wow"]):
        return "weight_on_wheels"
    if any(token in s for token in ["longitudinal_acceleration", "longitudinal accel", "x_accel", "x accel"]):
        return "longitudinal_acceleration"
    if s in {"time_reference", "time"}:
        return "time_reference"
    return s.replace(" ", "_")


def _norm_signal_set(available_signals: Optional[Iterable[str]]) -> Set[str]:
    if not available_signals:
        return set()
    return {_normalize_signal_key(sig) for sig in available_signals if sig}


def evaluate_capability_request(
    capability_key: str,
    *,
    available_signals: Optional[Iterable[str]] = None,
    has_dataset: bool = True,
    has_time_series_continuity: Optional[bool] = None,
    data_coverage_ok: Optional[bool] = None,
    event_detection_ok: Optional[bool] = None,
    request_certification_result: bool = False,
    correction_inputs_available: Optional[bool] = None,
    has_standards_context: bool = False,
) -> CapabilityEvaluation:
    capability = get_capability_definition(capability_key)
    if capability is None:
        return CapabilityEvaluation(
            capability_key=(capability_key or "").strip().lower() or "unknown",
            label="Unsupported Capability",
            status=CapabilityImplementationStatus.BLOCKED,
            authority=CapabilityAuthority.NOT_SUPPORTED,
            outcome=CapabilityOutcome.BLOCKED,
            reason_key="capability_not_supported",
            user_message="Requested capability is not supported by FTIAS.",
            missing_required_signals=[],
            applicability_boundaries=[
                "No capability definition is available for the requested analysis type."
            ],
            limitations=["Use a supported capability family or standards-only query mode."],
        )

    signal_set = _norm_signal_set(available_signals)
    missing_required_signals = [
        sig for sig in capability.required_inputs.required_signals if sig not in signal_set
    ]

    if capability.status in {
        CapabilityImplementationStatus.PLANNED,
        CapabilityImplementationStatus.BLOCKED,
    }:
        return CapabilityEvaluation(
            capability_key=capability.key,
            label=capability.label,
            status=capability.status,
            authority=CapabilityAuthority.NOT_SUPPORTED,
            outcome=CapabilityOutcome.BLOCKED,
            reason_key="capability_not_implemented",
            user_message=(
                f"{capability.label} is not implemented in this release. "
                "FTIAS can provide standards/context guidance only where available."
            ),
            missing_required_signals=[],
            applicability_boundaries=capability.applicability_boundaries,
            limitations=capability.default_limitations,
        )

    if not has_dataset:
        if has_standards_context:
            return CapabilityEvaluation(
                capability_key=capability.key,
                label=capability.label,
                status=capability.status,
                authority=capability.authority,
                outcome=CapabilityOutcome.STANDARDS_ONLY_GUIDANCE,
                reason_key="no_dataset_data",
                user_message=(
                    "No valid flight-test dataset available. Returning standards/context guidance only."
                ),
                missing_required_signals=missing_required_signals,
                applicability_boundaries=capability.applicability_boundaries,
                limitations=capability.default_limitations,
            )
        return CapabilityEvaluation(
            capability_key=capability.key,
            label=capability.label,
            status=capability.status,
            authority=capability.authority,
            outcome=CapabilityOutcome.BLOCKED,
            reason_key="no_dataset_data",
            user_message="No valid flight-test dataset available for deterministic analysis.",
            missing_required_signals=missing_required_signals,
            applicability_boundaries=capability.applicability_boundaries,
            limitations=capability.default_limitations,
        )

    if missing_required_signals:
        return CapabilityEvaluation(
            capability_key=capability.key,
            label=capability.label,
            status=capability.status,
            authority=capability.authority,
            outcome=CapabilityOutcome.BLOCKED,
            reason_key="missing_required_signals",
            user_message=(
                f"Missing required signals for {capability.label}: "
                + ", ".join(sorted(missing_required_signals))
            ),
            missing_required_signals=sorted(missing_required_signals),
            applicability_boundaries=capability.applicability_boundaries,
            limitations=capability.default_limitations,
        )

    if has_time_series_continuity is False or data_coverage_ok is False:
        return CapabilityEvaluation(
            capability_key=capability.key,
            label=capability.label,
            status=capability.status,
            authority=capability.authority,
            outcome=CapabilityOutcome.BLOCKED,
            reason_key="insufficient_data_coverage",
            user_message=(
                "Dataset coverage/continuity is insufficient for authoritative deterministic output."
            ),
            missing_required_signals=[],
            applicability_boundaries=capability.applicability_boundaries,
            limitations=capability.default_limitations,
        )

    if event_detection_ok is False:
        return CapabilityEvaluation(
            capability_key=capability.key,
            label=capability.label,
            status=capability.status,
            authority=capability.authority,
            outcome=CapabilityOutcome.BLOCKED,
            reason_key="invalid_event_detection",
            user_message=(
                "Required event boundaries could not be detected reliably from available signals."
            ),
            missing_required_signals=[],
            applicability_boundaries=capability.applicability_boundaries,
            limitations=capability.default_limitations,
        )

    if request_certification_result and not bool(correction_inputs_available):
        return CapabilityEvaluation(
            capability_key=capability.key,
            label=capability.label,
            status=capability.status,
            authority=capability.authority,
            outcome=CapabilityOutcome.PARTIAL_ESTIMATE,
            reason_key="certification_corrections_missing",
            user_message=(
                "Certification-style result requested without correction inputs. "
                "Returning deterministic partial estimate with explicit limitations."
            ),
            missing_required_signals=[],
            applicability_boundaries=capability.applicability_boundaries,
            limitations=capability.default_limitations,
        )

    # For implemented deterministic takeoff in current scope, keep explicit limitations.
    outcome = (
        CapabilityOutcome.ALLOW_WITH_LIMITATIONS
        if capability.key == "takeoff"
        else CapabilityOutcome.ALLOWED
    )
    return CapabilityEvaluation(
        capability_key=capability.key,
        label=capability.label,
        status=capability.status,
        authority=capability.authority,
        outcome=outcome,
        reason_key=None,
        user_message=f"{capability.label} is available.",
        missing_required_signals=[],
        applicability_boundaries=capability.applicability_boundaries,
        limitations=capability.default_limitations,
    )

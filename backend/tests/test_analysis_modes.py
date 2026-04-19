"""Tests for P2.1 analysis-mode registry and capability alignment."""

from app.analysis_modes import (
    get_analysis_mode_definition,
    list_analysis_modes,
    resolve_analysis_mode,
)
from app.capabilities import get_capability_definition


def test_analysis_mode_registry_contains_required_modes():
    keys = {mode.key for mode in list_analysis_modes()}
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


def test_analysis_mode_default_resolution_is_takeoff():
    assert resolve_analysis_mode(None).key == "takeoff"
    assert resolve_analysis_mode("").key == "takeoff"
    assert resolve_analysis_mode("not_real_mode").key == "takeoff"


def test_analysis_mode_capability_mapping_is_catalog_backed():
    for mode in list_analysis_modes():
        assert get_capability_definition(mode.capability_key) is not None
        assert get_analysis_mode_definition(mode.key) is not None

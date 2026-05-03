"""
Bounded atmosphere / air-data engineering helpers.

P3.3 scope:
- deterministic, explicit atmosphere and air-data support
- bounded engineering-use calculations (not full calibration/certification package)
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

SEA_LEVEL_TEMPERATURE_K = 288.15
SEA_LEVEL_PRESSURE_PA = 101_325.0
SEA_LEVEL_DENSITY_KG_M3 = 1.225
LAPSE_RATE_K_PER_M = 0.0065
GAS_CONSTANT_AIR = 287.05287
GRAVITY_M_S2 = 9.80665
GAMMA_AIR = 1.4
KNOT_TO_MPS = 0.514444
MPS_TO_KNOT = 1.0 / KNOT_TO_MPS


def isa_atmosphere_from_pressure_altitude_ft(
    pressure_altitude_ft: float,
) -> Optional[Dict[str, float]]:
    """
    ISA snapshot from pressure altitude using troposphere model.
    Returns bounded outputs up to ~36,089 ft (11 km).
    """
    try:
        altitude_m = float(pressure_altitude_ft) * 0.3048
    except (TypeError, ValueError):
        return None
    if altitude_m < -100.0 or altitude_m > 11_000.0:
        return None

    temp_k = SEA_LEVEL_TEMPERATURE_K - (LAPSE_RATE_K_PER_M * altitude_m)
    if temp_k <= 0:
        return None

    exponent = GRAVITY_M_S2 / (GAS_CONSTANT_AIR * LAPSE_RATE_K_PER_M)
    pressure_pa = SEA_LEVEL_PRESSURE_PA * (temp_k / SEA_LEVEL_TEMPERATURE_K) ** exponent
    density = pressure_pa / (GAS_CONSTANT_AIR * temp_k)
    speed_of_sound_mps = math.sqrt(GAMMA_AIR * GAS_CONSTANT_AIR * temp_k)

    return {
        "altitude_ft": float(pressure_altitude_ft),
        "temperature_k": temp_k,
        "temperature_c": temp_k - 273.15,
        "pressure_pa": pressure_pa,
        "density_kg_m3": density,
        "theta": temp_k / SEA_LEVEL_TEMPERATURE_K,
        "delta": pressure_pa / SEA_LEVEL_PRESSURE_PA,
        "sigma": density / SEA_LEVEL_DENSITY_KG_M3,
        "speed_of_sound_mps": speed_of_sound_mps,
    }


def density_altitude_estimate_ft(pressure_altitude_ft: float, oat_c: float) -> Optional[float]:
    """
    Approximate density altitude using common engineering approximation:
    DA ~= PA + 120 * (OAT_C - ISA_temp_C_at_PA)
    """
    isa = isa_atmosphere_from_pressure_altitude_ft(pressure_altitude_ft)
    if isa is None:
        return None
    try:
        oat_val = float(oat_c)
    except (TypeError, ValueError):
        return None
    isa_temp_c = isa["temperature_c"]
    return float(pressure_altitude_ft) + (120.0 * (oat_val - isa_temp_c))


def speed_of_sound_mps_from_temperature_c(temperature_c: float) -> Optional[float]:
    try:
        temp_k = float(temperature_c) + 273.15
    except (TypeError, ValueError):
        return None
    if temp_k <= 0:
        return None
    return math.sqrt(GAMMA_AIR * GAS_CONSTANT_AIR * temp_k)


def estimate_tas_from_cas_and_sigma_knots(cas_knots: float, sigma: float) -> Optional[float]:
    """
    Bounded low-compressibility support estimate:
    TAS ~= CAS / sqrt(sigma)
    """
    try:
        cas_val = float(cas_knots)
        sigma_val = float(sigma)
    except (TypeError, ValueError):
        return None
    if sigma_val <= 0:
        return None
    return cas_val / math.sqrt(sigma_val)


def estimate_mach_from_tas_knots_and_temperature_c(
    tas_knots: float,
    temperature_c: float,
) -> Optional[float]:
    try:
        tas_mps = float(tas_knots) * KNOT_TO_MPS
    except (TypeError, ValueError):
        return None
    speed_of_sound = speed_of_sound_mps_from_temperature_c(temperature_c)
    if speed_of_sound is None or speed_of_sound <= 0:
        return None
    return tas_mps / speed_of_sound


def summarize_series(values: List[float]) -> Optional[Dict[str, float]]:
    if not values:
        return None
    mean_val = sum(values) / len(values)
    variance = sum((value - mean_val) ** 2 for value in values) / len(values)
    return {
        "min": min(values),
        "max": max(values),
        "mean": mean_val,
        "std": math.sqrt(max(variance, 0.0)),
        "samples": float(len(values)),
    }

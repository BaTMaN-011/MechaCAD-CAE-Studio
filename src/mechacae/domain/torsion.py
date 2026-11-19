"""Elastic torsion response of solid and hollow circular shafts."""
from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt


@dataclass(frozen=True)
class ShaftResult:
    polar_moment_mm4: float
    maximum_shear_stress_mpa: float
    twist_radians: float
    twist_degrees: float
    estimated_shear_yield_mpa: float | None
    yield_safety_factor: float | None


class TorsionInputError(ValueError):
    pass


def calculate_shaft_torsion(
    torque_nm: float,
    length_mm: float,
    shear_modulus_mpa: float,
    outer_diameter_mm: float,
    inner_diameter_mm: float = 0.0,
    tensile_yield_strength_mpa: float | None = None,
) -> ShaftResult:
    """Compute maximum elastic shear stress and angle of twist.

    Ductile-material shear yield is estimated from tensile yield by the
    von-Mises relation. This is a classroom estimate, not a fatigue check.
    """
    if min(torque_nm, length_mm, shear_modulus_mpa, outer_diameter_mm) <= 0:
        raise TorsionInputError("Torque, shaft length, shear modulus, and outer diameter must be positive.")
    if inner_diameter_mm < 0 or inner_diameter_mm >= outer_diameter_mm:
        raise TorsionInputError("Inner diameter must be zero or smaller than the outer diameter.")
    if tensile_yield_strength_mpa is not None and tensile_yield_strength_mpa <= 0:
        raise TorsionInputError("Tensile yield strength must be positive.")
    polar = pi * (outer_diameter_mm**4 - inner_diameter_mm**4) / 32
    torque_nmm = torque_nm * 1000
    stress = torque_nmm * (outer_diameter_mm / 2) / polar
    twist = torque_nmm * length_mm / (polar * shear_modulus_mpa)
    shear_yield = tensile_yield_strength_mpa / sqrt(3) if tensile_yield_strength_mpa else None
    safety = shear_yield / stress if shear_yield and stress > 0 else None
    return ShaftResult(
        polar_moment_mm4=polar,
        maximum_shear_stress_mpa=stress,
        twist_radians=twist,
        twist_degrees=twist * 180 / pi,
        estimated_shear_yield_mpa=shear_yield,
        yield_safety_factor=safety,
    )

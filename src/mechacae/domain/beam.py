"""Euler-Bernoulli beam formulas for common classroom load cases."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BeamResult:
    support_model: str
    load_model: str
    maximum_moment_nmm: float
    maximum_deflection_mm: float
    maximum_bending_stress_mpa: float
    yield_safety_factor: float | None
    deflection_ratio: float
    assumptions: tuple[str, ...]


class BeamInputError(ValueError):
    pass


def calculate_beam(
    support_model: str,
    load_model: str,
    length_mm: float,
    elastic_modulus_mpa: float,
    second_moment_mm4: float,
    extreme_fibre_mm: float,
    *,
    point_load_n: float = 0.0,
    distributed_load_n_per_mm: float = 0.0,
    yield_strength_mpa: float | None = None,
) -> BeamResult:
    """Compute a maximum response for a uniform prismatic beam.

    Supported cases: simply supported with a centered point load or full-span
    uniform load; cantilever with an end point load or full-span uniform load.
    The result uses small-deflection, linear-elastic beam theory.
    """
    if support_model not in {"Simply supported", "Cantilever"}:
        raise BeamInputError("Choose a supported support model.")
    if load_model not in {"Point load", "Uniform load"}:
        raise BeamInputError("Choose a supported load model.")
    if min(length_mm, elastic_modulus_mpa, second_moment_mm4, extreme_fibre_mm) <= 0:
        raise BeamInputError("Length, modulus, section inertia, and fibre distance must be positive.")
    if yield_strength_mpa is not None and yield_strength_mpa <= 0:
        raise BeamInputError("Yield strength must be positive when supplied.")
    length = float(length_mm)
    modulus = float(elastic_modulus_mpa)
    inertia = float(second_moment_mm4)
    if load_model == "Point load":
        if point_load_n <= 0:
            raise BeamInputError("Enter a positive point load.")
        if support_model == "Simply supported":
            moment = point_load_n * length / 4
            deflection = point_load_n * length**3 / (48 * modulus * inertia)
        else:
            moment = point_load_n * length
            deflection = point_load_n * length**3 / (3 * modulus * inertia)
    else:
        if distributed_load_n_per_mm <= 0:
            raise BeamInputError("Enter a positive distributed load in N/mm.")
        if support_model == "Simply supported":
            moment = distributed_load_n_per_mm * length**2 / 8
            deflection = 5 * distributed_load_n_per_mm * length**4 / (384 * modulus * inertia)
        else:
            moment = distributed_load_n_per_mm * length**2 / 2
            deflection = distributed_load_n_per_mm * length**4 / (8 * modulus * inertia)

    stress = moment * extreme_fibre_mm / inertia
    safety = yield_strength_mpa / stress if yield_strength_mpa and stress > 0 else None
    return BeamResult(
        support_model=support_model,
        load_model=load_model,
        maximum_moment_nmm=moment,
        maximum_deflection_mm=deflection,
        maximum_bending_stress_mpa=stress,
        yield_safety_factor=safety,
        deflection_ratio=(length / deflection) if deflection > 0 else float("inf"),
        assumptions=(
            "Euler-Bernoulli beam theory; linear elastic, prismatic member.",
            "Point load acts at midspan for simply supported beams and at the free end for cantilevers.",
            "Uniform load covers the full span. Shear deformation, self-weight, and local instability are omitted.",
        ),
    )

"""Assembly roll-up metrics and mass completeness notes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssemblySummary:
    line_items: int
    total_quantity: int
    total_mass_kg: float
    lines_with_material: int
    lines_with_mass: int
    warnings: tuple[str, ...]


def summarize_assembly(components: list[dict[str, Any]]) -> AssemblySummary:
    """Summarize BOM mass and identify rows that need material review."""
    total_quantity = 0
    total_mass = 0.0
    material_rows = 0
    mass_rows = 0
    warnings = []
    for component in components:
        quantity = int(component.get("quantity", 0))
        mass_each = float(component.get("unit_mass_kg", 0) or 0)
        total_quantity += quantity
        total_mass += quantity * mass_each
        if component.get("material_id") is not None:
            material_rows += 1
        if mass_each > 0:
            mass_rows += 1
        elif quantity > 0:
            warnings.append(f"{component.get('part_number', 'Part')} has no estimated unit mass.")
    if components and material_rows < len(components):
        warnings.append("Some component rows do not reference a material.")
    return AssemblySummary(
        line_items=len(components),
        total_quantity=total_quantity,
        total_mass_kg=total_mass,
        lines_with_material=material_rows,
        lines_with_mass=mass_rows,
        warnings=tuple(warnings),
    )

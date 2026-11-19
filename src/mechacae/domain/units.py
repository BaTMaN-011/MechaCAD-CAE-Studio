"""Consistent engineering unit conversions for common project quantities."""
from __future__ import annotations

import math


UNIT_FACTORS = {
    "Length": {"mm": 1e-3, "cm": 1e-2, "m": 1.0, "in": 0.0254, "ft": 0.3048},
    "Area": {"mm²": 1e-6, "cm²": 1e-4, "m²": 1.0, "in²": 0.00064516},
    "Volume": {"mm³": 1e-9, "cm³": 1e-6, "m³": 1.0, "in³": 1.6387064e-5},
    "Force": {"N": 1.0, "kN": 1000.0, "lbf": 4.4482216153},
    "Torque": {"N·m": 1.0, "N·mm": 0.001, "lbf·ft": 1.3558179483},
    "Stress": {"Pa": 1.0, "kPa": 1000.0, "MPa": 1e6, "GPa": 1e9, "psi": 6894.7572932},
    "Rotational speed": {"rpm": 1.0, "rad/s": 60.0 / (2 * math.pi)},
    "Angle": {"degree": 1.0, "radian": 180.0 / math.pi},
    "Mass": {"kg": 1.0, "g": 0.001, "lb": 0.45359237},
}


def convert(value: float, category: str, source_unit: str, target_unit: str) -> float:
    """Convert a scalar through the category's canonical SI factor."""
    if not math.isfinite(value):
        raise ValueError("Enter a finite numeric value.")
    units = UNIT_FACTORS.get(category)
    if not units or source_unit not in units or target_unit not in units:
        raise ValueError("Choose matching units from one category.")
    return float(value) * units[source_unit] / units[target_unit]

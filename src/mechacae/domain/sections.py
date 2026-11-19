"""Educational centroidal properties for common symmetric cross sections."""
from __future__ import annotations

from dataclasses import dataclass
from math import pi


@dataclass(frozen=True)
class SectionProperties:
    name: str
    area_mm2: float
    ixx_mm4: float
    iyy_mm4: float
    cxx_mm: float
    cyy_mm: float
    dimensions: dict[str, float]

    @property
    def section_modulus_x_mm3(self) -> float:
        return self.ixx_mm4 / self.cxx_mm

    @property
    def section_modulus_y_mm3(self) -> float:
        return self.iyy_mm4 / self.cyy_mm


class SectionInputError(ValueError):
    pass


def _positive(values: dict[str, float], names: tuple[str, ...]) -> None:
    missing = [name for name in names if name not in values]
    if missing:
        raise SectionInputError("Missing section dimensions: " + ", ".join(missing))
    invalid = [name for name in names if float(values[name]) <= 0]
    if invalid:
        raise SectionInputError("Dimensions must be greater than zero: " + ", ".join(invalid))


def calculate_section(shape: str, dimensions: dict[str, float]) -> SectionProperties:
    """Return A, Ixx, Iyy and extreme-fibre distances in mm-based units.

    Axes pass through the centroid. For rectangles and I-sections, x is the
    horizontal centroidal axis and y is the vertical centroidal axis.
    """
    shape = shape.strip().lower()
    d = {key: float(value) for key, value in dimensions.items()}
    if shape == "rectangle":
        _positive(d, ("width", "height"))
        width, height = d["width"], d["height"]
        area = width * height
        ixx = width * height**3 / 12
        iyy = height * width**3 / 12
        cxx, cyy = height / 2, width / 2
        name = "Rectangle"
    elif shape == "solid circle":
        _positive(d, ("diameter",))
        diameter = d["diameter"]
        area = pi * diameter**2 / 4
        ixx = iyy = pi * diameter**4 / 64
        cxx = cyy = diameter / 2
        name = "Solid circle"
    elif shape == "hollow circle":
        _positive(d, ("outer_diameter", "inner_diameter"))
        outer, inner = d["outer_diameter"], d["inner_diameter"]
        if inner >= outer:
            raise SectionInputError("Inner diameter must be smaller than outer diameter.")
        area = pi * (outer**2 - inner**2) / 4
        ixx = iyy = pi * (outer**4 - inner**4) / 64
        cxx = cyy = outer / 2
        name = "Hollow circle"
    elif shape == "rectangular tube":
        _positive(d, ("width", "height", "wall"))
        width, height, wall = d["width"], d["height"], d["wall"]
        if 2 * wall >= min(width, height):
            raise SectionInputError("Wall thickness must be less than half of the smaller outer dimension.")
        inner_width, inner_height = width - 2 * wall, height - 2 * wall
        area = width * height - inner_width * inner_height
        ixx = (width * height**3 - inner_width * inner_height**3) / 12
        iyy = (height * width**3 - inner_height * inner_width**3) / 12
        cxx, cyy = height / 2, width / 2
        name = "Rectangular tube"
    elif shape == "I-section":
        _positive(d, ("width", "height", "flange", "web"))
        width, height = d["width"], d["height"]
        flange, web = d["flange"], d["web"]
        if 2 * flange >= height:
            raise SectionInputError("Two flange thicknesses must fit within the total height.")
        if web >= width:
            raise SectionInputError("Web thickness must be smaller than the flange width.")
        clear_height = height - 2 * flange
        area = 2 * width * flange + web * clear_height
        ixx = (width * height**3 - (width - web) * clear_height**3) / 12
        iyy = (2 * flange * width**3 + clear_height * web**3) / 12
        cxx, cyy = height / 2, width / 2
        name = "I-section"
    else:
        raise SectionInputError(f"Unsupported shape: {shape}")

    if area <= 0 or ixx <= 0 or iyy <= 0:
        raise SectionInputError("Section dimensions do not form a valid shape.")
    return SectionProperties(name, area, ixx, iyy, cxx, cyy, d)

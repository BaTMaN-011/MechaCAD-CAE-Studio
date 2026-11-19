"""Linear elastic 2D pin-jointed truss analysis by direct stiffness."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Node:
    x: float
    y: float
    force_x: float = 0.0
    force_y: float = 0.0
    fixed_x: bool = False
    fixed_y: bool = False


@dataclass(frozen=True)
class TrussElement:
    start: int
    end: int
    area: float
    youngs_modulus: float


class TrussInputError(ValueError):
    """Raised when an analysis model is incomplete or physically invalid."""


class TrussSolver:
    """Solve a small, linear, planar truss in N and mm units.

    Coordinates and cross-sectional areas are in mm and mm². Young's modulus
    is in MPa (N/mm²), nodal loads in N, stress in MPa, and displacement in mm.
    Supports are fixed translations; each member carries only axial force.
    """

    @classmethod
    def solve(cls, nodes: list[Node], elements: list[TrussElement]) -> dict:
        if len(nodes) < 2:
            raise TrussInputError("Add at least two nodes before solving.")
        if not elements:
            raise TrussInputError("Add at least one truss member before solving.")

        dof_count = 2 * len(nodes)
        stiffness = np.zeros((dof_count, dof_count), dtype=float)
        force = np.zeros(dof_count, dtype=float)
        fixed_dofs: set[int] = set()

        for index, node in enumerate(nodes):
            force[2 * index] = node.force_x
            force[2 * index + 1] = node.force_y
            if node.fixed_x:
                fixed_dofs.add(2 * index)
            if node.fixed_y:
                fixed_dofs.add(2 * index + 1)
        if not fixed_dofs:
            raise TrussInputError("The structure has no supports. Fix at least one translation.")

        for element_index, element in enumerate(elements, start=1):
            if not (0 <= element.start < len(nodes) and 0 <= element.end < len(nodes)):
                raise TrussInputError(f"Member {element_index} refers to a node that does not exist.")
            if element.start == element.end:
                raise TrussInputError(f"Member {element_index} starts and ends at the same node.")
            if element.area <= 0 or element.youngs_modulus <= 0:
                raise TrussInputError(f"Member {element_index} needs positive area and modulus values.")

            first = nodes[element.start]
            second = nodes[element.end]
            dx, dy = second.x - first.x, second.y - first.y
            length = float(np.hypot(dx, dy))
            if length <= 1e-9:
                raise TrussInputError(f"Member {element_index} has zero length.")
            cosine, sine = dx / length, dy / length
            direction = np.array([-cosine, -sine, cosine, sine], dtype=float)
            member_matrix = (element.area * element.youngs_modulus / length) * np.outer(direction, direction)
            dofs = [2 * element.start, 2 * element.start + 1, 2 * element.end, 2 * element.end + 1]
            for row, global_row in enumerate(dofs):
                for column, global_column in enumerate(dofs):
                    stiffness[global_row, global_column] += member_matrix[row, column]

        free_dofs = [dof for dof in range(dof_count) if dof not in fixed_dofs]
        if not free_dofs:
            raise TrussInputError("Every degree of freedom is fixed; there is nothing to solve.")
        reduced = stiffness[np.ix_(free_dofs, free_dofs)]
        if np.linalg.matrix_rank(reduced, tol=1e-9) < len(free_dofs):
            raise TrussInputError(
                "The model is unstable or disconnected. Check the supports and member layout."
            )

        displacements = np.zeros(dof_count, dtype=float)
        try:
            displacements[free_dofs] = np.linalg.solve(reduced, force[free_dofs])
        except np.linalg.LinAlgError as exc:
            raise TrussInputError("The stiffness matrix could not be solved.") from exc
        reactions = stiffness @ displacements - force

        member_results = []
        for index, element in enumerate(elements, start=1):
            first, second = nodes[element.start], nodes[element.end]
            dx, dy = second.x - first.x, second.y - first.y
            length = float(np.hypot(dx, dy))
            cosine, sine = dx / length, dy / length
            dofs = [2 * element.start, 2 * element.start + 1, 2 * element.end, 2 * element.end + 1]
            extension = float(np.dot(np.array([-cosine, -sine, cosine, sine]), displacements[dofs]))
            stress = element.youngs_modulus * extension / length
            member_results.append({
                "member": index,
                "start_node": element.start + 1,
                "end_node": element.end + 1,
                "length_mm": length,
                "area_mm2": element.area,
                "axial_force_n": stress * element.area,
                "stress_mpa": stress,
                "state": "Tension" if stress >= 0 else "Compression",
            })

        node_results = []
        for index, node in enumerate(nodes):
            node_results.append({
                "node": index + 1,
                "x_mm": node.x,
                "y_mm": node.y,
                "displacement_x_mm": float(displacements[2 * index]),
                "displacement_y_mm": float(displacements[2 * index + 1]),
                "reaction_x_n": float(reactions[2 * index]) if node.fixed_x else 0.0,
                "reaction_y_n": float(reactions[2 * index + 1]) if node.fixed_y else 0.0,
            })
        return {
            "units": {"length": "mm", "force": "N", "stress": "MPa"},
            "members": member_results,
            "nodes": node_results,
            "maximum_displacement_mm": float(np.max(np.abs(displacements))),
            "maximum_absolute_stress_mpa": max(abs(row["stress_mpa"]) for row in member_results),
        }

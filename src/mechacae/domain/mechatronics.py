"""Approximate lead-screw actuator and motor sizing calculations."""
from __future__ import annotations

from dataclasses import dataclass
from math import pi


@dataclass(frozen=True)
class ScrewDriveResult:
    torque_nm: float
    rotational_speed_rpm: float
    mechanical_power_w: float
    input_power_w: float
    service_factor: float
    efficiency: float
    assumptions: tuple[str, ...]


class ActuatorInputError(ValueError):
    pass


def size_lead_screw_drive(
    axial_force_n: float,
    lead_mm_per_rev: float,
    linear_speed_mm_per_s: float,
    efficiency: float,
    service_factor: float = 1.5,
) -> ScrewDriveResult:
    """Estimate torque and speed for a screw drive under a steady axial load.

    Friction and screw losses are represented by one user-supplied efficiency.
    This does not select a motor, gearbox, driver, or safety-critical brake.
    """
    if axial_force_n <= 0:
        raise ActuatorInputError("Axial force must be positive.")
    if lead_mm_per_rev <= 0:
        raise ActuatorInputError("Screw lead must be positive.")
    if linear_speed_mm_per_s <= 0:
        raise ActuatorInputError("Target linear speed must be positive.")
    if not 0 < efficiency <= 1:
        raise ActuatorInputError("Efficiency must be greater than zero and at most 100%.")
    if service_factor < 1:
        raise ActuatorInputError("Use a service factor of at least 1.0.")

    torque = (axial_force_n * (lead_mm_per_rev / 1000.0) / (2 * pi * efficiency)) * service_factor
    rpm = (linear_speed_mm_per_s / lead_mm_per_rev) * 60
    mechanical_power = torque * 2 * pi * rpm / 60
    input_power = axial_force_n * (linear_speed_mm_per_s / 1000.0) / efficiency * service_factor
    return ScrewDriveResult(
        torque_nm=torque,
        rotational_speed_rpm=rpm,
        mechanical_power_w=mechanical_power,
        input_power_w=input_power,
        service_factor=service_factor,
        efficiency=efficiency,
        assumptions=(
            "Steady axial motion with a lead screw; acceleration and starting torque are omitted.",
            "Efficiency represents the screw drive only; motor and gearbox losses are omitted.",
            "Confirm peak load, duty cycle, thermal limits, buckling, critical speed, and brake needs separately.",
        ),
    )

"""Time-domain simulation of a position-controlled permanent-magnet DC motor."""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class MotorSimulation:
    time_s: list[float]
    position_deg: list[float]
    current_a: list[float]
    voltage_v: list[float]
    target_deg: float
    rise_time_s: float | None
    settling_time_s: float | None
    overshoot_percent: float
    steady_state_error_deg: float
    peak_current_a: float
    saturation_percent: float


class ControlInputError(ValueError):
    pass


def simulate_dc_motor_position(
    target_deg: float,
    supply_voltage_v: float,
    duration_s: float,
    time_step_s: float,
    resistance_ohm: float,
    inductance_h: float,
    torque_constant_nm_per_a: float,
    back_emf_v_per_rad_s: float,
    inertia_kg_m2: float,
    viscous_friction_nm_per_rad_s: float,
    kp: float,
    ki: float,
    kd: float,
    load_torque_nm: float = 0.0,
) -> MotorSimulation:
    """Simulate a DC motor and saturated PID voltage controller using Euler steps.

    Electrical and rotational parameters use SI units. The controller regulates
    shaft position in radians, and its gains produce volts. Current and speed
    are integrated with a fixed, user-selected time step.
    """
    positive = {
        "target angle": target_deg, "supply voltage": supply_voltage_v,
        "duration": duration_s, "time step": time_step_s, "resistance": resistance_ohm,
        "inductance": inductance_h, "torque constant": torque_constant_nm_per_a,
        "back-emf constant": back_emf_v_per_rad_s, "rotor inertia": inertia_kg_m2,
    }
    invalid = [name for name, value in positive.items() if value <= 0]
    if invalid:
        raise ControlInputError("Values must be positive: " + ", ".join(invalid))
    if min(viscous_friction_nm_per_rad_s, kp, ki, kd, load_torque_nm) < 0:
        raise ControlInputError("Friction, PID gains, and opposing load torque cannot be negative.")
    steps = int(math.ceil(duration_s / time_step_s))
    if steps > 50000:
        raise ControlInputError("Use a time step that produces no more than 50,000 simulation steps.")
    if time_step_s > min(inductance_h / resistance_ohm, math.sqrt(inertia_kg_m2 / max(kp, 0.01))) * 0.2:
        raise ControlInputError("Time step is too large for these motor parameters; use a smaller step.")

    target = math.radians(target_deg)
    angle, speed, current = 0.0, 0.0, 0.0
    integral = 0.0
    times, positions, currents, voltages = [], [], [], []
    saturated_steps = 0
    max_current = 0.0

    for step in range(steps + 1):
        time_value = min(step * time_step_s, duration_s)
        error = target - angle
        derivative = -speed
        candidate_integral = integral + error * time_step_s
        raw_voltage = kp * error + ki * candidate_integral + kd * derivative
        voltage = max(-supply_voltage_v, min(supply_voltage_v, raw_voltage))
        saturated = abs(raw_voltage - voltage) > 1e-12
        if not saturated or (raw_voltage > supply_voltage_v and error < 0) or (raw_voltage < -supply_voltage_v and error > 0):
            integral = candidate_integral
            raw_voltage = kp * error + ki * integral + kd * derivative
            voltage = max(-supply_voltage_v, min(supply_voltage_v, raw_voltage))
        if saturated:
            saturated_steps += 1

        times.append(time_value)
        positions.append(math.degrees(angle))
        currents.append(current)
        voltages.append(voltage)
        max_current = max(max_current, abs(current))
        if step == steps:
            break
        current_rate = (voltage - resistance_ohm * current - back_emf_v_per_rad_s * speed) / inductance_h
        acceleration = (
            torque_constant_nm_per_a * current - viscous_friction_nm_per_rad_s * speed - load_torque_nm
        ) / inertia_kg_m2
        current += current_rate * time_step_s
        speed += acceleration * time_step_s
        angle += speed * time_step_s

    rise_time = next((t for t, angle_deg in zip(times, positions) if angle_deg >= 0.9 * target_deg), None)
    tolerance = max(0.5, target_deg * 0.02)
    settling_time = None
    remains_settled = True
    for index in range(len(positions) - 1, -1, -1):
        remains_settled = remains_settled and abs(positions[index] - target_deg) <= tolerance
        if remains_settled:
            settling_time = times[index]
    peak = max(positions, default=0.0)
    overshoot = max(0.0, (peak - target_deg) / target_deg * 100.0)
    return MotorSimulation(
        time_s=times,
        position_deg=positions,
        current_a=currents,
        voltage_v=voltages,
        target_deg=target_deg,
        rise_time_s=rise_time,
        settling_time_s=settling_time,
        overshoot_percent=overshoot,
        steady_state_error_deg=target_deg - positions[-1],
        peak_current_a=max_current,
        saturation_percent=100 * saturated_steps / max(steps, 1),
    )

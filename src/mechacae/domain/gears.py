"""Idealized multistage spur-gear ratio and output estimate."""
from __future__ import annotations

from dataclasses import dataclass
from math import pi


@dataclass(frozen=True)
class GearStage:
    driver_teeth: int
    driven_teeth: int
    efficiency: float = 0.95


@dataclass(frozen=True)
class GearTrainResult:
    total_ratio: float
    total_efficiency: float
    output_speed_rpm: float
    output_torque_nm: float
    output_power_w: float
    stages: int


class GearInputError(ValueError):
    pass


def calculate_gear_train(input_torque_nm: float, input_speed_rpm: float, stages: list[GearStage]) -> GearTrainResult:
    """Calculate an approximate speed/torque change from simple gear stages.

    Ratio is defined as driver speed divided by driven speed. Intermeshing
    external gears reverse direction each stage; direction is omitted here.
    """
    if input_torque_nm <= 0 or input_speed_rpm <= 0:
        raise GearInputError("Input torque and speed must be positive.")
    if not stages:
        raise GearInputError("Add at least one gear stage.")
    ratio = 1.0
    efficiency = 1.0
    for index, stage in enumerate(stages, start=1):
        if stage.driver_teeth <= 0 or stage.driven_teeth <= 0:
            raise GearInputError(f"Stage {index} tooth counts must be positive.")
        if not 0 < stage.efficiency <= 1:
            raise GearInputError(f"Stage {index} efficiency must be above 0 and at most 1.")
        ratio *= stage.driven_teeth / stage.driver_teeth
        efficiency *= stage.efficiency
    output_speed = input_speed_rpm / ratio
    output_torque = input_torque_nm * ratio * efficiency
    output_power = output_torque * 2 * pi * output_speed / 60
    return GearTrainResult(ratio, efficiency, output_speed, output_torque, output_power, len(stages))

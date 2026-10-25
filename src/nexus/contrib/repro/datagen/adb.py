"""ADB (Adaptive Driving Beam) target detection generation."""

from __future__ import annotations

import math
import random
from enum import StrEnum
from typing import Any

FOV_H_DEG = 16.0
FOV_V_DEG = 9.0
MAX_ANGLE_H = FOV_H_DEG / 2.0
MAX_ANGLE_V = FOV_V_DEG / 2.0
MIN_DISTANCE_M = 5.0
MAX_DISTANCE_M = 150.0


class TargetType(StrEnum):
    """Target classes simulated by the ADB generator."""

    CAR = "car"
    TRUCK = "truck"
    PEDESTRIAN = "pedestrian"
    BICYCLE = "bicycle"
    MOTORCYCLE = "motorcycle"


TARGET_DIMS: dict[TargetType, tuple[float, float]] = {
    TargetType.CAR: (1.8, 1.5),
    TargetType.TRUCK: (2.5, 3.0),
    TargetType.PEDESTRIAN: (0.5, 1.7),
    TargetType.BICYCLE: (0.6, 1.8),
    TargetType.MOTORCYCLE: (0.8, 1.4),
}


def calculate_edge_angles(
    center_h: float,
    center_v: float,
    distance_m: float,
    width_m: float,
    height_m: float,
) -> tuple[float, float, float, float]:
    """Calculate left/right/top/bottom angular bounds in degrees."""

    if distance_m <= 0:
        raise ValueError("distance_m must be positive")
    center_h_rad = math.radians(center_h)
    center_v_rad = math.radians(center_v)
    half_width_angle = math.atan((width_m / 2.0) / distance_m)
    half_height_angle = math.atan((height_m / 2.0) / distance_m)
    return (
        math.degrees(center_h_rad - half_width_angle),
        math.degrees(center_h_rad + half_width_angle),
        math.degrees(center_v_rad + half_height_angle),
        math.degrees(center_v_rad - half_height_angle),
    )


def _spawn_target(rng: random.Random) -> dict[str, Any]:
    target_type = rng.choice(list(TargetType))
    width, height = TARGET_DIMS[target_type]
    distance = rng.uniform(30.0, 120.0)
    angle_h = rng.uniform(-MAX_ANGLE_H * 0.8, MAX_ANGLE_H * 0.8)
    angle_v = rng.uniform(-1.0, 1.0)
    if target_type in (TargetType.PEDESTRIAN, TargetType.BICYCLE):
        relative_speed = rng.uniform(-10, 5)
    else:
        relative_speed = rng.uniform(-30, 20)
    return {
        "id": 0,
        "type": target_type,
        "distance_m": distance,
        "angle_h": angle_h,
        "angle_v": angle_v,
        "width_m": width,
        "height_m": height,
        "relative_speed_kmh": relative_speed,
    }


def generate_adb_targets(
    *,
    start_time: float,
    end_time: float,
    frequency_hz: float = 20.0,
    num_targets: int = 3,
    ego_speed_kmh: float = 60.0,
    timing_jitter_ms: int = 2,
    random_seed: int | None = None,
) -> list[dict[str, Any]]:
    """Generate ADB target detections at a fixed frequency with timing jitter."""

    if end_time <= start_time:
        raise ValueError("end_time must be after start_time")
    if frequency_hz <= 0:
        raise ValueError("frequency_hz must be positive")
    if num_targets < 0:
        raise ValueError("num_targets must be >= 0")
    if timing_jitter_ms < 0:
        raise ValueError("timing_jitter_ms must be >= 0")

    duration_s = (end_time - start_time) / 1000.0
    rng = random.Random(random_seed)
    targets = [_spawn_target(rng) for _ in range(num_targets)]
    for index, target in enumerate(targets, start=1):
        target["id"] = index

    ego_speed_ms = ego_speed_kmh / 3.6
    dt = 1.0 / frequency_hz
    records: list[dict[str, Any]] = []
    current_time_s = 0.0

    while current_time_s < duration_s:
        jitter = rng.randint(-timing_jitter_ms, timing_jitter_ms)
        timestamp_ms = start_time + current_time_s * 1000.0 + jitter
        current_targets: list[dict[str, Any]] = []

        for target in targets:
            relative_speed_ms = float(target["relative_speed_kmh"]) / 3.6
            target["distance_m"] = float(target["distance_m"]) - (ego_speed_ms - relative_speed_ms) * dt
            target["angle_h"] = float(target["angle_h"]) + rng.uniform(-0.1, 0.1)

            valid = (
                MIN_DISTANCE_M <= float(target["distance_m"]) <= MAX_DISTANCE_M
                and abs(float(target["angle_h"])) <= MAX_ANGLE_H
                and abs(float(target["angle_v"])) <= MAX_ANGLE_V
            )
            if valid:
                left, right, top, bottom = calculate_edge_angles(
                    center_h=float(target["angle_h"]),
                    center_v=float(target["angle_v"]),
                    distance_m=float(target["distance_m"]),
                    width_m=float(target["width_m"]),
                    height_m=float(target["height_m"]),
                )
                current_targets.append(
                    {
                        "id": target["id"],
                        "type": target["type"],
                        "distance_m": round(float(target["distance_m"]), 1),
                        "angle_left": round(left, 2),
                        "angle_right": round(right, 2),
                        "angle_top": round(top, 2),
                        "angle_bottom": round(bottom, 2),
                    }
                )
            else:
                new_type = rng.choice(list(TargetType))
                width, height = TARGET_DIMS[new_type]
                target["id"] = max((int(item["id"]) for item in targets), default=0) + 1
                target["type"] = new_type
                target["distance_m"] = rng.uniform(80.0, MAX_DISTANCE_M - 10)
                target["angle_h"] = rng.uniform(-MAX_ANGLE_H * 0.8, MAX_ANGLE_H * 0.8)
                target["angle_v"] = rng.uniform(-1.0, 1.0)
                target["width_m"] = width
                target["height_m"] = height
                if new_type in (TargetType.PEDESTRIAN, TargetType.BICYCLE):
                    target["relative_speed_kmh"] = rng.uniform(-10, 5)
                else:
                    target["relative_speed_kmh"] = rng.uniform(-30, 20)

        records.append({"timestamp_ms": timestamp_ms, "targets": current_targets})
        current_time_s += dt

    return records

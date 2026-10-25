"""Event-driven vehicle speed data generation."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpeedProfile:
    """A linear speed segment in km/h."""

    duration_s: float
    start_speed: float
    end_speed: float
    behavior: str = "constant"


DEFAULT_PROFILES = (
    SpeedProfile(5.0, 0, 40, "accelerate"),
    SpeedProfile(10.0, 40, 80, "accelerate"),
    SpeedProfile(15.0, 80, 80, "constant"),
    SpeedProfile(8.0, 80, 50, "decelerate"),
    SpeedProfile(7.0, 50, 50, "constant"),
)


def generate_speed(
    *,
    start_time: float,
    end_time: float,
    profiles: list[SpeedProfile] | tuple[SpeedProfile, ...] | None = None,
    max_interval_s: float = 5.0,
    change_threshold: float = 2.0,
    random_seed: int | None = None,
) -> list[dict[str, Any]]:
    """Generate event-driven speed records.

    The internal simulation runs at 100 Hz; a record is emitted when the speed
    changes by at least ``change_threshold`` or when ``max_interval_s`` elapses.
    """

    if end_time <= start_time:
        raise ValueError("end_time must be after start_time")
    duration_s = (end_time - start_time) / 1000.0
    if max_interval_s <= 0:
        raise ValueError("max_interval_s must be positive")
    if change_threshold < 0:
        raise ValueError("change_threshold must be >= 0")
    profiles = list(profiles or DEFAULT_PROFILES)
    if not profiles:
        raise ValueError("at least one speed profile is required")
    if any(profile.duration_s <= 0 for profile in profiles):
        raise ValueError("speed profile durations must be positive")

    rng = random.Random(random_seed)
    records: list[dict[str, Any]] = []
    current_time_s = 0.0
    last_recorded_time_s = 0.0
    last_recorded_speed = 0.0
    sampling_dt = 1.0 / 100.0
    profile_index = 0
    time_in_profile = 0.0

    while current_time_s < duration_s:
        if profile_index >= len(profiles):
            profile_index = len(profiles) - 1
        profile = profiles[profile_index]
        progress = min(time_in_profile / profile.duration_s, 1.0)
        speed = profile.start_speed + (profile.end_speed - profile.start_speed) * progress
        speed = max(0.0, speed + rng.uniform(-0.5, 0.5))

        changed = abs(speed - last_recorded_speed) >= change_threshold
        elapsed = (current_time_s - last_recorded_time_s) >= max_interval_s
        if not records or changed or elapsed:
            records.append(
                {
                    "timestamp_ms": start_time + current_time_s * 1000.0,
                    "speed": round(speed, 1),
                }
            )
            last_recorded_time_s = current_time_s
            last_recorded_speed = speed

        current_time_s += sampling_dt
        time_in_profile += sampling_dt
        if time_in_profile >= profile.duration_s:
            profile_index += 1
            time_in_profile = 0.0

    return records

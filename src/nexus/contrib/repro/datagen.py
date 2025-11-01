"""
Data generation utilities for repro module.

Provides functions to generate synthetic timeline, speed, and vehicle target data
for testing video data replay scenarios.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Tuple

import numpy as np

from .io import save_jsonl
from .utils import parse_time_string, parse_time_value, get_video_metadata


# =============================================================================
# Timeline Generation
# =============================================================================


def generate_timeline_with_jitter(
    fps: float,
    total_frames: int,
    start_timestamp_ms: float,
    jitter_ms: float = 1.5,
    random_seed: int | None = None,
) -> List[dict]:
    """
    Generate frame timeline with timestamp jitter to simulate real data collection.

    Real-world data collection never produces perfectly stable timestamps.
    This function adds random jitter to simulate actual capture conditions.

    Args:
        fps: Video frame rate (frames per second)
        total_frames: Number of frames in the video
        start_timestamp_ms: Starting absolute timestamp in milliseconds
        jitter_ms: Maximum jitter to add (±jitter_ms), default ±1.5ms
        random_seed: Random seed for reproducibility

    Returns:
        List of dicts with frame_index and timestamp_ms

    Example:
        >>> timeline = generate_timeline_with_jitter(
        ...     fps=30.0,
        ...     total_frames=900,  # 30 seconds
        ...     start_timestamp_ms=1759284000000.0,  # 2025-10-27 00:00:00
        ...     jitter_ms=1.5
        ... )
        >>> # Frame 0: ~1759284000000.0ms
        >>> # Frame 1: ~1759284000033.3ms ± 1.5ms
        >>> # Frame 2: ~1759284000066.7ms ± 1.5ms
    """
    if random_seed is not None:
        random.seed(random_seed)
        np.random.seed(random_seed)

    frame_duration_ms = 1000.0 / fps
    timeline = []

    for frame_idx in range(total_frames):
        # Calculate ideal timestamp
        ideal_timestamp = start_timestamp_ms + (frame_idx * frame_duration_ms)

        # Add random jitter: uniform distribution in [-jitter_ms, +jitter_ms]
        jitter = random.uniform(-jitter_ms, jitter_ms)
        actual_timestamp = ideal_timestamp + jitter

        timeline.append({
            "frame_index": frame_idx,
            "timestamp_ms": actual_timestamp,
        })

    return timeline


def save_timeline_csv(timeline: List[dict], output_path: Path) -> None:
    """
    Save timeline to CSV format.

    Args:
        timeline: List of frame timeline records
        output_path: Output CSV file path
    """
    import pandas as pd

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(timeline)
    df.to_csv(output_path, index=False)


# =============================================================================
# Speed Data Generation (Event-driven)
# =============================================================================


@dataclass
class SpeedProfile:
    """Speed profile segment for vehicle simulation."""
    duration_s: float  # Segment duration in seconds
    start_speed: float  # Starting speed (km/h)
    end_speed: float  # Ending speed (km/h)
    behavior: str  # "accelerate", "decelerate", "constant"


def generate_speed_data_event_driven(
    start_timestamp_ms: float,
    duration_s: float,
    speed_profiles: List[SpeedProfile] | None = None,
    max_interval_s: float = 5.0,
    speed_change_threshold: float = 2.0,
    random_seed: int | None = None,
) -> List[dict]:
    """
    Generate event-driven speed data.

    Speed is only recorded when:
    1. Speed changes by more than threshold
    2. At least max_interval_s has elapsed since last record

    This simulates real sensor behavior where data is sent on change,
    but with a mandatory periodic update.

    Args:
        start_timestamp_ms: Starting absolute timestamp
        duration_s: Total duration to generate data for
        speed_profiles: List of speed behavior segments (if None, uses default)
        max_interval_s: Maximum interval without sending data (default 5s)
        speed_change_threshold: Minimum speed change to trigger event (km/h)
        random_seed: Random seed for reproducibility

    Returns:
        List of dicts with timestamp_ms and speed

    Example:
        >>> profiles = [
        ...     SpeedProfile(10.0, 0, 60, "accelerate"),
        ...     SpeedProfile(20.0, 60, 60, "constant"),
        ...     SpeedProfile(10.0, 60, 30, "decelerate"),
        ... ]
        >>> speed_data = generate_speed_data_event_driven(
        ...     start_timestamp_ms=1759284000000.0,
        ...     duration_s=40.0,
        ...     speed_profiles=profiles
        ... )
    """
    if random_seed is not None:
        random.seed(random_seed)
        np.random.seed(random_seed)

    # Default speed profile: realistic driving scenario
    if speed_profiles is None:
        speed_profiles = [
            SpeedProfile(5.0, 0, 40, "accelerate"),  # Start from stop
            SpeedProfile(10.0, 40, 80, "accelerate"),  # Accelerate to highway speed
            SpeedProfile(15.0, 80, 80, "constant"),  # Cruise
            SpeedProfile(8.0, 80, 50, "decelerate"),  # Slow down
            SpeedProfile(7.0, 50, 50, "constant"),  # City speed
        ]

    speed_data = []
    current_time_s = 0.0
    last_recorded_time_s = 0.0
    last_recorded_speed = 0.0

    # Generate speed curve with high temporal resolution
    sampling_rate_hz = 100  # 100Hz internal sampling
    dt = 1.0 / sampling_rate_hz

    profile_idx = 0
    time_in_profile = 0.0

    while current_time_s < duration_s:
        # Get current profile
        if profile_idx >= len(speed_profiles):
            profile_idx = len(speed_profiles) - 1  # Stay at last profile

        profile = speed_profiles[profile_idx]

        # Calculate current speed based on profile
        progress = min(time_in_profile / profile.duration_s, 1.0)
        current_speed = profile.start_speed + (profile.end_speed - profile.start_speed) * progress

        # Add small random noise to simulate sensor noise
        current_speed += random.uniform(-0.5, 0.5)
        current_speed = max(0, current_speed)  # Speed cannot be negative

        # Check if we should record this data point
        speed_changed = abs(current_speed - last_recorded_speed) >= speed_change_threshold
        time_elapsed = (current_time_s - last_recorded_time_s) >= max_interval_s

        if speed_changed or time_elapsed or len(speed_data) == 0:
            timestamp_ms = start_timestamp_ms + (current_time_s * 1000.0)
            speed_data.append({
                "timestamp_ms": timestamp_ms,
                "speed": round(current_speed, 1),
            })
            last_recorded_time_s = current_time_s
            last_recorded_speed = current_speed

        # Advance time
        current_time_s += dt
        time_in_profile += dt

        # Move to next profile if current one finished
        if time_in_profile >= profile.duration_s:
            profile_idx += 1
            time_in_profile = 0.0

    return speed_data


# =============================================================================
# ADB Target Data Generation (Adaptive Driving Beam System)
# =============================================================================


class TargetType(str, Enum):
    """Target types detected by ADB system."""
    CAR = "car"
    TRUCK = "truck"
    PEDESTRIAN = "pedestrian"
    BICYCLE = "bicycle"
    MOTORCYCLE = "motorcycle"


def calculate_edge_angles(
    center_h: float,
    center_v: float,
    distance_m: float,
    width_m: float,
    height_m: float,
) -> Tuple[float, float, float, float]:
    """
    Calculate target edge angles from center position and dimensions.

    Args:
        center_h: Center horizontal angle (degrees)
        center_v: Center vertical angle (degrees)
        distance_m: Forward distance (meters)
        width_m: Target width (meters)
        height_m: Target height (meters)

    Returns:
        Tuple of (angle_left, angle_right, angle_top, angle_bottom) in degrees
    """
    # Convert angles to radians for calculation
    center_h_rad = np.deg2rad(center_h)
    center_v_rad = np.deg2rad(center_v)

    # Calculate half-width and half-height angular spans
    # Using small angle approximation for simplicity: tan(θ) ≈ θ for small angles
    half_width_angle = np.arctan((width_m / 2.0) / distance_m)
    half_height_angle = np.arctan((height_m / 2.0) / distance_m)

    # Calculate edge angles
    angle_left = center_h_rad - half_width_angle
    angle_right = center_h_rad + half_width_angle
    angle_top = center_v_rad + half_height_angle
    angle_bottom = center_v_rad - half_height_angle

    # Convert back to degrees
    return (
        np.rad2deg(angle_left),
        np.rad2deg(angle_right),
        np.rad2deg(angle_top),
        np.rad2deg(angle_bottom),
    )


def generate_adb_target_data(
    start_timestamp_ms: float,
    duration_s: float,
    frequency_hz: float = 20.0,
    num_targets: int = 3,
    ego_speed_kmh: float = 60.0,
    timing_jitter_ms: float = 2.0,
    random_seed: int | None = None,
) -> List[dict]:
    """
    Generate ADB (Adaptive Driving Beam) target data at specified frequency.

    Simulates targets (vehicles, pedestrians, etc.) detected in the vehicle's
    forward field of view. Target motion follows physical laws.
    Data is generated at 20Hz with realistic timing jitter.

    FOV: 16° horizontal × 9° vertical
    Detection range: 5m to 150m

    Args:
        start_timestamp_ms: Starting absolute timestamp
        duration_s: Total duration to generate data for
        frequency_hz: Target data frequency (default 20Hz)
        num_targets: Number of concurrent targets (2-3 typical)
        ego_speed_kmh: Speed of ego vehicle (km/h)
        timing_jitter_ms: Random timing error in data reception (±ms)
        random_seed: Random seed for reproducibility

    Returns:
        List of dicts with timestamp_ms and targets array

    Example:
        >>> target_data = generate_adb_target_data(
        ...     start_timestamp_ms=1759284000000.0,
        ...     duration_s=30.0,
        ...     frequency_hz=20.0,
        ...     num_targets=3,
        ...     ego_speed_kmh=60.0
        ... )
        >>> # Each record:
        >>> # {
        >>> #   "timestamp_ms": 1759284000000.0,
        >>> #   "targets": [
        >>> #     {
        >>> #       "id": 1,
        >>> #       "type": "car",
        >>> #       "distance_m": 45.2,
        >>> #       "angle_left": 1.8,
        >>> #       "angle_right": 2.8,
        >>> #       "angle_top": -0.3,
        >>> #       "angle_bottom": -0.7
        >>> #     },
        >>> #     ...
        >>> #   ]
        >>> # }
    """
    if random_seed is not None:
        random.seed(random_seed)
        np.random.seed(random_seed)

    # FOV constraints
    FOV_H_DEG = 16.0  # Horizontal FOV
    FOV_V_DEG = 9.0  # Vertical FOV
    MAX_ANGLE_H = FOV_H_DEG / 2.0
    MAX_ANGLE_V = FOV_V_DEG / 2.0
    MIN_DISTANCE_M = 5.0
    MAX_DISTANCE_M = 150.0

    # Target physical dimensions (typical values)
    TARGET_DIMS = {
        TargetType.CAR: (1.8, 1.5),  # width, height in meters
        TargetType.TRUCK: (2.5, 3.0),
        TargetType.PEDESTRIAN: (0.5, 1.7),
        TargetType.BICYCLE: (0.6, 1.8),
        TargetType.MOTORCYCLE: (0.8, 1.4),
    }

    # Initialize targets
    targets = []
    for i in range(num_targets):
        target_type = random.choice(list(TargetType))
        width, height = TARGET_DIMS[target_type]

        # Initial position
        distance = random.uniform(30.0, 120.0)
        angle_h = random.uniform(-MAX_ANGLE_H * 0.8, MAX_ANGLE_H * 0.8)
        angle_v = random.uniform(-1.0, 1.0)  # Mostly near horizon

        # Relative speed (km/h) - can be slower, same, or faster than ego
        if target_type == TargetType.PEDESTRIAN or target_type == TargetType.BICYCLE:
            relative_speed_kmh = random.uniform(-10, 5)  # Slower
        else:
            relative_speed_kmh = random.uniform(-30, 20)  # Varying speeds

        targets.append({
            "id": i + 1,
            "type": target_type,
            "distance_m": distance,
            "angle_h": angle_h,
            "angle_v": angle_v,
            "width_m": width,
            "height_m": height,
            "relative_speed_kmh": relative_speed_kmh,  # Internal use
        })

    # Generate time series data
    dt = 1.0 / frequency_hz
    target_data = []
    current_time_s = 0.0

    ego_speed_ms = ego_speed_kmh / 3.6  # Convert km/h to m/s

    while current_time_s < duration_s:
        # Add timing jitter to simulate unstable data reception
        jitter = random.uniform(-timing_jitter_ms, timing_jitter_ms)
        timestamp_ms = start_timestamp_ms + (current_time_s * 1000.0) + jitter

        # Update each target's position based on physics
        current_targets = []
        for target in targets:
            relative_speed_ms = target["relative_speed_kmh"] / 3.6

            # Update distance (closing or opening)
            # Positive ego_speed means we're approaching, negative relative_speed means target is slower
            target["distance_m"] -= (ego_speed_ms - relative_speed_ms) * dt

            # Add slight lateral movement (lane changes, pedestrian crossing)
            angle_drift = random.uniform(-0.1, 0.1)
            target["angle_h"] += angle_drift

            # Check if target is still in valid range and FOV
            if (MIN_DISTANCE_M <= target["distance_m"] <= MAX_DISTANCE_M and
                abs(target["angle_h"]) <= MAX_ANGLE_H and
                abs(target["angle_v"]) <= MAX_ANGLE_V):

                # Calculate edge angles
                angle_left, angle_right, angle_top, angle_bottom = calculate_edge_angles(
                    center_h=target["angle_h"],
                    center_v=target["angle_v"],
                    distance_m=target["distance_m"],
                    width_m=target["width_m"],
                    height_m=target["height_m"],
                )

                current_targets.append({
                    "id": target["id"],
                    "type": target["type"],
                    "distance_m": round(target["distance_m"], 1),
                    "angle_left": round(angle_left, 2),
                    "angle_right": round(angle_right, 2),
                    "angle_top": round(angle_top, 2),
                    "angle_bottom": round(angle_bottom, 2),
                })
            else:
                # Target out of range/FOV - spawn new target
                new_type = random.choice(list(TargetType))
                width, height = TARGET_DIMS[new_type]

                target["id"] = max([t["id"] for t in targets]) + 1
                target["type"] = new_type
                target["distance_m"] = random.uniform(80.0, MAX_DISTANCE_M - 10)
                target["angle_h"] = random.uniform(-MAX_ANGLE_H * 0.8, MAX_ANGLE_H * 0.8)
                target["angle_v"] = random.uniform(-1.0, 1.0)
                target["width_m"] = width
                target["height_m"] = height

                if new_type == TargetType.PEDESTRIAN or new_type == TargetType.BICYCLE:
                    target["relative_speed_kmh"] = random.uniform(-10, 5)
                else:
                    target["relative_speed_kmh"] = random.uniform(-30, 20)

        target_data.append({
            "timestamp_ms": timestamp_ms,
            "targets": current_targets,
        })

        current_time_s += dt

    return target_data


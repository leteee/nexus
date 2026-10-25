"""Deterministic generators for repro test data and synthetic video."""

from __future__ import annotations

from .adb import (
    MAX_ANGLE_H,
    MAX_ANGLE_V,
    TARGET_DIMS,
    TargetType,
    calculate_edge_angles,
    generate_adb_targets,
)
from .speed import DEFAULT_PROFILES, SpeedProfile, generate_speed
from .timeline import generate_timeline, generate_timeline_from_range, save_timeline_csv
from .video import generate_driving_video

__all__ = [
    "MAX_ANGLE_H",
    "MAX_ANGLE_V",
    "TARGET_DIMS",
    "TargetType",
    "calculate_edge_angles",
    "generate_adb_targets",
    "DEFAULT_PROFILES",
    "SpeedProfile",
    "generate_speed",
    "generate_timeline",
    "generate_timeline_from_range",
    "save_timeline_csv",
    "generate_driving_video",
]

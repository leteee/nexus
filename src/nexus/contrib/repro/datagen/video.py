"""Synthetic forward-driving video generation."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

from ..errors import OutputExistsError, VideoError
from ..models import VideoProbe

logger = logging.getLogger(__name__)


def generate_driving_video(
    output_path: Path | str,
    *,
    start_time: float,
    end_time: float,
    fps: float = 30.0,
    width: int = 1920,
    height: int = 1080,
    speed_kmh: float = 60.0,
    random_seed: int | None = None,
    overwrite: bool = False,
    progress: bool = True,
) -> VideoProbe:
    """Generate a synthetic forward-driving video with lane markings."""

    if end_time <= start_time:
        raise ValueError("end_time must be after start_time")
    if fps <= 0:
        raise ValueError("fps must be positive")
    duration_s = (end_time - start_time) / 1000.0
    if width < 2 or height < 2:
        raise ValueError("width and height must be >= 2")
    # Match generate_timeline's frame count exactly; the epsilon avoids
    # truncating exact multiples such as 2s * 30fps = 60 due to float error.
    total_frames = int(duration_s * fps + 1e-9)
    if total_frames < 1:
        raise ValueError("duration and fps produce no frames")

    output_path = Path(output_path)
    if output_path.exists() and not overwrite:
        raise OutputExistsError(f"output video already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.stem}.tmp-{uuid.uuid4().hex[:8]}{output_path.suffix}")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
    writer = cv2.VideoWriter(str(temporary), fourcc, fps, (width, height))
    if not writer.isOpened():
        temporary.unlink(missing_ok=True)
        raise VideoError(f"cannot create video writer: {temporary}")

    speed_ms = speed_kmh / 3.6
    distance_per_frame = speed_ms / fps
    horizon_y = int(height * 0.4)
    vanishing_x = width // 2
    lane_width = 3.5
    dash_length = 3.0
    dash_gap = 6.0
    distance_traveled = 0.0

    try:
        try:
            with tqdm(
                total=total_frames, desc="Generating driving video", unit="frame", disable=not progress
            ) as bar:
                for _ in range(total_frames):
                    frame = np.zeros((height, width, 3), dtype=np.uint8)
                    frame[:] = (40, 40, 40)

                    sky_top = (180, 120, 60)
                    sky_horizon = (200, 160, 100)
                    for y in range(horizon_y):
                        alpha = y / max(horizon_y, 1)
                        frame[y, :] = tuple(
                            int(sky_top[channel] * (1 - alpha) + sky_horizon[channel] * alpha)
                            for channel in range(3)
                        )
                    frame[horizon_y:, :] = (35, 35, 35)
                    _draw_lane_markings(
                        frame,
                        horizon_y=horizon_y,
                        vanishing_x=vanishing_x,
                        distance_traveled=distance_traveled,
                        lane_width=lane_width,
                        dash_length=dash_length,
                        dash_gap=dash_gap,
                    )
                    writer.write(frame)
                    distance_traveled += distance_per_frame
                    bar.update(1)
        finally:
            writer.release()
        os.replace(temporary, output_path)
    except OSError as exc:
        raise VideoError(f"cannot promote video output {output_path}: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)

    return VideoProbe(
        total_frames=total_frames,
        fps=fps,
        width=width,
        height=height,
        duration_s=duration_s,
        source=output_path,
        start_timestamp_ms=start_time,
        end_timestamp_ms=end_time,
    )


def _draw_lane_markings(
    frame: np.ndarray,
    horizon_y: int,
    vanishing_x: int,
    distance_traveled: float,
    lane_width: float,
    dash_length: float,
    dash_gap: float,
) -> None:
    """Draw perspective road lane markings in place."""

    height, width = frame.shape[:2]
    camera_height = 1.5
    focal_length_pixels = width * 0.6
    max_distance = 100.0

    for distance in np.linspace(5, max_distance, 100):
        adjusted_distance = distance - (distance_traveled % (dash_length + dash_gap))
        if adjusted_distance <= 0:
            continue
        y_screen = int(horizon_y + (camera_height * focal_length_pixels / adjusted_distance))
        if y_screen >= height or y_screen < horizon_y:
            continue
        lane_offset_pixels = int((lane_width * focal_length_pixels) / adjusted_distance)
        left_edge_x = vanishing_x - lane_offset_pixels
        if 0 <= left_edge_x < width:
            cv2.circle(frame, (left_edge_x, y_screen), 2, (200, 200, 200), -1)
        right_edge_x = vanishing_x + lane_offset_pixels
        if 0 <= right_edge_x < width:
            cv2.circle(frame, (right_edge_x, y_screen), 2, (200, 200, 200), -1)
        dash_cycle = dash_length + dash_gap
        position_in_cycle = (distance_traveled + adjusted_distance) % dash_cycle
        if position_in_cycle < dash_length:
            cv2.circle(frame, (vanishing_x, y_screen), 2, (0, 200, 200), -1)

    for y in range(horizon_y, height, 5):
        if y == horizon_y:
            continue
        distance = (camera_height * focal_length_pixels) / (y - horizon_y)
        if distance > max_distance or distance < 1:
            continue
        lane_offset_pixels = int((lane_width * focal_length_pixels) / distance)
        thickness = max(1, 3 - int(distance / 30))
        left_edge_x = vanishing_x - lane_offset_pixels
        if 0 <= left_edge_x < width:
            cv2.line(frame, (left_edge_x, y), (left_edge_x, y), (220, 220, 220), thickness)
        right_edge_x = vanishing_x + lane_offset_pixels
        if 0 <= right_edge_x < width:
            cv2.line(frame, (right_edge_x, y), (right_edge_x, y), (220, 220, 220), thickness)

"""
Video processing utilities for frame extraction and composition.

Provides functions to split videos into frames and compose frames back into video.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, List, Any, Callable, Dict

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

from .types import VideoMetadata
from .common.io import load_frame_timestamps

logger = logging.getLogger(__name__)


def extract_frames(
    video_path: Path,
    output_path: Path,
    *,
    frame_pattern: str = "frame_{:06d}.png",
) -> VideoMetadata:
    """
    Extract all frames from video and save as images.

    Args:
        video_path: Path to input video file
        output_path: Directory to save extracted frames
        frame_pattern: Filename pattern for frames (must contain one format spec)

    Returns:
        VideoMetadata with extraction info

    Example:
        >>> metadata = extract_frames(
        ...     Path("input.mp4"),
        ...     Path("frames/"),
        ...     frame_pattern="frame_{:06d}.png"
        ... )
        >>> print(f"Extracted {metadata.total_frames} frames at {metadata.fps} FPS")
    """
    video_path = Path(video_path)
    output_path = Path(output_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    output_path.mkdir(parents=True, exist_ok=True)

    # Open video
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    try:
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        logger.info(
            f"Video: {total_frames} frames, {fps:.2f} FPS, {width}x{height}"
        )

        frame_idx = 0

        with tqdm(total=total_frames, desc="Extracting frames", unit="frame") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Save frame
                frame_path = output_path / frame_pattern.format(frame_idx)
                cv2.imwrite(str(frame_path), frame)

                frame_idx += 1
                pbar.update(1)

        logger.info(f"Completed: extracted {frame_idx} frames to {output_path}")

        return VideoMetadata(
            total_frames=frame_idx,
            fps=fps,
            width=width,
            height=height,
            output_path=output_path,
        )

    finally:
        cap.release()


def compose_video(
    frames_dir: Path,
    output_path: Path,
    *,
    fps: float = 30.0,
    frame_pattern: str = "frame_{:06d}.png",
    codec: str = "mp4v",
    start_frame: int = 0,
    end_frame: Optional[int] = None,
) -> Path:
    """
    Compose video from sequence of frame images.

    Args:
        frames_dir: Directory containing frame images
        output_path: Path for output video file
        fps: Frames per second for output video
        frame_pattern: Filename pattern for frames
        codec: FourCC codec code (e.g., 'mp4v', 'XVID', 'H264')
        start_frame: First frame index to include
        end_frame: Last frame index (None = all frames)

    Returns:
        Path to created video file

    Example:
        >>> compose_video(
        ...     Path("frames/"),
        ...     Path("output.mp4"),
        ...     fps=30.0,
        ...     frame_pattern="frame_{:06d}.png"
        ... )
    """
    frames_dir = Path(frames_dir)
    output_path = Path(output_path)

    if not frames_dir.exists():
        raise FileNotFoundError(f"Frames directory not found: {frames_dir}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Find all frames
    frame_files = sorted(frames_dir.glob(frame_pattern.replace("{:06d}", "*")))
    if not frame_files:
        raise FileNotFoundError(f"No frames found in {frames_dir}")

    # Filter by frame range
    if end_frame is not None:
        frame_files = frame_files[start_frame : end_frame + 1]
    else:
        frame_files = frame_files[start_frame:]

    if not frame_files:
        raise ValueError(f"No frames in range {start_frame}-{end_frame}")

    logger.info(f"Composing video from {len(frame_files)} frames at {fps} FPS")

    # Read first frame to get dimensions
    first_frame = cv2.imread(str(frame_files[0]))
    if first_frame is None:
        raise RuntimeError(f"Failed to read frame: {frame_files[0]}")

    height, width = first_frame.shape[:2]

    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*codec)
    writer = cv2.VideoWriter(
        str(output_path),
        fourcc,
        fps,
        (width, height),
    )

    if not writer.isOpened():
        raise RuntimeError(f"Failed to create video writer: {output_path}")

    try:
        with tqdm(total=len(frame_files), desc="Composing video", unit="frame") as pbar:
            for idx, frame_path in enumerate(frame_files):
                frame = cv2.imread(str(frame_path))
                if frame is None:
                    logger.warning(f"Failed to read frame: {frame_path}, skipping")
                    continue

                writer.write(frame)
                pbar.update(1)

        logger.info(f"Completed: created video at {output_path}")
        return output_path

    finally:
        writer.release()


from .common.sensor_manager import SensorDataManager

def render_all_frames(
    frames_dir: Path,
    output_path: Path,
    timestamps_path: Path,
    sensor_configs: List[Dict[str, Any]],
    renderer_configs: List[Dict[str, Any]],
    *,
    frame_pattern: str = "frame_{:06d}.png",
    start_time_ms: Optional[float] = None,
    end_time_ms: Optional[float] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    ctx: Any,
) -> Path:
    """
    Apply multiple data renderers to all video frames using the SensorDataManager.

    This function orchestrates the entire rendering process:
    1. Sets up a SensorDataManager with all sensor sources.
    2. Instantiates all configured renderers.
    3. For each frame, gets the required data from the manager and "pushes" it to the renderer.
    """
    import importlib

    frames_dir = Path(frames_dir)
    output_path = Path(output_path)
    timestamps_path = Path(timestamps_path)

    # Validate inputs
    if not frames_dir.exists():
        raise FileNotFoundError(f"Frames directory not found: {frames_dir}")
    if not timestamps_path.exists():
        raise FileNotFoundError(f"Timestamps file not found: {timestamps_path}")

    output_path.mkdir(parents=True, exist_ok=True)

    # 1. Set up SensorDataManager
    logger.info(f"Setting up SensorDataManager with {len(sensor_configs)} sensors...")
    sensor_manager = SensorDataManager()
    for sensor_conf in sensor_configs:
        sensor_manager.register_sensor(
            name=sensor_conf["name"],
            data_path=sensor_conf["path"],
            time_offset_ms=sensor_conf.get("time_offset_ms", 0),
            tolerance_ms=sensor_conf.get("tolerance_ms", float('inf')),
        )

    # 2. Instantiate all renderers
    logger.info(f"Preparing {len(renderer_configs)} renderers...")
    renderers: List[Dict[str, Any]] = []
    for i, renderer_conf in enumerate(renderer_configs):
        class_path = renderer_conf.get("class")
        if not class_path:
            raise ValueError(f"Renderer config missing 'class' key: {renderer_conf}")

        try:
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            renderer_class = getattr(module, class_name)
        except (ValueError, ImportError, AttributeError) as e:
            raise ImportError(f"Failed to import renderer class '{class_path}': {e}")

        renderer_kwargs = renderer_conf.get("kwargs", {})
        renderer_instance = renderer_class(ctx, **renderer_kwargs)

        renderers.append({
            "instance": renderer_instance,
            "sensor": renderer_conf.get("sensor"),  # Can be None
            "strategy": renderer_conf.get("match_strategy", "forward"),  # Default to 'forward'
        })
        logger.info(f"  [{i+1}] {class_path} -> links to sensor '{renderers[-1]['sensor']}'")

    # 3. Load and filter frame timestamps
    logger.info(f"Loading frame timestamps from {timestamps_path}")
    frame_times = load_frame_timestamps(timestamps_path)

    if start_time_ms is not None:
        frame_times = frame_times[frame_times["timestamp_ms"] >= start_time_ms]
    if end_time_ms is not None:
        frame_times = frame_times[frame_times["timestamp_ms"] <= end_time_ms]

    if len(frame_times) == 0:
        logger.warning("No frames in specified time range")
        return output_path

    # 4. Render all frames
    logger.info(f"Rendering {len(frame_times)} frames...")
    rendered_count = 0
    total_frames = len(frame_times)

    with tqdm(total=total_frames, desc="Rendering frames", unit="frame", disable=progress_callback is not None) as pbar:
        for _, row in frame_times.iterrows():
            frame_idx = int(row["frame_index"])
            timestamp_ms = int(row["timestamp_ms"])

            frame_path = frames_dir / frame_pattern.format(frame_idx)
            if not frame_path.exists():
                logger.warning(f"Frame not found: {frame_path}, skipping")
                continue

            frame = cv2.imread(str(frame_path))
            if frame is None:
                logger.warning(f"Failed to read frame: {frame_path}")
                continue

            ctx.remember("current_frame_idx", frame_idx)

            # Apply all renderers sequentially using the new data-push model
            for renderer_info in renderers:
                renderer_instance = renderer_info["instance"]
                sensor_name = renderer_info["sensor"]
                strategy = renderer_info["strategy"]
                
                data_to_render = None
                if sensor_name:
                    # This is a data-driven renderer
                    if sensor_name in sensor_manager.sensors:
                        stream = sensor_manager.sensors[sensor_name]
                        data_to_render = stream.get_value_at(timestamp_ms, strategy=strategy)
                    else:
                        logger.warning(f"Sensor '{sensor_name}' not found in SensorDataManager.")
                else:
                    # This is a context-driven renderer like FrameInfoRenderer
                    data_to_render = {'snapshot_time_ms': timestamp_ms}
                
                frame = renderer_instance.render(frame, data_to_render)

            # Save rendered frame
            output_file = output_path / frame_pattern.format(frame_idx)
            cv2.imwrite(str(output_file), frame)

            rendered_count += 1
            if progress_callback:
                progress_callback(rendered_count, total_frames)
            else:
                pbar.update(1)

    logger.info(f"Completed: rendered {rendered_count} frames to {output_path}")
    return output_path


"""Video probing, frame extraction, blank-frame generation and composition."""

from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

from .errors import OutputExistsError, VideoError
from .models import ComposeResult, ExtractResult, FrameSetResult, VideoProbe
from .timeline import FramePattern, FrameTimeline


def probe_video(path: Path | str) -> VideoProbe:
    """Read basic metadata from a video file."""

    path = Path(path)
    if not path.exists():
        raise VideoError(f"video not found: {path}")
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise VideoError(f"cannot open video: {path}")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        capture.release()
    if fps <= 0 or total_frames <= 0 or width <= 0 or height <= 0:
        raise VideoError(
            f"video has invalid metadata: fps={fps}, frames={total_frames}, size={width}x{height}"
        )
    return VideoProbe(
        total_frames=total_frames,
        fps=fps,
        width=width,
        height=height,
        duration_s=total_frames / fps,
        source=path,
    )


@contextmanager
def atomic_output_dir(output_dir: Path | str, *, overwrite: bool) -> Iterator[Path]:
    """Yield an output directory and promote it atomically on success.

    Existing output is never modified unless ``overwrite=True``; in that case a
    temporary sibling is populated first and swapped into place at the end.
    """

    output_dir = Path(output_dir)
    if output_dir.exists():
        if not overwrite:
            raise OutputExistsError(f"output directory already exists: {output_dir}")
        if not output_dir.is_dir():
            raise OutputExistsError(f"output path is not a directory: {output_dir}")
        temporary = output_dir.with_name(f".{output_dir.name}.tmp-{uuid.uuid4().hex[:8]}")
        temporary.mkdir(parents=True)
        try:
            yield temporary
            if output_dir.exists():
                shutil.rmtree(output_dir)
            temporary.rename(output_dir)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
        return

    output_dir.mkdir(parents=True)
    try:
        yield output_dir
    except Exception:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise


def extract_frames(
    video_path: Path | str,
    output_dir: Path | str,
    *,
    frame_pattern: str = "frame_{:06d}.png",
    overwrite: bool = False,
    progress: bool = True,
) -> ExtractResult:
    """Extract every video frame as an image."""

    video_path = Path(video_path)
    pattern = FramePattern(frame_pattern)
    probe = probe_video(video_path)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise VideoError(f"cannot open video: {video_path}")

    try:
        with atomic_output_dir(output_dir, overwrite=overwrite) as target:
            frame_index = 0
            with tqdm(total=probe.total_frames, desc="Extracting frames", unit="frame", disable=not progress) as bar:
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    path = pattern.path_for(target, frame_index)
                    if not cv2.imwrite(str(path), frame):
                        raise VideoError(f"failed to write frame {frame_index} to {path}")
                    frame_index += 1
                    bar.update(1)
            if frame_index == 0:
                raise VideoError(f"video contains no readable frames: {video_path}")
            result = ExtractResult(output_dir=target, probe=probe, frame_count=frame_index)
        return ExtractResult(
            output_dir=Path(output_dir),
            probe=probe,
            frame_count=result.frame_count,
        )
    finally:
        capture.release()


def blank_frames(
    timeline: FrameTimeline,
    output_dir: Path | str,
    *,
    width: int,
    height: int,
    color: tuple[int, int, int] = (0, 0, 0),
    frame_pattern: str = "frame_{:06d}.png",
    overwrite: bool = False,
    progress: bool = True,
) -> FrameSetResult:
    """Generate a solid-color frame for every timeline entry."""

    pattern = FramePattern(frame_pattern)
    if width <= 0 or height <= 0:
        raise VideoError("frame width and height must be positive")
    blank = np.full((height, width, 3), color, dtype=np.uint8)
    with (
        atomic_output_dir(output_dir, overwrite=overwrite) as target,
        tqdm(total=len(timeline), desc="Generating blank frames", unit="frame", disable=not progress) as bar,
    ):
        for frame_index, _timestamp in timeline:
            path = pattern.path_for(target, frame_index)
            if not cv2.imwrite(str(path), blank):
                raise VideoError(f"failed to write blank frame {frame_index} to {path}")
            bar.update(1)
    return FrameSetResult(
        output_dir=Path(output_dir),
        frame_count=len(timeline),
        width=width,
        height=height,
    )


def compose_video(
    frames_dir: Path | str,
    output_path: Path | str,
    *,
    fps: float,
    frame_pattern: str = "frame_{:06d}.png",
    codec: str = "mp4v",
    start_frame: int | None = None,
    end_frame: int | None = None,
    overwrite: bool = False,
    progress: bool = True,
) -> ComposeResult:
    """Compose frames into a video, ordered by parsed frame index."""

    frames_dir = Path(frames_dir)
    output_path = Path(output_path)
    if fps <= 0:
        raise VideoError("fps must be positive")
    if output_path.exists() and not overwrite:
        raise OutputExistsError(f"output video already exists: {output_path}")
    pattern = FramePattern(frame_pattern)
    frames = pattern.discover(frames_dir)
    if start_frame is not None:
        frames = [(index, path) for index, path in frames if index >= start_frame]
    if end_frame is not None:
        frames = [(index, path) for index, path in frames if index <= end_frame]
    if not frames:
        raise VideoError(f"no frames selected in {frames_dir} with pattern {frame_pattern!r}")

    first = cv2.imread(str(frames[0][1]))
    if first is None:
        raise VideoError(f"cannot read first frame: {frames[0][1]}")
    height, width = first.shape[:2]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.stem}.tmp-{uuid.uuid4().hex[:8]}{output_path.suffix}")
    fourcc = cv2.VideoWriter_fourcc(*codec)  # type: ignore[attr-defined]
    writer = cv2.VideoWriter(str(temporary), fourcc, fps, (width, height))
    if not writer.isOpened():
        temporary.unlink(missing_ok=True)
        raise VideoError(f"cannot create video writer: {temporary}")
    written = 0
    try:
        try:
            with tqdm(total=len(frames), desc="Composing video", unit="frame", disable=not progress) as bar:
                for index, path in frames:
                    frame = cv2.imread(str(path))
                    if frame is None:
                        raise VideoError(f"cannot read frame {index}: {path}")
                    if frame.shape[:2] != (height, width):
                        raise VideoError(
                            f"frame {index} has size {frame.shape[1]}x{frame.shape[0]}, "
                            f"expected {width}x{height}"
                        )
                    writer.write(frame)
                    written += 1
                    bar.update(1)
        finally:
            writer.release()
        os.replace(temporary, output_path)
    except OSError as exc:
        raise VideoError(f"cannot promote video output {output_path}: {exc}") from exc
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)
    return ComposeResult(
        output_path=output_path,
        frame_count=written,
        fps=fps,
        width=width,
        height=height,
    )

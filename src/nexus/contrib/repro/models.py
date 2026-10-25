"""Domain models and configuration contracts for the repro pack."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MatchStrategy = Literal["forward", "backward", "nearest"]
MissingFramePolicy = Literal["fail", "skip"]


class ReproModel(BaseModel):
    """Base model for repro configuration objects."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, arbitrary_types_allowed=True)


class SensorSpec(ReproModel):
    """How to load and query one sensor stream."""

    path: Path = Field(description="JSONL file containing records with a numeric 'timestamp_ms'.")
    offset_ms: float = Field(default=0.0, description="Added to raw timestamps to obtain world time.")
    tolerance_ms: float = Field(
        default=math.inf,
        ge=0.0,
        description="Maximum distance between a matched record and the snapshot time.",
    )
    strategy: MatchStrategy = Field(default="forward", description="Default matching strategy.")

    @field_validator("path", mode="before")
    @classmethod
    def _expand_path(cls, value: Any) -> Any:
        return Path(value).expanduser() if value is not None else value


class SensorMatch(ReproModel):
    """A sensor record aligned to one video frame."""

    sensor: str
    raw_timestamp_ms: float
    world_timestamp_ms: float
    snapshot_ms: float
    delta_ms: float
    strategy: MatchStrategy
    tolerance_ms: float
    data: dict[str, Any] = Field(default_factory=dict)


class RendererSpec(ReproModel):
    """Configuration for one renderer instance."""

    type: str = Field(description="Registered renderer type, for example 'speed'.")
    sensors: dict[str, str] = Field(
        default_factory=dict,
        description="Role -> sensor name mapping. A list of names is accepted as role == name.",
    )
    config: dict[str, Any] = Field(default_factory=dict, description="Renderer-specific configuration.")
    enabled: bool = Field(default=True, description="Set to false to skip this renderer.")

    @field_validator("sensors", mode="before")
    @classmethod
    def _coerce_sensors(cls, value: Any) -> Any:
        if value is None:
            return {}
        if isinstance(value, str):
            return {value: value}
        if isinstance(value, (list, tuple, set)):
            return {str(item): str(item) for item in value}
        if isinstance(value, dict):
            return {str(key): str(item) for key, item in value.items()}
        raise ValueError("renderer.sensors must be a list, string or mapping")


@dataclass(frozen=True)
class VideoProbe:
    """Basic metadata for a video file."""

    total_frames: int
    fps: float
    width: int
    height: int
    duration_s: float
    source: Path | None = None
    start_timestamp_ms: float | None = None
    end_timestamp_ms: float | None = None


@dataclass(frozen=True)
class ExtractResult:
    """Result of extracting frames from a video."""

    output_dir: Path
    probe: VideoProbe
    frame_count: int


@dataclass(frozen=True)
class FrameSetResult:
    """Result of generating a directory of frames."""

    output_dir: Path
    frame_count: int
    width: int
    height: int


@dataclass(frozen=True)
class ComposeResult:
    """Result of composing a video from frames."""

    output_path: Path
    frame_count: int
    fps: float
    width: int
    height: int


@dataclass
class RenderRequest:
    """Inputs for one replay rendering run."""

    frames_dir: Path
    timeline: Any  # FrameTimeline or path to a timeline CSV
    output_dir: Path
    sensors: dict[str, SensorSpec] = field(default_factory=dict)
    renderers: list[RendererSpec] = field(default_factory=list)
    start_ms: float | None = None
    end_ms: float | None = None
    start_frame: int | None = None
    end_frame: int | None = None
    workers: int = 1
    overwrite: bool = False
    missing_frame: MissingFramePolicy = "fail"
    frame_pattern: str = "frame_{:06d}.png"
    progress: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.frames_dir = Path(self.frames_dir).expanduser()
        self.output_dir = Path(self.output_dir).expanduser()
        if self.workers < 1:
            raise ValueError("workers must be >= 1")


@dataclass(frozen=True)
class RenderResult:
    """Outcome of one replay rendering run."""

    output_dir: Path
    frame_count: int
    rendered_count: int
    skipped_count: int
    duration_ms: float
    workers: int
    renderers: tuple[str, ...]
    sensors: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

"""Exception hierarchy for the repro pack."""

from __future__ import annotations


class ReproError(Exception):
    """Base class for repro errors."""


class TimelineError(ReproError):
    """A timeline or frame pattern is invalid."""


class SensorDataError(ReproError):
    """A sensor JSONL file is invalid or unreadable."""


class RendererError(ReproError):
    """A renderer type or its configuration is invalid."""


class CameraError(ReproError):
    """Camera calibration or projection is invalid."""


class VideoError(ReproError):
    """Video probing, extraction or composition failed."""


class OutputExistsError(ReproError):
    """An output directory already contains data."""


class MissingFrameError(ReproError):
    """A frame referenced by the timeline is missing or unreadable."""

"""Replay rendering pipeline: timeline + sensors + renderers -> frames."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import cv2
from tqdm import tqdm

from .errors import MissingFrameError, RendererError, TimelineError, VideoError
from .models import (
    RendererSpec,
    RenderRequest,
    RenderResult,
    SensorMatch,
)
from .renderers import (
    RenderContext,
    Renderer,
    RendererRegistry,
    default_renderer_registry,
)
from .sensors import SensorStore
from .timeline import FramePattern, FrameTimeline
from .video import atomic_output_dir


@dataclass(frozen=True)
class _Binding:
    spec: RendererSpec
    renderer: Renderer
    sensor_roles: dict[str, str]
    needed_sensors: frozenset[str]


class ReplayPipeline:
    """Coordinates frame loading, sensor matching and renderer execution."""

    def __init__(self, registry: RendererRegistry | None = None) -> None:
        self.registry = registry or default_renderer_registry

    def render(self, request: RenderRequest) -> RenderResult:
        started = time.perf_counter()
        frames_dir = Path(request.frames_dir)
        if not frames_dir.is_dir():
            raise VideoError(f"frames directory not found: {frames_dir}")

        timeline = self._load_timeline(request)
        timeline = self._filter_timeline(timeline, request)
        pattern = FramePattern(request.frame_pattern)

        active_specs = [spec for spec in request.renderers if spec.enabled]
        with SensorStore(request.sensors) as sensors:
            bindings = self._build_bindings(active_specs, sensors)
            needed_sensors = frozenset().union(*(binding.needed_sensors for binding in bindings)) if bindings else frozenset()

            with atomic_output_dir(request.output_dir, overwrite=request.overwrite) as target:
                skipped = self._render_frames(
                    request=request,
                    timeline=timeline,
                    pattern=pattern,
                    frames_dir=frames_dir,
                    target=target,
                    sensors=sensors,
                    bindings=bindings,
                    needed_sensors=needed_sensors,
                )

        duration_ms = (time.perf_counter() - started) * 1000
        return RenderResult(
            output_dir=Path(request.output_dir),
            frame_count=len(timeline),
            rendered_count=len(timeline) - skipped,
            skipped_count=skipped,
            duration_ms=duration_ms,
            workers=request.workers,
            renderers=tuple(spec.type for spec in active_specs),
            sensors=tuple(request.sensors),
            metadata={
                "frames_dir": str(frames_dir),
                "timeline": str(request.timeline) if isinstance(request.timeline, (str, Path)) else "<memory>",
                "frame_pattern": request.frame_pattern,
                "range": {
                    "start_ms": request.start_ms,
                    "end_ms": request.end_ms,
                    "start_frame": request.start_frame,
                    "end_frame": request.end_frame,
                },
                **request.metadata,
            },
        )

    # -- setup ------------------------------------------------------------

    @staticmethod
    def _load_timeline(request: RenderRequest) -> FrameTimeline:
        if isinstance(request.timeline, FrameTimeline):
            return request.timeline
        return FrameTimeline.from_csv(request.timeline)

    @staticmethod
    def _filter_timeline(timeline: FrameTimeline, request: RenderRequest) -> FrameTimeline:
        try:
            return timeline.filter(
                start_ms=request.start_ms,
                end_ms=request.end_ms,
                start_frame=request.start_frame,
                end_frame=request.end_frame,
            )
        except TimelineError as exc:
            raise TimelineError(f"timeline selection failed: {exc}") from exc

    def _build_bindings(self, specs: list[RendererSpec], sensors: SensorStore) -> list[_Binding]:
        bindings: list[_Binding] = []
        available = set(sensors.names)
        for spec in specs:
            try:
                renderer = self.registry.create(spec)
            except RendererError as exc:
                raise RendererError(f"cannot create renderer '{spec.type}': {exc}") from exc
            for role, sensor_name in spec.sensors.items():
                if sensor_name not in available:
                    raise RendererError(
                        f"renderer '{spec.type}' role '{role}' references unknown sensor "
                        f"'{sensor_name}'; available: {', '.join(sorted(available)) or '(none)'}"
                    )
            bindings.append(
                _Binding(
                    spec=spec,
                    renderer=renderer,
                    sensor_roles=dict(spec.sensors),
                    needed_sensors=frozenset(spec.sensors.values()),
                )
            )
        return bindings

    # -- rendering --------------------------------------------------------

    def _render_frames(
        self,
        *,
        request: RenderRequest,
        timeline: FrameTimeline,
        pattern: FramePattern,
        frames_dir: Path,
        target: Path,
        sensors: SensorStore,
        bindings: list[_Binding],
        needed_sensors: frozenset[str],
    ) -> int:
        items = list(zip(timeline.frame_indices.tolist(), timeline.timestamps_ms.tolist(), strict=True))
        skipped = 0

        def render_one(index: int, timestamp_ms: float) -> bool:
            frame_path = pattern.path_for(frames_dir, index)
            frame = cv2.imread(str(frame_path))
            if frame is None:
                if request.missing_frame == "skip":
                    return False
                raise MissingFrameError(f"frame {index} is missing or unreadable: {frame_path}")
            matches: dict[str, SensorMatch | None] = {
                name: sensors.match(name, timestamp_ms) for name in needed_sensors
            }
            for binding in bindings:
                context = RenderContext(
                    frame_index=index,
                    timestamp_ms=timestamp_ms,
                    sensors={role: matches.get(sensor_name) for role, sensor_name in binding.sensor_roles.items()},
                    metadata={"sensor_names": binding.sensor_roles},
                )
                rendered = binding.renderer.render(frame, context)
                if rendered is None:
                    raise RendererError(f"renderer '{binding.spec.type}' returned None for frame {index}")
                frame = rendered
            output_path = pattern.path_for(target, index)
            if not cv2.imwrite(str(output_path), frame):
                raise VideoError(f"failed to write frame {index} to {output_path}")
            return True

        if request.workers <= 1:
            with tqdm(total=len(items), desc="Rendering frames", unit="frame", disable=not request.progress) as bar:
                for index, timestamp_ms in items:
                    if not render_one(index, timestamp_ms):
                        skipped += 1
                    bar.update(1)
            return skipped

        with (
            ThreadPoolExecutor(max_workers=request.workers, thread_name_prefix="repro-render") as pool,
            tqdm(total=len(items), desc="Rendering frames", unit="frame", disable=not request.progress) as bar,
        ):
            futures = {
                pool.submit(render_one, index, timestamp_ms): index for index, timestamp_ms in items
            }
            try:
                for future in as_completed(futures):
                    if not future.result():
                        skipped += 1
                    bar.update(1)
            except Exception:
                for future in futures:
                    future.cancel()
                raise
        return skipped

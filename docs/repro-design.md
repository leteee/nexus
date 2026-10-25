# Repro Design (Nexus 2.0)

`nexus.contrib.repro` is an optional domain pack for video data replay. It
aligns time-series sensor data to video frames, renders typed overlays and
composes the result back into a video. The pack is independent of the Nexus
core; installing `nexus[repro]` adds `numpy`, `opencv-python-headless` and
`tqdm`.

This document describes the current 2.0 design. It is a reference for the
implementation and for teams building similar domain packs.

## Package layout

```text
src/nexus/contrib/repro/
├── __init__.py              # public domain API
├── models.py                # Pydantic configs + domain models
├── timeline.py              # FrameTimeline, FramePattern
├── sensors.py               # SensorSpec, SensorStore, SensorMatch
├── video.py                 # probe / extract / blank / compose
├── render.py                # ReplayPipeline, match cache, workers
├── camera.py                # CameraModel, target projection
├── text.py                  # TextboxStyle, draw_textbox
├── datagen/
│   ├── timeline.py
│   ├── speed.py
│   ├── adb.py
│   └── video.py
├── renderers/
│   ├── base.py              # Renderer ABC, RenderContext, registry
│   ├── frame_info.py
│   ├── speed.py
│   └── targets.py
├── nodes.py                 # Nexus node adapters
├── camera_calibration.json  # default 1920x1080 calibration
└── README.md
```

## Time model

All public timestamps are Unix milliseconds. Flow-facing nodes use
`start_time` / `end_time` bounds (ISO datetime, `datetime` or milliseconds);
duration is an internal derivation. Sensor world time is:

```text
world_timestamp_ms = raw_timestamp_ms + offset_ms
```

Matching strategies:

| Strategy | Meaning |
| --- | --- |
| `forward` | Latest record with `world_timestamp_ms <= snapshot_ms`. |
| `backward` | Earliest record with `world_timestamp_ms >= snapshot_ms`. |
| `nearest` | Closest record by absolute delta. |

A match is rejected when `abs(world_timestamp_ms - snapshot_ms) > tolerance_ms`.
Every match carries `sensor`, `raw_timestamp_ms`, `world_timestamp_ms`,
`snapshot_ms`, `delta_ms`, `strategy`, `tolerance_ms` and the decoded `data`.

## SensorStore

`SensorStore` owns named `SensorReader` objects:

```python
store.match("speed", snapshot_ms) -> SensorMatch | None
store.snapshot(snapshot_ms) -> dict[str, SensorMatch | None]
```

`SensorReader` scans JSONL once and stores sorted timestamp, byte-offset and
line-length arrays. Record bodies are read on demand with `os.pread`, so memory
scales with the number of records rather than JSON payload size. During
rendering, one match per sensor per frame is shared by all renderers.

## Camera calibration

`CameraModel` loads an OpenCV-style calibration and projects ADB target angles
into image coordinates. Calibration is used as-is: `image_width` /
`image_height` must match the rendered frame. Nexus does not rescale intrinsics
automatically across resolutions or aspect ratios; a mismatch raises
`CameraError` and asks for a calibration matching the video.

The default calibration targets 1920x1080. Smaller example videos use an
explicit matching calibration, such as `flows/repro/camera_320x240.json`.

## Renderers

```python
class RenderContext(BaseModel):
    frame_index: int
    timestamp_ms: float
    sensors: Mapping[str, SensorMatch | None]
    metadata: Mapping[str, Any]

class Renderer(ABC):
    name: ClassVar[str]
    Config: ClassVar[type[BaseModel]]

    def __init__(self, config: BaseModel) -> None: ...
    @abstractmethod
    def render(self, frame: np.ndarray, context: RenderContext) -> np.ndarray: ...
```

Built-in types:

| Type | Role default | Draws |
| --- | --- | --- |
| `frame_info` | none | frame index + formatted timestamp |
| `speed` | `speed` | speed and timestamp traceability |
| `target` | `targets` | ADB target boxes + info panel |

Renderers are registered with `@register_renderer("type")`. YAML uses `type` +
typed `config`; renderers never load files or query sensors themselves. A
custom pack registers its renderers at import time.

## Render pipeline

```python
pipeline = ReplayPipeline()
result = pipeline.render(
    RenderRequest(
        frames_dir=...,
        timeline=...,
        output_dir=...,
        sensors={"speed": SensorSpec(...)},
        renderers=[RendererSpec(type="speed", sensors={"speed": "speed"}, config={...})],
        start_ms=...,
        end_ms=...,
        workers=1,
        overwrite=False,
    )
)
```

The pipeline guarantees:

- timeline validation (`frame_index`, `timestamp_ms`, monotonic ordering);
- frame discovery through `FramePattern`, not ad-hoc glob rules;
- one sensor match per frame, reused across renderers;
- explicit overwrite; when enabled, output is built in a temp directory and
  atomically promoted;
- `workers > 1` renders frames concurrently with deterministic output;
- missing/corrupt frames fail with frame index and path, or are skipped when
  `missing_frame="skip"`.

## Datagen

Generators use instance-local RNGs and never mutate global `random` state:

- `generate_timeline(...) -> list[dict]`
- `generate_speed(...) -> list[dict]`
- `generate_adb_targets(...) -> list[dict]`
- `generate_driving_video(...) -> VideoProbe`

The same seed produces byte-identical JSONL/CSV. Video generation writes through
a temporary file and atomically promotes the result.

## Nexus nodes

| Node | Purpose |
| --- | --- |
| `repro.datagen.video` | Generate a synthetic forward-driving video. |
| `repro.datagen.timeline` | Build a timeline CSV with jitter. |
| `repro.timeline.from_range` | Build a timeline from `start_time` / `end_time`. |
| `repro.datagen.speed` | Event-driven speed JSONL. |
| `repro.datagen.adb` | ADB target detections JSONL. |
| `repro.video.split` | Extract frames from a video. |
| `repro.render.frames` | Render typed sensor overlays. |
| `repro.video.blank_frames` | Generate solid-color frames from a timeline. |
| `repro.video.compose` | Compose frames into a video. |

The nodes are thin adapters: they resolve paths, parse time bounds and map
domain results to step outputs.

## Non-goals

- Audio, VFR/timecode, GPU rendering, remote object storage.
- Replacing OpenCV.
- A new database or message queue.
- Automatic camera-intrinsic rescaling.

## Quality gates

- Unit tests for matching strategies, offsets, tolerance, timeline validation,
  frame patterns, camera calibration and datagen determinism.
- A tiny end-to-end flow: datagen → split → render → compose, with assertions on
  output dimensions, fps and frame count.
- `pytest`, `ruff` and `mypy` pass; optional repro tests skip without extras.

# Repro (Nexus 2.0)

Optional video data replay pack for Nexus 2.0. It aligns time-series sensor
data to video frames, renders typed overlays, and composes the result back into
a video. It also generates reproducible synthetic video/data for testing.

The pack is framework-independent at its core; [`nodes.py`](nodes.py) is a thin
Nexus adapter. The Nexus engine never imports repro, so OpenCV/numpy stay
optional.

## Install

```bash
pip install -e ".[repro]"
```

Dependencies: `numpy`, `opencv-python-headless`, `tqdm` (no pandas).

After installation the `nexus.nodes` entry point exposes nine nodes:

| Node | Purpose |
| --- | --- |
| `repro.datagen.video` | Generate a synthetic forward-driving video. |
| `repro.datagen.timeline` | Build a frame timeline CSV with jitter. |
| `repro.timeline.from_range` | Build a timeline from start/end time + fps. |
| `repro.datagen.speed` | Event-driven speed JSONL. |
| `repro.datagen.adb` | ADB target detections JSONL. |
| `repro.video.split` | Extract frames from a video. |
| `repro.render.frames` | Render sensor overlays using `ReplayPipeline`. |
| `repro.video.compose` | Compose frames into a video. |
| `repro.video.blank_frames` | Generate solid-color frames from a timeline. |

From a source tree without installing, add:

```yaml
# config/nexus.yaml
node_modules:
  - "nexus.contrib.repro.nodes"
```

## Architecture

```text
models.py        typed config + domain models
timeline.py      FrameTimeline, TimeRange, FramePattern
sensors.py       indexed JSONL SensorReader, SensorStore, matching
camera.py        CameraModel, target projection, calibration resolution check
text.py          TextboxStyle, safe coordinate evaluation, drawing
video.py         probe / extract / blank frames / compose
render.py        ReplayPipeline: cache matches, optional ordered workers
renderers/       Renderer ABC, registry, frame_info / speed / target
datagen/         deterministic timeline, speed, ADB and synthetic video
nodes.py         Nexus node adapters
```

### Time model

Flow-facing repro nodes use `start_time` / `end_time` (ISO datetime, `datetime`
or Unix milliseconds). Do not pass a duration to repro nodes; duration is derived
internally from the two bounds. All timestamps are Unix milliseconds. Sensor
world time is:

```text
world_timestamp_ms = raw_timestamp_ms + offset_ms
```

`SensorSpec.strategy` selects:

| Strategy | Match |
| --- | --- |
| `forward` | latest record with `world_timestamp_ms <= snapshot_ms` |
| `backward` | earliest record with `world_timestamp_ms >= snapshot_ms` |
| `nearest` | closest record by absolute delta |

A match is rejected when `abs(delta) > tolerance_ms`. The result carries
`sensor`, `raw_timestamp_ms`, `world_timestamp_ms`, `snapshot_ms`, `delta_ms`,
`strategy`, `tolerance_ms` and the decoded `data`.

`SensorReader` scans the JSONL once and keeps only timestamp/byte-offset/
line-length arrays. Record bodies are read with `os.pread`, so memory does not
scale with JSON payload size.

### Rendering

```yaml
- id: render
  use: repro.render.frames
  with:
    frames_dir: "${steps.split.frames_dir}"
    timeline: "temp/timeline.csv"
    output_dir: "temp/rendered_frames"
    workers: 2
    overwrite: true
    sensors:
      speed:
        path: "input/speed.jsonl"
        offset_ms: 0
        tolerance_ms: 5000
        strategy: forward
      targets:
        path: "input/adb_targets.jsonl"
        offset_ms: 0
        tolerance_ms: 50
        strategy: nearest
    renderers:
      - type: frame_info
        config:
          format: datetime
          style: "${vars.textbox_base}"
      - type: speed
        sensors: {speed: speed}
        config:
          show_timestamp: true
          style: "${merge(vars.textbox_base, {'text_color': [0, 255, 0]})}"
      - type: target
        sensors: {targets: targets}
        config:
          camera: auto
          display: angle
          style: "${vars.textbox_base}"
```

`type` resolves through the typed renderer registry; `class`/`kwargs` import
paths are gone. `sensors` maps renderer roles to named sensors, so one renderer
can consume multiple sensors.

### Camera calibration

`TargetRenderer` requires a calibration file whose `image_width`/`image_height`
match the video resolution. There is **no automatic intrinsic scaling**: a
1920x1080 calibration will be rejected for a 320x240 frame (and vice versa)
instead of silently producing distorted boxes. Use `camera: auto` for the
default 1920x1080 calibration, which the demo uses.

`flows/repro/camera_320x240.json` is a small fixture for intentionally 320x240
test clips; pass it explicitly only for those:

```bash
-s camera=flows/repro/camera_320x240.json
```

`ReplayPipeline`:

- validates the timeline and filters by time or frame index;
- caches one match per sensor per frame across renderers;
- writes into a temporary directory and atomically replaces the output when
  `overwrite: true`;
- supports ordered deterministic concurrency via `workers`;
- fails with the frame index/path on missing/corrupt frames (or skips them with
  `missing_frame: skip`).

## End-to-end example

```bash
# Defaults: 1920x1080 @ 30fps; the 2s range keeps the demo quick.
nexus run repro/repro_datagen -w runs/repro-data \
  -s start_time="2025-10-27 08:30:00" \
  -s end_time="2025-10-27 08:30:02"

nexus run repro/repro -w runs/repro-data \
  -s start_time="2025-10-27 08:30:00" \
  -s end_time="2025-10-27 08:30:02"
```

`camera: auto` matches the demo's 1920x1080 frames. Without the time overrides,
the datagen flow produces 20s at 30fps and the replay flow renders the default
`08:30:10–08:30:20` window (still 1920x1080).

The datagen flow writes `input/synthetic_driving.mp4`, `temp/timeline.csv`,
`input/speed.jsonl` and `input/adb_targets.jsonl`. The replay flow extracts
frames, renders `frame_info`, `speed` and `target`, then composes
`output/repro.mp4`.

See [`flows/repro/`](../../../../flows/repro) for the complete YAML and
[`docs/repro-design.md`](../../../../docs/repro-design.md) for the
design contract.

## Datagen determinism

All generators use an instance-local RNG (`random.Random(seed)` /
`numpy.random.default_rng(seed)`); they never mutate the global `random` or
`numpy.random` state. The same seed produces byte-identical JSONL/CSV.

## Tests

```bash
pytest tests/test_repro*.py
```

The tests cover matching strategies, offsets/tolerances, timeline validation,
frame patterns, camera calibration/projection, renderer determinism, overwrite
semantics, datagen determinism and a tiny end-to-end video pipeline. They are
skipped automatically when optional dependencies are missing.

# Renderers

A renderer draws already-matched data onto one frame. It does not load files,
query sensors or know about Nexus contexts.

## Contract

```python
from nexus.contrib.repro.renderers import RenderContext, Renderer, register_renderer
from nexus.contrib.repro.models import ReproModel

class MyConfig(ReproModel):
    color: tuple[int, int, int] = (0, 255, 0)

@register_renderer("my_renderer")
class MyRenderer(Renderer[MyConfig]):
    Config = MyConfig

    def render(self, frame, context: RenderContext):
        match = context.sensors.get("my_sensor")
        if match is not None:
            # draw with cv2 ...
            pass
        return frame
```

`RenderContext` exposes:

- `frame_index` and `timestamp_ms`;
- `sensors`: renderer-role -> `SensorMatch | None`;
- `metadata`: optional per-run metadata.

`RendererSpec.sensors` in YAML maps roles to sensor names:

```yaml
- type: speed
  sensors: {speed: vehicle_speed}
  config:
    style: {position: {x: "width - 10", y: 30, anchor: top_right}}
```

## Built-in types

| Type | Role default | Draws |
| --- | --- | --- |
| `frame_info` | none | frame index + formatted timestamp |
| `speed` | `speed` | speed + optional data/snapshot timestamps |
| `target` | `targets` | projected ADB boxes + info panel |

## Styling

`TextboxStyle` is a typed Pydantic model:

```yaml
style:
  text_color: [0, 255, 255]
  outline_color: [0, 0, 0]
  outline_thickness: 3
  position: {x: "width - 10", y: 30, anchor: top_right}
  font: {scale: 0.8, thickness: 1, line_spacing: 1.5}
  panel: {enabled: true, padding: 10, bg_color: [40, 40, 40]}
```

Coordinates are evaluated without `eval`; supported expressions are integer
literals, `width`, `height`, parentheses and `+ - * / // %`.

See [`flows/repro/repro.yaml`](../../../../../flows/repro/repro.yaml) for a full
configuration.

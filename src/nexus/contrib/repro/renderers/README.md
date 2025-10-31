# 可扩展数据渲染器架构

## 设计理念

这个架构允许用户通过实现简单的类来扩展系统，轻松将新类型的数据叠加到视频帧上。

### 核心特性

1. **单一职责**：每个 Renderer 只负责一种数据类型
2. **配置驱动**：通过 YAML 配置即可组合多个渲染器
3. **易于扩展**：继承 `BaseDataRenderer` 实现 `render()` 即可
4. **内置匹配策略**：提供 nearest/forward/backward 三种时间匹配策略

---

## 架构组件

### 1. 基类层级

```
DataRenderer (抽象接口)
    ↓
BaseDataRenderer (带匹配策略的基类)
    ↓
SpeedRenderer / TargetRenderer / GPSRenderer (具体实现)
```

### 2. 文件组织

```
src/nexus/contrib/repro/
├── types.py                      # DataRenderer 抽象接口
└── renderers/
    ├── __init__.py               # 导出所有渲染器
    ├── base.py                   # BaseDataRenderer 基类
    ├── speed_renderer.py         # 速度渲染器
    ├── target_renderer.py        # 目标渲染器
    └── example_gps_renderer.py   # GPS 示例（展示如何扩展）
```

---

## 使用方式

### 方式 1：直接使用（编程式）

```python
from nexus.contrib.repro.renderers import SpeedRenderer, TargetRenderer

# 创建渲染器
speed_renderer = SpeedRenderer(
    data_path="input/speed.jsonl",
    position=(30, 60),
    tolerance_ms=5000.0,
)

target_renderer = TargetRenderer(
    data_path="input/adb_targets.jsonl",
    calibration_path="camera_calibration.yaml",
    tolerance_ms=50.0,
)

# 渲染帧
frame = cv2.imread("frame_0000.png")
timestamp_ms = 1761525000000.0

frame = speed_renderer.render(frame, timestamp_ms)
frame = target_renderer.render(frame, timestamp_ms)
```

### 方式 2：配置驱动（推荐）

**YAML 配置示例**：

```yaml
pipeline:
  - plugin: "Video Splitter"
    config:
      video_path: "input/vehicle.mp4"
      output_dir: "temp/frames"

  - plugin: "Data Renderer"
    config:
      frames_dir: "temp/frames"
      output_dir: "temp/rendered_frames"
      renderers:
        - class: "nexus.contrib.repro.renderers.SpeedRenderer"
          kwargs:
            data_path: "input/speed.jsonl"
            position: [30, 60]
            tolerance_ms: 5000

        - class: "nexus.contrib.repro.renderers.TargetRenderer"
          kwargs:
            data_path: "input/adb_targets.jsonl"
            calibration_path: "camera_calibration.yaml"
            tolerance_ms: 50

        - class: "custom.GPSRenderer"
          kwargs:
            data_path: "input/gps.jsonl"
            position: [20, 100]

  - plugin: "Video Composer"
    config:
      frames_dir: "temp/rendered_frames"
      output_path: "output/result.mp4"
```

---

## 如何扩展：添加新的数据类型

### 步骤 1：实现自定义 Renderer

```python
from nexus.contrib.repro.renderers import BaseDataRenderer
import cv2
import numpy as np

class GPSRenderer(BaseDataRenderer):
    """渲染 GPS 坐标"""

    def __init__(self, data_path, position=(20, 100), tolerance_ms=1000.0):
        # 调用基类初始化（自动加载数据）
        super().__init__(
            data_path=data_path,
            tolerance_ms=tolerance_ms,
            match_strategy="nearest",  # 使用最近匹配
        )
        self.position = position

    def render(self, frame, timestamp_ms):
        # 1. 匹配数据（基类提供）
        matched = self.match_data(timestamp_ms)
        if not matched:
            return frame

        # 2. 提取数据
        gps = matched[0]
        lat = gps.get("lat", 0.0)
        lon = gps.get("lon", 0.0)

        # 3. 渲染到帧上
        text = f"GPS: {lat:.6f}°, {lon:.6f}°"
        cv2.putText(frame, text, self.position, ...)

        return frame
```

### 步骤 2：数据文件格式（JSONL）

```jsonl
{"timestamp_ms": 1759284000000.0, "lat": 39.9042, "lon": 116.4074}
{"timestamp_ms": 1759284001000.0, "lat": 39.9043, "lon": 116.4075}
```

### 步骤 3：配置使用

```yaml
renderers:
  - class: "myproject.GPSRenderer"
    kwargs:
      data_path: "input/gps.jsonl"
      position: [20, 100]
      tolerance_ms: 1000
```

**完成！** 新的数据类型已集成到渲染流程。

---

## 内置渲染器

### SpeedRenderer

**功能**：渲染车速数据

**参数**：
- `data_path`: 速度数据文件路径（JSONL）
- `position`: 文字位置 `(x, y)`，默认 `(30, 60)`
- `tolerance_ms`: 匹配容忍度，默认 `5000` ms（前向匹配）
- `font_scale`: 字体大小，默认 `1.2`
- `color`: 颜色 BGR，默认绿色 `(0, 255, 0)`

**数据格式**：
```jsonl
{"timestamp_ms": 1759284000000.0, "speed": 120.5}
```

**匹配策略**：Forward（前向匹配，速度"保持"直到下次更新）

---

### TargetRenderer

**功能**：渲染 3D 目标检测框（投影到 2D）

**参数**：
- `data_path`: 目标数据文件路径（JSONL）
- `calibration_path`: 相机标定文件路径（YAML）
- `tolerance_ms`: 匹配容忍度，默认 `50` ms（最近匹配）
- `box_color`: 框颜色 BGR，默认绿色 `(0, 255, 0)`
- `show_panel`: 是否显示信息面板，默认 `True`

**数据格式**：
```jsonl
{
  "timestamp_ms": 1761524999999.678,
  "targets": [
    {
      "id": 1,
      "type": "car",
      "distance_m": 31.5,
      "angle_left": -4.53,
      "angle_right": -1.25,
      "angle_top": 0.81,
      "angle_bottom": -1.92
    }
  ]
}
```

**标定格式**（YAML）：
```yaml
camera:
  intrinsics:
    fx: 1000.0
    fy: 1000.0
    cx: 960.0
    cy: 540.0
  extrinsics:
    translation: {x: 0.0, y: 0.0, z: 1.5}
    rotation: {roll: 0.0, pitch: 0.0, yaw: 0.0}
  resolution:
    width: 1920
    height: 1080
```

**匹配策略**：Nearest（最近匹配）

---

## 匹配策略说明

BaseDataRenderer 提供三种时间匹配策略：

### 1. Nearest（最近匹配）

选择时间戳最接近的数据点（双向）。

**适用场景**：高频数据（如目标检测 20Hz）

```python
match_strategy="nearest"
```

### 2. Forward（前向匹配）

选择时间戳 **≤ 当前帧** 的最新数据。

**适用场景**：低频数据需要"保持"（如速度、GPS）

```python
match_strategy="forward"
```

### 3. Backward（后向匹配）

选择时间戳 **≥ 当前帧** 的最早数据。

**适用场景**：预测数据、前瞻场景

```python
match_strategy="backward"
```

---

## 完整工作流程

```
视频文件 (vehicle.mp4)
    ↓
[Video Splitter] 切分成帧 + 时间戳
    ↓
帧图片 (frame_0000.png, ...) + timestamps.csv
    ↓
[Data Renderer] 应用多个渲染器
    ├─ SpeedRenderer     → 叠加速度
    ├─ TargetRenderer    → 叠加目标框
    └─ GPSRenderer       → 叠加 GPS
    ↓
渲染后的帧 (rendered_0000.png, ...)
    ↓
[Video Composer] 合成视频
    ↓
最终视频 (result.mp4)
```

---

## 最佳实践

### 1. 数据格式统一

所有数据文件使用 **JSONL** 格式，每行一个 JSON 对象：

```jsonl
{"timestamp_ms": <时间戳>, "字段1": 值1, "字段2": 值2, ...}
```

**必须字段**：`timestamp_ms`（毫秒级 Unix 时间戳）

### 2. 渲染器职责单一

一个渲染器只负责一种数据类型，便于：
- 独立测试
- 复用组合
- 配置灵活

### 3. 容忍度设置

根据数据更新频率设置 `tolerance_ms`：

| 数据类型 | 更新频率 | 推荐容忍度 |
|---------|---------|-----------|
| 速度    | ~0.2Hz  | 5000 ms   |
| GPS     | ~1Hz    | 1000 ms   |
| 目标检测 | 20Hz    | 50 ms     |

### 4. 坐标系转换

涉及 3D 数据时，明确定义坐标系：
- **ADS 坐标系**：X=前，Y=左，Z=上
- **相机坐标系**：X=右，Y=下，Z=前

示例见 `TargetRenderer._project_target_to_image()`

---

## 参考示例

完整示例代码：`src/nexus/contrib/repro/renderers/example_gps_renderer.py`

运行示例：
```bash
python -m nexus.contrib.repro.renderers.example_gps_renderer
```

---

## 总结

这个可扩展架构的核心优势：

✅ **简单**：用户只需实现 `render()` 方法
✅ **灵活**：通过配置组合任意多个渲染器
✅ **复用**：基类提供通用功能（数据加载、时间匹配）
✅ **清晰**：每个渲染器职责单一，易于理解和维护

来了新的数据类型？
→ 写一个 Renderer 类
→ 配置 YAML
→ 完成！

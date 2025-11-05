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
SpeedRenderer / TargetRenderer / 自定义Renderer
```

### 2. 文件组织

```
src/nexus/contrib/repro/
├── types.py                      # DataRenderer 抽象接口
└── renderers/
    ├── __init__.py               # 导出所有渲染器
    ├── base.py                   # BaseDataRenderer 基类
    ├── speed_renderer.py         # 速度渲染器
    └── target_renderer.py        # 目标渲染器
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
      video_path: "input/synthetic_driving.mp4"
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
- `time_offset_ms`: 时间偏移（毫秒），默认 `0` ⭐ 新增
- `font_scale`: 字体大小，默认 `1.2`
- `color`: 颜色 BGR，默认绿色 `(0, 255, 0)`

**数据格式**：
```jsonl
{"timestamp_ms": 1759284000000.0, "speed": 120.5}
```

**匹配策略**：Forward（前向匹配，速度"保持"直到下次更新）

**时间偏移示例**：
```python
# 数据与视频完全同步
SpeedRenderer(data_path="speed.jsonl", time_offset_ms=0)

# 数据晚到100ms（补偿延迟）
SpeedRenderer(data_path="speed.jsonl", time_offset_ms=100)
```

---

### TargetRenderer

**功能**：渲染 3D 目标检测框（投影到 2D）

**参数**：
- `data_path`: 目标数据文件路径（JSONL）
- `calibration_path`: 相机标定文件路径（JSON）⭐ 更新为JSON
- `tolerance_ms`: 匹配容忍度，默认 `50` ms（最近匹配）
- `time_offset_ms`: 时间偏移（毫秒），默认 `0` ⭐ 新增
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

**标定格式**（JSON）⭐ 更新：
```json
{
  "camera": {
    "resolution": {"width": 640, "height": 360},
    "intrinsics": {
      "fx": 554.0,
      "fy": 554.0,
      "cx": 320.0,
      "cy": 180.0,
      "distortion": [0.0, 0.0, 0.0, 0.0, 0.0]
    },
    "extrinsics": {
      "translation": {"x": 2.5, "y": 0.0, "z": 1.8},
      "rotation": {"roll": 0.0, "pitch": -10.0, "yaw": 0.0}
    }
  }
}
```

**匹配策略**：Nearest（最近匹配）

**坐标系统**：
- 车辆坐标系: Z=前, X=右, Y=上
- 相机坐标系: X=右, Y=下, Z=前
- 投影: 使用 `cv2.projectPoints` 进行3D→2D转换

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

## ⏰ 时间偏移 (time_offset_ms) ⭐ 新功能

### 概念

**时间偏移**允许调整数据时间线与视频时间线的相对位置，用于：
- 补偿数据采集延迟
- 同步不同来源的数据
- 调试时间对齐问题

### 工作原理

```
视频帧时间: 1000 ms
time_offset_ms: +100 ms
──────────────────────────────────
搜索数据时间: 1000 + 100 = 1100 ms
```

**公式**: `search_time = frame_time + time_offset_ms`

### 使用场景

**场景1: 数据延迟（Data Delayed）**
```python
# 数据比视频晚到100ms
# 视频1000ms的帧应该匹配数据1100ms的值
SpeedRenderer(data_path="speed.jsonl", time_offset_ms=+100)
```

**场景2: 数据提前（Data Ahead）**
```python
# 数据比视频早到50ms
# 视频1000ms的帧应该匹配数据950ms的值
TargetRenderer(data_path="targets.jsonl", time_offset_ms=-50)
```

**场景3: 完全同步（Synchronized）**
```python
# 数据和视频完全同步
GPSRenderer(data_path="gps.jsonl", time_offset_ms=0)  # 默认值
```

### YAML配置示例

```yaml
renderers:
  # Speed data: 延迟0ms（同步）
  - class: "nexus.contrib.repro.renderers.SpeedRenderer"
    kwargs:
      data_path: "input/speed.jsonl"
      time_offset_ms: 0

  # Target data: 提前50ms（补偿处理延迟）
  - class: "nexus.contrib.repro.renderers.TargetRenderer"
    kwargs:
      data_path: "input/targets.jsonl"
      time_offset_ms: -50

  # GPS data: 延迟100ms（补偿接收延迟）
  - class: "custom.GPSRenderer"
    kwargs:
      data_path: "input/gps.jsonl"
      time_offset_ms: 100
```

### 调试技巧

1. **找到最佳偏移量**：
   - 从 `time_offset_ms=0` 开始
   - 观察数据与视频是否对齐
   - 逐步调整（±50ms, ±100ms）

2. **检查数据时间戳**：
   ```python
   # 打印数据时间范围
   data = load_jsonl("data.jsonl")
   print(f"Data range: {data[0]['timestamp_ms']} - {data[-1]['timestamp_ms']}")

   # 打印视频时间范围
   frame_times = load_frame_timestamps("timestamps.csv")
   print(f"Video range: {frame_times['timestamp_ms'].min()} - {frame_times['timestamp_ms'].max()}")
   ```

---

## 完整工作流程

```
视频文件 (synthetic_driving.mp4)
    ↓
[Video Splitter] 切分成帧 + 时间戳
    ↓
帧图片 (frame_0000.png, ...) + timestamps.csv
    ↓
[Data Renderer] 应用多个渲染器
    ├─ SpeedRenderer     → 叠加速度
    ├─ TargetRenderer    → 叠加目标框
    └─ CustomRenderer    → 自定义数据
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

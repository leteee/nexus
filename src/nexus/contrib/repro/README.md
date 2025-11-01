# Repro - Data Replay Visualization Module

数据回放可视化系统，将时序数据同步到视频帧进行可视化回放。

---

## ⭐ 核心特性

### 🕐 时间是一等公民

- **视频时间线**是主要时间线（primary timeline）
- 所有数据时间线同步到视频时间线
- **全局时间控制**: `start_time` / `end_time` 过滤渲染帧范围
- **数据时间偏移**: 每个渲染器独立的 `time_offset_ms` 调整同步

### 🎨 可扩展渲染器架构

- **模块化设计**: 每个渲染器只负责一种数据类型
- **配置驱动**: 通过YAML配置即可组合多个渲染器
- **易于扩展**: 继承 `BaseDataRenderer` 实现 `render()` 即可

### 📊 灵活的数据匹配策略

- **Nearest**: 最近匹配（双向，适合高频数据）
- **Forward**: 前向匹配（保持值，适合低频数据）
- **Backward**: 后向匹配（前瞻，适合预测数据）

---

## 📐 架构概览

### 工作流程

```
视频 ──┐
       ├─→ Video Splitter ──→ Data Renderer ──→ Video Composer ──→ 输出视频
数据 ──┘                     (应用多个渲染器)
```

### 模块结构

```
repro/
├── types.py          # DataRenderer 抽象接口
├── io.py             # I/O 工具 (load_jsonl, save_jsonl)
├── utils.py          # 时间解析, 视频元数据
├── video.py          # 视频处理 (extract_frames, compose_video, render_all_frames)
├── datagen.py        # 数据生成工具
└── renderers/        # 渲染器模块
    ├── base.py       # BaseDataRenderer (带匹配策略)
    ├── speed_renderer.py    # 速度渲染器
    └── target_renderer.py   # 3D目标渲染器
```

### 渲染器类层次

```
DataRenderer (抽象接口)
    ↓
BaseDataRenderer (基类: 自动加载数据 + 时间匹配)
    ↓
SpeedRenderer / TargetRenderer / 自定义Renderer
```

---

## 🚀 快速开始

### 1. 创建自定义渲染器

```python
from nexus.contrib.repro.renderers import BaseDataRenderer
import cv2

class MyRenderer(BaseDataRenderer):
    def __init__(self, data_path, position=(20, 50), **kwargs):
        # 调用基类初始化（自动加载数据 + 时间匹配）
        super().__init__(
            data_path=data_path,
            tolerance_ms=1000.0,           # 匹配容忍度
            match_strategy="nearest",      # nearest/forward/backward
            time_offset_ms=0.0,            # 时间偏移
        )
        self.position = position

    def render(self, frame, timestamp_ms):
        """唯一需要实现的方法：如何绘制到帧上"""
        # 1. 匹配数据（基类自动处理时间偏移）
        matched = self.match_data(timestamp_ms)
        if not matched:
            return frame

        # 2. 绘制到帧上
        data = matched[0]
        cv2.putText(frame, f"Value: {data['value']}",
                   self.position, cv2.FONT_HERSHEY_SIMPLEX,
                   1.0, (0, 255, 0), 2)
        return frame
```

### 2. 配置 YAML

```yaml
case_info:
  name: "Data Replay"
  version: "3.0.0"

pipeline:
  # Step 1: 视频切帧
  - plugin: "Video Splitter"
    config:
      video_path: "input/vehicle.mp4"
      output_dir: "temp/frames"

  # Step 2: 数据渲染
  - plugin: "Data Renderer"
    config:
      # 全局时间范围（可选）
      # start_time: "2025-10-27 00:00:00"  # or timestamp_ms or null
      # end_time: "2025-10-27 00:01:00"

      frames_dir: "temp/frames"
      output_dir: "temp/rendered_frames"
      timestamps_path: "input/vehicle_timeline.csv"

      # 多个渲染器（按顺序应用）
      renderers:
        - class: "nexus.contrib.repro.renderers.SpeedRenderer"
          kwargs:
            data_path: "input/speed.jsonl"
            position: [30, 60]
            tolerance_ms: 5000
            time_offset_ms: 0        # 数据同步

        - class: "nexus.contrib.repro.renderers.TargetRenderer"
          kwargs:
            data_path: "input/adb_targets.jsonl"
            calibration_path: "camera_calibration.json"
            tolerance_ms: 50
            time_offset_ms: -50      # 数据提前50ms

        - class: "myproject.MyRenderer"
          kwargs:
            data_path: "input/custom.jsonl"
            position: [20, 100]

  # Step 3: 合成视频
  - plugin: "Video Composer"
    config:
      frames_dir: "temp/rendered_frames"
      output_path: "output/result.mp4"
      fps: 30.0
```

### 3. 运行

```bash
nexus run -c case_name -t template_name
```

---

## 📄 数据格式

### Frame Timestamps (CSV)

```csv
frame_index,timestamp_ms
0,1759284000000.0
1,1759284000033.3
2,1759284000066.7
```

### Data Files (JSONL)

**必须字段**: `timestamp_ms` (Unix毫秒时间戳)

**简单数值** (`speed.jsonl`):
```jsonl
{"timestamp_ms": 1759284000000.0, "speed": 120.5}
{"timestamp_ms": 1759284002150.5, "speed": 122.3}
```

**嵌套结构** (`gps.jsonl`):
```jsonl
{"timestamp_ms": 0.0, "gps": {"lat": 39.9042, "lon": 116.4074}, "altitude": 50.0}
```

**复杂数据** (`targets.jsonl`):
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

### Camera Calibration (JSON)

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

---

## 🎨 内置渲染器

### SpeedRenderer

显示车速数据（前向匹配，速度保持）

**参数**:
- `data_path`: 速度数据路径 (JSONL)
- `position`: 文字位置，默认 `(30, 60)`
- `tolerance_ms`: 匹配容忍度，默认 `5000` ms
- `time_offset_ms`: 时间偏移，默认 `0`
- `font_scale`: 字体大小，默认 `1.2`
- `color`: BGR颜色，默认 `(0, 255, 0)` 绿色

### TargetRenderer

显示3D目标检测框（最近匹配）

**参数**:
- `data_path`: 目标数据路径 (JSONL)
- `calibration_path`: 相机标定路径 (JSON)
- `tolerance_ms`: 匹配容忍度，默认 `50` ms
- `time_offset_ms`: 时间偏移，默认 `0`
- `box_color`: 框颜色，默认 `(0, 255, 0)` 绿色
- `show_panel`: 显示信息面板，默认 `True`

**坐标系统**:
- 车辆: Z=前, X=右, Y=上
- 相机: X=右, Y=下, Z=前
- 投影: 使用 `cv2.projectPoints` 进行3D→2D转换

---

## ⏰ 时间同步机制

### 匹配策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `nearest` | 最接近的数据点（双向） | 高频数据（20Hz目标检测） |
| `forward` | 最近的 ≤ 当前时间 | 低频数据（速度、GPS保持） |
| `backward` | 最早的 ≥ 当前时间 | 预测数据、前瞻场景 |

### 时间偏移 (time_offset_ms)

**公式**: `search_time = frame_time + time_offset_ms`

**使用场景**:

```python
# 数据延迟100ms（数据晚到）
SpeedRenderer(data_path="speed.jsonl", time_offset_ms=+100)

# 数据提前50ms（数据早到）
TargetRenderer(data_path="targets.jsonl", time_offset_ms=-50)

# 完全同步
GPSRenderer(data_path="gps.jsonl", time_offset_ms=0)
```

**工作原理**:
```
视频帧 1000ms
time_offset_ms: +100
───────────────────
搜索数据: 1100ms
```

---

## 🛠️ API 参考

### 模块导入

```python
# Core types
from nexus.contrib.repro import DataRenderer, VideoMetadata

# I/O
from nexus.contrib.repro import load_jsonl, save_jsonl, load_frame_timestamps

# Time utilities
from nexus.contrib.repro import parse_time_value, parse_time_string, get_video_metadata

# Video processing
from nexus.contrib.repro import extract_frames, compose_video, render_all_frames

# Data generation
from nexus.contrib.repro import (
    generate_timeline_with_jitter,
    generate_speed_data_event_driven,
    generate_adb_target_data,
)

# Renderers
from nexus.contrib.repro.renderers import BaseDataRenderer, SpeedRenderer, TargetRenderer
```

### 视频处理

```python
# 切帧
metadata = extract_frames(
    video_path=Path("input.mp4"),
    output_dir=Path("frames/"),
    frame_pattern="frame_{:06d}.png"
)

# 合成
compose_video(
    frames_dir=Path("frames/"),
    output_path=Path("output.mp4"),
    fps=30.0,
    codec="mp4v"
)

# 渲染（应用多个渲染器）
render_all_frames(
    frames_dir=Path("frames/"),
    output_dir=Path("rendered/"),
    timestamps_path=Path("timestamps.csv"),
    renderer_configs=[
        {
            "class": "nexus.contrib.repro.renderers.SpeedRenderer",
            "kwargs": {"data_path": "speed.jsonl"}
        }
    ],
    start_time_ms=None,    # 可选：全局时间范围
    end_time_ms=None,
)
```

### 时间工具

```python
# 解析多种时间格式
timestamp = parse_time_value("2025-10-27 08:30:00")  # → 1759284000000.0
timestamp = parse_time_value(1759284000000.0)        # → 1759284000000.0
timestamp = parse_time_value(None)                    # → None

# 获取视频元数据
meta = get_video_metadata("video.mp4")
# → {"fps": 30.0, "total_frames": 900, "duration_s": 30.0, ...}
```

### I/O 操作

```python
# 加载/保存 JSONL
data = load_jsonl("data.jsonl")        # List[dict]
save_jsonl(data, "output.jsonl")

# 加载帧时间戳
frame_times = load_frame_timestamps("timestamps.csv")  # DataFrame
```

### 数据生成

```python
# 生成时间线（带抖动）
timeline = generate_timeline_with_jitter(
    fps=30.0,
    total_frames=900,
    start_timestamp_ms=1759284000000.0,
    jitter_ms=1.5
)

# 生成速度数据（事件驱动）
speed_data = generate_speed_data_event_driven(
    start_timestamp_ms=1759284000000.0,
    duration_s=30.0,
    max_interval_s=5.0,
    speed_change_threshold=2.0
)

# 生成ADB目标数据（20Hz）
target_data = generate_adb_target_data(
    start_timestamp_ms=1759284000000.0,
    duration_s=30.0,
    frequency_hz=20.0
)
```

---

## 🎨 OpenCV 绘图速查

### 常用函数

```python
import cv2

# 文本
cv2.putText(frame, "Text", (x, y), cv2.FONT_HERSHEY_SIMPLEX,
            font_scale, color, thickness, cv2.LINE_AA)

# 矩形
cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

# 圆形
cv2.circle(frame, (cx, cy), radius, color, thickness)

# 多边形
cv2.polylines(frame, [points], isClosed=True, color=color, thickness=thickness)
```

### 颜色代码 (BGR)

```python
BLACK   = (0, 0, 0)
WHITE   = (255, 255, 255)
RED     = (0, 0, 255)
GREEN   = (0, 255, 0)
BLUE    = (255, 0, 0)
YELLOW  = (0, 255, 255)
CYAN    = (255, 255, 0)
MAGENTA = (255, 0, 255)
```

---

## 🐛 常见问题

### Q1: 没有数据匹配

**检查容忍度**:
```python
matched = renderer.match_data(timestamp_ms, tolerance_ms=1000.0)
```

**检查时间范围**:
```python
print(f"Data: {data[0]['timestamp_ms']} - {data[-1]['timestamp_ms']}")
print(f"Frame: {timestamp_ms}")
```

### Q2: 数据不对齐

**调整时间偏移**:
```python
renderer = SpeedRenderer(
    data_path="speed.jsonl",
    time_offset_ms=100  # 尝试不同的值: 0, ±50, ±100
)
```

### Q3: 性能慢

**优化方法**:
1. 在 `__init__` 中预加载所有数据
2. 对大数据集使用二分查找
3. 考虑并行处理帧：
```python
from multiprocessing import Pool

def render_frame(args):
    frame_idx, timestamp_ms, renderers = args
    frame = cv2.imread(f"frames/frame_{frame_idx:06d}.png")
    for renderer in renderers:
        frame = renderer.render(frame, timestamp_ms)
    cv2.imwrite(f"rendered/frame_{frame_idx:06d}.png", frame)

with Pool(processes=8) as pool:
    pool.map(render_frame, frame_args)
```

### Q4: 找不到最佳偏移量

**调试步骤**:
1. 从 `time_offset_ms=0` 开始
2. 观察数据与视频是否对齐
3. 逐步调整（±50ms, ±100ms）
4. 打印数据和视频的时间范围对比

---

## 📚 完整示例

### Python API 直接调用

```python
from pathlib import Path
from nexus.contrib.repro import extract_frames, render_all_frames, compose_video
from nexus.contrib.repro.renderers import SpeedRenderer
import cv2

# 1. 切帧
metadata = extract_frames(Path("input.mp4"), Path("frames/"))
print(f"Extracted {metadata.total_frames} frames at {metadata.fps} FPS")

# 2. 渲染
renderer_configs = [
    {
        "class": "nexus.contrib.repro.renderers.SpeedRenderer",
        "kwargs": {
            "data_path": "input/speed.jsonl",
            "position": [30, 60],
            "tolerance_ms": 5000,
            "time_offset_ms": 0
        }
    }
]

render_all_frames(
    frames_dir=Path("frames/"),
    output_dir=Path("rendered/"),
    timestamps_path=Path("input/timestamps.csv"),
    renderer_configs=renderer_configs
)

# 3. 合成
compose_video(
    frames_dir=Path("rendered/"),
    output_path=Path("output.mp4"),
    fps=metadata.fps
)
```

### 编程式使用

```python
from nexus.contrib.repro.renderers import SpeedRenderer, TargetRenderer
from nexus.contrib.repro import load_frame_timestamps
import cv2

# 创建渲染器
speed_renderer = SpeedRenderer(
    data_path="input/speed.jsonl",
    position=(30, 60),
    tolerance_ms=5000.0
)

target_renderer = TargetRenderer(
    data_path="input/targets.jsonl",
    calibration_path="calibration.json",
    tolerance_ms=50.0
)

# 加载帧时间戳
frame_times = load_frame_timestamps("input/timestamps.csv")

# 渲染每一帧
for _, row in frame_times.iterrows():
    frame_idx = int(row["frame_index"])
    timestamp_ms = row["timestamp_ms"]

    # 读取帧
    frame = cv2.imread(f"frames/frame_{frame_idx:06d}.png")

    # 应用渲染器
    frame = speed_renderer.render(frame, timestamp_ms)
    frame = target_renderer.render(frame, timestamp_ms)

    # 保存
    cv2.imwrite(f"rendered/frame_{frame_idx:06d}.png", frame)
```

---

## 🎯 典型应用场景

- **自动驾驶**: 传感器数据、轨迹、速度叠加到行车记录
- **体育分析**: 心率、速度、位置可视化
- **无人机**: GPS轨迹、高度、姿态角
- **实验记录**: 温度、压力、流量等测量值
- **游戏回放**: 玩家状态、坐标、操作

---

## 📖 扩展阅读

### 渲染器详细文档

参见 [renderers/README.md](./renderers/README.md) 获取：
- 渲染器架构详解
- 时间偏移机制详细说明
- 扩展示例

### 外部资源

- **OpenCV文档**: https://docs.opencv.org/
- **JSONL格式**: https://jsonlines.org/
- **Python ABC**: https://docs.python.org/3/library/abc.html

---

## 📊 版本历史

| 版本 | 主要变更 |
|------|----------|
| v3.0.0 | 添加时间偏移功能，全局时间控制，重构工具模块 |
| v2.0.0 | 模块化渲染器架构，BaseDataRenderer |
| v1.0.0 | 初始版本 |

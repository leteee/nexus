# Repro模块 - 视频数据回放

独立的视频时序数据可视化模块

## 概述

Repro是Nexus框架中的一个**独立模块**，专门用于视频数据回放和可视化：
- 将视频分解为帧序列
- 在帧上渲染时序数据（速度、目标检测等）
- 将渲染后的帧合成为视频

**核心特性**：
- ✨ 简单的渲染器类系统（使用全类名）
- 🎬 完整的视频处理工具链
- ⏱️ 精确的时间戳匹配
- 🎨 模块化的数据渲染器
- 🧪 内置合成数据生成器

## 快速示例

### 1. 基础数据渲染

```python
from nexus.contrib.repro.renderers import BaseDataRenderer
import cv2

# 定义渲染器类
class SpeedRenderer(BaseDataRenderer):
    def __init__(self, data_path, position=(30, 60), **kwargs):
        super().__init__(data_path, **kwargs)
        self.position = position

    def render(self, frame, timestamp_ms):
        # 匹配时间戳的数据
        matched = self.match_data(timestamp_ms)
        if not matched:
            return frame

        # 在帧上绘制速度
        speed = matched[0]['speed']
        cv2.putText(
            frame, f"Speed: {speed:.1f} km/h",
            self.position, cv2.FONT_HERSHEY_SIMPLEX,
            1.0, (0, 255, 0), 2
        )
        return frame
```

### 2. 使用Pipeline运行

```yaml
# repro.yaml
pipeline:
  # 步骤1: 分割视频
  - plugin: "Video Splitter"
    config:
      video_path: "input/video.mp4"
      output_dir: "temp/frames"

  # 步骤2: 渲染数据
  - plugin: "Data Renderer"
    config:
      frames_dir: "temp/frames"
      output_dir: "temp/rendered"
      timestamps_path: "input/frame_timestamps.csv"
      renderers:
        - class: "nexus.contrib.repro.renderers.SpeedRenderer"  # 使用全类名
          kwargs:
            data_path: "input/speed.jsonl"
            position: [30, 60]
            tolerance_ms: 5000

  # 步骤3: 合成视频
  - plugin: "Video Composer"
    config:
      frames_dir: "temp/rendered"
      output_path: "output/video_with_data.mp4"
      fps: 30.0
```

运行：
```bash
nexus run --case my_replay --template repro/repro
```

## 核心概念

### 渲染器 (Renderer)

渲染器负责将时序数据可视化到视频帧上。

**定义渲染器**：
```python
from nexus.contrib.repro.renderers import BaseDataRenderer

class MyRenderer(BaseDataRenderer):
    def render(self, frame, timestamp_ms):
        # 实现渲染逻辑
        return frame
```

**使用渲染器**：
```yaml
renderers:
  - class: "your.module.path.MyRenderer"  # 使用全类名
    kwargs:
      data_path: "input/data.jsonl"
```

### 时间戳匹配

Repro使用三种匹配策略将时序数据与视频帧对齐：

1. **Nearest (最近匹配)**：
   - 找到时间戳最接近的数据点
   - 适用：高频数据（目标检测20Hz）

2. **Forward (前向匹配)**：
   - 使用最近的历史数据点
   - 数据"保持"直到下一次更新
   - 适用：事件驱动数据（速度变化时才发送）

3. **Backward (后向匹配)**：
   - 使用最近的未来数据点
   - 适用：预测性数据

**示例**：
```python
class MyRenderer(BaseDataRenderer):
    def __init__(self, data_path, **kwargs):
        super().__init__(
            data_path,
            match_strategy="forward",  # 选择策略
            tolerance_ms=5000.0         # 容差（毫秒）
        )
```

### 时间偏移

处理数据和视频时间不同步：

```python
# 数据比视频晚100ms
renderer = MyRenderer(
    data_path="data.jsonl",
    time_offset_ms=100  # 在查找数据时加100ms
)
```

## 内置渲染器

### 1. SpeedRenderer (速度渲染器)

显示车辆速度：

```yaml
- class: "nexus.contrib.repro.renderers.SpeedRenderer"
  kwargs:
    data_path: "input/speed.jsonl"
    position: [30, 60]           # 文本位置
    tolerance_ms: 5000.0         # 前向匹配，保持5s
    font_scale: 1.2
    color: [0, 255, 0]           # 绿色
    thickness: 3
```

**数据格式** (JSONL):
```json
{"timestamp_ms": 1759284000000.0, "speed": 0.0}
{"timestamp_ms": 1759284002150.5, "speed": 12.3}
```

### 2. TargetRenderer (目标检测渲染器)

渲染3D目标检测框：

```yaml
- class: "nexus.contrib.repro.renderers.TargetRenderer"
  kwargs:
    data_path: "input/adb_targets.jsonl"
    calibration_path: "camera_calibration.json"
    tolerance_ms: 50.0           # 最近匹配
    box_color: [0, 255, 0]
    box_thickness: 2
    show_panel: true
```

**数据格式** (JSONL):
```json
{
  "timestamp_ms": 1759284000000.0,
  "targets": [
    {
      "id": 1,
      "type": "car",
      "distance_m": 45.2,
      "angle_left": 1.8,
      "angle_right": 2.8,
      "angle_top": -0.3,
      "angle_bottom": -0.7
    }
  ]
}
```

## 视频处理流程

### 完整Pipeline

```
原始视频 (MP4)
    ↓
┌──────────────────────┐
│  Video Splitter      │  分割为帧序列
└─────────┬────────────┘
          ↓
    帧序列 (PNG)
    frame_000001.png
    frame_000002.png
    ...
          ↓
┌──────────────────────┐
│  Data Renderer       │  在帧上渲染数据
│  ─ SpeedRenderer     │
│  ─ TargetRenderer    │
└─────────┬────────────┘
          ↓
   渲染帧序列 (PNG)
          ↓
┌──────────────────────┐
│  Video Composer      │  合成为视频
└─────────┬────────────┘
          ↓
    输出视频 (MP4)
```

### 时间戳对齐

**帧时间戳文件** (`frame_timestamps.csv`):
```csv
frame_index,timestamp_ms
0,1759284000000.0
1,1759284000033.4
2,1759284000066.8
```

每一帧都有精确的采集时间戳，用于与数据对齐。

## 数据生成工具

Repro包含完整的合成数据生成器，用于测试和演示。

### 1. 生成合成视频

```yaml
- plugin: "Synthetic Video Generator"
  config:
    output_path: "input/synthetic_driving.mp4"
    duration_s: 60.0
    fps: 30.0
    width: 1920
    height: 1080
    speed_kmh: 60.0
```

### 2. 生成帧时间戳

```yaml
- plugin: "Timeline Generator"
  config:
    video_path: "input/synthetic_driving.mp4"
    start_time: "2025-10-27 08:30:00"
    jitter_ms: 2
    output_csv: "input/frame_timestamps.csv"
```

### 3. 生成速度数据

```yaml
- plugin: "Speed Data Generator"
  config:
    video_path: "input/synthetic_driving.mp4"
    start_time: "2025-10-27 08:30:00"
    max_interval_s: 5.0
    speed_change_threshold: 2.0
    output_jsonl: "input/speed.jsonl"
```

### 4. 生成目标检测数据

```yaml
- plugin: "ADB Target Generator"
  config:
    video_path: "input/synthetic_driving.mp4"
    start_time: "2025-10-27 08:30:00"
    frequency_hz: 20.0
    num_targets: 3
    output_jsonl: "input/adb_targets.jsonl"
```

## 完整示例

### 从零生成演示数据并渲染

使用 `repro_datagen` 模板：

```bash
nexus run --case demo_repro --template repro/repro_datagen
```

这会：
1. 生成60s的合成驾驶视频
2. 生成帧时间戳
3. 生成速度数据（事件驱动）
4. 生成ADB目标检测数据（20Hz）

生成的数据位于 `cases/demo_repro/input/`。

### 渲染已有数据

使用 `repro` 模板：

```bash
nexus run --case my_replay --template repro/repro
```

前提：`cases/my_replay/input/` 包含：
- `synthetic_driving.mp4` - 视频
- `frame_timestamps.csv` - 帧时间戳
- `speed.jsonl` - 速度数据
- `adb_targets.jsonl` - 目标数据

## 配置引用

Repro完全支持Nexus的配置引用系统：

```yaml
defaults:
  # 定义共享配置
  renderer_base:
    tolerance_ms: 50.0
    time_offset_ms: 0

  speed_renderer:
    position: [30, 60]
    tolerance_ms: 5000.0
    font_scale: 1.2
    color: [0, 255, 0]

pipeline:
  - plugin: "Data Renderer"
    config:
      renderers:
        # 使用_extends继承配置
        - class: "nexus.contrib.repro.renderers.SpeedRenderer"
          kwargs:
            _extends: "@defaults.speed_renderer"
            data_path: "input/speed.jsonl"
```

## 路径自动解析

所有 `*_path` 参数自动解析为绝对路径：

```yaml
renderers:
  - class: "nexus.contrib.repro.renderers.SpeedRenderer"
    kwargs:
      data_path: "input/speed.jsonl"  # 自动解析为绝对路径
      position: [30, 60]               # 保持不变

  - class: "nexus.contrib.repro.renderers.TargetRenderer"
    kwargs:
      data_path: "input/targets.jsonl"       # 自动解析
      calibration_path: "camera_calib.json"  # 自动解析
```

## 架构设计

### 渲染器类系统

Repro使用简单的类导入系统，无需注册：

```python
# 在配置中使用全类名
renderers:
  - class: "nexus.contrib.repro.renderers.SpeedRenderer"
    kwargs:
      data_path: "input/speed.jsonl"
```

**特点**：
- 简单：直接使用Python类
- 显式：全类名明确指定渲染器
- 灵活：可以使用任何可导入的类
- 无注册：不需要额外的装饰器或注册步骤

### 基础渲染器

```python
class BaseDataRenderer:
    """所有渲染器的基类"""

    def __init__(self, data_path, tolerance_ms=50.0,
                 match_strategy="nearest", time_offset_ms=0):
        self.data = load_jsonl(data_path)
        self.tolerance_ms = tolerance_ms
        self.match_strategy = match_strategy
        self.time_offset_ms = time_offset_ms

    def match_data(self, timestamp_ms, tolerance_ms=None):
        """匹配数据（应用时间偏移和容差）"""
        adjusted_ts = timestamp_ms + self.time_offset_ms
        # 根据match_strategy查找数据
        ...

    def render(self, frame, timestamp_ms):
        """子类必须实现"""
        raise NotImplementedError
```

### 插件集成

Repro通过Nexus插件暴露给用户：

```python
# nexus/contrib/nexus/repro.py

@plugin(name="Data Renderer", config=DataRendererConfig)
def render_data_on_frames(ctx: PluginContext):
    """Nexus插件：调用repro模块渲染数据"""

    # 解析路径
    renderer_configs = []
    for rc in config.renderers:
        kwargs = ctx.auto_resolve_paths(rc["kwargs"])
        renderer_configs.append({"class": rc["class"], "kwargs": kwargs})

    # 调用repro函数
    render_all_frames(
        frames_dir=frames_dir,
        renderer_configs=renderer_configs,
        ...
    )
```

## 独立性

Repro模块是**独立的**：
- 可以作为Python库直接使用
- 不依赖Nexus核心（除了插件适配器）
- 使用标准Python类导入机制

**直接使用**（不通过Nexus）：
```python
from nexus.contrib.repro import render_all_frames

render_all_frames(
    frames_dir="frames/",
    output_dir="rendered/",
    timestamps_path="timestamps.csv",
    renderer_configs=[
        {
            "class": "nexus.contrib.repro.renderers.SpeedRenderer",
            "kwargs": {"data_path": "speed.jsonl"}
        }
    ]
)
```

## 下一步

- [快速开始](quick-start.md) - 第一个repro示例
- [渲染器系统](renderers.md) - 深入了解渲染器
- [视频处理](video-processing.md) - 视频处理API
- [数据生成](data-generation.md) - 合成数据工具
- [API参考](api-reference.md) - 完整API文档
- [编写渲染器](../guides/writing-renderers.md) - 自定义渲染器指南

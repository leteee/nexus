# Repro - Data Replay Visualization Module

数据回放可视化系统，用于将时序数据同步到视频帧进行可视化回放。

## 📋 **核心概念**

### **工作流程**

```
原始视频 → 切帧 → 数据匹配 → 渲染叠加 → 合成视频
```

1. **视频切分** - 将视频分解成独立帧 + 时间戳映射
2. **时间匹配** - 根据物理时间匹配数据到对应帧
3. **数据渲染** - 将数据可视化绘制到帧上
4. **视频合成** - 将处理后的帧合成新视频

---

## 📁 **数据结构设计**

### **1. 帧时间映射** (`frame_timestamps.csv`)

视频切分时自动生成：

```csv
frame_index,timestamp_ms
0,0.0
1,33.33
2,66.67
3,100.00
```

### **2. 数据时间线** (必须包含 `timestamp_ms` 列)

示例 - 速度数据 (`speed_data.csv`):
```csv
timestamp_ms,speed_kmh,acceleration
0.0,0.0,0.0
50.0,10.5,2.1
100.0,20.3,1.8
150.0,30.1,2.0
```

示例 - GPS数据 (`gps_data.csv`):
```csv
timestamp_ms,latitude,longitude,altitude
0.0,39.9042,116.4074,50.0
100.0,39.9043,116.4075,50.5
200.0,39.9044,116.4076,51.0
```

---

## 🏗️ **模块架构**

### **业务逻辑** (`contrib/repro/`)

```
repro/
├── types.py        # 数据结构和协议定义
├── video.py        # 视频处理（切分/合成）
├── matching.py     # 时间匹配算法
└── rendering.py    # 渲染接口和基础实现
```

### **Nexus插件** (`contrib/nexus/__init__.py`)

- `Video Splitter` - 视频切帧插件
- `Video Composer` - 帧合成视频插件

---

## 🎨 **自定义数据渲染器**

实现 `DataRenderer` 协议来可视化自定义数据类型：

```python
from nexus.contrib.repro.types import DataPoint, DataRenderer
from nexus.contrib.repro.rendering import BaseRenderer
import numpy as np

class SpeedRenderer(BaseRenderer):
    """速度数据渲染器"""

    def __init__(self, data_series):
        self.data_series = data_series

    def match_data(self, timestamp_ms, tolerance_ms=50.0):
        from nexus.contrib.repro.matching import match_data_to_timestamp
        return match_data_to_timestamp(
            self.data_series,
            timestamp_ms,
            tolerance_ms=tolerance_ms,
            method="nearest"
        )

    def render_on_frame(self, frame, data):
        if not data:
            return frame

        speed = data[0].data.get("speed_kmh", 0)

        # 绘制速度表
        text = f"Speed: {speed:.1f} km/h"
        frame = self.draw_text(
            frame,
            text,
            position=(20, 50),
            font_scale=1.5,
            color=(0, 255, 0),
            bg_color=(0, 0, 0)
        )

        return frame
```

### **渲染器接口定义**

```python
class DataRenderer(Protocol):
    def match_data(self, timestamp_ms: float, tolerance_ms: float) -> List[DataPoint]:
        """匹配数据点到时间戳"""
        ...

    def render_on_frame(self, frame: np.ndarray, data: List[DataPoint]) -> np.ndarray:
        """将数据绘制到帧上"""
        ...
```

---

## 🚀 **使用示例**

### **示例1: 视频切分**

使用 Nexus CLI:
```bash
nexus plugin "Video Splitter" --case replay \
  --config video_path=input.mp4 \
  --config output_dir=frames
```

Python API:
```python
from pathlib import Path
from nexus.contrib.repro.video import extract_frames

metadata = extract_frames(
    Path("input.mp4"),
    Path("frames/"),
    frame_pattern="frame_{:06d}.png",
    save_timestamps=True
)

print(f"Extracted {metadata.total_frames} frames at {metadata.fps} FPS")
```

### **示例2: 视频合成**

```bash
nexus plugin "Video Composer" --case replay \
  --config frames_dir=frames \
  --config output_path=output.mp4 \
  --config fps=30.0
```

### **示例3: 完整数据回放流程**

```python
from pathlib import Path
import pandas as pd
from nexus.contrib.repro.video import extract_frames, compose_video, get_frame_at_timestamp
from nexus.contrib.repro.types import load_frame_timestamps, load_data_series
from nexus.contrib.repro.rendering import TextRenderer

# 1. 切分视频
metadata = extract_frames(
    Path("input.mp4"),
    Path("frames/"),
)

# 2. 加载数据
frame_times = load_frame_timestamps(Path("frames/frame_timestamps.csv"))
speed_data = load_data_series(Path("speed_data.csv"))

# 3. 创建渲染器
renderer = TextRenderer(
    speed_data,
    label="Speed",
    value_column="speed_kmh",
    position=(20, 50)
)

# 4. 渲染每一帧
rendered_dir = Path("rendered_frames/")
rendered_dir.mkdir(exist_ok=True)

for _, row in frame_times.iterrows():
    frame_idx = int(row["frame_index"])
    timestamp = row["timestamp_ms"]

    # 加载原始帧
    frame = get_frame_at_timestamp(
        Path("frames/"),
        timestamp,
        frame_times
    )

    # 匹配数据并渲染
    data = renderer.match_data(timestamp, tolerance_ms=50.0)
    rendered_frame = renderer.render_on_frame(frame, data)

    # 保存渲染后的帧
    import cv2
    cv2.imwrite(str(rendered_dir / f"frame_{frame_idx:06d}.png"), rendered_frame)

# 5. 合成视频
compose_video(
    rendered_dir,
    Path("replay_output.mp4"),
    fps=metadata.fps
)
```

---

## 🛠️ **高级功能**

### **时间匹配方法**

```python
from nexus.contrib.repro.matching import match_data_to_timestamp

# 最近邻匹配
data = match_data_to_timestamp(data_series, 100.0, method="nearest")

# 范围匹配（容差内所有点）
data = match_data_to_timestamp(data_series, 100.0, method="range", tolerance_ms=100)

# 线性插值
data = match_data_to_timestamp(data_series, 100.0, method="interpolate")
```

### **自定义渲染工具**

`BaseRenderer` 提供了常用绘图函数：

```python
# 文本绘制
frame = renderer.draw_text(frame, "Hello", (100, 100))

# 数值显示
frame = renderer.draw_value_overlay(frame, "Speed", "120.5", (20, 50))

# 简单折线图
frame = renderer.draw_graph(frame, [1, 2, 3, 4], (50, 50), (200, 100))
```

---

## 📊 **性能建议**

1. **帧格式选择**:
   - PNG - 无损，文件较大，适合精确渲染
   - JPEG - 有损，文件小，适合快速预览

2. **批处理**:
   - 处理大量帧时考虑多进程并行渲染
   - 使用 `start_frame` 和 `end_frame` 参数处理视频片段

3. **内存优化**:
   - 流式处理：读取帧 → 渲染 → 保存 → 释放
   - 避免同时加载所有帧到内存

---

## 🎯 **典型应用场景**

- 自动驾驶数据回放（传感器数据叠加到行车记录）
- 体育比赛数据可视化（速度、心率等）
- 无人机飞行数据分析（GPS轨迹、高度、姿态）
- 实验数据记录（时序测量值可视化）

---

## 📝 **后续扩展**

可以创建更多专用渲染器插件：

- `GPS Trajectory Renderer` - 绘制地图轨迹
- `Chart Renderer` - 动态图表显示
- `Heatmap Renderer` - 热力图叠加
- `3D Overlay Renderer` - 3D模型叠加

每个渲染器可以作为独立Nexus插件，实现 `DataRenderer` 协议即可。

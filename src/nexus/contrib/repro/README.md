# Repro - Data Replay Visualization Module

数据回放可视化系统，将时序数据同步到视频帧进行可视化回放。

## 🎯 **设计理念**

**用户继承抽象基类 `DataRenderer`，实现三个方法即可将自定义数据叠加到视频帧：**

```python
from nexus.contrib.repro.types import DataRenderer

class MyRenderer(DataRenderer):
    def load_data(self, data_path):
        """如何加载数据"""

    def match_data(self, timestamp_ms):
        """如何匹配时间戳"""

    def render(self, frame, data):
        """如何绘制到帧上"""
```

---

## 📋 **工作流程**

```
视频 ──┐
       ├─→ 切帧 ──→ 数据渲染 ──→ 合成视频
数据 ──┘
```

### **三个Nexus插件**

1. **Video Splitter** - 视频切帧 + 生成时间戳映射
2. **Data Renderer** - 应用自定义渲染器到所有帧 ⭐ 核心
3. **Video Composer** - 帧序列合成视频

---

## 📁 **数据格式 - JSONL (推荐)**

### **为什么用JSONL而非CSV？**

| 格式 | 优势 | 劣势 |
|------|------|------|
| **CSV** | 简单 | ❌ 只能扁平结构 |
| **JSONL** | ✅ 支持嵌套数据<br>✅ 灵活字段<br>✅ 逐行解析 | 稍复杂 |

### **JSONL示例**

**简单数值** (`speed.jsonl`):
```jsonl
{"timestamp_ms": 0.0, "speed": 120.5}
{"timestamp_ms": 50.0, "speed": 125.3}
{"timestamp_ms": 100.0, "speed": 130.1}
```

**嵌套结构** (`gps.jsonl`):
```jsonl
{"timestamp_ms": 0.0, "gps": {"lat": 39.9042, "lon": 116.4074}, "altitude": 50.0}
{"timestamp_ms": 50.0, "gps": {"lat": 39.9043, "lon": 116.4075}, "altitude": 51.2}
```

**复杂传感器** (`sensors.jsonl`):
```jsonl
{
  "timestamp_ms": 0.0,
  "vehicle": {
    "speed": 120.5,
    "gear": 3,
    "rpm": 3000
  },
  "sensors": {
    "temperature": 85.0,
    "pressure": 101.3
  },
  "gps": {"lat": 39.9, "lon": 116.4}
}
```

---

## 🏗️ **抽象基类 `DataRenderer`**

### **定义**

```python
from abc import ABC, abstractmethod
from pathlib import Path
import numpy as np

class DataRenderer(ABC):
    """
    抽象基类：用户继承此类实现自定义数据渲染。

    必须实现三个方法：
    1. load_data() - 加载数据
    2. match_data() - 匹配时间戳
    3. render() - 绘制到帧
    """

    def __init__(self, data_path: Path | str):
        self.data_path = Path(data_path)
        self.data = None
        self.load_data(self.data_path)  # 自动调用

    @abstractmethod
    def load_data(self, data_path: Path) -> None:
        """加载数据到 self.data"""

    @abstractmethod
    def match_data(self, timestamp_ms: float, tolerance_ms: float = 50.0) -> List[dict]:
        """返回匹配时间戳的数据列表"""

    @abstractmethod
    def render(self, frame: np.ndarray, data: List[dict]) -> np.ndarray:
        """在帧上绘制数据，返回修改后的帧"""
```

---

## 📝 **示例实现**

### **示例1：简单数值渲染器**

```python
from nexus.contrib.repro.types import DataRenderer, load_jsonl
import cv2

class SpeedRenderer(DataRenderer):
    """显示速度数据"""

    def __init__(self, data_path, label="Speed", position=(20, 50)):
        self.label = label
        self.position = position
        super().__init__(data_path)  # 调用父类，触发 load_data

    def load_data(self, data_path):
        """加载JSONL数据"""
        self.data = load_jsonl(data_path)

    def match_data(self, timestamp_ms, tolerance_ms=50.0):
        """最近邻匹配"""
        if not self.data:
            return []

        closest = min(self.data, key=lambda d: abs(d["timestamp_ms"] - timestamp_ms))

        if abs(closest["timestamp_ms"] - timestamp_ms) <= tolerance_ms:
            return [closest]
        return []

    def render(self, frame, data):
        """绘制速度文本"""
        if not data:
            text = f"{self.label}: N/A"
        else:
            speed = data[0].get("speed", 0)
            text = f"{self.label}: {speed:.1f} km/h"

        # 绘制黑色背景
        cv2.rectangle(frame, (15, 25), (250, 60), (0, 0, 0), -1)

        # 绘制绿色文本
        cv2.putText(frame, text, self.position,
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        return frame
```

### **示例2：嵌套数据渲染器**

```python
class GPSRenderer(DataRenderer):
    """显示GPS坐标和海拔"""

    def load_data(self, data_path):
        self.data = load_jsonl(data_path)

    def match_data(self, timestamp_ms, tolerance_ms=50.0):
        # 同上
        ...

    def render(self, frame, data):
        if not data:
            return frame

        # 提取嵌套结构
        record = data[0]
        gps = record.get("gps", {})
        lat = gps.get("lat", 0)
        lon = gps.get("lon", 0)
        alt = record.get("altitude", 0)

        # 绘制多行文本
        lines = [
            f"GPS: {lat:.4f}, {lon:.4f}",
            f"Alt: {alt:.1f}m"
        ]

        y = 50
        for line in lines:
            cv2.putText(frame, line, (20, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
            y += 35

        return frame
```

### **内置示例渲染器**

位于 `nexus.contrib.repro.examples`:

- `SimpleTextRenderer` - 单个数值显示
- `MultiValueRenderer` - 多字段仪表盘
- `NestedDataRenderer` - 嵌套数据示例

---

## 🚀 **完整使用流程**

### **步骤1：准备数据**

创建 `data/speed.jsonl`:
```jsonl
{"timestamp_ms": 0.0, "speed": 120.5}
{"timestamp_ms": 33.33, "speed": 122.0}
{"timestamp_ms": 66.67, "speed": 125.5}
```

### **步骤2：实现渲染器**

创建 `my_renderers.py`:
```python
from nexus.contrib.repro.types import DataRenderer, load_jsonl
import cv2

class SpeedRenderer(DataRenderer):
    # ... 参考上面的实现
```

### **步骤3：配置Pipeline**

创建 `case.yaml`:
```yaml
pipeline:
  # 1. 切分视频
  - plugin: "Video Splitter"
    config:
      video_path: "input.mp4"
      output_dir: "frames"

  # 2. 渲染数据 ⭐ 指定自定义渲染器
  - plugin: "Data Renderer"
    config:
      frames_dir: "frames"
      output_dir: "rendered_frames"
      renderer_class: "my_renderers.SpeedRenderer"  # 你的渲染器类
      renderer_kwargs:
        data_path: "data/speed.jsonl"
        label: "Vehicle Speed"
        position: [20, 50]

  # 3. 合成视频
  - plugin: "Video Composer"
    config:
      frames_dir: "rendered_frames"
      output_path: "output.mp4"
      fps: 30.0
```

### **步骤4：运行**

```bash
nexus run --case my_replay
```

---

## 📊 **高级用法**

### **多数据线渲染**

同时渲染多个数据源：

```python
class MultiDataRenderer(DataRenderer):
    def __init__(self, speed_path, gps_path):
        self.speed_data = load_jsonl(speed_path)
        self.gps_data = load_jsonl(gps_path)
        # 不调用 super().__init__，因为有多个数据源

    def load_data(self, data_path):
        pass  # 已在 __init__ 中加载

    def match_data(self, timestamp_ms, tolerance_ms=50.0):
        speed = self._match_from(self.speed_data, timestamp_ms, tolerance_ms)
        gps = self._match_from(self.gps_data, timestamp_ms, tolerance_ms)
        return [{"speed": speed, "gps": gps}]

    def _match_from(self, data, timestamp_ms, tolerance_ms):
        # 通用匹配逻辑
        ...
```

### **使用内置示例**

```yaml
- plugin: "Data Renderer"
  config:
    renderer_class: "nexus.contrib.repro.examples.SimpleTextRenderer"
    renderer_kwargs:
      data_path: "data/speed.jsonl"
      value_key: "speed"
      label: "Speed"
```

### **Python API直接调用**

```python
from pathlib import Path
from nexus.contrib.repro.video import extract_frames, compose_video
from nexus.contrib.repro.types import load_frame_timestamps
from my_renderers import SpeedRenderer
import cv2

# 1. 切帧
metadata = extract_frames(Path("input.mp4"), Path("frames/"))

# 2. 渲染
frame_times = load_frame_timestamps(Path("frames/frame_timestamps.csv"))
renderer = SpeedRenderer("data/speed.jsonl")

for _, row in frame_times.iterrows():
    frame_idx = int(row["frame_index"])
    timestamp = row["timestamp_ms"]

    frame = cv2.imread(f"frames/frame_{frame_idx:06d}.png")
    data = renderer.match_data(timestamp)
    rendered = renderer.render(frame, data)
    cv2.imwrite(f"rendered/frame_{frame_idx:06d}.png", rendered)

# 3. 合成
compose_video(Path("rendered/"), Path("output.mp4"), fps=metadata.fps)
```

---

## 🛠️ **工具函数**

### **数据加载**

```python
from nexus.contrib.repro.types import load_jsonl, save_jsonl, load_data_series

# JSONL
data = load_jsonl("data.jsonl")  # List[dict]

# CSV (向后兼容)
df = load_data_series("data.csv")  # DataFrame

# 保存JSONL
save_jsonl(data, "output.jsonl")
```

### **时间匹配算法**

```python
from nexus.contrib.repro.matching import match_data_to_timestamp

# 最近邻
data = match_data_to_timestamp(df, 100.0, method="nearest")

# 范围匹配
data = match_data_to_timestamp(df, 100.0, method="range", tolerance_ms=100)

# 线性插值
data = match_data_to_timestamp(df, 100.0, method="interpolate")
```

---

## 🎨 **渲染技巧**

### **使用OpenCV绘图**

```python
import cv2

# 文本
cv2.putText(frame, "Hello", (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

# 矩形
cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), -1)  # -1填充

# 圆形
cv2.circle(frame, (cx, cy), radius, (0, 0, 255), 2)

# 折线
points = np.array([[x1, y1], [x2, y2], ...], np.int32)
cv2.polylines(frame, [points], False, (255, 255, 0), 2)
```

### **颜色代码**

OpenCV使用BGR格式：
```python
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (0, 0, 255)
GREEN = (0, 255, 0)
BLUE = (255, 0, 0)
YELLOW = (0, 255, 255)
MAGENTA = (255, 0, 255)
CYAN = (255, 255, 0)
```

---

## 📂 **项目结构**

```
contrib/repro/
├── types.py          # DataRenderer抽象基类 + JSONL工具
├── video.py          # 视频切分/合成
├── matching.py       # 时间匹配算法
├── rendering.py      # (已废弃，使用examples.py)
├── examples.py       # 示例渲染器实现 ⭐
└── README.md         # 本文档

contrib/nexus/
└── __init__.py       # 3个插件：Video Splitter, Data Renderer, Video Composer
```

---

## 🎯 **典型应用场景**

- **自动驾驶**: 传感器数据、轨迹、速度叠加到行车记录
- **体育分析**: 心率、速度、位置可视化
- **无人机**: GPS轨迹、高度、姿态角
- **实验记录**: 温度、压力、流量等测量值
- **游戏回放**: 玩家状态、坐标、操作

---

## 🔧 **FAQ**

**Q: 必须用JSONL吗？**
A: 不是。继承 `DataRenderer` 后，`load_data()` 可以读取任何格式（CSV、数据库、API等）。JSONL只是推荐格式。

**Q: 如何处理大数据？**
A: 渲染器中用生成器或分块加载。`match_data()` 可以使用二分查找优化。

**Q: 能否并行渲染？**
A: 可以。参考 `multiprocessing` 并行处理帧。

**Q: 渲染器能否有状态（如历史窗口）？**
A: 可以。在 `__init__` 中初始化状态，在 `render()` 中更新。

---

## 📚 **参考资料**

- OpenCV文档: https://docs.opencv.org/
- JSONL格式: https://jsonlines.org/
- Python ABC: https://docs.python.org/3/library/abc.html

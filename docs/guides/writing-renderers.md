# 编写Repro渲染器

创建自定义数据渲染器用于视频可视化

## 概述

Repro渲染器是独立的Python类，用于将时序数据可视化到视频帧上。

**核心特点**：
- 继承 `BaseDataRenderer` 获得匹配功能
- 只需实现 `render()` 方法
- 使用全类名在配置中引用

## 最简单的渲染器

```python
from nexus.contrib.repro.renderers import BaseDataRenderer
import cv2

class MyRenderer(BaseDataRenderer):
    def render(self, frame, timestamp_ms):
        # 在帧上绘制文本
        cv2.putText(
            frame, "Hello Repro!",
            (30, 60),  # 位置
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,  # 字体大小
            (0, 255, 0),  # 颜色 (BGR)
            2  # 粗细
        )
        return frame
```

**使用**：

```yaml
renderers:
  - class: "your.module.path.MyRenderer"  # 全类名
    kwargs: {}
```

## 带数据的渲染器

大多数渲染器需要加载和匹配时序数据。

```python
class TemperatureRenderer(BaseDataRenderer):
    def __init__(self, data_path, position=(30, 60), **kwargs):
        # 调用父类初始化（加载数据，设置匹配参数）
        super().__init__(data_path, **kwargs)
        self.position = position

    def render(self, frame, timestamp_ms):
        # 匹配数据
        matched = self.match_data(timestamp_ms)

        if not matched:
            # 没有匹配的数据，直接返回原帧
            return frame

        # 获取数据
        temperature = matched[0]['temperature']

        # 绘制温度
        text = f"Temperature: {temperature:.1f}°C"
        cv2.putText(
            frame, text,
            self.position,
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0, (255, 255, 255), 2
        )

        return frame
```

**数据格式** (JSONL):
```json
{"timestamp_ms": 1759284000000.0, "temperature": 25.3}
{"timestamp_ms": 1759284001000.0, "temperature": 25.5}
```

**使用**：

```yaml
renderers:
  - class: "your.module.path.TemperatureRenderer"
    kwargs:
      data_path: "input/temperature.jsonl"
      position: [30, 60]
      tolerance_ms: 1000.0  # 1秒容差
```

## BaseDataRenderer功能

继承 `BaseDataRenderer` 获得：

### 1. 自动数据加载

```python
def __init__(self, data_path, **kwargs):
    super().__init__(data_path, **kwargs)
    # self.data已经加载为list of dict
```

### 2. 时间匹配

```python
# 三种匹配策略
super().__init__(
    data_path,
    match_strategy="nearest",  # 或 "forward", "backward"
    tolerance_ms=50.0
)

# 在render中使用
matched = self.match_data(timestamp_ms)
```

**匹配策略**：

- **nearest**：最接近的数据点（双向）
  - 适用：高频均匀数据（20Hz目标检测）

- **forward**：最近的历史数据点（向前查找）
  - 数据"保持"直到下一次更新
  - 适用：事件驱动数据（速度变化时才发送）

- **backward**：最近的未来数据点（向后查找）
  - 适用：预测性数据

### 3. 时间偏移

处理数据和视频时间不同步：

```python
super().__init__(
    data_path,
    time_offset_ms=100  # 数据比视频晚100ms
)

# match_data自动应用offset
```

## 完整示例：GPS渲染器

```python
from nexus.contrib.repro.renderers import BaseDataRenderer
import cv2
import numpy as np

class GPSRenderer(BaseDataRenderer):
    """
    渲染GPS位置和轨迹。

    数据格式 (JSONL):
        {"timestamp_ms": 1234567890.0, "lat": 40.7128, "lon": -74.0060}
    """

    def __init__(
        self,
        data_path,
        position=(30, 60),
        map_center=(40.7128, -74.0060),
        map_scale=1000.0,  # 米/像素
        show_trail=True,
        trail_length=50,  # 轨迹点数
        **kwargs
    ):
        super().__init__(
            data_path,
            match_strategy="nearest",
            tolerance_ms=1000.0,  # 1秒容差
            **kwargs
        )

        self.position = position
        self.map_center = map_center
        self.map_scale = map_scale
        self.show_trail = show_trail
        self.trail_length = trail_length

        # 轨迹历史
        self.trail_history = []

    def render(self, frame, timestamp_ms):
        # 匹配数据
        matched = self.match_data(timestamp_ms)

        if not matched:
            return frame

        gps_data = matched[0]
        lat = gps_data['lat']
        lon = gps_data['lon']

        # 绘制当前位置
        text = f"GPS: {lat:.6f}, {lon:.6f}"
        cv2.putText(
            frame, text,
            self.position,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7, (255, 255, 255), 2
        )

        # 添加到轨迹历史
        if self.show_trail:
            self.trail_history.append((lat, lon))
            if len(self.trail_history) > self.trail_length:
                self.trail_history.pop(0)

            # 绘制轨迹
            self._draw_trail(frame)

        return frame

    def _draw_trail(self, frame):
        """绘制GPS轨迹"""
        if len(self.trail_history) < 2:
            return

        # 转换GPS坐标到像素坐标
        points = []
        for lat, lon in self.trail_history:
            x = int((lon - self.map_center[1]) * self.map_scale + 500)
            y = int((self.map_center[0] - lat) * self.map_scale + 500)
            points.append((x, y))

        # 绘制轨迹线
        points_array = np.array(points, dtype=np.int32)
        cv2.polylines(
            frame, [points_array],
            isClosed=False,
            color=(0, 255, 255),  # 黄色
            thickness=2
        )

        # 绘制当前位置（红点）
        if points:
            cv2.circle(frame, points[-1], 5, (0, 0, 255), -1)
```

**使用**：

```yaml
renderers:
  - class: "your.module.path.GPSRenderer"
    kwargs:
      data_path: "input/gps.jsonl"
      position: [30, 60]
      map_center: [40.7128, -74.0060]  # NYC
      map_scale: 1000.0
      show_trail: true
      trail_length: 100
```

## 高级技巧

### 1. 多数据源

渲染器可以加载多个数据文件：

```python
from nexus.contrib.repro.io import load_jsonl

class MultiSensorRenderer:
    def __init__(self, speed_path, temp_path, **kwargs):
        # 手动加载多个数据文件
        self.speed_data = load_jsonl(speed_path)
        self.temp_data = load_jsonl(temp_path)

        # 初始化匹配参数
        self.tolerance_ms = kwargs.get('tolerance_ms', 50.0)

    def render(self, frame, timestamp_ms):
        # 手动匹配速度数据
        speed_matched = self._match_nearest(
            self.speed_data, timestamp_ms, self.tolerance_ms
        )

        # 手动匹配温度数据
        temp_matched = self._match_nearest(
            self.temp_data, timestamp_ms, self.tolerance_ms
        )

        # 绘制两种数据
        ...

        return frame

    def _match_nearest(self, data, timestamp_ms, tolerance_ms):
        """手动实现最近匹配"""
        if not data:
            return []

        closest = min(
            data,
            key=lambda d: abs(d["timestamp_ms"] - timestamp_ms)
        )

        if abs(closest["timestamp_ms"] - timestamp_ms) <= tolerance_ms:
            return [closest]
        return []
```

### 2. 状态保持

在渲染器中保持状态：

```python
@render("particle_filter")
class ParticleFilterRenderer(BaseDataRenderer):
    def __init__(self, data_path, **kwargs):
        super().__init__(data_path, **kwargs)

        # 初始化状态
        self.particles = self._initialize_particles()
        self.last_timestamp = None

    def render(self, frame, timestamp_ms):
        matched = self.match_data(timestamp_ms, self.tolerance_ms)

        if matched:
            # 更新粒子
            measurement = matched[0]
            self._update_particles(measurement)

        # 绘制粒子
        self._draw_particles(frame)

        self.last_timestamp = timestamp_ms
        return frame
```

### 3. 配置颜色

支持动态颜色配置：

```python
@render("configurable")
class ConfigurableRenderer(BaseDataRenderer):
    def __init__(
        self,
        data_path,
        color=(0, 255, 0),  # BGR tuple
        **kwargs
    ):
        super().__init__(data_path, **kwargs)

        # 支持多种颜色格式
        if isinstance(color, str):
            self.color = self._parse_color(color)
        else:
            self.color = tuple(color)  # 列表转元组

    def _parse_color(self, color_str):
        """解析颜色字符串"""
        colors = {
            "red": (0, 0, 255),
            "green": (0, 255, 0),
            "blue": (255, 0, 0),
            "yellow": (0, 255, 255),
            "white": (255, 255, 255)
        }
        return colors.get(color_str.lower(), (255, 255, 255))
```

**使用**：

```yaml
renderers:
  - name: "configurable"
    kwargs:
      data_path: "input/data.jsonl"
      color: "red"  # 或 [0, 0, 255]
```

### 4. 条件渲染

根据数据值决定是否渲染：

```python
@render("conditional")
class ConditionalRenderer(BaseDataRenderer):
    def __init__(self, data_path, threshold=50.0, **kwargs):
        super().__init__(data_path, **kwargs)
        self.threshold = threshold

    def render(self, frame, timestamp_ms):
        matched = self.match_data(timestamp_ms, self.tolerance_ms)

        if not matched:
            return frame

        value = matched[0]['value']

        # 只在超过阈值时渲染
        if value > self.threshold:
            # 红色警告
            cv2.putText(
                frame, f"WARNING: {value:.1f}",
                (30, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5, (0, 0, 255), 3
            )

        return frame
```

## 测试渲染器

### 1. 单元测试

```python
import pytest
import numpy as np
from my_renderer import TemperatureRenderer

def test_temperature_renderer():
    # 创建测试帧
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    # 创建渲染器
    renderer = TemperatureRenderer(
        data_path="test/data/temperature.jsonl",
        position=(30, 60)
    )

    # 渲染
    result = renderer.render(frame, timestamp_ms=1000000)

    # 验证
    assert result.shape == frame.shape
    assert not np.array_equal(result, frame)  # 应该有修改
```

### 2. 可视化测试

```python
# test_visual.py
from nexus.contrib.repro import render_all_frames

render_all_frames(
    frames_dir="test/frames",
    output_dir="test/output",
    timestamps_path="test/timestamps.csv",
    renderer_configs=[
        {
            "name": "my_renderer",
            "kwargs": {"data_path": "test/data.jsonl"}
        }
    ]
)

print("Check test/output/ for rendered frames")
```

### 3. Pipeline测试

```yaml
# test_case/case.yaml
pipeline:
  - plugin: "Video Splitter"
    config:
      video_path: "test/video.mp4"
      output_dir: "temp/frames"

  - plugin: "Data Renderer"
    config:
      frames_dir: "temp/frames"
      output_dir: "temp/rendered"
      renderers:
        - name: "my_renderer"
          kwargs:
            data_path: "test/data.jsonl"
```

```bash
nexus run --case test_case
```

## 性能优化

### 1. 缓存计算结果

```python
@render("optimized")
class OptimizedRenderer(BaseDataRenderer):
    def __init__(self, data_path, **kwargs):
        super().__init__(data_path, **kwargs)

        # 预计算
        self._precompute()

    def _precompute(self):
        """预计算复杂运算"""
        self.lookup_table = {}
        for data_point in self.data:
            value = data_point['value']
            # 预计算复杂函数
            self.lookup_table[value] = expensive_function(value)

    def render(self, frame, timestamp_ms):
        matched = self.match_data(timestamp_ms, self.tolerance_ms)
        if matched:
            value = matched[0]['value']
            # 使用预计算结果
            result = self.lookup_table.get(value)
            ...
        return frame
```

### 2. 跳过不必要的绘制

```python
def render(self, frame, timestamp_ms):
    matched = self.match_data(timestamp_ms, self.tolerance_ms)

    if not matched:
        return frame  # 快速返回

    # 检查是否有变化
    if matched[0] == self.last_data:
        return frame  # 数据没变，跳过

    self.last_data = matched[0]

    # 执行绘制
    ...
    return frame
```

## 常见模式

### 1. 文本渲染器

```python
@render("text")
class TextRenderer(BaseDataRenderer):
    def render(self, frame, timestamp_ms):
        matched = self.match_data(timestamp_ms, self.tolerance_ms)
        if matched:
            text = matched[0]['text']
            cv2.putText(frame, text, self.position, ...)
        return frame
```

### 2. 图形渲染器

```python
@render("box")
class BoxRenderer(BaseDataRenderer):
    def render(self, frame, timestamp_ms):
        matched = self.match_data(timestamp_ms, self.tolerance_ms)
        if matched:
            box = matched[0]['box']  # [x, y, w, h]
            cv2.rectangle(
                frame,
                (box[0], box[1]),
                (box[0] + box[2], box[1] + box[3]),
                self.color, 2
            )
        return frame
```

### 3. 轨迹渲染器

```python
@render("trail")
class TrailRenderer(BaseDataRenderer):
    def __init__(self, data_path, trail_length=100, **kwargs):
        super().__init__(data_path, **kwargs)
        self.trail_length = trail_length
        self.trail = []

    def render(self, frame, timestamp_ms):
        matched = self.match_data(timestamp_ms, self.tolerance_ms)
        if matched:
            point = matched[0]['point']  # [x, y]
            self.trail.append(point)
            if len(self.trail) > self.trail_length:
                self.trail.pop(0)

        # 绘制轨迹
        if len(self.trail) >= 2:
            points = np.array(self.trail, dtype=np.int32)
            cv2.polylines(frame, [points], False, self.color, 2)

        return frame
```

## 下一步

- [Repro概览](../repro/README.md) - 了解Repro模块
- [渲染器系统](../repro/renderers.md) - 内置渲染器参考
- [视频处理](../repro/video-processing.md) - 视频处理API
- [API参考](../repro/api-reference.md) - 完整API文档

# Configuration References and Shared Defaults

## 概述

Nexus 支持配置引用机制，允许你在 `defaults` 命名空间中定义共享配置，然后在 pipeline 中引用它们。

## 核心特性

### 1. `defaults` 命名空间

在 `global.yaml` 或 `case.yaml` 中定义共享配置：

```yaml
# global.yaml 或 case.yaml
defaults:
  # 定义可重用的配置块
  speed_renderer:
    position: [30, 60]
    tolerance_ms: 5000.0
    font_scale: 1.2
    color: [0, 255, 0]
```

### 2. 引用语法

使用 `@defaults.` 前缀引用配置：

```yaml
# 直接引用
value: "@defaults.speed_renderer"

# 继承并覆盖
config:
  _extends: "@defaults.speed_renderer"
  data_path: "input/speed.jsonl"  # 新增字段
  color: [255, 0, 0]               # 覆盖字段
```

## 使用方式

### 方式1：直接引用

完全使用默认配置，适合不需要修改的场景：

```yaml
defaults:
  common_settings:
    tolerance_ms: 50.0
    time_offset_ms: 0

pipeline:
  - plugin: "My Plugin"
    config:
      settings: "@defaults.common_settings"
      # settings 将被替换为 {tolerance_ms: 50.0, time_offset_ms: 0}
```

**结果：**
```yaml
settings:
  tolerance_ms: 50.0
  time_offset_ms: 0
```

### 方式2：继承并覆盖 (推荐)

继承基础配置，同时覆盖部分字段：

```yaml
defaults:
  speed_renderer:
    position: [30, 60]
    tolerance_ms: 5000.0
    font_scale: 1.2
    color: [0, 255, 0]

pipeline:
  - plugin: "Data Renderer"
    config:
      renderers:
        - name: "speed"
          kwargs:
            _extends: "@defaults.speed_renderer"  # 继承基础配置
            data_path: "input/speed.jsonl"        # 新增字段
            color: [255, 0, 0]                    # 覆盖为红色
```

**结果：**
```yaml
kwargs:
  position: [30, 60]              # 来自 defaults
  tolerance_ms: 5000.0            # 来自 defaults
  font_scale: 1.2                 # 来自 defaults
  color: [255, 0, 0]              # 本地覆盖
  data_path: "input/speed.jsonl"  # 本地新增
```

### 方式3：嵌套引用

支持多层嵌套的配置引用：

```yaml
defaults:
  camera:
    main:
      calibration_path: "config/camera_calibration.yaml"
      resolution:
        width: 1920
        height: 1080

pipeline:
  - plugin: "Data Renderer"
    config:
      renderers:
        - name: "target"
          kwargs:
            calibration_path: "@defaults.camera.main.calibration_path"
            # 引用深层嵌套的值
```

## 配置优先级

```
global.yaml defaults (最低优先级)
    ↓ 覆盖
case.yaml defaults
    ↓ 覆盖
pipeline 本地配置 (最高优先级)
```

### 示例：多层覆盖

```yaml
# global.yaml
defaults:
  renderer_base:
    tolerance_ms: 100.0
    color: [0, 255, 0]

# case.yaml
defaults:
  renderer_base:
    tolerance_ms: 50.0  # 覆盖 global

# pipeline
renderers:
  - name: "speed"
    kwargs:
      _extends: "@defaults.renderer_base"
      tolerance_ms: 30.0  # 覆盖 case

# 最终结果：
# tolerance_ms: 30.0 (pipeline)
# color: [0, 255, 0] (global)
```

## 深度合并

嵌套字典会被智能合并：

```yaml
defaults:
  base_config:
    a: 1
    b:
      c: 2
      d: 3
    e: [1, 2, 3]

pipeline:
  - plugin: "My Plugin"
    config:
      settings:
        _extends: "@defaults.base_config"
        b:
          d: 999  # 只覆盖 b.d，保留 b.c
        f: 4      # 新增字段
```

**结果：**
```yaml
settings:
  a: 1           # 来自 base
  b:
    c: 2         # 来自 base (保留)
    d: 999       # 本地覆盖
  e: [1, 2, 3]   # 来自 base
  f: 4           # 本地新增
```

## 完整示例

```yaml
# case.yaml
defaults:
  # 通用渲染器配置
  renderer_base:
    tolerance_ms: 50.0
    time_offset_ms: 0

  # 速度渲染器配置
  speed_renderer:
    position: [30, 60]
    tolerance_ms: 5000.0
    font_scale: 1.2
    color: [0, 255, 0]

  # 目标渲染器配置
  target_renderer:
    tolerance_ms: 50.0
    box_color: [0, 255, 0]
    box_thickness: 2
    show_panel: true

  # 摄像头配置
  camera:
    main_calibration: "config/camera_calibration.yaml"

pipeline:
  - plugin: "Video Splitter"
    config:
      video_path: "input/video.mp4"
      output_dir: "temp/frames"

  - plugin: "Data Renderer"
    config:
      frames_dir: "temp/frames"
      output_dir: "temp/rendered"

      renderers:
        # 速度渲染器：继承并覆盖
        - name: "speed"
          kwargs:
            _extends: "@defaults.speed_renderer"
            data_path: "input/speed.jsonl"
            color: [255, 0, 0]  # 改为红色

        # 目标渲染器：继承并引用嵌套值
        - name: "target"
          kwargs:
            _extends: "@defaults.target_renderer"
            data_path: "input/targets.jsonl"
            calibration_path: "@defaults.camera.main_calibration"

  - plugin: "Video Composer"
    config:
      frames_dir: "temp/rendered"
      output_path: "output/final.mp4"
      fps: 30.0
```

## 最佳实践

### ✅ 推荐

1. **使用 `defaults` 命名空间**
```yaml
defaults:
  my_config:
    key: value
```

2. **使用 `_extends` 继承配置**
```yaml
config:
  _extends: "@defaults.base"
  additional_key: value
```

3. **分层组织配置**
```yaml
defaults:
  renderers:
    speed: {...}
    target: {...}
  camera:
    main: {...}
    backup: {...}
```

4. **在 global.yaml 定义通用默认值**
```yaml
# global.yaml
defaults:
  common:
    tolerance_ms: 50.0
```

5. **在 case.yaml 定义案例特定默认值**
```yaml
# case.yaml
defaults:
  speed_renderer:
    data_path: "input/speed.jsonl"
```

### ❌ 避免

1. **循环引用**
```yaml
# ✗ 错误
defaults:
  a: "@defaults.b"
  b: "@defaults.a"
```

2. **引用不存在的配置**
```yaml
# ✗ 错误
config: "@defaults.nonexistent"
```

3. **在 defaults 中使用引用自己**
```yaml
# ✗ 错误
defaults:
  a:
    value: "@defaults.a"
```

## 错误处理

系统会检测并报告以下错误：

### 1. 引用不存在
```
ConfigResolutionError: Reference '@defaults.speed_renderer' not found:
'speed_renderer' missing in path
```

### 2. 循环引用
```
ConfigResolutionError: Circular reference detected:
defaults.a -> defaults.b -> defaults.a
```

### 3. 类型错误
```
ConfigResolutionError: Cannot extend non-dict value:
@defaults.value -> <class 'str'>
```

## 技术细节

### 引用模式

```python
# 引用模式：@namespace.path.to.config
REFERENCE_PATTERN = r'^@([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)$'

# 有效引用：
"@defaults.speed_renderer"          # ✓
"@defaults.camera.main"              # ✓
"@defaults.a.b.c.d"                  # ✓

# 无效引用：
"defaults.speed_renderer"            # ✗ 缺少 @
"@speed_renderer"                    # ✗ 缺少 defaults 命名空间
"@defaults"                          # ✗ 缺少具体路径
```

### 解析流程

```
1. 加载 global.yaml → 读取 defaults
2. 加载 case.yaml → 合并 defaults (case 覆盖 global)
3. 加载 pipeline 配置
4. 遇到引用时：
   a. 解析引用路径
   b. 查找 defaults 中的值
   c. 递归解析引用的值
   d. 如果是 _extends，深度合并配置
5. 返回完全展开的配置
6. 传递给 plugin
```

### API 参考

```python
from nexus.core.config_resolver import (
    ConfigResolver,
    resolve_config,
    ConfigResolutionError,
)

# 创建解析器
resolver = ConfigResolver(defaults={'key': 'value'})

# 解析配置
resolved = resolver.resolve(config)

# 便捷函数
resolved = resolve_config(config, defaults)
```

## 相关文件

- 实现：`src/nexus/core/config_resolver.py`
- 集成：`src/nexus/core/engine.py`
- 示例：`examples/config_references_example.yaml`

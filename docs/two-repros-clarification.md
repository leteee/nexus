# 重要澄清：两个不同的 repro

## 问题

在导入流程中，有两个名为 `repro` 的东西，容易混淆：

1. `src/nexus/contrib/nexus/repro.py` - Plugin 适配器模块
2. `src/nexus/contrib/repro/` - Repro 业务逻辑包

---

## 区别说明

### 1. Plugin 适配器模块（`contrib/nexus/repro.py`）

**路径**: `src/nexus/contrib/nexus/repro.py`

**类型**: Python 模块文件（.py 文件）

**作用**:
- 定义 Nexus plugin（使用 `@plugin` 装饰器）
- 将 repro 功能适配为 Nexus 插件接口
- 充当"胶水代码"，连接框架和业务逻辑

**内容示例**:
```python
from nexus.core.discovery import plugin
from nexus.core.types import PluginConfig

# 导入业务逻辑包的功能
from nexus.contrib.repro.video import extract_frames, compose_video, render_all_frames

@plugin(name="Video Splitter", config=VideoSplitterConfig)
def split_video_to_frames(ctx: PluginContext) -> Any:
    """Extract all frames from video and save as images."""
    # 调用业务逻辑
    metadata = extract_frames(video_path, output_dir)
    return metadata
```

---

### 2. Repro 业务逻辑包（`contrib/repro/`）

**路径**: `src/nexus/contrib/repro/`

**类型**: Python 包（目录，包含 `__init__.py`）

**作用**:
- 包含视频处理、数据渲染等业务逻辑
- 框架无关，可以独立使用
- 定义 Renderer（使用 `@register_unit` 装饰器）

**目录结构**:
```
src/nexus/contrib/repro/
├── __init__.py          # 包初始化，导入 standard_runners 和 renderers
├── video.py             # 视频处理功能
├── io.py                # I/O 工具
├── utils.py             # 工具函数
├── datagen.py           # 数据生成
├── types.py             # 类型定义
└── renderers/           # Renderer 子包
    ├── __init__.py
    ├── base.py
    ├── speed_renderer.py     # @register_unit("speed", unit_type="renderer")
    └── target_renderer.py    # @register_unit("target", unit_type="renderer")
```

---

## 导入流程详解

### 步骤 1: 导入 plugin 适配器模块

```python
# src/nexus/contrib/nexus/__init__.py:13
from . import repro  # 导入 src/nexus/contrib/nexus/repro.py
```

**导入的是**: Plugin 适配器模块（`.py` 文件）

**Python 加载**: `src/nexus/contrib/nexus/repro.py`

**效果**:
- 执行 `repro.py` 中的所有顶层代码
- 注册所有 `@plugin` 装饰的函数

---

### 步骤 2: Plugin 适配器导入业务逻辑包

```python
# src/nexus/contrib/nexus/repro.py:13
from nexus.contrib.repro.video import extract_frames, compose_video, render_all_frames
#     ^^^^^^^^^^^^^^^^^^^
#     这是一个包路径，不是模块！
```

**导入的是**: Repro 业务逻辑包的 `video` 模块

**Python 加载顺序**:
1. 检查 `nexus.contrib.repro` 包是否已导入
2. 如果没有，先导入包（执行 `nexus.contrib.repro/__init__.py`）
3. 然后导入包中的 `video` 模块（执行 `nexus.contrib.repro/video.py`）

**关键**: 这里会触发 `src/nexus/contrib/repro/__init__.py` 的执行！

---

### 步骤 3: Repro 包初始化，注册 Renderer

```python
# src/nexus/contrib/repro/__init__.py:44
from nexus.core import standard_runners  # 注册 "renderer" 类型

# src/nexus/contrib/repro/__init__.py:78-84
from .renderers import (
    SpeedRenderer,      # 触发 @register_unit("speed", ...)
    TargetRenderer,     # 触发 @register_unit("target", ...)
)
```

**效果**:
1. 注册 "renderer" 类型到统一执行单元框架
2. 导入所有 renderer 类，触发 `@register_unit` 装饰器
3. 所有 renderer 注册到全局注册表

---

## 可视化对比

### 两个 repro 的关系

```
┌─────────────────────────────────────────────────────────────┐
│ Plugin 适配器模块 (contrib/nexus/repro.py)                 │
│                                                             │
│ - 定义 @plugin 装饰的函数                                  │
│ - 充当 Nexus 框架和业务逻辑的桥梁                         │
│                                                             │
│   @plugin(name="Video Splitter")                           │
│   def split_video_to_frames(ctx):                          │
│       return extract_frames(...)  # 调用业务逻辑         │
│                                                             │
│   需要使用 ↓                                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ from nexus.contrib.repro.video import ...
                            │
                            v
┌─────────────────────────────────────────────────────────────┐
│ 业务逻辑包 (contrib/repro/)                                │
│                                                             │
│ ├── __init__.py      # 注册 renderer 类型和实例          │
│ ├── video.py         # def extract_frames()               │
│ ├── io.py                                                  │
│ ├── utils.py                                               │
│ └── renderers/                                             │
│     ├── speed_renderer.py                                  │
│     │   @register_unit("speed", unit_type="renderer")     │
│     │   class SpeedRenderer: ...                          │
│     │                                                      │
│     └── target_renderer.py                                 │
│         @register_unit("target", unit_type="renderer")    │
│         class TargetRenderer: ...                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 为什么这样设计？

### 设计模式：Adapter Pattern（适配器模式）

**目标**: 将框架无关的业务逻辑适配为 Nexus 插件

**好处**:

1. **解耦合**: 业务逻辑不依赖 Nexus 框架
   ```python
   # 业务逻辑可以独立使用
   from nexus.contrib.repro import extract_frames
   metadata = extract_frames("video.mp4", "frames/")
   ```

2. **可复用**: 同一套业务逻辑可以适配到不同框架
   ```
   contrib/repro/           # 业务逻辑（框架无关）
   contrib/nexus/repro.py   # Nexus 适配器
   contrib/airflow/repro.py # Airflow 适配器（假设）
   contrib/luigi/repro.py   # Luigi 适配器（假设）
   ```

3. **测试友好**: 业务逻辑可以独立测试，无需启动框架
   ```python
   # 单元测试不需要 Nexus
   from nexus.contrib.repro import extract_frames
   result = extract_frames(...)
   assert result.total_frames == 100
   ```

4. **清晰职责**:
   - `contrib/repro/`: 业务逻辑实现
   - `contrib/nexus/repro.py`: 框架集成和配置处理

---

## 导入时机对比

| 模块/包 | 导入时机 | 触发方式 |
|---------|----------|----------|
| `contrib.nexus.repro` (模块) | Plugin 发现阶段 | `discover_from_path()` → `import contrib.nexus` |
| `nexus.contrib.repro` (包) | Plugin 适配器导入业务逻辑时 | `from nexus.contrib.repro.video import ...` |
| `SpeedRenderer` | Repro 包初始化时 | `nexus.contrib.repro/__init__.py` → `from .renderers import ...` |

---

## 完整导入链（澄清版）

```
discover_from_path("src/nexus/contrib")
    │
    ├─> import contrib
    │      └─> src/nexus/contrib/__init__.py (空)
    │
    └─> import contrib.nexus
           └─> src/nexus/contrib/nexus/__init__.py
                  │
                  ├─> from . import basic
                  │      └─> src/nexus/contrib/nexus/basic.py
                  │
                  └─> from . import repro  ← 注意：这是导入模块
                         └─> src/nexus/contrib/nexus/repro.py (Plugin 适配器)
                                │
                                │ 第 13 行执行：
                                │ from nexus.contrib.repro.video import ...
                                │                ^^^^^^^^^^^^^^^^^^
                                │                这是包路径！
                                │
                                └─> 触发导入 src/nexus/contrib/repro/ (业务逻辑包)
                                       │
                                       └─> src/nexus/contrib/repro/__init__.py
                                              │
                                              ├─> from nexus.core import standard_runners
                                              │      └─> register_type("renderer", ...)
                                              │
                                              └─> from .renderers import SpeedRenderer, TargetRenderer
                                                     ├─> @register_unit("speed", ...)
                                                     └─> @register_unit("target", ...)
```

---

## 关键理解点

### 1. 名字相同，性质不同

- **`contrib.nexus.repro`**: 模块（`.py` 文件）
- **`nexus.contrib.repro`**: 包（目录）

### 2. 导入触发顺序

```
contrib.nexus.repro 被导入
    ↓
contrib.nexus.repro 执行 import 语句
    ↓
nexus.contrib.repro 被导入（首次）
    ↓
nexus.contrib.repro/__init__.py 执行
    ↓
Renderer 注册完成
```

### 3. Python 导入机制

当执行 `from nexus.contrib.repro.video import ...` 时：
1. Python 检查 `nexus.contrib.repro` 是否已导入
2. 如果没有，先导入包（执行 `__init__.py`）
3. 然后导入子模块 `video`

**这就是为什么 `nexus.contrib.repro/__init__.py` 会被执行！**

---

## 验证方法

可以通过添加 print 语句验证导入顺序：

```python
# src/nexus/contrib/nexus/__init__.py
print(">>> Loading contrib.nexus adapter package")
from . import repro
```

```python
# src/nexus/contrib/nexus/repro.py
print(">>> Loading contrib.nexus.repro adapter module")
from nexus.contrib.repro.video import ...
```

```python
# src/nexus/contrib/repro/__init__.py
print(">>> Loading nexus.contrib.repro business logic package")
from nexus.core import standard_runners
from .renderers import SpeedRenderer, TargetRenderer
```

**输出顺序**:
```
>>> Loading contrib.nexus adapter package
>>> Loading contrib.nexus.repro adapter module
>>> Loading nexus.contrib.repro business logic package
Registered unit type: renderer
```

---

## 总结

- **问题**: `from . import repro` 导入的是哪个 repro？
- **答案**: 导入的是 `src/nexus/contrib/nexus/repro.py`（Plugin 适配器模块）

- **问题**: 什么时候导入 `nexus.contrib.repro` 包？
- **答案**: 当 `repro.py` 执行 `from nexus.contrib.repro.video import ...` 时

- **问题**: Renderer 在哪里注册？
- **答案**: 在 `nexus.contrib.repro/__init__.py` 中，当它被首次导入时

- **关键**: Python 导入包时会先执行 `__init__.py`，这是触发 renderer 注册的关键！

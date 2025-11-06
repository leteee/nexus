# Renderer 发现机制详解

## 核心问题

框架是如何发现 renderer 的？

## 简短回答

通过 **装饰器注册 + 模块导入时自动执行** 的机制实现自动发现。

---

## 详细流程

### 1. 注册阶段（模块导入时）

```
程序启动
    │
    ├─> 导入 nexus.contrib.repro
    │      │
    │      ├─> 导入 nexus.core.standard_runners
    │      │      └─> 注册 "renderer" 类型到全局注册表
    │      │
    │      └─> 导入 renderers 子模块
    │             │
    │             ├─> 导入 SpeedRenderer
    │             │      └─> @register_unit("speed", unit_type="renderer")
    │             │             └─> 装饰器执行，调用 _registry.register_unit(...)
    │             │                    └─> 注册 "speed" -> SpeedRenderer 到注册表
    │             │
    │             └─> 导入 TargetRenderer
    │                    └─> @register_unit("target", unit_type="renderer")
    │                           └─> 装饰器执行，调用 _registry.register_unit(...)
    │                                  └─> 注册 "target" -> TargetRenderer 到注册表
    │
    └─> 所有 renderer 已注册完成，可以通过名称引用
```

### 2. 使用阶段（执行渲染时）

```
用户调用 render_all_frames(renderer_configs=[{"name": "speed", ...}])
    │
    ├─> 验证阶段
    │      └─> get_unit("speed", "renderer")
    │             └─> 从全局注册表查找 "speed"
    │                    └─> 找到！返回 UnitSpec(name="speed", implementation=SpeedRenderer, ...)
    │
    └─> 执行阶段
           └─> execute_unit("speed", "renderer", frame, timestamp_ms, config={...})
                  │
                  ├─> 获取 UnitSpec
                  ├─> 获取 RendererRunner
                  └─> runner.execute(spec, frame, timestamp_ms, config)
                         │
                         ├─> 检查缓存：是否已实例化？
                         │      └─> 否 -> 实例化 SpeedRenderer(**config)
                         │      └─> 是 -> 复用已有实例
                         │
                         └─> instance.render(frame, timestamp_ms)
```

---

## 关键代码路径

### 步骤 1: 类型注册（程序启动时）

**文件**: `src/nexus/core/standard_runners.py`

```python
# 定义 RendererRunner
class RendererRunner(UnitRunner):
    def __init__(self):
        self._instances: Dict[str, Any] = {}  # 实例缓存

    def execute(self, spec, frame, timestamp_ms, config=None):
        # 获取或创建实例
        if spec.name not in self._instances:
            instance = spec.implementation(**config)
            self._instances[spec.name] = instance

        renderer = self._instances[spec.name]
        return renderer.render(frame, timestamp_ms)

# 注册 "renderer" 类型
def register_standard_types():
    register_type(
        "renderer",
        RendererRunner(),
        "Data visualization renderers"
    )

# 模块导入时自动执行
register_standard_types()
```

**效果**: 全局注册表中注册了 "renderer" 类型，可以接受 renderer 单元的注册。

---

### 步骤 2: Renderer 注册（模块导入时）

**文件**: `src/nexus/contrib/repro/renderers/speed_renderer.py`

```python
from nexus.core.execution_units import register_unit

@register_unit("speed", unit_type="renderer")  # ← 装饰器在模块导入时执行
class SpeedRenderer(BaseDataRenderer):
    def __init__(self, data_path, position=(30, 60), **kwargs):
        super().__init__(data_path=data_path, **kwargs)
        self.position = position

    def render(self, frame, timestamp_ms):
        # 渲染逻辑
        return frame
```

**装饰器展开后相当于**:

```python
class SpeedRenderer(BaseDataRenderer):
    # ... 类定义 ...

# 装饰器立即执行以下代码：
_registry.register_unit(
    name="speed",
    unit_type="renderer",
    implementation=SpeedRenderer,
    config_model=None,
    description="Speed renderer for displaying...",
    metadata=None
)
```

---

### 步骤 3: 触发导入（确保注册执行）

**文件**: `src/nexus/contrib/repro/__init__.py`

```python
# 1. 确保 "renderer" 类型已注册
from nexus.core import standard_runners  # 导入时执行 register_standard_types()

# 2. 导入 renderers 模块，触发 @register_unit 装饰器
from .renderers import (
    BaseDataRenderer,
    SpeedRenderer,      # ← 导入时执行 @register_unit("speed", ...)
    TargetRenderer,     # ← 导入时执行 @register_unit("target", ...)
)
```

**效果**:
- `standard_runners` 导入 -> "renderer" 类型注册
- `SpeedRenderer` 导入 -> "speed" renderer 注册
- `TargetRenderer` 导入 -> "target" renderer 注册

---

### 步骤 4: 查找和执行 Renderer

**文件**: `src/nexus/contrib/repro/video.py`

```python
from nexus.core.execution_units import execute_unit, get_unit

def render_all_frames(
    frames_dir: Path,
    renderer_configs: list[dict],
    ...
):
    # 1. 验证所有 renderer 是否存在
    validated_configs = []
    for config in renderer_configs:
        renderer_name = config.get("name") or config.get("class")

        # 查找 renderer（会从全局注册表查找）
        spec = get_unit(renderer_name, "renderer")  # ← 查找注册表

        # 验证成功，记录配置
        validated_configs.append({
            "name": renderer_name,
            "kwargs": config.get("kwargs", {})
        })

    # 2. 对每一帧执行所有 renderer
    for frame_file in sorted(frame_files):
        frame = cv2.imread(str(frame_file))

        # 对每个 renderer 依次执行
        for renderer_config in validated_configs:
            frame = execute_unit(
                name=renderer_config["name"],      # "speed"
                unit_type="renderer",               # "renderer"
                frame=frame,                        # 参数
                timestamp_ms=timestamp_ms,          # 参数
                config=renderer_config["kwargs"]    # 配置
            )

        # 保存渲染后的帧
        cv2.imwrite(str(output_file), frame)
```

---

## 全局注册表结构

```python
# 内部结构
_registry = {
    _types: {
        "plugin": UnitType(name="plugin", runner=PluginRunner(), ...),
        "renderer": UnitType(name="renderer", runner=RendererRunner(), ...),
    },
    _units: {
        "plugin": {
            "Video Splitter": UnitSpec(...),
            "Data Renderer": UnitSpec(...),
            # ... 其他 plugins
        },
        "renderer": {
            "speed": UnitSpec(
                name="speed",
                unit_type="renderer",
                implementation=SpeedRenderer,
                description="Speed renderer for displaying...",
            ),
            "target": UnitSpec(
                name="target",
                unit_type="renderer",
                implementation=TargetRenderer,
                description="Render 3D target detections...",
            ),
        }
    }
}
```

---

## 时序图

```
程序启动时:
┌─────────────┐       ┌──────────────────┐       ┌─────────────────┐
│   Python    │       │ standard_runners │       │ Global Registry │
└──────┬──────┘       └────────┬─────────┘       └────────┬────────┘
       │                       │                           │
       │ import standard_runners                           │
       ├──────────────────────>│                           │
       │                       │                           │
       │                       │ register_type("renderer") │
       │                       ├──────────────────────────>│
       │                       │                           │
       │                       │<─────── OK ───────────────┤
       │                       │                           │
       │ import SpeedRenderer  │                           │
       ├──────────────────────────────────────────────────>│
       │                       │                           │
       │ @register_unit("speed", unit_type="renderer")     │
       │ (装饰器自动执行)        │                           │
       ├───────────────────────────────────────────────────>│
       │                       │                           │
       │                       │     register "speed"      │
       │                       │                           │
       │                       │<────── OK ────────────────┤
       │                       │                           │
       │ import TargetRenderer │                           │
       ├──────────────────────────────────────────────────>│
       │                       │                           │
       │ @register_unit("target", unit_type="renderer")    │
       │ (装饰器自动执行)        │                           │
       ├───────────────────────────────────────────────────>│
       │                       │                           │
       │                       │    register "target"      │
       │                       │                           │
       │                       │<────── OK ────────────────┤
       │                       │                           │

执行渲染时:
┌─────────────┐       ┌──────────────┐       ┌──────────────────┐
│   video.py  │       │ execute_unit │       │ RendererRunner   │
└──────┬──────┘       └──────┬───────┘       └────────┬─────────┘
       │                     │                         │
       │ execute_unit("speed", "renderer", ...)        │
       ├────────────────────>│                         │
       │                     │                         │
       │                     │ 查找 "speed"            │
       │                     ├─────────────────────────>│
       │                     │                         │
       │                     │<── SpeedRenderer ───────┤
       │                     │                         │
       │                     │ runner.execute()        │
       │                     ├────────────────────────>│
       │                     │                         │
       │                     │       检查缓存          │
       │                     │       实例化（首次）    │
       │                     │       调用 .render()    │
       │                     │                         │
       │                     │<──── rendered frame ────┤
       │                     │                         │
       │<──── frame ─────────┤                         │
       │                     │                         │
```

---

## 关键设计特点

### 1. **自动发现 = 装饰器 + 模块导入**

- **不需要手动注册**: 只要类定义了 `@register_unit` 装饰器，模块导入时自动注册
- **不需要配置文件**: 不需要在某个 YAML/JSON 中列出所有 renderer
- **不需要类路径**: 使用短名称 `"speed"` 而非 `"nexus.contrib.repro.renderers.SpeedRenderer"`

### 2. **延迟实例化 + 缓存**

- **首次使用时实例化**: `RendererRunner` 在第一次 `execute()` 时才创建实例
- **实例缓存**: 同一 renderer 在处理多帧时复用同一实例（性能优化）
- **按需加载**: 如果配置中没有使用某个 renderer，不会实例化它

### 3. **类型安全**

- **注册时验证**: `RendererRunner.validate()` 检查类是否有 `render()` 方法
- **使用时验证**: `get_unit()` 检查 renderer 是否存在
- **启动时失败**: 配置错误在程序启动时就会发现，而非运行到一半才报错

---

## 对比旧方式

### 旧方式（手动加载）

```python
# 配置
renderer_configs = [
    {
        "class": "nexus.contrib.repro.renderers.SpeedRenderer",
        "kwargs": {"data_path": "speed.jsonl"}
    }
]

# 代码
import importlib

for config in renderer_configs:
    # 手动解析类路径
    module_path, class_name = config["class"].rsplit(".", 1)
    module = importlib.import_module(module_path)
    RendererClass = getattr(module, class_name)

    # 手动实例化
    renderer = RendererClass(**config["kwargs"])

    # 手动执行
    frame = renderer.render(frame, timestamp_ms)
```

**问题**:
- ❌ 配置冗长（完整导入路径）
- ❌ 手动管理实例化
- ❌ 无缓存，每次都创建新实例
- ❌ 无类型验证
- ❌ 运行时才发现错误

### 新方式（自动发现）

```python
# 配置
renderer_configs = [
    {
        "name": "speed",  # 简洁！
        "kwargs": {"data_path": "speed.jsonl"}
    }
]

# 代码
from nexus.core.execution_units import execute_unit

for config in renderer_configs:
    # 框架自动查找、实例化、缓存、执行
    frame = execute_unit(
        name=config["name"],
        unit_type="renderer",
        frame=frame,
        timestamp_ms=timestamp_ms,
        config=config["kwargs"]
    )
```

**优势**:
- ✅ 配置简洁（短名称）
- ✅ 自动实例化和缓存
- ✅ 启动时类型验证
- ✅ 统一的执行模式
- ✅ 易于扩展（一行装饰器）

---

## 如何添加新 Renderer

### 步骤 1: 定义 Renderer 类

```python
# src/nexus/contrib/repro/renderers/my_renderer.py

from nexus.core.execution_units import register_unit
from .base import BaseDataRenderer

@register_unit("my_custom", unit_type="renderer")
class MyCustomRenderer(BaseDataRenderer):
    def __init__(self, data_path, **kwargs):
        super().__init__(data_path=data_path, **kwargs)

    def render(self, frame, timestamp_ms):
        # 自定义渲染逻辑
        return frame
```

### 步骤 2: 导入（触发注册）

```python
# src/nexus/contrib/repro/renderers/__init__.py

from .speed_renderer import SpeedRenderer
from .target_renderer import TargetRenderer
from .my_renderer import MyCustomRenderer  # ← 添加这行

__all__ = [
    "BaseDataRenderer",
    "SpeedRenderer",
    "TargetRenderer",
    "MyCustomRenderer",  # ← 添加这行
]
```

### 步骤 3: 使用

```yaml
# repro.yaml
renderers:
  - name: "speed"
    kwargs: {...}

  - name: "my_custom"  # ← 直接使用！
    kwargs:
      data_path: "input/my_data.jsonl"
```

**就这样！** 不需要修改任何其他代码。

---

## 总结

### 发现机制的核心

```
装饰器注册 (@register_unit)
    ↓
模块导入时自动执行
    ↓
注册到全局注册表 (_registry)
    ↓
通过名称查找和执行 (get_unit / execute_unit)
```

### 关键优势

1. **自动化**: 装饰器 + 导入时注册，无需手动管理
2. **简洁性**: 短名称，清晰配置
3. **类型安全**: 编译时验证，启动时失败
4. **高性能**: 实例缓存，避免重复创建
5. **易扩展**: 一行装饰器即可添加新 renderer

### 适用场景

这种模式适用于：
- ✅ Plugin 系统
- ✅ Renderer 系统
- ✅ Validator 系统
- ✅ Exporter 系统
- ✅ 任何需要"注册 + 发现 + 执行"的扩展点

---

## 参考

- **核心框架**: `src/nexus/core/execution_units.py`
- **Renderer Runner**: `src/nexus/core/standard_runners.py`
- **使用示例**: `examples/repro_renderer_demo.py`
- **设计文档**: `docs/unified-execution-units-design.md`

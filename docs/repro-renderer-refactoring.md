# Repro Renderer 重构完成总结

## 重构目标

将 `nexus.contrib.repro` 的 renderer 系统迁移到统一执行单元框架，实现：
- ✅ 使用 `@register_unit` 装饰器注册 renderer
- ✅ 通过名称引用 renderer（不再使用完整导入路径）
- ✅ 自动实例化和缓存
- ✅ 类型安全验证
- ✅ 无兼容代码（完全重构）

## 修改的文件

### 1. `src/nexus/contrib/repro/renderers/speed_renderer.py`
**改动**：添加装饰器注册

```python
# 之前
class SpeedRenderer(BaseDataRenderer):
    ...

# 之后
from nexus.core.execution_units import register_unit

@register_unit("speed", unit_type="renderer")
class SpeedRenderer(BaseDataRenderer):
    ...
```

### 2. `src/nexus/contrib/repro/renderers/target_renderer.py`
**改动**：添加装饰器注册

```python
# 之前
class TargetRenderer(BaseDataRenderer):
    ...

# 之后
from nexus.core.execution_units import register_unit

@register_unit("target", unit_type="renderer")
class TargetRenderer(BaseDataRenderer):
    ...
```

### 3. `src/nexus/contrib/repro/video.py`
**改动**：使用执行单元框架替代手动实例化

```python
# 之前
import importlib

def load_renderer(class_path: str, kwargs: dict):
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    RendererClass = getattr(module, class_name)
    return RendererClass(**kwargs)

renderers = []
for config in renderer_configs:
    renderer = load_renderer(config["class"], config["kwargs"])
    renderers.append(renderer)

for renderer in renderers:
    frame = renderer.render(frame, timestamp_ms)

# 之后
from nexus.core.execution_units import execute_unit, get_unit

# 验证配置
for config in renderer_configs:
    renderer_name = config.get("name") or config.get("class")
    spec = get_unit(renderer_name, "renderer")  # 验证存在

# 执行（自动实例化和缓存）
for config in validated_configs:
    frame = execute_unit(
        name=config["name"],
        unit_type="renderer",
        frame=frame,
        timestamp_ms=timestamp_ms,
        config=config["kwargs"]
    )
```

### 4. `src/nexus/contrib/repro/__init__.py`
**改动**：
- 添加 `from nexus.core import standard_runners` 确保 renderer 类型被注册
- 移除旧的 registry 模块导入
- 更新文档字符串展示新用法

```python
# 确保标准执行单元类型被注册（plugin, renderer）
from nexus.core import standard_runners

# 导入 renderers 触发注册
from .renderers import (
    BaseDataRenderer,
    SpeedRenderer,
    TargetRenderer,
)
```

### 5. `examples/repro_renderer_demo.py` ✨ 新增
**功能**：完整的使用示例
- 列出已注册的 renderer
- 使用已注册的 renderer
- 创建自定义 renderer
- 组合多个 renderer

## 使用方式对比

### 之前（旧方式）

```python
# 配置 - 使用完整导入路径
renderer_configs = [
    {
        "class": "nexus.contrib.repro.renderers.SpeedRenderer",
        "kwargs": {"data_path": "speed.jsonl", "position": (30, 60)}
    }
]

# 手动实例化
from nexus.contrib.repro.renderers import SpeedRenderer
renderer = SpeedRenderer(data_path="speed.jsonl", position=(30, 60))
frame = renderer.render(frame, timestamp_ms)
```

### 之后（新方式）

```python
# 配置 - 使用简短名称
renderer_configs = [
    {
        "name": "speed",  # 简洁！
        "kwargs": {"data_path": "speed.jsonl", "position": (30, 60)}
    }
]

# 框架自动实例化和缓存
from nexus.contrib.repro import render_all_frames

render_all_frames(
    frames_dir=Path("frames/"),
    output_dir=Path("rendered/"),
    timestamps_path=Path("timestamps.csv"),
    renderer_configs=renderer_configs
)
```

### 创建自定义 Renderer

```python
from nexus.core.execution_units import register_unit
from nexus.contrib.repro.renderers import BaseDataRenderer

@register_unit("my_renderer", unit_type="renderer")
class MyRenderer(BaseDataRenderer):
    def __init__(self, **kwargs):
        super().__init__(data_path="", **kwargs)

    def render(self, frame, timestamp_ms):
        # 自定义渲染逻辑
        return frame

# 立即可用
renderer_configs = [{"name": "my_renderer", "kwargs": {}}]
```

## 核心优势

### 1. **简洁性**
- ✅ 配置更简单：`{"name": "speed"}` vs `{"class": "nexus.contrib.repro.renderers.SpeedRenderer"}`
- ✅ 不需要记住完整导入路径
- ✅ 代码更清晰易读

### 2. **自动化**
- ✅ 自动实例化（首次调用时）
- ✅ 自动缓存（同一 renderer 只实例化一次）
- ✅ 自动生命周期管理

### 3. **类型安全**
- ✅ 注册时验证接口（必须有 render() 方法）
- ✅ 启动时验证存在性（配置阶段就发现错误）
- ✅ 清晰的错误提示

### 4. **可扩展性**
- ✅ 注册即可用（一行装饰器）
- ✅ 可以轻松添加新 renderer
- ✅ 可以在运行时查看所有注册的 renderer

### 5. **统一性**
- ✅ 与 plugin 系统使用相同的底层框架
- ✅ 相同的注册方式
- ✅ 相同的执行模式

## 测试结果

运行 `python examples/repro_renderer_demo.py`：

```
✓ 已注册 3 个 renderer: speed, target, watermark
✓ 可以列出所有 renderer
✓ 可以查看 renderer 详细信息
✓ 可以创建自定义 renderer
✓ 可以组合多个 renderer
```

## 向后兼容性

**无** - 这是一次完全重构，不保留兼容代码。

理由：
- 旧代码没有在生产环境使用
- 新方式更优秀
- 避免维护两套系统

## 迁移指南

如果有旧代码，迁移步骤：

1. **更新配置**
   ```python
   # 旧
   {"class": "nexus.contrib.repro.renderers.SpeedRenderer", "kwargs": {...}}

   # 新
   {"name": "speed", "kwargs": {...}}
   ```

2. **更新 renderer 定义**
   ```python
   # 旧
   class MyRenderer(BaseDataRenderer):
       ...

   # 新
   @register_unit("my_renderer", unit_type="renderer")
   class MyRenderer(BaseDataRenderer):
       ...
   ```

3. **更新执行方式**
   ```python
   # 旧
   renderer = MyRenderer(**config)
   frame = renderer.render(frame, timestamp_ms)

   # 新
   frame = execute_unit("my_renderer", "renderer", frame, timestamp_ms, config=config)
   # 或直接使用 render_all_frames()
   ```

## 下一步

可能的扩展：
1. ✨ 添加更多内置 renderer（网格、文本叠加、边界框等）
2. ✨ 支持 renderer 链式配置
3. ✨ 添加 renderer 预览功能
4. ✨ 添加性能监控和统计
5. ✨ 支持异步渲染

## 相关文件

- 📄 `/docs/unified-execution-units-design.md` - 统一执行单元框架设计文档
- 📄 `/examples/unified_execution_units_demo.py` - 框架完整示例
- 📄 `/examples/repro_renderer_demo.py` - Repro renderer 使用示例
- 💻 `/src/nexus/core/execution_units.py` - 核心框架
- 💻 `/src/nexus/core/standard_runners.py` - Plugin/Renderer runner 实现

## 总结

✅ **重构成功完成**

- Repro renderer 系统已完全迁移到统一执行单元框架
- 代码更简洁、更安全、更易扩展
- 与 plugin 系统保持一致性
- 测试通过，所有功能正常

这次重构验证了**统一执行单元框架**的设计理念：
> Plugin 和 Renderer 本质相同，只是接口规范和执行方式不同。
> 通过统一的框架管理，可以消除重复代码，提高一致性和可维护性。

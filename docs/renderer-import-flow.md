# Renderer 导入流程详解

## 问题

程序启动时在哪里导入了 `nexus.contrib.repro`？

---

## 完整导入链

```
用户执行命令
    │
    └─> python -m nexus run -c repro -t repro
           │
           ├─> src/nexus/__main__.py
           │      └─> from .cli import main
           │             └─> main()
           │
           ├─> src/nexus/cli.py:132 (run 命令)
           │      └─> engine = PipelineEngine(project_root, case_dir)
           │
           ├─> src/nexus/core/engine.py:32 (PipelineEngine.__init__)
           │      └─> discover_all_plugins(self.project_root)
           │
           ├─> src/nexus/core/discovery.py:83 (discover_all_plugins)
           │      ├─> 读取 config/global.yaml
           │      │      └─> framework.packages: ["src/nexus/contrib"]
           │      │
           │      └─> for package in packages:
           │             └─> discover_from_path(package, project_root)
           │
           ├─> src/nexus/core/discovery.py:46 (discover_from_path)
           │      ├─> 添加 "src/nexus" 到 sys.path
           │      ├─> importlib.import_module("contrib")
           │      │      └─> 导入 src/nexus/contrib/__init__.py
           │      │
           │      └─> importlib.import_module("contrib.nexus")
           │             └─> 导入 src/nexus/contrib/nexus/__init__.py
           │
           ├─> src/nexus/contrib/nexus/__init__.py:12-13
           │      ├─> from . import basic  # 触发 basic plugin 注册
           │      └─> from . import repro  # 触发 repro plugin 注册
           │
           └─> src/nexus/contrib/nexus/repro.py:13
                  └─> from nexus.contrib.repro.video import ...
                         │
                         └─> src/nexus/contrib/repro/__init__.py:44
                                ├─> from nexus.core import standard_runners
                                │      └─> 注册 "renderer" 类型
                                │
                                └─> from .renderers import SpeedRenderer, TargetRenderer
                                       ├─> SpeedRenderer: @register_unit("speed", ...)
                                       └─> TargetRenderer: @register_unit("target", ...)
```

---

## 关键文件路径

### 1. 配置文件

**`config/global.yaml:34-35`**
```yaml
packages:
  - "src/nexus/contrib"  # Built-in plugins
```

**作用**: 指定需要发现的 plugin 包路径

---

### 2. CLI 入口

**`src/nexus/__main__.py:5,8`**
```python
from .cli import main

if __name__ == "__main__":
    main()
```

**作用**: Python 模块入口点（`python -m nexus`）

---

### 3. CLI Run 命令

**`src/nexus/cli.py:132-153`**
```python
@cli.command()
def run(case: str, template: Optional[str], ...):
    project_root = find_project_root(Path.cwd())
    manager = _load_case_manager(project_root)

    # ... 加载配置 ...

    engine = PipelineEngine(project_root, manager.resolve_case_path(case))  # ← 这里！
    engine.run_pipeline(case_config, overrides)
```

**作用**: 创建 `PipelineEngine` 实例，触发 plugin 发现

---

### 4. Pipeline Engine 初始化

**`src/nexus/core/engine.py:27-32`**
```python
class PipelineEngine:
    def __init__(self, project_root: Path, case_dir: Path):
        self.project_root = project_root
        self.case_dir = case_dir
        self.logger = logger

        discover_all_plugins(self.project_root)  # ← 这里触发发现！
```

**作用**: 在引擎初始化时触发 plugin 发现

---

### 5. Plugin 发现

**`src/nexus/core/discovery.py:83-95`**
```python
def discover_all_plugins(project_root: Path) -> None:
    clear_registry()
    global_config = load_global_configuration(project_root)  # 读取 config/global.yaml

    packages: List[str] = list(
        dict.fromkeys(
            global_config.get("framework", {}).get("packages", [])  # 获取 packages 列表
        )
    )

    for package in packages:
        discover_from_path(package, project_root)  # 发现每个包

    logger.info("Discovery complete: %s plugins", len(PLUGIN_REGISTRY))
```

**作用**:
1. 读取全局配置
2. 获取 `framework.packages` 列表
3. 对每个包调用 `discover_from_path()`

---

### 6. 包导入

**`src/nexus/core/discovery.py:46-73`**
```python
def discover_from_path(path_str: str, project_root: Path) -> int:
    """Import a package (and sub-packages) to trigger plugin registration."""

    path = resolve_path(path_str, project_root)  # "src/nexus/contrib"
    if not path.exists() or not path.is_dir():
        logger.warning("Package path not found: %s", path)
        return 0

    # Ensure the parent directory is discoverable by Python
    parent = path.parent  # "src/nexus"
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))  # 添加到 sys.path
        logger.debug("Added %s to sys.path", parent)

    package_name = path.name  # "contrib"
    try:
        importlib.import_module(package_name)  # 导入 "contrib"

        adapter_module = f"{package_name}.nexus"  # "contrib.nexus"
        try:
            importlib.import_module(adapter_module)  # 导入 "contrib.nexus"
        except ImportError:
            pass  # Adapter module doesn't exist, that's OK
    except Exception as exc:
        logger.error("Failed to import '%s': %s", package_name, exc)
        return 0

    logger.info("Imported package '%s'", package_name)
    return 1
```

**作用**:
1. 解析包路径 `"src/nexus/contrib"`
2. 添加父目录 `"src/nexus"` 到 `sys.path`
3. 导入包 `"contrib"`（即 `src/nexus/contrib/__init__.py`）
4. 导入适配器模块 `"contrib.nexus"`（即 `src/nexus/contrib/nexus/__init__.py`）

---

### 7. Nexus 适配器入口

**`src/nexus/contrib/nexus/__init__.py:12-13`**
```python
"""
Nexus plugin adapters entry point.

Imports all adapter modules to register plugins with Nexus discovery system.
"""

# Import adapter modules to trigger plugin registration
from . import basic  # noqa: F401
from . import repro  # noqa: F401  ← 这里触发 repro.py 导入！
```

**作用**: 导入所有适配器模块，触发 `@plugin` 装饰器注册

---

### 8. Repro Plugin 适配器

**`src/nexus/contrib/nexus/repro.py:13-26`**
```python
from nexus.contrib.repro.video import extract_frames, compose_video, render_all_frames
from nexus.contrib.repro.io import save_jsonl
from nexus.contrib.repro.utils import (
    parse_time_string,
    parse_time_value,
    get_video_metadata,
)
from nexus.contrib.repro.datagen import (
    generate_timeline_with_jitter,
    generate_speed_data_event_driven,
    generate_adb_target_data,
    save_timeline_csv,
    SpeedProfile,
)
```

**作用**: 导入 `nexus.contrib.repro` 模块的函数，触发 repro 包初始化

---

### 9. Repro 包初始化

**`src/nexus/contrib/repro/__init__.py:44`**
```python
# Ensure standard execution unit types are registered (plugin, renderer)
from nexus.core import standard_runners  # ← 注册 "renderer" 类型
```

**作用**: 导入 `standard_runners`，触发 renderer 类型注册

---

### 10. 标准 Runner 注册

**`src/nexus/core/standard_runners.py:115-122`**
```python
def register_standard_types():
    """Register standard execution unit types (plugin, renderer)."""
    register_type(
        "plugin",
        PluginRunner(),
        "Nexus plugin execution units"
    )
    register_type(
        "renderer",
        RendererRunner(),
        "Data visualization renderers"
    )
    logger.info("Registered standard execution unit types: plugin, renderer")

# Auto-register on module import
register_standard_types()  # ← 模块导入时自动执行！
```

**作用**: 注册 "renderer" 类型到全局注册表

---

### 11. Renderer 导入和注册

**`src/nexus/contrib/repro/__init__.py:78-84`**
```python
# Import renderers to trigger registration with execution unit framework
# This ensures all built-in renderers are registered when module is imported
from .renderers import (
    BaseDataRenderer,
    SpeedRenderer,     # ← @register_unit("speed", unit_type="renderer")
    TargetRenderer,    # ← @register_unit("target", unit_type="renderer")
)
```

**作用**: 导入 renderer 类，触发 `@register_unit` 装饰器

---

### 12. Renderer 类定义

**`src/nexus/contrib/repro/renderers/speed_renderer.py:18`**
```python
@register_unit("speed", unit_type="renderer")  # ← 装饰器在导入时执行
class SpeedRenderer(BaseDataRenderer):
    def render(self, frame, timestamp_ms):
        return frame
```

**作用**: 装饰器将 "speed" renderer 注册到全局注册表

---

## 时序图

```
程序启动
    │
    v
python -m nexus run -c repro -t repro
    │
    ├─> CLI 解析命令
    │
    ├─> 创建 PipelineEngine
    │       │
    │       v
    │   discover_all_plugins()
    │       │
    │       ├─> 读取 config/global.yaml
    │       │      packages: ["src/nexus/contrib"]
    │       │
    │       ├─> discover_from_path("src/nexus/contrib")
    │       │      │
    │       │      ├─> sys.path.insert(0, "src/nexus")
    │       │      │
    │       │      ├─> import contrib
    │       │      │      └─> contrib/__init__.py (空)
    │       │      │
    │       │      └─> import contrib.nexus
    │       │             └─> contrib/nexus/__init__.py
    │       │                    │
    │       │                    ├─> from . import basic
    │       │                    │
    │       │                    └─> from . import repro
    │       │                           └─> contrib/nexus/repro.py
    │       │                                  │
    │       │                                  └─> from nexus.contrib.repro.video import ...
    │       │                                         │
    │       │                                         v
    │       │                                     nexus/contrib/repro/__init__.py
    │       │                                         │
    │       │                                         ├─> from nexus.core import standard_runners
    │       │                                         │      └─> register_type("renderer", RendererRunner())
    │       │                                         │
    │       │                                         └─> from .renderers import SpeedRenderer, TargetRenderer
    │       │                                                │
    │       │                                                ├─> @register_unit("speed", unit_type="renderer")
    │       │                                                └─> @register_unit("target", unit_type="renderer")
    │       │
    │       └─> logger.info("Discovery complete: 11 plugins")
    │
    └─> engine.run_pipeline(...)
           └─> 执行 pipeline，使用已注册的 renderers
```

---

## 日志验证

从测试日志可以看到完整的导入过程：

```
2025-11-06 22:39:45,921 - nexus.core.execution_units - INFO - Registered unit type: renderer
2025-11-06 22:39:45,921 - nexus.core.standard_runners - INFO - Registered standard execution unit types: plugin, renderer
2025-11-06 22:39:46,002 - nexus.core.discovery - INFO - Imported package 'contrib'
2025-11-06 22:39:46,009 - nexus.core.discovery - INFO - Discovery complete: 11 plugins
```

**日志解读**:
1. `Registered unit type: renderer` - `standard_runners` 注册了 renderer 类型
2. `Imported package 'contrib'` - `discover_from_path()` 成功导入 contrib 包
3. `Discovery complete: 11 plugins` - 发现了 11 个 plugins（包括 repro 相关的）

---

## 关键设计特点

### 1. **配置驱动的包发现**

- 不是硬编码导入
- 通过 `config/global.yaml` 配置需要发现的包
- 可以轻松添加外部包

```yaml
# config/local.yaml
framework:
  packages:
    - "src/nexus/contrib"
    - "external/my_plugins"  # 添加外部插件包
```

### 2. **双层导入机制**

```
package_name (contrib)
    └─> package_name.nexus (contrib.nexus)
           └─> 触发 plugin 和 renderer 注册
```

**优点**:
- 业务逻辑和框架适配分离
- 业务代码可以独立使用（不依赖 nexus）
- 适配层按需加载

### 3. **延迟注册**

- **类型注册**: 在 `standard_runners` 模块导入时
- **Renderer 注册**: 在 renderer 类导入时（通过装饰器）
- **执行**: 在 `execute_unit()` 调用时（延迟实例化）

### 4. **导入顺序保证**

```python
# src/nexus/contrib/repro/__init__.py

# 1. 先导入 standard_runners，确保 "renderer" 类型存在
from nexus.core import standard_runners

# 2. 再导入 renderer 类，触发 @register_unit 装饰器
from .renderers import SpeedRenderer, TargetRenderer
```

**如果顺序反了**: `@register_unit("speed", unit_type="renderer")` 会失败，因为 "renderer" 类型还没注册。

---

## 为什么这样设计？

### 问题：如果每次都手动导入会怎样？

**不好的方式**:
```python
# 每个使用 renderer 的地方都要导入
from nexus.contrib.repro.renderers import SpeedRenderer, TargetRenderer

# 使用时需要完整类路径
renderer_configs = [
    {
        "class": "nexus.contrib.repro.renderers.SpeedRenderer",
        "kwargs": {...}
    }
]
```

**问题**:
- ❌ 使用者需要知道完整类路径
- ❌ 配置冗长
- ❌ 重构时需要更新所有引用
- ❌ 难以扩展（添加新 renderer 需要修改多处）

### 解决方案：自动发现 + 注册

**好的方式**:
```python
# 程序启动时自动导入和注册
# 使用者只需要知道短名称
renderer_configs = [
    {
        "name": "speed",  # 简洁！
        "kwargs": {...}
    }
]
```

**优势**:
- ✅ 配置简洁（短名称）
- ✅ 自动发现（无需手动导入）
- ✅ 易于扩展（添加新 renderer 只需一行装饰器）
- ✅ 解耦合（使用者不需要知道实现细节）

---

## 如何添加自己的包？

### 场景：你有一个外部插件包 `my_project`

**结构**:
```
my_project/
  ├── __init__.py
  ├── business_logic.py     # 框架无关的业务代码
  └── nexus/
      ├── __init__.py
      ├── plugins.py        # @plugin 装饰器
      └── renderers.py      # @register_unit 装饰器
```

**步骤 1: 配置发现路径**

```yaml
# config/local.yaml
framework:
  packages:
    - "src/nexus/contrib"    # 内置
    - "external/my_project"  # 你的包
```

**步骤 2: 定义 Renderer**

```python
# external/my_project/nexus/renderers.py

from nexus.core.execution_units import register_unit
from nexus.contrib.repro.renderers import BaseDataRenderer

@register_unit("my_renderer", unit_type="renderer")
class MyRenderer(BaseDataRenderer):
    def render(self, frame, timestamp_ms):
        # 自定义渲染逻辑
        return frame
```

**步骤 3: 导入模块**

```python
# external/my_project/nexus/__init__.py

from . import renderers  # 触发 @register_unit 装饰器
```

**步骤 4: 使用**

```yaml
# templates/my_template/template.yaml
pipeline:
  - plugin: "Data Renderer"
    config:
      renderers:
        - name: "my_renderer"  # 直接使用！
          kwargs:
            data_path: "data.jsonl"
```

**就这样！** 程序启动时会自动发现并注册你的 renderer。

---

## 总结

### 导入链总结

```
CLI 命令
  └─> PipelineEngine.__init__()
       └─> discover_all_plugins()
            └─> 读取 config/global.yaml
                 └─> packages: ["src/nexus/contrib"]
                      └─> discover_from_path()
                           ├─> import contrib
                           └─> import contrib.nexus
                                └─> from . import repro
                                     └─> from nexus.contrib.repro.video import ...
                                          └─> nexus.contrib.repro.__init__.py
                                               ├─> from nexus.core import standard_runners
                                               │      └─> register_type("renderer", ...)
                                               │
                                               └─> from .renderers import SpeedRenderer
                                                      └─> @register_unit("speed", ...)
```

### 关键文件

1. **配置**: `config/global.yaml:34-35` - 指定包路径
2. **入口**: `src/nexus/core/engine.py:32` - 触发发现
3. **发现**: `src/nexus/core/discovery.py:83,61,64` - 导入包
4. **适配**: `src/nexus/contrib/nexus/__init__.py:13` - 导入 repro
5. **初始化**: `src/nexus/contrib/repro/__init__.py:44,78-84` - 注册 renderer

### 核心机制

- **配置驱动**: 通过配置文件指定包路径
- **自动发现**: 程序启动时自动导入
- **装饰器注册**: 导入时触发注册
- **延迟实例化**: 首次使用时创建实例
- **全局注册表**: 统一管理所有 execution units

---

## 参考

- **配置文件**: `config/global.yaml`
- **发现机制**: `src/nexus/core/discovery.py`
- **执行引擎**: `src/nexus/core/engine.py`
- **标准 Runners**: `src/nexus/core/standard_runners.py`
- **Repro 初始化**: `src/nexus/contrib/repro/__init__.py`
- **Renderer 注册**: `docs/renderer-discovery-mechanism.md`

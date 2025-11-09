# Path Resolution Convention

## Overview

Nexus框架使用 **`*_path` 命名约定**来自动解析路径参数。任何以 `_path` 结尾的参数都会被自动解析为相对于案例目录的绝对路径。

## 约定规则

### 1. 自动解析

所有以 `_path` 结尾的参数会被自动解析：

```yaml
# 配置文件
data_path: "input/data.json"           # ✓ 自动解析
output_path: "output/results.csv"      # ✓ 自动解析
calibration_path: "calib.yaml"         # ✓ 自动解析
threshold: 0.5                          # ✗ 不解析（不以_path结尾）
```

解析结果：
```python
data_path: "/abs/case/path/input/data.json"
output_path: "/abs/case/path/output/results.csv"
calibration_path: "/abs/case/path/calib.yaml"
threshold: 0.5
```

### 2. 支持嵌套结构

支持嵌套字典和列表：

```yaml
config:
  data_path: "input/data.json"           # ✓ 自动解析
  calibration_path: "calib.yaml"         # ✓ 自动解析

renderers:
  - name: "speed"
    kwargs:
      data_path: "speed.jsonl"           # ✓ 自动解析
```

### 3. 禁用自动解析

如果某个 `*_path` 字段不需要自动解析，可以在 Pydantic Field 中禁用：

```python
from pydantic import Field

class MyConfig(PluginConfig):
    data_path: str = Field(
        description="Path to data file"
        # 默认会自动解析
    )

    template_path: str = Field(
        description="Path template (not resolved)",
        json_schema_extra={"skip_path_resolve": True}
        # 显式禁用自动解析
    )
```

## 使用方法

### 在 Plugin 中使用

有两种方式使用路径解析：

#### 方式1：使用 `ctx.auto_resolve_paths()` (推荐)

```python
@plugin(name="My Plugin", config=MyPluginConfig)
def my_plugin(ctx: PluginContext) -> Any:
    config: MyPluginConfig = ctx.config

    # 方式1：解析字典
    params = {"data_path": "input/data.json", "threshold": 0.5}
    resolved = ctx.auto_resolve_paths(params)
    # resolved["data_path"] 现在是绝对路径

    # 方式2：解析 Pydantic 模型（in-place）
    renderer_config = RendererConfig(data_path="input/data.json")
    ctx.auto_resolve_paths(renderer_config)
    # renderer_config.data_path 现在是绝对路径
```

#### 方式2：使用 `ctx.resolve_path()` (手动)

```python
@plugin(name="My Plugin", config=MyPluginConfig)
def my_plugin(ctx: PluginContext) -> Any:
    config: MyPluginConfig = ctx.config

    # 手动解析单个路径
    data_path = ctx.resolve_path(config.data_path)
    output_path = ctx.resolve_path(config.output_path)
```

### 在代码中使用

```python
from nexus.core.path_resolver import PathResolver, auto_resolve_paths

# 检查字段是否应该解析
PathResolver.should_resolve_field("data_path")      # True
PathResolver.should_resolve_field("threshold")      # False

# 解析字典
params = {"data_path": "input/data.json"}
resolved = PathResolver.resolve_dict(params, ctx.resolve_path)

# 解析 Pydantic 模型
config = MyConfig(data_path="input/data.json")
PathResolver.resolve_config(config, ctx.resolve_path)
```

## 最佳实践

### ✅ 推荐

1. **遵循命名约定**：所有路径参数使用 `*_path` 命名
```python
data_path: str        # ✓ 好
input_file_path: str  # ✓ 好
```

2. **使用 `ctx.auto_resolve_paths()`**：让框架自动处理
```python
resolved = ctx.auto_resolve_paths(params)  # ✓ 推荐
```

3. **在文档中说明约定**：
```python
"""
Path Resolution:
    All parameters ending with '_path' are automatically resolved
    to absolute paths relative to the case directory.
"""
```

4. **混用绝对路径和相对路径**（支持）：
```python
# ✓ 完全支持混用
data_path: "/abs/path/to/data.json"  # 绝对路径 → 保持不变
output_path: "output/results.csv"    # 相对路径 → 相对 case 目录解析

# 解析结果：
# data_path   → /abs/path/to/data.json (不变)
# output_path → /case/path/output/results.csv
```

### ❌ 避免

1. **不遵循命名约定**：
```python
data_file: str         # ✗ 不会自动解析
input_location: str    # ✗ 不会自动解析
```

2. **手动拼接路径**：
```python
# ✗ 不要这样做
full_path = str(ctx.case_path) + "/" + config.data_path

# ✓ 应该这样做
full_path = ctx.resolve_path(config.data_path)
# 或者使用自动解析
resolved = ctx.auto_resolve_paths({"data_path": config.data_path})
```

## 示例

### 完整的 Plugin 示例

```python
from nexus.core.discovery import plugin
from nexus.core.context import PluginContext
from nexus.core.types import PluginConfig
from pydantic import Field

class DataProcessorConfig(PluginConfig):
    """Configuration for data processor plugin."""

    # 这些会被自动解析
    input_path: str = Field(description="Path to input data")
    output_path: str = Field(description="Path to output data")
    config_path: str = Field(description="Path to config file")

    # 这些不会被自动解析
    threshold: float = Field(default=0.5, description="Processing threshold")
    mode: str = Field(default="auto", description="Processing mode")

@plugin(name="Data Processor", config=DataProcessorConfig)
def process_data(ctx: PluginContext) -> Any:
    """
    Process data from input file and save to output file.

    Path Resolution Convention:
        All *_path parameters are automatically resolved to absolute paths.
    """
    config: DataProcessorConfig = ctx.config

    # 选项1：手动解析（如果需要更多控制）
    input_path = ctx.resolve_path(config.input_path)
    output_path = ctx.resolve_path(config.output_path)

    # 选项2：批量解析（推荐用于复杂嵌套结构）
    params = {
        "input_path": config.input_path,
        "output_path": config.output_path,
        "config": {
            "calibration_path": "calib.yaml"
        }
    }
    resolved = ctx.auto_resolve_paths(params)

    # 处理数据...
    ctx.logger.info(f"Processing {input_path} -> {output_path}")

    return output_path
```

### Renderer 配置示例

```yaml
# repro.yaml
pipeline:
  - plugin: "Data Renderer"
    config:
      frames_dir: "temp/frames"          # 手动解析
      output_dir: "temp/rendered"        # 手动解析
      timestamps_path: "input/timestamps.csv"  # 手动解析

      renderers:
        - name: "speed"
          kwargs:
            data_path: "input/speed.jsonl"  # 自动解析
            position: [30, 60]

        - name: "target"
          kwargs:
            data_path: "input/targets.jsonl"         # 自动解析
            calibration_path: "config/calibration.yaml"  # 自动解析
```

## 技术细节

### 实现原理

路径解析通过递归遍历配置结构实现：

1. 检查每个键是否以 `_path` 结尾
2. 如果是，使用 `ctx.resolve_path()` 解析值
3. 递归处理嵌套的字典和列表
4. 对于 Pydantic 模型，检查 Field 元数据是否禁用解析

### 相对路径解析规则

```python
def resolve_path(value: Union[str, Path]) -> Path:
    """
    相对路径：相对于案例目录
    绝对路径：保持不变
    """
    path = Path(value)
    if path.is_absolute():
        return path
    return case_path / path
```

示例：
```python
案例目录: /project/cases/mycase

"input/data.json"           -> /project/cases/mycase/input/data.json
"../shared/config.yaml"     -> /project/cases/shared/config.yaml
"/tmp/temp.dat"             -> /tmp/temp.dat (保持不变)
```

## 相关API

- `PluginContext.resolve_path(path)` - 解析单个路径
- `PluginContext.auto_resolve_paths(config)` - 自动解析所有路径参数
- `PathResolver.resolve_dict(params, resolve_fn)` - 解析字典
- `PathResolver.resolve_config(config, resolve_fn)` - 解析 Pydantic 模型
- `PathResolver.should_resolve_field(field_name)` - 检查字段是否应该解析

## 参考

- 源代码：`src/nexus/core/path_resolver.py`
- Context：`src/nexus/core/context.py`
- 示例：`src/nexus/contrib/nexus/repro.py`

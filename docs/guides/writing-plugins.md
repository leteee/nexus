# 编写Nexus插件

从零开始创建你的第一个Nexus插件

## 基本结构

一个最简单的Nexus插件：

```python
from nexus.core.discovery import plugin
from nexus.core.context import PluginContext

@plugin(name="My Plugin")
def my_plugin(ctx: PluginContext):
    """我的第一个插件"""
    ctx.logger.info("Hello from my plugin!")
    return "Success"
```

就这么简单！

## 添加配置

使用Pydantic定义配置模型：

```python
from pydantic import Field
from nexus.core.types import PluginConfig
from nexus.core.discovery import plugin

class MyPluginConfig(PluginConfig):
    """我的插件配置"""
    threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="处理阈值"
    )
    input_file: str = Field(
        description="输入文件路径"
    )
    output_file: str = "output.txt"

@plugin(name="My Plugin", config=MyPluginConfig)
def my_plugin(ctx: PluginContext):
    # 访问配置
    threshold = ctx.config.threshold
    input_file = ctx.config.input_file

    ctx.logger.info(f"Threshold: {threshold}")
    ctx.logger.info(f"Input: {input_file}")

    return threshold
```

**在YAML中使用**：

```yaml
pipeline:
  - plugin: "My Plugin"
    config:
      threshold: 0.8
      input_file: "data/input.txt"
      output_file: "data/output.txt"
```

## 使用PluginContext

`PluginContext` 提供了插件所需的所有工具。

### 1. 配置访问

```python
@plugin(name="My Plugin", config=MyPluginConfig)
def my_plugin(ctx: PluginContext):
    # 访问配置
    value = ctx.config.threshold

    # 配置是Pydantic模型，自动验证
    assert 0.0 <= value <= 1.0
```

### 2. 日志记录

```python
@plugin(name="My Plugin")
def my_plugin(ctx: PluginContext):
    ctx.logger.debug("Debug信息")
    ctx.logger.info("常规信息")
    ctx.logger.warning("警告信息")
    ctx.logger.error("错误信息")
```

### 3. 路径解析

```python
@plugin(name="My Plugin")
def my_plugin(ctx: PluginContext):
    # 解析相对路径（相对于case目录）
    input_path = ctx.resolve_path("data/input.txt")
    # 返回：/abs/path/to/cases/mycase/data/input.txt

    # 绝对路径保持不变
    abs_path = ctx.resolve_path("/tmp/data.txt")
    # 返回：/tmp/data.txt
```

### 4. 共享状态

在pipeline步骤之间共享数据：

```python
# 插件1：保存数据
@plugin(name="Producer")
def producer(ctx: PluginContext):
    data = {"key": "value"}

    # 保存到共享状态
    ctx.remember("my_data", data)
    ctx.remember("last_result", data)  # 惯例：last_result

    return data

# 插件2：读取数据
@plugin(name="Consumer")
def consumer(ctx: PluginContext):
    # 从共享状态读取
    data = ctx.recall("my_data")

    if data is None:
        raise RuntimeError("No data found!")

    return data
```

## 路径自动解析

所有以 `_path` 结尾的参数会自动解析为绝对路径。

### 手动方式

```python
@plugin(name="My Plugin", config=MyPluginConfig)
def my_plugin(ctx: PluginContext):
    # 手动解析每个路径
    input_path = ctx.resolve_path(ctx.config.input_file)
    output_path = ctx.resolve_path(ctx.config.output_file)
```

### 自动方式（推荐）

```python
class MyPluginConfig(PluginConfig):
    input_path: str  # 以_path结尾
    output_path: str  # 以_path结尾
    threshold: float

@plugin(name="My Plugin", config=MyPluginConfig)
def my_plugin(ctx: PluginContext):
    # 自动解析所有*_path参数
    config_dict = ctx.auto_resolve_paths(ctx.config.model_dump())

    # 或者自动解析dict
    params = {
        "data_path": "input/data.txt",
        "output_path": "output/result.txt",
        "threshold": 0.5
    }
    resolved = ctx.auto_resolve_paths(params)

    # resolved["data_path"]现在是绝对路径
    # resolved["threshold"]保持不变
```

## 完整示例

一个实用的数据处理插件：

```python
from pathlib import Path
from typing import Optional
import pandas as pd
from pydantic import Field

from nexus.core.discovery import plugin
from nexus.core.types import PluginConfig
from nexus.core.context import PluginContext

class DataCleanerConfig(PluginConfig):
    """数据清洗配置"""

    input_path: str = Field(
        description="输入CSV文件路径"
    )
    output_path: str = Field(
        default="data/cleaned.csv",
        description="输出CSV文件路径"
    )
    drop_nulls: bool = Field(
        default=True,
        description="是否删除空值行"
    )
    drop_duplicates: bool = Field(
        default=True,
        description="是否删除重复行"
    )
    columns: Optional[list[str]] = Field(
        default=None,
        description="只保留指定列（None=保留所有）"
    )

@plugin(name="Data Cleaner", config=DataCleanerConfig)
def clean_data(ctx: PluginContext) -> pd.DataFrame:
    """
    清洗CSV数据。

    功能：
    - 删除空值行
    - 删除重复行
    - 选择列

    Returns:
        清洗后的DataFrame
    """
    config: DataCleanerConfig = ctx.config  # type hint

    # 自动解析路径
    paths = ctx.auto_resolve_paths({
        "input_path": config.input_path,
        "output_path": config.output_path
    })

    input_path = Path(paths["input_path"])
    output_path = Path(paths["output_path"])

    # 读取数据
    ctx.logger.info(f"Reading data from {input_path}")
    df = pd.read_csv(input_path)

    ctx.logger.info(f"Original shape: {df.shape}")

    # 清洗
    if config.drop_nulls:
        before = len(df)
        df = df.dropna()
        ctx.logger.info(f"Dropped {before - len(df)} null rows")

    if config.drop_duplicates:
        before = len(df)
        df = df.drop_duplicates()
        ctx.logger.info(f"Dropped {before - len(df)} duplicate rows")

    if config.columns:
        df = df[config.columns]
        ctx.logger.info(f"Selected columns: {config.columns}")

    ctx.logger.info(f"Final shape: {df.shape}")

    # 保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    ctx.logger.info(f"Saved to {output_path}")

    # 保存到共享状态
    ctx.remember("last_result", df)
    ctx.remember("cleaned_data", df)

    return df
```

**使用示例**：

```yaml
# case.yaml
pipeline:
  - plugin: "Data Cleaner"
    config:
      input_path: "data/raw.csv"
      output_path: "data/cleaned.csv"
      drop_nulls: true
      drop_duplicates: true
      columns: ["id", "name", "value"]
```

## 最佳实践

### 1. 使用类型提示

```python
@plugin(name="My Plugin", config=MyPluginConfig)
def my_plugin(ctx: PluginContext) -> pd.DataFrame:  # 返回类型
    config: MyPluginConfig = ctx.config  # 类型提示
    ...
```

### 2. 详细的配置描述

```python
class MyPluginConfig(PluginConfig):
    threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="阈值：用于过滤低置信度结果（0.0-1.0）"
    )
```

### 3. 记录日志

```python
@plugin(name="My Plugin")
def my_plugin(ctx: PluginContext):
    ctx.logger.info("开始处理...")  # 进度
    ctx.logger.debug(f"参数：{ctx.config}")  # 调试信息
    ctx.logger.warning("找到异常值")  # 警告
    ctx.logger.info("处理完成")  # 完成
```

### 4. 保存结果到共享状态

```python
@plugin(name="My Plugin")
def my_plugin(ctx: PluginContext):
    result = process_data()

    # 惯例：保存到last_result
    ctx.remember("last_result", result)

    # 也可以用描述性名称
    ctx.remember("processed_data", result)

    return result
```

### 5. 处理错误

```python
@plugin(name="My Plugin")
def my_plugin(ctx: PluginContext):
    input_path = ctx.resolve_path(ctx.config.input_path)

    if not input_path.exists():
        ctx.logger.error(f"Input file not found: {input_path}")
        raise FileNotFoundError(f"Input file not found: {input_path}")

    try:
        data = load_data(input_path)
    except Exception as e:
        ctx.logger.error(f"Failed to load data: {e}")
        raise

    return data
```

### 6. 验证配置

```python
from pydantic import Field, field_validator

class MyPluginConfig(PluginConfig):
    threshold: float = Field(ge=0.0, le=1.0)
    window_size: int = Field(gt=0)

    @field_validator("window_size")
    @classmethod
    def validate_window_size(cls, v):
        if v % 2 == 0:
            raise ValueError("window_size must be odd")
        return v
```

## 插件发现机制

### 内置插件位置

内置插件位于：
```
src/nexus/contrib/
├── basic/                # 基础插件
│   └── generation.py
└── nexus/                # Nexus适配器
    ├── basic.py          # @plugin装饰器
    └── repro.py
```

### 外部插件

在 `config/global.yaml` 或 `config/local.yaml` 中配置：

```yaml
framework:
  packages:
    - "src/nexus/contrib"           # 内置
    - "/path/to/my/custom/plugins"  # 外部
```

**目录结构**：
```
my_custom_plugins/
├── __init__.py          # 业务逻辑
├── data_processing.py
└── nexus/               # Nexus适配器
    └── __init__.py      # @plugin装饰器
```

**nexus/__init__.py**：
```python
from nexus.core.discovery import plugin
from ..data_processing import process_data

@plugin(name="My Custom Plugin")
def my_custom_plugin(ctx):
    # 调用业务逻辑
    result = process_data(...)
    return result
```

### 发现流程

1. Nexus读取 `framework.packages`
2. 对每个package路径：
   - 添加父目录到 `sys.path`
   - 导入 `package_name`
   - 自动导入 `package_name.nexus` (如果存在)
3. `@plugin` 装饰器自动注册插件

## 测试插件

### 单独运行

```bash
# 运行单个插件
nexus plugin "My Plugin" --case test_case \
  --config threshold=0.8 \
  --config input_file=data/test.csv
```

### 在Pipeline中测试

```yaml
# test_case/case.yaml
pipeline:
  - plugin: "My Plugin"
    config:
      threshold: 0.8
      input_file: "data/test.csv"
```

```bash
nexus run --case test_case
```

### Python单元测试

```python
import pytest
from pathlib import Path
from nexus.core.context import PluginContext
from my_plugin import my_plugin, MyPluginConfig

def test_my_plugin():
    # 创建测试配置
    config = MyPluginConfig(
        threshold=0.8,
        input_file="test/data.csv"
    )

    # 创建mock context
    from unittest.mock import Mock
    ctx = Mock(spec=PluginContext)
    ctx.config = config
    ctx.logger = Mock()
    ctx.resolve_path = lambda p: Path(p)

    # 运行插件
    result = my_plugin(ctx)

    # 验证结果
    assert result is not None
    ctx.logger.info.assert_called()
```

## 常见模式

### 1. 数据转换插件

```python
@plugin(name="Transformer", config=TransformerConfig)
def transform_data(ctx: PluginContext):
    # 从上游获取数据
    df = ctx.recall("last_result")

    if df is None:
        raise RuntimeError("No upstream data")

    # 转换
    df_transformed = transform(df, ctx.config)

    # 传递给下游
    ctx.remember("last_result", df_transformed)

    return df_transformed
```

### 2. 过滤插件

```python
@plugin(name="Filter", config=FilterConfig)
def filter_data(ctx: PluginContext):
    df = ctx.recall("last_result")

    # 过滤
    df_filtered = df[df[ctx.config.column] > ctx.config.threshold]

    ctx.logger.info(f"Filtered: {len(df)} -> {len(df_filtered)} rows")

    ctx.remember("last_result", df_filtered)
    return df_filtered
```

### 3. 数据生成插件

```python
@plugin(name="Generator", config=GeneratorConfig)
def generate_data(ctx: PluginContext):
    # 生成数据
    df = generate(ctx.config)

    # 保存到文件
    output_path = ctx.resolve_path(ctx.config.output_path)
    df.to_csv(output_path, index=False)

    # 传递给下游
    ctx.remember("last_result", df)

    return df
```

## 下一步

- [配置系统](../core/configuration.md) - 深入了解配置机制
- [执行上下文](../core/context.md) - PluginContext详细说明
- [配置最佳实践](configuration-best-practices.md) - 配置系统最佳实践

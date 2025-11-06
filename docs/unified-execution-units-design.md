# 统一执行单元框架设计文档

## 核心洞察

**Plugin 和 Renderer 本质上是相同的东西**：它们都是"可执行代码单元"，只是：
- **接口规范不同**：Plugin 是 `func(ctx) -> Any`，Renderer 是 `class.render(frame, timestamp_ms) -> frame`
- **启动方式不同**：Plugin 直接调用函数，Renderer 需要先实例化类再调用方法

因此，我们可以将所有这类代码统一抽象为"执行单元"（Execution Unit），通过不同的 Runner 来处理不同的接口规范和启动方式。

## 设计原则

### 1. 第一性原理
- 一切可执行的代码都是"执行单元"
- 执行单元只是实现代码的容器
- 类型定义如何验证和执行

### 2. 开放封闭原则
- 核心框架对扩展开放（可以轻松添加新类型）
- 核心框架对修改封闭（添加新类型不需要修改框架代码）

### 3. 单一职责
- Registry：只负责存储和检索
- Runner：只负责验证和执行
- UnitType：只负责定义类型规范

## 架构设计

```
┌────────────────────────────────────────────────────────────────┐
│                     Unified Registry                           │
│                                                                 │
│  Storage Structure:                                            │
│  {                                                             │
│    "plugin": {                                                 │
│      "csv_loader": UnitSpec(name, type, impl, ...),          │
│      "json_parser": UnitSpec(...),                           │
│    },                                                         │
│    "renderer": {                                              │
│      "speed": UnitSpec(name, type, impl, ...),               │
│      "target": UnitSpec(...),                                │
│    }                                                          │
│  }                                                            │
│                                                                │
│  Operations:                                                   │
│  - register_unit(name, type, impl)                            │
│  - get_unit(name, type) -> UnitSpec                           │
│  - list_units(type) -> Dict[name, UnitSpec]                   │
│  - execute_unit(name, type, *args, **kwargs) -> result        │
└────────────────────────────────────────────────────────────────┘
                              ▲
                              │
                    register_type(name, runner)
                              │
┌────────────────────────────┴────────────────────────────────────┐
│                        Unit Types                               │
│                                                                  │
│  Each type defines:                                             │
│  1. Name: "plugin", "renderer", "validator", etc.              │
│  2. Runner: How to validate and execute                        │
│  3. Interface: What the implementation must provide            │
└──────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
┌─────────────▼──────────┐      ┌────────────▼─────────┐
│   Plugin Type          │      │   Renderer Type      │
│                        │      │                      │
│  Interface:            │      │  Interface:          │
│  func(ctx) -> Any      │      │  class:              │
│                        │      │    __init__(**cfg)   │
│  Runner:               │      │    render(frame, ts) │
│  - validate: callable  │      │                      │
│  - execute: call func  │      │  Runner:             │
│                        │      │  - validate: has     │
│                        │      │    render method     │
│                        │      │  - execute:          │
│                        │      │    1. instantiate    │
│                        │      │    2. cache          │
│                        │      │    3. call render()  │
└────────────────────────┘      └──────────────────────┘
```

## 核心概念

### 1. 执行单元 (Execution Unit)
任何可以被注册、配置、执行的代码，可以是：
- 函数 (Function)
- 类 (Class)
- 实例 (Instance)
- 任何可调用对象

### 2. 单元类型 (Unit Type)
定义一类执行单元的规范，包括：
- **名称**：如 "plugin"、"renderer"
- **接口协议**：单元必须实现什么接口
- **Runner**：如何验证和执行这类单元
- **默认配置模型**：可选的 pydantic 模型

### 3. 单元规范 (Unit Spec)
具体执行单元的元数据：
```python
@dataclass
class UnitSpec:
    name: str                    # 单元名称
    unit_type: str              # 所属类型
    implementation: Any         # 实际代码
    config_model: Optional[Type] # 配置模型
    description: str            # 描述
    metadata: Dict[str, Any]    # 额外元数据
```

### 4. 单元执行器 (Unit Runner)
知道如何执行特定类型的单元：
```python
class UnitRunner(ABC):
    @abstractmethod
    def validate(self, spec: UnitSpec) -> bool:
        """验证实现是否符合接口规范"""

    @abstractmethod
    def execute(self, spec: UnitSpec, *args, **kwargs) -> Any:
        """执行单元"""
```

## 使用方式

### 定义新的执行单元类型

只需实现一个 Runner：

```python
from nexus.core.execution_units import UnitRunner, UnitSpec, register_type

class ValidatorRunner(UnitRunner):
    """验证器类型：func(data: Any) -> bool"""

    def validate(self, spec: UnitSpec) -> bool:
        if not callable(spec.implementation):
            raise TypeError("Validator must be callable")
        return True

    def execute(self, spec: UnitSpec, data: Any) -> bool:
        func = spec.implementation
        result = func(data)
        if not isinstance(result, bool):
            raise TypeError("Validator must return bool")
        return result

# 注册新类型
register_type(
    name="validator",
    runner=ValidatorRunner(),
    description="Data validators: func(data) -> bool"
)
```

### 注册执行单元

```python
from nexus.core.execution_units import register_unit

# 注册 Plugin 类型
@register_unit("csv_loader", unit_type="plugin")
def load_csv(ctx):
    return pd.read_csv(ctx.config.file_path)

# 注册 Renderer 类型
@register_unit("speed", unit_type="renderer")
class SpeedRenderer:
    def __init__(self, data_path, **kwargs):
        self.data_path = data_path

    def render(self, frame, timestamp_ms):
        # 绘制速度
        return frame

# 注册 Validator 类型
@register_unit("positive_checker", unit_type="validator")
def check_positive(data):
    return all(x > 0 for x in data)
```

### 执行单元

```python
from nexus.core.execution_units import execute_unit

# 执行 plugin
result = execute_unit("csv_loader", "plugin", ctx)

# 执行 renderer
frame = execute_unit(
    "speed",
    "renderer",
    frame,
    timestamp_ms,
    config={"data_path": "speed.jsonl"}
)

# 执行 validator
is_valid = execute_unit("positive_checker", "validator", [1, 2, 3])
```

## 类型对比

### Plugin 类型

**接口规范：**
```python
def plugin_func(ctx: PluginContext) -> Any:
    """
    ctx: 包含配置、路径、共享状态的上下文
    返回：任意结果
    """
    pass
```

**Runner 行为：**
- 验证：检查是否可调用，至少接受一个参数
- 执行：直接调用 `func(ctx)`
- 生命周期：无状态，每次都是新调用

**使用场景：**
- 数据加载
- 数据处理
- 数据转换
- 业务逻辑

### Renderer 类型

**接口规范：**
```python
class Renderer:
    def __init__(self, **config):
        """配置初始化"""
        pass

    def render(self, frame: np.ndarray, timestamp_ms: int) -> np.ndarray:
        """
        frame: 视频帧
        timestamp_ms: 时间戳（毫秒）
        返回：修改后的帧
        """
        return frame
```

**Runner 行为：**
- 验证：检查是否有 render 方法，render 至少接受 2 个参数
- 执行：
  1. 首次调用时实例化类：`instance = RendererClass(**config)`
  2. 缓存实例
  3. 调用 render 方法：`instance.render(frame, timestamp_ms)`
- 生命周期：有状态，实例被缓存复用

**使用场景：**
- 视频帧渲染
- 数据可视化
- 图像处理
- 实时叠加

## 扩展示例：添加新类型

假设我们需要一个"导出器"类型：

```python
# 1. 定义 Runner
class ExporterRunner(UnitRunner):
    """导出器类型：func(data: Any, path: Path) -> None"""

    def validate(self, spec: UnitSpec) -> bool:
        if not callable(spec.implementation):
            raise TypeError("Exporter must be callable")

        # 检查参数数量
        sig = inspect.signature(spec.implementation)
        if len(sig.parameters) < 2:
            raise TypeError("Exporter must accept (data, path)")

        return True

    def execute(self, spec: UnitSpec, data: Any, path: Path) -> None:
        func = spec.implementation
        logger.info(f"Exporting with {spec.name} to {path}")
        func(data, path)
        logger.info(f"Export completed")

# 2. 注册类型
register_type(
    name="exporter",
    runner=ExporterRunner(),
    description="Data exporters: func(data, path) -> None"
)

# 3. 注册具体单元
@register_unit("csv_exporter", unit_type="exporter")
def export_csv(data: pd.DataFrame, path: Path):
    data.to_csv(path, index=False)

@register_unit("json_exporter", unit_type="exporter")
def export_json(data: dict, path: Path):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

# 4. 使用
execute_unit("csv_exporter", "exporter", df, Path("output.csv"))
execute_unit("json_exporter", "exporter", data_dict, Path("output.json"))
```

## 优势总结

### 1. 统一性
- 所有可执行代码都用相同方式管理
- 统一的注册、发现、执行接口
- 减少认知负担

### 2. 可扩展性
- 添加新类型只需实现 Runner
- 不需要修改核心框架
- 类型之间完全隔离

### 3. 类型安全
- 每个类型有严格的接口验证
- 注册时立即检查
- 运行时错误更清晰

### 4. 灵活性
- 支持函数、类、实例等多种形式
- 可选的配置模型
- 可自定义生命周期管理

### 5. 一致性
- Plugin 和 Renderer 使用相同的注册方式
- 都通过 `execute_unit` 执行
- 统一的元数据管理

## 实现文件

- `nexus/core/execution_units.py` - 核心框架
- `nexus/core/standard_runners.py` - Plugin 和 Renderer 的 Runner 实现

## 迁移路径

### 现有 Plugin 系统
```python
# 旧方式
from nexus.core.discovery import plugin

@plugin(name="csv_loader", config=CsvConfig)
def load_csv(ctx):
    pass

# 新方式（完全兼容）
from nexus.core.execution_units import register_unit

@register_unit("csv_loader", unit_type="plugin", config_model=CsvConfig)
def load_csv(ctx):
    pass
```

### 现有 Renderer 系统
```python
# 旧方式
from nexus.contrib.repro.registry import register_renderer

@register_renderer("speed")
class SpeedRenderer(BaseDataRenderer):
    pass

# 新方式（完全兼容）
from nexus.core.execution_units import register_unit

@register_unit("speed", unit_type="renderer")
class SpeedRenderer(BaseDataRenderer):
    pass
```

## 未来扩展可能性

基于这个框架，可以轻松添加：

1. **Validator 类型**: `func(data) -> bool`
2. **Transformer 类型**: `func(data) -> data`
3. **Exporter 类型**: `func(data, path) -> None`
4. **Aggregator 类型**: `func(List[data]) -> data`
5. **Filter 类型**: `func(data) -> bool`
6. **Handler 类型**: `func(event) -> None`

每种类型只需：
1. 定义接口规范
2. 实现 Runner
3. 调用 `register_type()`

就能立即使用统一的注册和执行系统！

## 总结

这个设计将"可执行代码"从具体的实现形式（函数 vs 类）中抽象出来，聚焦于"做什么"（单元类型）而不是"怎么做"（实现方式）。通过 Runner 封装不同的启动逻辑，我们实现了真正的统一和可扩展性。

**核心思想**：Plugin 和 Renderer 不是两个不同的东西，它们只是同一个"执行单元"概念的不同类型而已。

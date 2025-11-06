"""
完整示例：统一执行单元框架的使用

展示如何使用统一执行单元框架来：
1. 使用内置的 plugin 和 renderer 类型
2. 定义新的执行单元类型
3. 在实际场景中组合使用
"""

import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import dataclass

# 导入核心模块（会自动注册标准类型）
from nexus.core.execution_units import register_unit, execute_unit, list_units
from nexus.core import standard_runners  # 自动注册 plugin 和 renderer 类型

# ============================================================================
# 示例 1: 使用 Plugin 类型（数据处理）
# ============================================================================

# 模拟 PluginContext
@dataclass
class PluginContext:
    config: object
    case_path: Path

# 注册多个 plugin
@register_unit("csv_loader", unit_type="plugin")
def load_csv(ctx):
    """加载 CSV 文件"""
    print(f"Loading CSV from {ctx.config.file_path}")
    return pd.DataFrame({"col1": [1, 2, 3], "col2": [4, 5, 6]})


@register_unit("data_filter", unit_type="plugin")
def filter_data(ctx):
    """过滤数据"""
    data = ctx.config.data
    threshold = ctx.config.threshold
    print(f"Filtering data with threshold {threshold}")
    return data[data["col1"] > threshold]


@register_unit("data_aggregator", unit_type="plugin")
def aggregate_data(ctx):
    """聚合数据"""
    data = ctx.config.data
    print("Aggregating data")
    return data.sum()


# 使用 plugin
def example_plugin_pipeline():
    """演示 plugin 类型的使用"""
    print("=" * 70)
    print("示例 1: Plugin 类型 - 数据处理流水线")
    print("=" * 70)

    # 1. 加载数据
    @dataclass
    class LoadConfig:
        file_path: str = "data.csv"

    ctx1 = PluginContext(config=LoadConfig(), case_path=Path("."))
    data = execute_unit("csv_loader", "plugin", ctx1)
    print(f"Loaded data:\n{data}\n")

    # 2. 过滤数据
    @dataclass
    class FilterConfig:
        data: pd.DataFrame
        threshold: float

    ctx2 = PluginContext(config=FilterConfig(data=data, threshold=1), case_path=Path("."))
    filtered = execute_unit("data_filter", "plugin", ctx2)
    print(f"Filtered data:\n{filtered}\n")

    # 3. 聚合数据
    @dataclass
    class AggConfig:
        data: pd.DataFrame

    ctx3 = PluginContext(config=AggConfig(data=filtered), case_path=Path("."))
    result = execute_unit("data_aggregator", "plugin", ctx3)
    print(f"Aggregated result:\n{result}\n")


# ============================================================================
# 示例 2: 使用 Renderer 类型（视频帧处理）
# ============================================================================

# 注册多个 renderer
@register_unit("text_overlay", unit_type="renderer")
class TextOverlayRenderer:
    """在帧上叠加文本"""

    def __init__(self, text, position=(10, 30), **kwargs):
        self.text = text
        self.position = position
        print(f"Initialized TextOverlayRenderer with text='{text}'")

    def render(self, frame, timestamp_ms):
        print(f"  Rendering text at timestamp {timestamp_ms}ms")
        # 模拟绘制文本
        return frame


@register_unit("speed_display", unit_type="renderer")
class SpeedDisplayRenderer:
    """显示速度信息"""

    def __init__(self, data_path, **kwargs):
        self.data_path = data_path
        print(f"Initialized SpeedDisplayRenderer with data_path='{data_path}'")

    def render(self, frame, timestamp_ms):
        print(f"  Rendering speed at timestamp {timestamp_ms}ms")
        # 模拟查找并绘制速度
        return frame


# 使用 renderer
def example_renderer_pipeline():
    """演示 renderer 类型的使用"""
    print("\n" + "=" * 70)
    print("示例 2: Renderer 类型 - 视频帧渲染流水线")
    print("=" * 70)

    # 创建模拟视频帧
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    timestamps = [0, 33, 66, 100]  # 模拟 4 帧

    # 第一次调用会实例化 renderer
    print("\n首次渲染（会实例化 renderer）：")
    for ts in timestamps:
        frame = execute_unit(
            "text_overlay",
            "renderer",
            frame,
            ts,
            config={"text": "Hello", "position": (10, 30)}
        )
        frame = execute_unit(
            "speed_display",
            "renderer",
            frame,
            ts,
            config={"data_path": "speed.jsonl"}
        )

    # 再次调用会复用实例
    print("\n第二次渲染（复用实例）：")
    for ts in [150, 183]:
        frame = execute_unit(
            "text_overlay",
            "renderer",
            frame,
            ts,
            config={"text": "Hello", "position": (10, 30)}
        )


# ============================================================================
# 示例 3: 定义新的执行单元类型 - Validator
# ============================================================================

import inspect
from nexus.core.execution_units import UnitRunner, UnitSpec, register_type

class ValidatorRunner(UnitRunner):
    """验证器类型：func(data: Any) -> bool"""

    def validate(self, spec: UnitSpec) -> bool:
        if not callable(spec.implementation):
            raise TypeError(f"Validator '{spec.name}' must be callable")

        # 检查参数
        try:
            sig = inspect.signature(spec.implementation)
            if len(sig.parameters) < 1:
                raise TypeError(
                    f"Validator '{spec.name}' must accept at least one argument"
                )
        except (ValueError, TypeError):
            pass

        return True

    def execute(self, spec: UnitSpec, data) -> bool:
        func = spec.implementation
        result = func(data)

        if not isinstance(result, bool):
            raise TypeError(
                f"Validator '{spec.name}' must return bool, got {type(result)}"
            )

        return result


# 注册新类型
register_type(
    name="validator",
    runner=ValidatorRunner(),
    description="Data validators: func(data) -> bool"
)

# 注册几个 validator
@register_unit("positive_checker", unit_type="validator")
def check_all_positive(data):
    """检查是否所有值都为正"""
    return all(x > 0 for x in data)


@register_unit("range_checker", unit_type="validator")
def check_in_range(data):
    """检查是否在 0-100 范围内"""
    return all(0 <= x <= 100 for x in data)


@register_unit("length_checker", unit_type="validator")
def check_min_length(data):
    """检查长度是否至少为 3"""
    return len(data) >= 3


# 使用 validator
def example_validator_type():
    """演示自定义 validator 类型"""
    print("\n" + "=" * 70)
    print("示例 3: 自定义 Validator 类型 - 数据验证")
    print("=" * 70)

    test_data = [10, 20, 30, 40]

    print(f"\n测试数据: {test_data}")

    validators = ["positive_checker", "range_checker", "length_checker"]
    for validator_name in validators:
        result = execute_unit(validator_name, "validator", test_data)
        print(f"  {validator_name}: {'✓ PASS' if result else '✗ FAIL'}")

    # 测试失败情况
    print(f"\n测试数据: [-1, 2, 3]")
    result = execute_unit("positive_checker", "validator", [-1, 2, 3])
    print(f"  positive_checker: {'✓ PASS' if result else '✗ FAIL'}")


# ============================================================================
# 示例 4: 定义新的执行单元类型 - Exporter
# ============================================================================

class ExporterRunner(UnitRunner):
    """导出器类型：func(data: Any, path: Path) -> None"""

    def validate(self, spec: UnitSpec) -> bool:
        if not callable(spec.implementation):
            raise TypeError(f"Exporter '{spec.name}' must be callable")
        return True

    def execute(self, spec: UnitSpec, data, path: Path) -> None:
        func = spec.implementation
        print(f"  Exporting with '{spec.name}' to {path}")
        func(data, path)
        print(f"  Export completed")


# 注册新类型
register_type(
    name="exporter",
    runner=ExporterRunner(),
    description="Data exporters: func(data, path) -> None"
)

# 注册几个 exporter
@register_unit("csv_exporter", unit_type="exporter")
def export_to_csv(data: pd.DataFrame, path: Path):
    """导出为 CSV"""
    print(f"    Writing CSV with {len(data)} rows")
    # data.to_csv(path, index=False)


@register_unit("json_exporter", unit_type="exporter")
def export_to_json(data: dict, path: Path):
    """导出为 JSON"""
    import json
    print(f"    Writing JSON with {len(data)} keys")
    # with open(path, 'w') as f:
    #     json.dump(data, f, indent=2)


@register_unit("summary_exporter", unit_type="exporter")
def export_summary(data: pd.DataFrame, path: Path):
    """导出数据摘要"""
    print(f"    Writing summary: shape={data.shape}, columns={list(data.columns)}")
    # with open(path, 'w') as f:
    #     f.write(data.describe().to_string())


# 使用 exporter
def example_exporter_type():
    """演示自定义 exporter 类型"""
    print("\n" + "=" * 70)
    print("示例 4: 自定义 Exporter 类型 - 数据导出")
    print("=" * 70)

    # 准备数据
    df = pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie"],
        "age": [25, 30, 35],
        "salary": [50000, 60000, 70000]
    })

    print(f"\n数据:\n{df}\n")

    # 导出为不同格式
    execute_unit("csv_exporter", "exporter", df, Path("output.csv"))
    execute_unit("summary_exporter", "exporter", df, Path("summary.txt"))

    # JSON 导出需要字典
    data_dict = df.to_dict()
    execute_unit("json_exporter", "exporter", data_dict, Path("output.json"))


# ============================================================================
# 示例 5: 查看注册的所有单元
# ============================================================================

def example_list_all_units():
    """列出所有注册的执行单元"""
    print("\n" + "=" * 70)
    print("示例 5: 查看所有注册的执行单元")
    print("=" * 70)

    from nexus.core.execution_units import list_types

    # 列出所有类型
    types = list_types()
    print(f"\n已注册的单元类型 ({len(types)}):")
    for type_name, type_info in types.items():
        print(f"  - {type_name}: {type_info.description}")

    # 列出每种类型的单元
    for type_name in types:
        units = list_units(type_name)
        print(f"\n{type_name} 类型的单元 ({len(units)}):")
        for unit_name, unit_spec in units.items():
            desc = unit_spec.description.split('\n')[0] if unit_spec.description else "No description"
            print(f"  - {unit_name}: {desc[:60]}")


# ============================================================================
# 示例 6: 组合使用 - 完整数据处理流水线
# ============================================================================

def example_complete_pipeline():
    """演示组合使用多种类型"""
    print("\n" + "=" * 70)
    print("示例 6: 完整流水线 - 组合使用多种单元类型")
    print("=" * 70)

    print("\n步骤 1: 使用 plugin 加载数据")
    @dataclass
    class LoadConfig:
        file_path: str = "data.csv"

    ctx = PluginContext(config=LoadConfig(), case_path=Path("."))
    data = execute_unit("csv_loader", "plugin", ctx)

    print("\n步骤 2: 使用 validator 验证数据")
    # 将 DataFrame 转换为列表进行验证
    values = data["col1"].tolist()
    is_valid = execute_unit("positive_checker", "validator", values)
    print(f"  验证结果: {'✓ 数据有效' if is_valid else '✗ 数据无效'}")

    if is_valid:
        print("\n步骤 3: 使用 plugin 处理数据")
        @dataclass
        class FilterConfig:
            data: pd.DataFrame
            threshold: float

        ctx = PluginContext(config=FilterConfig(data=data, threshold=1), case_path=Path("."))
        processed = execute_unit("data_filter", "plugin", ctx)

        print("\n步骤 4: 使用 exporter 导出结果")
        execute_unit("csv_exporter", "exporter", processed, Path("result.csv"))

    print("\n✓ 流水线执行完成")


# ============================================================================
# 运行所有示例
# ============================================================================

if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "统一执行单元框架 - 完整示例" + " " * 15 + "║")
    print("╚" + "=" * 68 + "╝")

    # 运行所有示例
    example_plugin_pipeline()
    example_renderer_pipeline()
    example_validator_type()
    example_exporter_type()
    example_list_all_units()
    example_complete_pipeline()

    print("\n" + "=" * 70)
    print("所有示例运行完成！")
    print("=" * 70)
    print("\n核心要点:")
    print("  1. Plugin 和 Renderer 都是执行单元，只是类型不同")
    print("  2. 可以轻松定义新类型（Validator, Exporter 等）")
    print("  3. 所有类型使用统一的注册和执行接口")
    print("  4. 类型之间可以灵活组合使用")
    print()

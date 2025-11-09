"""
示例：使用 repro 模块渲染视频帧

展示如何：
1. 列出所有注册的 renderer
2. 使用 render_all_frames 渲染视频帧
3. 创建自定义 renderer
"""

from pathlib import Path
from nexus.contrib.repro import render_all_frames, list_renderers, render, get_renderer
from nexus.contrib.repro.renderers import BaseDataRenderer
import numpy as np


# ============================================================================
# 示例 1: 列��所有已注册的 renderer
# ============================================================================

def example_list_renderers():
    """列出所有可用的 renderer"""
    print("=" * 70)
    print("示例 1: 列出所有已注册的 renderer")
    print("=" * 70)

    renderers = list_renderers()

    print(f"\n已注册的 renderer ({len(renderers)}):")
    for name, renderer_cls in renderers.items():
        print(f"  - {name}: {renderer_cls.__name__}")
        if renderer_cls.__doc__:
            doc_first_line = renderer_cls.__doc__.strip().split('\n')[0]
            print(f"    {doc_first_line[:70]}")

    print()


# ============================================================================
# 示例 2: 使用已注册的 renderer
# ============================================================================

def example_using_renderers():
    """演示使用已注册的 renderer"""
    print("=" * 70)
    print("示例 2: 使用已注册的 renderer 渲染视频帧")
    print("=" * 70)

    # 配置 renderers（使用注册名称）
    renderer_configs = [
        {
            "name": "speed",  # 注册名称
            "kwargs": {
                "data_path": Path("data/speed.jsonl"),
                "position": (30, 60),
                "tolerance_ms": 5000.0,
                "time_offset_ms": 0,
            }
        },
        {
            "name": "target",
            "kwargs": {
                "data_path": Path("data/targets.jsonl"),
                "calibration_path": Path("data/camera_calibration.yaml"),
                "tolerance_ms": 50.0,
                "time_offset_ms": -50,
            }
        }
    ]

    print("\nRenderer 配置:")
    for i, config in enumerate(renderer_configs, 1):
        print(f"  [{i}] {config['name']}")
        for key, value in config['kwargs'].items():
            print(f"      {key}: {value}")

    # 注意：这只是演示配置，实际使用需要提供真实的文件路径
    print("\n注意：实际使用时需要提供真实的帧目录和数据文件")
    print("示例配置：")
    print("""
    render_all_frames(
        frames_dir=Path("frames/"),
        output_dir=Path("rendered/"),
        timestamps_path=Path("timestamps.csv"),
        renderer_configs=renderer_configs,
        start_time_ms=1000.0,
        end_time_ms=5000.0,
        show_frame_info=True
    )
    """)


# ============================================================================
# 示例 3: 创建自定义 renderer
# ============================================================================

@render("watermark")
class WatermarkRenderer(BaseDataRenderer):
    """
    在帧上添加水印。

    这是一个自定义 renderer 示例，展示如何：
    - 继承 BaseDataRenderer
    - 使用 @render 装饰器注册
    - 实现 render() 方法
    """

    def __init__(self, text="Nexus", position=(10, 30), **kwargs):
        # BaseDataRenderer 需要 data_path，但我们不需要实际加载数据
        super().__init__(data_path="", **kwargs)
        self.text = text
        self.position = position
        print(f"    WatermarkRenderer initialized: text='{text}', position={position}")

    def render(self, frame: np.ndarray, timestamp_ms: int) -> np.ndarray:
        """在帧上绘制水印"""
        import cv2

        # 准备文本
        text = f"{self.text} @ {timestamp_ms}ms"

        # 绘制文本
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(
            frame,
            text,
            self.position,
            font,
            0.7,
            (255, 255, 255),  # White
            2,
            cv2.LINE_AA
        )

        return frame


def example_custom_renderer():
    """演示创建和使用自定义 renderer"""
    print("\n" + "=" * 70)
    print("示例 3: 创建和使用自定义 renderer")
    print("=" * 70)

    print("\n自定义 renderer 已注册: WatermarkRenderer")
    print("  注册名称: 'watermark'")
    print("  功能: 在视频帧上添加水印文本")

    # 查看是否成功注册
    try:
        watermark_cls = get_renderer("watermark")
        print(f"\n✓ 验证注册成功:")
        print(f"  名称: watermark")
        print(f"  实现: {watermark_cls.__name__}")
    except KeyError as e:
        print(f"\n✗ 注册失败: {e}")

    # 演示如何使用
    print("\n使用方式:")
    print("""
    renderer_configs = [
        {
            "name": "watermark",
            "kwargs": {
                "text": "My Video",
                "position": (10, 30)
            }
        }
    ]

    render_all_frames(
        frames_dir=Path("frames/"),
        output_dir=Path("output/"),
        timestamps_path=Path("timestamps.csv"),
        renderer_configs=renderer_configs
    )
    """)


# ============================================================================
# 示例 4: 组合多个 renderer
# ============================================================================

def example_combined_renderers():
    """演示组合使用多个 renderer"""
    print("\n" + "=" * 70)
    print("示例 4: 组合使用多个 renderer")
    print("=" * 70)

    print("\n可以在一个渲染任务中组合多个 renderer:")
    print("""
    renderer_configs = [
        {"name": "speed", "kwargs": {"data_path": "speed.jsonl"}},
        {"name": "target", "kwargs": {"data_path": "targets.jsonl"}},
        {"name": "watermark", "kwargs": {"text": "© 2025", "position": (10, 460)}},
    ]

    # Renderers 按顺序应用到每一帧
    # 1. SpeedRenderer 绘制速度
    # 2. TargetRenderer 绘制目标检测框
    # 3. WatermarkRenderer 添加水印
    """)

    print("\n关键特性:")
    print("  - 所有 renderer 使用简单的装饰器注册")
    print("  - 每个 renderer 实例化一次，重用于所有帧")
    print("  - 简洁配置（使用名称而非完整导入路径）")
    print("  - 无复杂的框架依赖")


# ============================================================================
# 运行所有示例
# ============================================================================

if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 18 + "Repro Renderer 示例" + " " * 18 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    example_list_renderers()
    example_using_renderers()
    example_custom_renderer()
    example_combined_renderers()

    print("\n" + "=" * 70)
    print("所有示例演示完成！")
    print("=" * 70)
    print("\n核心特性:")
    print("  ✓ 简洁的注册方式：@render('name')")
    print("  ✓ 简洁的配置方式：{'name': 'speed', 'kwargs': {...}}")
    print("  ✓ 自动实例化和重用")
    print("  ✓ 无复杂框架依赖")
    print()

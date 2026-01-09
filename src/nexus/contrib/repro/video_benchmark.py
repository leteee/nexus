"""
Benchmarking tools for video processing performance.

Provides utilities to measure and compare performance of different rendering methods.
"""

from __future__ import annotations

import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""

    method_name: str
    total_frames: int
    total_time: float  # seconds
    frames_per_second: float
    time_per_frame: float  # milliseconds
    memory_peak_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if not self.success:
            return f"{self.method_name}: FAILED - {self.error}"

        return (
            f"{self.method_name}:\n"
            f"  Total Time: {self.total_time:.2f}s\n"
            f"  FPS: {self.frames_per_second:.2f}\n"
            f"  Time/Frame: {self.time_per_frame:.2f}ms"
        )


def benchmark_render_function(
    render_func: Callable,
    frames_dir: Path,
    output_path: Path,
    timestamps_path: Path,
    sensor_configs: List[Dict[str, Any]],
    renderer_configs: List[Dict[str, Any]],
    ctx: Any,
    *,
    method_name: str = "Unknown",
    measure_memory: bool = False,
    measure_cpu: bool = False,
    **kwargs,
) -> BenchmarkResult:
    """
    Benchmark a single rendering function.

    Args:
        render_func: The rendering function to benchmark
        method_name: Name for this benchmark
        measure_memory: Track memory usage (requires psutil)
        measure_cpu: Track CPU usage (requires psutil)
        **kwargs: Additional arguments for render_func

    Returns:
        BenchmarkResult with timing and performance metrics
    """
    import pandas as pd
    from .common.io import load_frame_timestamps

    # Load timestamps to get frame count
    frame_times = load_frame_timestamps(timestamps_path)
    total_frames = len(frame_times)

    # Clean output directory
    if output_path.exists():
        import shutil
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    # Setup monitoring
    memory_peak_mb = None
    cpu_percent = None

    if measure_memory or measure_cpu:
        try:
            import psutil
            process = psutil.Process()

            if measure_memory:
                process.memory_info()  # Warm up
            if measure_cpu:
                process.cpu_percent()  # Warm up
        except ImportError:
            logger.warning("psutil not installed, cannot measure memory/CPU")
            measure_memory = False
            measure_cpu = False

    # Run benchmark
    logger.info(f"Benchmarking: {method_name}")
    logger.info(f"Processing {total_frames} frames...")

    start_time = time.time()

    try:
        # Execute rendering
        render_func(
            frames_dir=frames_dir,
            output_path=output_path,
            timestamps_path=timestamps_path,
            sensor_configs=sensor_configs,
            renderer_configs=renderer_configs,
            ctx=ctx,
            **kwargs,
        )

        end_time = time.time()
        total_time = end_time - start_time

        # Collect metrics
        if measure_memory:
            import psutil
            memory_peak_mb = process.memory_info().rss / 1024 / 1024

        if measure_cpu:
            import psutil
            cpu_percent = process.cpu_percent()

        # Calculate stats
        frames_per_second = total_frames / total_time if total_time > 0 else 0
        time_per_frame = (total_time / total_frames * 1000) if total_frames > 0 else 0

        return BenchmarkResult(
            method_name=method_name,
            total_frames=total_frames,
            total_time=total_time,
            frames_per_second=frames_per_second,
            time_per_frame=time_per_frame,
            memory_peak_mb=memory_peak_mb,
            cpu_percent=cpu_percent,
            success=True,
            metadata=kwargs,
        )

    except Exception as e:
        end_time = time.time()
        total_time = end_time - start_time

        logger.error(f"Benchmark failed: {e}")

        return BenchmarkResult(
            method_name=method_name,
            total_frames=total_frames,
            total_time=total_time,
            frames_per_second=0,
            time_per_frame=0,
            success=False,
            error=str(e),
        )


def compare_render_methods(
    frames_dir: Path,
    output_base: Path,
    timestamps_path: Path,
    sensor_configs: List[Dict[str, Any]],
    renderer_configs: List[Dict[str, Any]],
    ctx: Any,
    *,
    methods: Optional[List[str]] = None,
    num_workers: int = 4,
) -> pd.DataFrame:
    """
    Compare performance of different rendering methods.

    Args:
        methods: List of methods to test. Options:
            - "sequential": Original sequential processing
            - "optimized": Optimized sequential (current default)
            - "parallel": Parallel processing
        num_workers: Number of workers for parallel method

    Returns:
        DataFrame with comparison results
    """
    from .video import render_all_frames
    from .video_parallel import render_all_frames_parallel

    if methods is None:
        methods = ["sequential", "parallel"]

    results: List[BenchmarkResult] = []

    for method in methods:
        output_path = output_base / method

        if method == "sequential" or method == "optimized":
            result = benchmark_render_function(
                render_func=render_all_frames,
                frames_dir=frames_dir,
                output_path=output_path,
                timestamps_path=timestamps_path,
                sensor_configs=sensor_configs,
                renderer_configs=renderer_configs,
                ctx=ctx,
                method_name=f"Sequential ({method})",
                measure_memory=True,
                measure_cpu=True,
            )

        elif method == "parallel":
            result = benchmark_render_function(
                render_func=render_all_frames_parallel,
                frames_dir=frames_dir,
                output_path=output_path,
                timestamps_path=timestamps_path,
                sensor_configs=sensor_configs,
                renderer_configs=renderer_configs,
                ctx=ctx,
                method_name=f"Parallel ({num_workers} workers)",
                num_workers=num_workers,
                measure_memory=True,
                measure_cpu=True,
            )

        else:
            logger.warning(f"Unknown method: {method}")
            continue

        results.append(result)
        print(f"\n{result}")

    # Create comparison DataFrame
    if not results:
        return pd.DataFrame()

    data = {
        "Method": [r.method_name for r in results],
        "Total Time (s)": [r.total_time for r in results],
        "FPS": [r.frames_per_second for r in results],
        "Time/Frame (ms)": [r.time_per_frame for r in results],
        "Memory (MB)": [r.memory_peak_mb for r in results],
        "Success": [r.success for r in results],
    }

    df = pd.DataFrame(data)

    # Calculate speedup relative to first method
    if len(results) > 1 and results[0].success:
        baseline_time = results[0].total_time
        df["Speedup"] = baseline_time / df["Total Time (s)"]

    return df


def profile_rendering_pipeline(
    frames_dir: Path,
    output_path: Path,
    timestamps_path: Path,
    sensor_configs: List[Dict[str, Any]],
    renderer_configs: List[Dict[str, Any]],
    ctx: Any,
    *,
    num_frames: int = 10,
) -> Dict[str, float]:
    """
    Profile different stages of the rendering pipeline.

    Measures time spent in:
    - Loading frames (I/O)
    - Sensor data retrieval
    - Rendering
    - Saving frames (I/O)

    Args:
        num_frames: Number of frames to profile (default: 10)

    Returns:
        Dict with timing breakdown by stage
    """
    import cv2
    import importlib
    from .common.io import load_frame_timestamps
    from .common.sensor_manager import SensorDataManager

    # Setup
    frame_times = load_frame_timestamps(timestamps_path)
    frame_times = frame_times.head(num_frames)

    sensor_manager = SensorDataManager()
    for sensor_conf in sensor_configs:
        sensor_manager.register_sensor(
            name=sensor_conf["name"],
            data_path=sensor_conf["path"],
            time_offset_ms=sensor_conf.get("time_offset_ms", 0),
            tolerance_ms=sensor_conf.get("tolerance_ms", float('inf')),
        )

    # Initialize renderers
    renderers = []
    for renderer_conf in renderer_configs:
        class_path = renderer_conf.get("class")
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        renderer_class = getattr(module, class_name)
        renderer_kwargs = renderer_conf.get("kwargs", {})
        renderer_instance = renderer_class(ctx, **renderer_kwargs)

        renderers.append({
            "instance": renderer_instance,
            "sensor": renderer_conf.get("sensor"),
            "strategy": renderer_conf.get("match_strategy", "forward"),
        })

    # Profile stages
    timings = {
        "load_frame": 0.0,
        "get_sensor_data": 0.0,
        "render": 0.0,
        "save_frame": 0.0,
    }

    frame_pattern = "frame_{:06d}.png"

    for i, (_, row) in enumerate(frame_times.iterrows()):
        frame_idx = int(row["frame_index"])
        timestamp_ms = float(row["timestamp_ms"])

        # Load frame
        start = time.time()
        frame_path = frames_dir / frame_pattern.format(frame_idx)
        frame = cv2.imread(str(frame_path))
        timings["load_frame"] += time.time() - start

        if frame is None:
            continue

        ctx.remember("current_frame_idx", frame_idx)

        # Render
        for renderer_info in renderers:
            # Get sensor data
            start = time.time()
            sensor_name = renderer_info["sensor"]
            strategy = renderer_info["strategy"]

            if sensor_name and sensor_name in sensor_manager.sensors:
                stream = sensor_manager.sensors[sensor_name]
                data_to_render = stream.get_value_at(timestamp_ms, strategy=strategy)
            else:
                data_to_render = {'snapshot_time_ms': timestamp_ms}

            timings["get_sensor_data"] += time.time() - start

            # Render
            start = time.time()
            frame = renderer_info["instance"].render(frame, data_to_render)
            timings["render"] += time.time() - start

        # Save frame
        start = time.time()
        output_file = output_path / frame_pattern.format(frame_idx)
        cv2.imwrite(str(output_file), frame)
        timings["save_frame"] += time.time() - start

    # Calculate percentages
    total_time = sum(timings.values())
    percentages = {
        f"{stage}_percent": (time_val / total_time * 100) if total_time > 0 else 0
        for stage, time_val in timings.items()
    }

    result = {**timings, **percentages, "total": total_time}

    # Print report
    print("\n=== Rendering Pipeline Profile ===")
    print(f"Profiled {num_frames} frames")
    print(f"Total time: {total_time:.3f}s")
    print("\nTime breakdown:")
    for stage, time_val in timings.items():
        percent = result[f"{stage}_percent"]
        print(f"  {stage:20s}: {time_val:6.3f}s ({percent:5.1f}%)")

    return result

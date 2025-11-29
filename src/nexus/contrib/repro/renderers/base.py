"""
Base renderer class providing common functionality for all data renderers.

This module provides BaseDataRenderer with default implementations for:
- Data loading from JSONL/CSV
- Forward/nearest/backward matching strategies
- Common helper methods

Subclasses only need to implement render() method.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Literal, Optional, Union

import numpy as np

from ..types import DataRenderer
from ..common.io import load_jsonl


class BaseDataRenderer(DataRenderer):
    """
    Base class for data renderers with common matching strategies.

    Provides:
    - Automatic data loading from JSONL
    - Three matching strategies: nearest, forward, backward
    - Configurable tolerance

    Subclasses implement:
    - render(frame, timestamp_ms): How to draw data on frame

    Example:
        >>> class SpeedRenderer(BaseDataRenderer):
        ...     def __init__(self, ctx, data_path, position=(20, 50), **kwargs):
        ...         super().__init__(ctx, data_path, **kwargs)
        ...         self.position = position
        ...
        ...     def render(self, frame, timestamp_ms):
        ...         matched = self.match_data(timestamp_ms)
        ...         if not matched:
        ...             return frame
        ...         self.ctx.logger.debug(f"Rendering speed at {timestamp_ms}ms")
        ...         speed = matched[0]['speed']
        ...         cv2.putText(frame, f"Speed: {speed:.1f}", self.position, ...)
        ...         return frame
    """

    def __init__(
        self,
        ctx: Any,
        data_path: Union[Path, str],
        tolerance_ms: float = 50.0,
        match_strategy: Literal["nearest", "forward", "backward"] = "nearest",
        time_offset_ms: int = 0,
    ):
        """
        Args:
            ctx: Context object providing logger, path resolution, shared state access
            data_path: Path to JSONL data file
            tolerance_ms: Matching tolerance in milliseconds
            match_strategy: Matching strategy - "nearest", "forward", or "backward"
            time_offset_ms: Time offset to correct data timestamp bias (int milliseconds)
                          Positive: data timestamps are slow (recorded smaller than actual)
                          Negative: data timestamps are fast (recorded larger than actual)
                          Example: time_offset_ms=100 means data recorded at 900ms actually happened at 1000ms
        """
        self.ctx = ctx
        self.data_path = Path(data_path)
        self.tolerance_ms = tolerance_ms
        self.match_strategy = match_strategy
        self.time_offset_ms = time_offset_ms
        self.data: List[dict] = []

        # Load data if path exists
        if self.data_path.exists():
            self.load_data(self.data_path)

    def load_data(self, data_path: Path) -> None:
        """
        Load time-series data from JSONL file.

        Args:
            data_path: Path to JSONL file
        """
        self.data = load_jsonl(data_path)

    def match_data(
        self,
        timestamp_ms: int,
        tolerance_ms: Optional[float] = None,
    ) -> List[dict]:
        """
        Match data using configured strategy with time offset applied.

        Time offset corrects data timestamp bias: searches for data at (timestamp_ms - time_offset_ms).
        - time_offset_ms > 0: Data timestamps are slow (recorded smaller than actual)
        - time_offset_ms < 0: Data timestamps are fast (recorded larger than actual)

        Args:
            timestamp_ms: Target timestamp in milliseconds (video frame time, int)
            tolerance_ms: Override tolerance (uses self.tolerance_ms if None)

        Returns:
            List with single matching data dict, or empty list if no match

        Example:
            >>> # Video frame at 1000ms, time_offset_ms=100 (data timestamps slow by 100ms)
            >>> # Will search for data recorded at 900ms (which actually happened at 1000ms)
            >>> renderer.match_data(1000)  # Finds data near 900ms
        """
        if tolerance_ms is None:
            tolerance_ms = self.tolerance_ms

        if not self.data:
            return []

        # Apply time offset to correct data timestamp bias
        # If data timestamps are slow, subtract offset to find earlier recorded timestamps
        adjusted_timestamp_ms = timestamp_ms - self.time_offset_ms

        if self.match_strategy == "nearest":
            return self._match_nearest(adjusted_timestamp_ms, tolerance_ms)
        elif self.match_strategy == "forward":
            return self._match_forward(adjusted_timestamp_ms, tolerance_ms)
        elif self.match_strategy == "backward":
            return self._match_backward(adjusted_timestamp_ms, tolerance_ms)
        else:
            raise ValueError(f"Unknown match_strategy: {self.match_strategy}")

    def _match_nearest(self, timestamp_ms: int, tolerance_ms: float) -> List[dict]:
        """
        Find nearest data point within tolerance.

        Args:
            timestamp_ms: Target timestamp (int)
            tolerance_ms: Maximum acceptable time difference

        Returns:
            List with nearest data point, or empty if outside tolerance
        """
        closest = min(
            self.data,
            key=lambda d: abs(d["timestamp_ms"] - timestamp_ms)
        )

        time_diff = abs(closest["timestamp_ms"] - timestamp_ms)
        if time_diff <= tolerance_ms:
            return [closest]

        return []

    def _match_forward(self, timestamp_ms: int, tolerance_ms: float) -> List[dict]:
        """
        Forward match: Find most recent data BEFORE or AT timestamp.

        Useful for data that should "hold" until next update (e.g., speed).

        Args:
            timestamp_ms: Target timestamp (int)
            tolerance_ms: Maximum time since last data point

        Returns:
            List with most recent data point, or empty if too old
        """
        # Filter data points BEFORE or AT frame timestamp
        candidates = [
            d for d in self.data
            if d["timestamp_ms"] <= timestamp_ms
        ]

        if not candidates:
            return []

        # Get most recent
        closest = max(candidates, key=lambda d: d["timestamp_ms"])
        time_diff = timestamp_ms - closest["timestamp_ms"]

        # Check tolerance
        if time_diff <= tolerance_ms:
            return [closest]

        return []

    def _match_backward(self, timestamp_ms: int, tolerance_ms: float) -> List[dict]:
        """
        Backward match: Find earliest data AFTER or AT timestamp.

        Useful for predictive data or lookahead scenarios.

        Args:
            timestamp_ms: Target timestamp
            tolerance_ms: Maximum time until next data point

        Returns:
            List with earliest future data point, or empty if too far
        """
        # Filter data points AFTER or AT frame timestamp
        candidates = [
            d for d in self.data
            if d["timestamp_ms"] >= timestamp_ms
        ]

        if not candidates:
            return []

        # Get earliest
        closest = min(candidates, key=lambda d: d["timestamp_ms"])
        time_diff = closest["timestamp_ms"] - timestamp_ms

        # Check tolerance
        if time_diff <= tolerance_ms:
            return [closest]

        return []

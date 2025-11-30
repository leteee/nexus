"""
Type definitions for data replay system.

Defines data structures for frame timing, data points, and rendering protocols.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

import numpy as np


@dataclass
class VideoMetadata:
    """Metadata about extracted video frames."""

    total_frames: int
    fps: float
    width: int
    height: int
    output_path: Path


class DataRenderer(ABC):
    """
    Abstract base class for all renderers that operate on a "push" model.

    This interface defines the contract for a renderer in the new architecture.
    The renderer is expected to receive data that has already been processed
    and matched for the current timestamp. Its only responsibility is to draw.
    """

    @abstractmethod
    def render(
        self,
        frame: np.ndarray,
        data: Optional[Dict[str, Any]],
    ) -> np.ndarray:
        """
        Renders the given data onto the frame.

        Args:
            frame: The video frame (as a numpy array) to draw on.
            data: A dictionary containing the specific data for this renderer
                  at the current timestamp. This can be None if no data was
                  found for the current timestamp.

        Returns:
            The modified frame.
        """
        raise NotImplementedError


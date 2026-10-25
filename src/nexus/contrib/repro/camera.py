"""Camera calibration and 3D target projection."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .errors import CameraError

DEFAULT_CAMERA_PATH = Path(__file__).with_name("camera_calibration.json")


@dataclass(frozen=True)
class ProjectedTarget:
    """A target projected from ADS coordinates into image coordinates."""

    corners: tuple[tuple[int, int], ...]
    target: dict[str, Any]
    ads_bounds: dict[str, float]


class CameraModel:
    """Pinhole camera model loaded from an OpenCV-style calibration file."""

    def __init__(
        self,
        camera_matrix: Any,
        distortion_coefficients: Any,
        rotation_vector: Any,
        translation_vector: Any,
        *,
        source: Path | None = None,
        image_width: int | None = None,
        image_height: int | None = None,
    ) -> None:
        try:
            self.camera_matrix = np.asarray(camera_matrix, dtype=np.float32)
            self.distortion_coefficients = np.asarray(distortion_coefficients, dtype=np.float32)
            self.rotation_vector = np.asarray(rotation_vector, dtype=np.float32).reshape(3, 1)
            self.translation_vector = np.asarray(translation_vector, dtype=np.float32).reshape(3, 1)
        except (TypeError, ValueError) as exc:
            raise CameraError(f"invalid camera calibration arrays: {exc}") from exc

        if self.camera_matrix.shape != (3, 3):
            raise CameraError(f"camera_matrix must be 3x3, got {self.camera_matrix.shape}")
        if self.distortion_coefficients.ndim != 1:
            raise CameraError("distortion_coefficients must be a one-dimensional array")
        if self.rotation_vector.shape != (3, 1) or self.translation_vector.shape != (3, 1):
            raise CameraError("rotation_vector and translation_vector must contain three values")
        self.source = source
        self.image_width = int(image_width) if image_width else None
        self.image_height = int(image_height) if image_height else None

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, source: Path | None = None) -> CameraModel:
        required = ("camera_matrix", "distortion_coefficients", "rotation_vector", "translation_vector")
        missing = [key for key in required if key not in data]
        if missing:
            raise CameraError(f"camera calibration is missing keys: {', '.join(missing)}")
        return cls(
            data["camera_matrix"],
            data["distortion_coefficients"],
            data["rotation_vector"],
            data["translation_vector"],
            source=source,
            image_width=data.get("image_width"),
            image_height=data.get("image_height"),
        )

    @classmethod
    def from_file(cls, path: Path | str) -> CameraModel:
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise CameraError(f"cannot read camera calibration {path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise CameraError(f"invalid camera calibration JSON {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise CameraError(f"camera calibration {path} must contain a JSON object")
        return cls.from_dict(data, source=path)

    @classmethod
    def load(cls, source: str | Path | None = None) -> CameraModel:
        if source is None or source == "auto":
            return cls.from_file(DEFAULT_CAMERA_PATH)
        return cls.from_file(Path(source))

    def validate_frame_size(self, width: int, height: int) -> None:
        """Ensure the calibration reference size matches the rendered frame.

        Intrinsics are calibrated for a concrete sensor/image size.  Silently
        rescaling them for a different resolution (especially a different aspect
        ratio) changes the projection semantics and produces misleading boxes.
        """

        if not self.image_width or not self.image_height:
            return
        if (width, height) != (self.image_width, self.image_height):
            source = f" ({self.source})" if self.source else ""
            raise CameraError(
                f"camera calibration{source} is for {self.image_width}x{self.image_height}, "
                f"but the frame is {width}x{height}; provide a calibration matching the video "
                f"resolution (or regenerate the video at the calibrated size)"
            )

    def project(self, points_3d: np.ndarray) -> np.ndarray:
        points = np.asarray(points_3d, dtype=np.float32)
        if points.ndim != 2 or points.shape[1] != 3:
            raise CameraError(f"points_3d must have shape (N, 3), got {points.shape}")
        projected, _ = cv2.projectPoints(
            points,
            self.rotation_vector,
            self.translation_vector,
            self.camera_matrix,
            self.distortion_coefficients,
        )
        return projected.reshape(-1, 2)

    def project_target_box(self, target: dict[str, Any]) -> ProjectedTarget | None:
        """Project the four angular corners of one target detection.

        The current ADS record carries a distance plus left/right/top/bottom
        angles.  The four box corners are therefore placed at that distance;
        this is a visualization approximation, not a full 3D box fit.
        """

        try:
            distance = float(target["distance_m"])
            angle_left = -math.radians(float(target["angle_left"]))
            angle_right = -math.radians(float(target["angle_right"]))
            angle_top = math.radians(float(target["angle_top"]))
            angle_bottom = math.radians(float(target["angle_bottom"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise CameraError(f"invalid target record: {target!r}") from exc
        if distance <= 0:
            return None

        x_left = distance * math.tan(angle_left)
        x_right = distance * math.tan(angle_right)
        y_top = distance * math.tan(angle_top)
        y_bottom = distance * math.tan(angle_bottom)

        corners_3d = np.array(
            [
                [x_left, y_bottom, distance],
                [x_right, y_bottom, distance],
                [x_right, y_top, distance],
                [x_left, y_top, distance],
            ],
            dtype=np.float32,
        )
        points_2d = self.project(corners_3d)
        corners = tuple((int(point[0]), int(point[1])) for point in points_2d)
        return ProjectedTarget(
            corners=corners,
            target=target,
            ads_bounds={
                "x_left": -x_left,
                "x_right": -x_right,
                "y_top": y_top,
                "y_bottom": y_bottom,
            },
        )

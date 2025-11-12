"""
Target renderer for displaying 3D object detections on video frames.

Projects 3D targets from ADS coordinates to 2D image using camera calibration.
Renders bounding boxes and information panel.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import List, Optional, Tuple, Union, Any

import cv2
import numpy as np

from .base import BaseDataRenderer


class TargetRenderer(BaseDataRenderer):
    """
    Render 3D target detections projected to 2D image.

    Features:
    - Projects 3D bounding boxes from ADS to camera coordinates
    - Draws boxes with target IDs
    - Optional information panel in bottom-left corner (disabled by default)
    - Configurable tolerance for matching

    Data format (JSONL):
        {
          "timestamp_ms": 1761524999999.678,
          "targets": [
            {
              "id": 1,
              "type": "car",
              "distance_m": 31.5,
              "angle_left": -4.53,
              "angle_right": -1.25,
              "angle_top": 0.81,
              "angle_bottom": -1.92
            },
            ...
          ]
        }

    Calibration format (JSON):
        {
          "camera": {
            "intrinsics": {
              "fx": 1000.0,
              "fy": 1000.0,
              "cx": 960.0,
              "cy": 540.0
            },
            "extrinsics": {
              "translation": {"x": 0.0, "y": 0.0, "z": 1.5},
              "rotation": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}
            },
            "resolution": {
              "width": 1920,
              "height": 1080
            }
          }
        }

    Example:
        >>> renderer = TargetRenderer(
        ...     ctx=ctx,  # Pass PluginContext
        ...     data_path="input/adb_targets.jsonl",
        ...     calibration_path="camera_calibration.json",
        ...     tolerance_ms=50.0,
        ... )
        >>> frame = cv2.imread("frame_0000.png")
        >>> frame = renderer.render(frame, timestamp_ms=1761524999999.678)
    """

    def __init__(
        self,
        ctx: Any,
        data_path: Union[Path, str],
        calibration_path: Union[Path, str],
        tolerance_ms: float = 50.0,
        time_offset_ms: int = 0,
        box_color: Tuple[int, int, int] = (0, 255, 0),  # Green
        box_thickness: int = 2,
        text_color: Tuple[int, int, int] = (0, 255, 255),  # Yellow
        font_scale: float = 0.5,
        text_thickness: int = 1,
        show_panel: bool = False,
    ):
        """
        Args:
            ctx: Context object providing logger, path resolution, shared state access
            data_path: Path to targets JSONL file
            calibration_path: Path to camera calibration YAML file
            tolerance_ms: Matching tolerance (default 50ms, nearest strategy)
            time_offset_ms: Time offset to correct data timestamp bias (int, default 0ms)
            box_color: Bounding box color in BGR format
            box_thickness: Bounding box line thickness
            text_color: ID label text color in BGR format (default: yellow)
            font_scale: ID label font size multiplier (default: 0.5)
            text_thickness: ID label text thickness (default: 1)
            show_panel: Whether to show info panel in bottom-left (default: False)
        """
        # Use nearest matching for targets
        super().__init__(
            ctx=ctx,
            data_path=data_path,
            tolerance_ms=tolerance_ms,
            match_strategy="nearest",
            time_offset_ms=time_offset_ms,
        )

        self.calibration_path = Path(calibration_path)
        self.box_color = box_color
        self.box_thickness = box_thickness
        self.text_color = text_color
        self.font_scale = font_scale
        self.text_thickness = text_thickness
        self.show_panel = show_panel

        # Load camera calibration
        with open(self.calibration_path, 'r', encoding='utf-8') as f:
            self.calib = json.load(f)

        # Build projection matrix
        self._build_projection_matrix()

    def _build_projection_matrix(self) -> None:
        """Build camera projection matrix and rvec/tvec for cv2.projectPoints."""
        # Load camera intrinsic matrix K (3x3)
        self.K = np.array(self.calib['camera_matrix'], dtype=np.float32)

        # Load distortion coefficients
        self.dist_coeffs = np.array(self.calib['distortion_coefficients'], dtype=np.float32)

        # Load rotation vector (Rodrigues format, 3x1)
        self.rvec = np.array(self.calib['rotation_vector'], dtype=np.float32).reshape(3, 1)

        # Load translation vector (3x1)
        self.tvec = np.array(self.calib['translation_vector'], dtype=np.float32).reshape(3, 1)

        # Get image resolution
        self.img_width = self.calib['image_width']
        self.img_height = self.calib['image_height']

    def _project_target_to_image(self, target: dict) -> Optional[dict]:
        """
        Project 3D target in vehicle coordinates to 2D image coordinates.

        Coordinate system:
        - Vehicle: Z=forward, X=right, Y=up
        - Camera: X=right, Y=down, Z=forward
        - Conversion: cam_X=vehicle_X, cam_Y=-vehicle_Y, cam_Z=vehicle_Z

        Target data format:
        - distance_m: Forward distance along Z-axis
        - angle_left/right: Horizontal angles (XZ plane, left is negative)
        - angle_top/bottom: Vertical angles (YZ plane, top is positive)

        Calculation:
        - Z = distance_m
        - X = distance_m * tan(angle_horizontal)
        - Y = distance_m * tan(angle_vertical)

        Args:
            target: Target dict with distance_m and angle edges (in degrees)

        Returns:
            Dict with projected 2D corners, or None if out of view
        """
        distance = target["distance_m"]
        angle_left = math.radians(target["angle_left"])
        angle_right = math.radians(target["angle_right"])
        angle_top = math.radians(target["angle_top"])
        angle_bottom = math.radians(target["angle_bottom"])

        # Calculate 3D corners in vehicle coordinates
        # Z is the same for all corners (forward distance)
        z = distance

        # Check if target is in front of vehicle (valid for projection)
        if z <= 0:
            return None  # Target behind vehicle, skip

        # X coordinates from horizontal angles
        x_left = distance * math.tan(angle_left)    # Left edge (negative)
        x_right = distance * math.tan(angle_right)  # Right edge (positive)

        # Y coordinates from vertical angles
        y_top = distance * math.tan(angle_top)       # Top edge (positive)
        y_bottom = distance * math.tan(angle_bottom) # Bottom edge (negative)

        # Four corners in vehicle coordinates
        # Top-left
        vehicle_tl = [x_left, y_top, z]
        # Top-right
        vehicle_tr = [x_right, y_top, z]
        # Bottom-right
        vehicle_br = [x_right, y_bottom, z]
        # Bottom-left
        vehicle_bl = [x_left, y_bottom, z]

        # Convert vehicle coordinates to camera coordinates
        # cam_X = vehicle_X, cam_Y = -vehicle_Y, cam_Z = vehicle_Z
        corners_3d = np.array([
            [vehicle_tl[0], -vehicle_tl[1], vehicle_tl[2]],  # TL
            [vehicle_tr[0], -vehicle_tr[1], vehicle_tr[2]],  # TR
            [vehicle_br[0], -vehicle_br[1], vehicle_br[2]],  # BR
            [vehicle_bl[0], -vehicle_bl[1], vehicle_bl[2]],  # BL
        ], dtype=np.float32)

        # Project to 2D using OpenCV
        points_2d, _ = cv2.projectPoints(
            corners_3d,
            self.rvec,
            self.tvec,
            self.K,
            None  # No distortion
        )

        # Convert to list of tuples
        # OpenCV will automatically clip coordinates to image bounds when drawing
        corners_2d = [(int(pt[0][0]), int(pt[0][1])) for pt in points_2d]  # type: ignore

        return {
            "corners": corners_2d,
            "target": target,
        }

    def _draw_target_box(
        self,
        frame: np.ndarray,
        proj_target: dict,
    ) -> np.ndarray:
        """Draw axis-aligned bounding box for projected target."""
        corners = proj_target["corners"]
        target = proj_target["target"]

        # Calculate axis-aligned bounding box (AABB) from projected corners
        # This ensures only horizontal and vertical lines (no diagonal edges)
        x_coords = [pt[0] for pt in corners]
        y_coords = [pt[1] for pt in corners]

        x_min = min(x_coords)
        x_max = max(x_coords)
        y_min = min(y_coords)
        y_max = max(y_coords)

        # Draw axis-aligned rectangle
        cv2.rectangle(
            frame,
            (x_min, y_min),
            (x_max, y_max),
            color=self.box_color,
            thickness=self.box_thickness,
        )

        # Draw target ID above box with text outline
        label = f"ID:{target['id']}"

        font = cv2.FONT_HERSHEY_SIMPLEX
        outline_color = (0, 0, 0)  # Black outline
        outline_thickness = self.text_thickness + 2

        label_pos = (x_min, max(y_min - 5, 15))

        # Draw text outline for better visibility
        cv2.putText(
            frame,
            label,
            label_pos,
            font,
            self.font_scale,
            outline_color,
            outline_thickness,
            cv2.LINE_AA,
        )

        # Draw main text
        cv2.putText(
            frame,
            label,
            label_pos,
            font,
            self.font_scale,
            self.text_color,
            self.text_thickness,
            cv2.LINE_AA,
        )

        return frame

    def _draw_target_panel(
        self,
        frame: np.ndarray,
        targets: List[dict],
    ) -> np.ndarray:
        """Draw target information panel in bottom-left corner."""
        if not targets:
            return frame

        # Panel configuration
        panel_x = 10
        panel_width = 350
        line_height = 25
        padding = 10

        # Calculate panel height
        panel_height = padding * 2 + len(targets) * (line_height * 4 + 5)
        panel_y = frame.shape[0] - panel_height - 10

        # Draw semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(
            overlay,
            (panel_x, panel_y),
            (panel_x + panel_width, panel_y + panel_height),
            (40, 40, 40),
            -1,
        )
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Draw border
        cv2.rectangle(
            frame,
            (panel_x, panel_y),
            (panel_x + panel_width, panel_y + panel_height),
            (100, 100, 100),
            2,
        )

        # Draw target info
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1

        y = panel_y + padding + 15

        for target in targets:
            lines = [
                f"ID: {target['id']}  Type: {target['type']}",
                f"Distance: {target['distance_m']:.1f}m",
                f"Angle L/R: {target['angle_left']:.1f}° / {target['angle_right']:.1f}°",
                f"Angle T/B: {target['angle_top']:.1f}° / {target['angle_bottom']:.1f}°",
            ]

            for line in lines:
                cv2.putText(
                    frame,
                    line,
                    (panel_x + padding, y),
                    font,
                    font_scale,
                    (0, 255, 255),  # Yellow
                    thickness,
                    cv2.LINE_AA,
                )
                y += line_height

            y += 5  # Extra spacing between targets

        return frame

    def render(self, frame: np.ndarray, timestamp_ms: int) -> np.ndarray:
        """
        Render 3D targets on frame.

        Args:
            frame: Video frame (H, W, C) in BGR format
            timestamp_ms: Frame timestamp in milliseconds

        Returns:
            Frame with targets rendered
        """
        # Log rendering start
        self.ctx.logger.debug(f"Rendering targets at timestamp {timestamp_ms}ms")

        # Match target data
        matched = self.match_data(timestamp_ms)

        if not matched:
            self.ctx.logger.debug(f"No target data found for timestamp {timestamp_ms}ms")
            return frame

        # Get targets list from matched data
        targets = matched[0].get("targets", [])

        if not targets:
            self.ctx.logger.debug(f"Matched data has no targets at timestamp {timestamp_ms}ms")
            return frame

        self.ctx.logger.debug(f"Rendering {len(targets)} targets from data at {matched[0].get('timestamp_ms', 'N/A')}ms")

        # Project and draw each target
        projected_targets = []
        for target in targets:
            proj = self._project_target_to_image(target)
            if proj is not None:
                frame = self._draw_target_box(frame, proj)
                projected_targets.append(target)
            else:
                self.ctx.logger.debug(f"Target {target.get('id', 'N/A')} could not be projected (out of view or behind camera)")

        self.ctx.logger.debug(f"Successfully rendered {len(projected_targets)}/{len(targets)} targets")

        # Draw info panel if enabled
        if self.show_panel:
            frame = self._draw_target_panel(frame, projected_targets)

        return frame

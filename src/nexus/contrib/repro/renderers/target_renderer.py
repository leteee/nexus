"""
Target renderer for displaying 3D object detections on video frames.

Projects 3D targets from ADS coordinates to 2D image using camera calibration.
Renders bounding boxes and information panel.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import List

import cv2
import numpy as np
import yaml

from .base import BaseDataRenderer


class TargetRenderer(BaseDataRenderer):
    """
    Render 3D target detections projected to 2D image.

    Features:
    - Projects 3D bounding boxes from ADS to camera coordinates
    - Draws boxes with target IDs
    - Information panel in bottom-left corner
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

    Calibration format (YAML):
        camera:
          intrinsics:
            fx: 1000.0
            fy: 1000.0
            cx: 960.0
            cy: 540.0
          extrinsics:
            translation: {x: 0.0, y: 0.0, z: 1.5}
            rotation: {roll: 0.0, pitch: 0.0, yaw: 0.0}
          resolution:
            width: 1920
            height: 1080

    Example:
        >>> renderer = TargetRenderer(
        ...     data_path="input/adb_targets.jsonl",
        ...     calibration_path="camera_calibration.yaml",
        ...     tolerance_ms=50.0,
        ... )
        >>> frame = cv2.imread("frame_0000.png")
        >>> frame = renderer.render(frame, timestamp_ms=1761524999999.678)
    """

    def __init__(
        self,
        data_path: Path | str,
        calibration_path: Path | str,
        tolerance_ms: float = 50.0,
        box_color: tuple[int, int, int] = (0, 255, 0),  # Green
        box_thickness: int = 2,
        show_panel: bool = True,
    ):
        """
        Args:
            data_path: Path to targets JSONL file
            calibration_path: Path to camera calibration YAML file
            tolerance_ms: Matching tolerance (default 50ms, nearest strategy)
            box_color: Bounding box color in BGR format
            box_thickness: Bounding box line thickness
            show_panel: Whether to show info panel in bottom-left
        """
        # Use nearest matching for targets
        super().__init__(
            data_path=data_path,
            tolerance_ms=tolerance_ms,
            match_strategy="nearest",
        )

        self.calibration_path = Path(calibration_path)
        self.box_color = box_color
        self.box_thickness = box_thickness
        self.show_panel = show_panel

        # Load camera calibration
        with open(self.calibration_path, 'r', encoding='utf-8') as f:
            self.calib = yaml.safe_load(f)

        # Build projection matrix
        self._build_projection_matrix()

    def _build_projection_matrix(self):
        """Build camera projection matrix and rvec/tvec for cv2.projectPoints."""
        # Get intrinsics
        fx = self.calib['camera']['intrinsics']['fx']
        fy = self.calib['camera']['intrinsics']['fy']
        cx = self.calib['camera']['intrinsics']['cx']
        cy = self.calib['camera']['intrinsics']['cy']

        # Camera intrinsic matrix K
        self.K = np.array([
            [fx, 0, cx],
            [0, fy, cy],
            [0, 0, 1]
        ], dtype=np.float32)

        # Get extrinsics
        tx = self.calib['camera']['extrinsics']['translation']['x']
        ty = self.calib['camera']['extrinsics']['translation']['y']
        tz = self.calib['camera']['extrinsics']['translation']['z']

        roll = math.radians(self.calib['camera']['extrinsics']['rotation']['roll'])
        pitch = math.radians(self.calib['camera']['extrinsics']['rotation']['pitch'])
        yaw = math.radians(self.calib['camera']['extrinsics']['rotation']['yaw'])

        # Build rotation matrix (ZYX Euler convention)
        cx, sx = math.cos(roll), math.sin(roll)
        cy, sy = math.cos(pitch), math.sin(pitch)
        cz, sz = math.cos(yaw), math.sin(yaw)

        Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
        Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])

        R = Rz @ Ry @ Rx

        # Translation vector
        t = np.array([[tx], [ty], [tz]], dtype=np.float32)

        # Convert to rotation vector for cv2.projectPoints
        self.rvec, _ = cv2.Rodrigues(R.astype(np.float32))
        self.tvec = t

        # Get image resolution
        self.img_width = self.calib['camera']['resolution']['width']
        self.img_height = self.calib['camera']['resolution']['height']

    def _project_target_to_image(self, target: dict) -> dict | None:
        """
        Project 3D target in ADS coordinates to 2D image coordinates.

        Coordinate system conversion:
        - ADS: X=forward, Y=left, Z=up
        - Camera: X=right, Y=down, Z=forward
        - Conversion: cam_X=-ADS_Y, cam_Y=-ADS_Z, cam_Z=ADS_X

        Args:
            target: Target dict with distance_m and angle edges

        Returns:
            Dict with projected 2D corners, or None if out of view
        """
        distance = target["distance_m"]
        angle_left = math.radians(target["angle_left"])
        angle_right = math.radians(target["angle_right"])
        angle_top = math.radians(target["angle_top"])
        angle_bottom = math.radians(target["angle_bottom"])

        # Convert edge angles to 3D corners in ADS coordinates
        # Top-left
        x_tl = distance * math.cos(angle_left)
        y_tl = distance * math.sin(angle_left)
        z_tl = distance * math.tan(angle_top)

        # Top-right
        x_tr = distance * math.cos(angle_right)
        y_tr = distance * math.sin(angle_right)
        z_tr = distance * math.tan(angle_top)

        # Bottom-left
        x_bl = distance * math.cos(angle_left)
        y_bl = distance * math.sin(angle_left)
        z_bl = distance * math.tan(angle_bottom)

        # Bottom-right
        x_br = distance * math.cos(angle_right)
        y_br = distance * math.sin(angle_right)
        z_br = distance * math.tan(angle_bottom)

        # Convert ADS to Camera coordinates
        # cam_X = -ADS_Y, cam_Y = -ADS_Z, cam_Z = ADS_X
        corners_3d = np.array([
            [-y_tl, -z_tl, x_tl],  # TL
            [-y_tr, -z_tr, x_tr],  # TR
            [-y_br, -z_br, x_br],  # BR
            [-y_bl, -z_bl, x_bl],  # BL
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
        corners_2d = [(int(pt[0][0]), int(pt[0][1])) for pt in points_2d]

        # Check if any point is outside image bounds (with margin)
        margin = 100
        for x, y in corners_2d:
            if (x < -margin or y < -margin or
                x > self.img_width + margin or y > self.img_height + margin):
                return None

        return {
            "corners": corners_2d,
            "target": target,
        }

    def _draw_target_box(
        self,
        frame: np.ndarray,
        proj_target: dict,
    ) -> np.ndarray:
        """Draw bounding box for projected target."""
        corners = proj_target["corners"]
        target = proj_target["target"]

        # Draw polygon
        pts = np.array(corners, np.int32).reshape((-1, 1, 2))
        cv2.polylines(
            frame,
            [pts],
            isClosed=True,
            color=self.box_color,
            thickness=self.box_thickness,
        )

        # Draw target ID above box
        top_left = corners[0]
        label = f"ID:{target['id']}"

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1

        cv2.putText(
            frame,
            label,
            (top_left[0], max(top_left[1] - 5, 15)),
            font,
            font_scale,
            (0, 255, 255),  # Yellow
            thickness,
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

    def render(self, frame: np.ndarray, timestamp_ms: float) -> np.ndarray:
        """
        Render 3D targets on frame.

        Args:
            frame: Video frame (H, W, C) in BGR format
            timestamp_ms: Frame timestamp in milliseconds

        Returns:
            Frame with targets rendered
        """
        # Match target data
        matched = self.match_data(timestamp_ms)

        if not matched:
            return frame

        # Get targets list from matched data
        targets = matched[0].get("targets", [])

        if not targets:
            return frame

        # Project and draw each target
        projected_targets = []
        for target in targets:
            proj = self._project_target_to_image(target)
            if proj is not None:
                frame = self._draw_target_box(frame, proj)
                projected_targets.append(target)

        # Draw info panel if enabled
        if self.show_panel:
            frame = self._draw_target_panel(frame, projected_targets)

        return frame

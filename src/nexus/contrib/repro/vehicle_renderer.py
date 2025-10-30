"""
Comprehensive vehicle data renderer for ADS replay visualization.

This module provides VehicleDataRenderer for rendering vehicle speed,
3D target detections, and frame information on video frames.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import cv2
import numpy as np

from .types import DataRenderer, load_jsonl


class VehicleDataRenderer(DataRenderer):
    """
    Comprehensive vehicle data renderer for ADS replay.

    Renders:
    - Frame ID and timestamp (absolute time + formatted date)
    - Vehicle speed (forward matching with configurable tolerance)
    - 3D ADB targets projected to 2D image with bounding boxes
    - Target information panel in bottom-left corner

    Data sources:
    - speed.jsonl: Vehicle speed data
    - adb_targets.jsonl: 3D target detections in ADS coordinates
    - camera_calibration.yaml: Camera intrinsics and extrinsics
    """

    def __init__(
        self,
        speed_data_path: Path | str,
        targets_data_path: Path | str,
        calibration_path: Path | str,
        speed_tolerance_ms: float = 5000.0,
        target_tolerance_ms: float = 50.0,
    ):
        """
        Args:
            speed_data_path: Path to speed JSONL file
            targets_data_path: Path to ADB targets JSONL file
            calibration_path: Path to camera calibration YAML file
            speed_tolerance_ms: Forward matching tolerance for speed (default 5000ms)
            target_tolerance_ms: Matching tolerance for targets (default 50ms)
        """
        import yaml
        import math

        self.speed_tolerance_ms = speed_tolerance_ms
        self.target_tolerance_ms = target_tolerance_ms
        self.math = math  # Store for use in methods

        # Load speed data
        self.speed_data = load_jsonl(Path(speed_data_path))

        # Load target data
        self.targets_data = load_jsonl(Path(targets_data_path))

        # Load camera calibration
        with open(calibration_path, 'r', encoding='utf-8') as f:
            self.calib = yaml.safe_load(f)

        # Build camera projection matrix
        self._build_projection_matrix()

        # Data placeholder (not used as we load separately)
        self.data = []

        # Context storage for frame_idx and timestamp
        self._current_frame_idx = 0
        self._current_timestamp_ms = 0.0

    def _build_projection_matrix(self):
        """Build camera projection matrix and rvec/tvec for cv2.projectPoints."""
        import math

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
        # R = Rz(yaw) * Ry(pitch) * Rx(roll)
        cx, sx = math.cos(roll), math.sin(roll)
        cy, sy = math.cos(pitch), math.sin(pitch)
        cz, sz = math.cos(yaw), math.sin(yaw)

        Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
        Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])

        R = Rz @ Ry @ Rx

        # Translation vector
        t = np.array([[tx], [ty], [tz]], dtype=np.float32)

        # For cv2.projectPoints, convert rotation matrix to rotation vector
        self.rvec, _ = cv2.Rodrigues(R.astype(np.float32))
        self.tvec = t

        # Extrinsic matrix [R|t] (for reference, not used with cv2.projectPoints)
        self.RT = np.hstack([R, t]).astype(np.float32)

        # Full projection matrix P = K * [R|t] (for reference)
        self.P = self.K @ self.RT

    def load_data(self, data_path: Path) -> None:
        """Not used - data loaded in __init__."""
        pass

    def match_data(
        self,
        timestamp_ms: float,
        tolerance_ms: float = 50.0,
    ) -> List[dict]:
        """Match data returns frame context for compatibility."""
        # Store timestamp for use in render()
        self._current_timestamp_ms = timestamp_ms
        return [{"timestamp_ms": timestamp_ms}]

    def _match_speed_forward(self, timestamp_ms: float) -> dict | None:
        """
        Forward match speed data within tolerance.

        Searches for most recent speed data within speed_tolerance_ms BEFORE frame time.
        Returns None if no match found.
        """
        if not self.speed_data:
            return None

        # Filter data points BEFORE or AT frame timestamp
        candidates = [
            d for d in self.speed_data
            if d["timestamp_ms"] <= timestamp_ms
        ]

        if not candidates:
            return None

        # Get most recent
        closest = max(candidates, key=lambda d: d["timestamp_ms"])
        time_diff = timestamp_ms - closest["timestamp_ms"]

        # Check tolerance
        if time_diff <= self.speed_tolerance_ms:
            return closest

        return None

    def _match_targets_nearest(self, timestamp_ms: float) -> List[dict]:
        """
        Match ADB targets to frame timestamp (nearest within tolerance).

        Returns list of targets for the matched frame.
        """
        if not self.targets_data:
            return []

        # Find nearest timestamp
        closest = min(
            self.targets_data,
            key=lambda d: abs(d["timestamp_ms"] - timestamp_ms)
        )

        time_diff = abs(closest["timestamp_ms"] - timestamp_ms)

        if time_diff <= self.target_tolerance_ms:
            return closest.get("targets", [])

        return []

    def _project_target_to_image(self, target: dict) -> dict | None:
        """
        Project 3D target in ADS coordinates to 2D image coordinates using OpenCV.

        Coordinate system conversion:
        - ADS: X=forward, Y=left, Z=up
        - Camera: X=right, Y=down, Z=forward
        - Conversion: cam_X=-ADS_Y, cam_Y=-ADS_Z, cam_Z=ADS_X

        Args:
            target: Target dict with distance_m and angle edges

        Returns:
            Dict with projected 2D corners, or None if out of view
        """
        import math

        distance = target["distance_m"]
        angle_left = math.radians(target["angle_left"])
        angle_right = math.radians(target["angle_right"])
        angle_top = math.radians(target["angle_top"])
        angle_bottom = math.radians(target["angle_bottom"])

        # Convert edge angles to 3D corners in ADS coordinates
        # ADS: X forward, Y left, Z up

        # Top-left corner
        x_tl = distance * math.cos(angle_left)
        y_tl = distance * math.sin(angle_left)
        z_tl = distance * math.tan(angle_top)

        # Top-right corner
        x_tr = distance * math.cos(angle_right)
        y_tr = distance * math.sin(angle_right)
        z_tr = distance * math.tan(angle_top)

        # Bottom-left corner
        x_bl = distance * math.cos(angle_left)
        y_bl = distance * math.sin(angle_left)
        z_bl = distance * math.tan(angle_bottom)

        # Bottom-right corner
        x_br = distance * math.cos(angle_right)
        y_br = distance * math.sin(angle_right)
        z_br = distance * math.tan(angle_bottom)

        # Convert ADS to Camera coordinates
        # ADS: X=forward, Y=left, Z=up
        # Camera: X=right, Y=down, Z=forward
        # Conversion: cam_X = -ADS_Y, cam_Y = -ADS_Z, cam_Z = ADS_X
        corners_3d = np.array([
            [-y_tl, -z_tl, x_tl],  # TL
            [-y_tr, -z_tr, x_tr],  # TR
            [-y_br, -z_br, x_br],  # BR
            [-y_bl, -z_bl, x_bl],  # BL
        ], dtype=np.float32)

        # Use OpenCV's projectPoints (standard method)
        # rvec and tvec from extrinsics (rotation vector and translation)
        points_2d, _ = cv2.projectPoints(
            corners_3d,
            self.rvec,  # Rotation vector
            self.tvec,  # Translation vector
            self.K,     # Camera intrinsic matrix
            None        # No distortion
        )

        # Convert to list of tuples
        corners_2d = [(int(pt[0][0]), int(pt[0][1])) for pt in points_2d]

        # Get image bounds from calibration
        img_width = self.calib['camera']['resolution']['width']
        img_height = self.calib['camera']['resolution']['height']

        # Check if any point is outside image bounds (allow some margin)
        margin = 100
        for x, y in corners_2d:
            if x < -margin or y < -margin or x > img_width + margin or y > img_height + margin:
                return None

        return {
            "corners": corners_2d,  # [(x, y), ...] for TL, TR, BR, BL
            "target": target,
        }

    def _draw_frame_info(
        self,
        frame: np.ndarray,
        frame_idx: int,
        timestamp_ms: float,
    ) -> np.ndarray:
        """Draw frame ID and timestamp in top-right corner."""
        from datetime import datetime

        # Convert timestamp to datetime
        dt = datetime.fromtimestamp(timestamp_ms / 1000.0)
        date_str = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # millisecond precision

        # Prepare text
        lines = [
            f"Frame: {frame_idx}",
            f"Time: {timestamp_ms:.1f} ms",
            f"Date: {date_str}",
        ]

        # Position in top-right
        img_width = frame.shape[1]
        x_start = img_width - 400
        y_start = 30

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 2
        line_height = 30

        for i, text in enumerate(lines):
            y = y_start + i * line_height

            # Get text size
            (text_w, text_h), baseline = cv2.getTextSize(
                text, font, font_scale, thickness
            )

            # Draw background
            padding = 5
            cv2.rectangle(
                frame,
                (x_start - padding, y - text_h - padding),
                (x_start + text_w + padding, y + baseline + padding),
                (0, 0, 0),
                -1,
            )

            # Draw text
            cv2.putText(
                frame,
                text,
                (x_start, y),
                font,
                font_scale,
                (255, 255, 255),  # White
                thickness,
                cv2.LINE_AA,
            )

        return frame

    def _draw_speed(
        self,
        frame: np.ndarray,
        speed_data: dict | None,
    ) -> np.ndarray:
        """Draw speed in top-left corner."""
        if speed_data is None:
            speed_str = "N/A"
        else:
            speed_str = f"{speed_data['speed']:.1f} km/h"

        text = f"Speed: {speed_str}"

        # Position in top-left
        x, y = 30, 60

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.2
        thickness = 3

        (text_w, text_h), baseline = cv2.getTextSize(
            text, font, font_scale, thickness
        )

        padding = 10
        cv2.rectangle(
            frame,
            (x - padding, y - text_h - padding),
            (x + text_w + padding, y + baseline + padding),
            (0, 0, 0),
            -1,
        )

        cv2.putText(
            frame,
            text,
            (x, y),
            font,
            font_scale,
            (0, 255, 0),  # Green
            thickness,
            cv2.LINE_AA,
        )

        return frame

    def _draw_target_box(
        self,
        frame: np.ndarray,
        proj_target: dict,
    ) -> np.ndarray:
        """Draw bounding box for projected target."""
        corners = proj_target["corners"]
        target = proj_target["target"]

        # Draw polygon (connect corners)
        pts = np.array(corners, np.int32).reshape((-1, 1, 2))
        cv2.polylines(
            frame,
            [pts],
            isClosed=True,
            color=(0, 255, 0),  # Green
            thickness=2,
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

        img_height = frame.shape[0]

        # Panel position and size
        panel_x = 10
        panel_width = 350
        line_height = 25
        padding = 10

        # Calculate panel height
        panel_height = padding * 2 + len(targets) * (line_height * 4 + 5)
        panel_y = img_height - panel_height - 10

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

        # Draw targets
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1

        y = panel_y + padding + 15

        for target in targets:
            # Calculate derived values
            distance = target["distance_m"]
            angle_left_deg = target["angle_left"]
            angle_right_deg = target["angle_right"]
            angle_top_deg = target["angle_top"]
            angle_bottom_deg = target["angle_bottom"]

            # Prepare text lines
            lines = [
                f"ID: {target['id']}  Type: {target['type']}",
                f"Distance: {distance:.1f}m",
                f"Angle L/R: {angle_left_deg:.1f}° / {angle_right_deg:.1f}°",
                f"Angle T/B: {angle_top_deg:.1f}° / {angle_bottom_deg:.1f}°",
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

    def render(self, frame: np.ndarray, data: List[dict]) -> np.ndarray:
        """
        Render with DataRenderer interface compatibility.

        Uses stored frame_idx and timestamp_ms from context.
        """
        frame_idx = self._current_frame_idx
        timestamp_ms = self._current_timestamp_ms

        return self.render_with_context(frame, frame_idx, timestamp_ms)

    def render_with_context(
        self,
        frame: np.ndarray,
        frame_idx: int,
        timestamp_ms: float,
    ) -> np.ndarray:
        """
        Render all vehicle data on frame with explicit context.

        This is the actual rendering method with all required parameters.
        """
        # 1. Draw frame info and timestamp
        frame = self._draw_frame_info(frame, frame_idx, timestamp_ms)

        # 2. Match and draw speed
        speed_data = self._match_speed_forward(timestamp_ms)
        frame = self._draw_speed(frame, speed_data)

        # 3. Match targets
        targets = self._match_targets_nearest(timestamp_ms)

        # 4. Project and draw target boxes
        projected_targets = []
        for target in targets:
            proj = self._project_target_to_image(target)
            if proj is not None:
                frame = self._draw_target_box(frame, proj)
                projected_targets.append(target)

        # 5. Draw target info panel
        frame = self._draw_target_panel(frame, projected_targets)

        return frame

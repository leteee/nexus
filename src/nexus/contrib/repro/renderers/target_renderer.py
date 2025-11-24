"""
Target renderer for displaying 3D object detections on video frames.

Projects 3D targets from ADS coordinates to 2D image using camera calibration.
Renders bounding boxes and information panel.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

import cv2
import numpy as np

from ..types import TextAlignment
from ..utils import resolve_position
from .base import BaseDataRenderer


class TargetRenderer(BaseDataRenderer):
    """
    Render 3D target detections projected to 2D image.
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
        show_box_label: bool = False,
        show_panel: bool = False,
        show_timestamp: bool = True,
        style: dict | TextAlignment = None,
    ):
        """
        Args:
            ctx: Context object providing logger, path resolution, shared state access
            data_path: Path to targets JSONL file
            calibration_path: Path to camera calibration file
            tolerance_ms: Matching tolerance (default 50ms, nearest strategy)
            time_offset_ms: Time offset to correct data timestamp bias (int, default 0ms)
            box_color: Bounding box color in BGR format
            box_thickness: Bounding box line thickness
            show_box_label: Show ID label above each box (default: False)
            show_panel: Whether to show detailed info panel (default: False)
            show_timestamp: Whether to show data and adjusted timestamps (default True)
            style: Text styling and positioning for the info list.
        """
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
        self.show_box_label = show_box_label
        self.show_panel = show_panel
        self.show_timestamp = show_timestamp

        if style is None:
            # Default style: bottom-left corner, 10px from edges
            self.style = TextAlignment(
                position={"anchor": "bottom_left", "coords": (10, -10)},
                color=(0, 255, 255),
                font_scale=0.6,
                thickness=1,
            )
        elif isinstance(style, dict):
            self.style = TextAlignment.model_validate(style)
        else:
            self.style = style

        with open(self.calibration_path, 'r', encoding='utf-8') as f:
            self.calib = json.load(f)
        self._build_projection_matrix()

    def _build_projection_matrix(self) -> None:
        self.K = np.array(self.calib['camera_matrix'], dtype=np.float32)
        self.dist_coeffs = np.array(self.calib['distortion_coefficients'], dtype=np.float32)
        self.rvec = np.array(self.calib['rotation_vector'], dtype=np.float32).reshape(3, 1)
        self.tvec = np.array(self.calib['translation_vector'], dtype=np.float32).reshape(3, 1)
        self.img_width = self.calib['image_width']
        self.img_height = self.calib['image_height']

    def _project_target_to_image(self, target: dict) -> Optional[dict]:
        distance = target["distance_m"]
        if distance <= 0:
            return None

        angle_left = math.radians(target["angle_left"])
        angle_right = math.radians(target["angle_right"])
        angle_top = math.radians(target["angle_top"])
        angle_bottom = math.radians(target["angle_bottom"])

        z = distance
        x_left = distance * math.tan(angle_left)
        x_right = distance * math.tan(angle_right)
        y_top = distance * math.tan(angle_top)
        y_bottom = distance * math.tan(angle_bottom)

        corners_3d = np.array([
            [x_left, -y_top, z],
            [x_right, -y_top, z],
            [x_right, -y_bottom, z],
            [x_left, -y_bottom, z],
        ], dtype=np.float32)

        points_2d, _ = cv2.projectPoints(corners_3d, self.rvec, self.tvec, self.K, None)
        corners_2d = [(int(pt[0][0]), int(pt[0][1])) for pt in points_2d]

        return {"corners": corners_2d, "target": target}

    def _draw_target_box(self, frame: np.ndarray, proj_target: dict) -> None:
        corners = proj_target["corners"]
        x_min, y_min = np.min(corners, axis=0)
        x_max, y_max = np.max(corners, axis=0)

        cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), self.box_color, self.box_thickness)

        if self.show_box_label:
            label = f"ID:{proj_target['target']['id']}"
            # Use a simpler position for the box label: top-left of the box
            label_pos = (x_min, y_min - 5)
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(
                frame, label, label_pos, font, self.style.font_scale, (0, 0, 0), self.style.thickness + 2, cv2.LINE_AA
            )
            cv2.putText(
                frame, label, label_pos, font, self.style.font_scale, self.style.color, self.style.thickness, cv2.LINE_AA
            )

    def _draw_target_info_list(
        self,
        frame: np.ndarray,
        targets: List[dict],
        data_timestamp_ms: Optional[float],
        adjusted_timestamp_ms: Optional[int],
    ) -> None:
        if not targets and not self.show_timestamp:
            return

        lines = [f"ID:{t['id']} {t['type']} {t['distance_m']:.1f}m" for t in targets]
        
        if self.show_timestamp and data_timestamp_ms is not None:
            ts_text = f"[Data: {data_timestamp_ms}ms | Adj: {adjusted_timestamp_ms}ms]"
            lines.append(ts_text)

        if not lines:
            return

        # We use the last line as the anchor for bottom-aligned text blocks
        # and draw upwards from there.
        last_line_pos = resolve_position(
            frame, lines[-1], self.style.font_scale, self.style.thickness, self.style.position
        )
        
        line_height = int(30 * self.style.font_scale)
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        for i, line in enumerate(reversed(lines)):
            pos = (last_line_pos[0], last_line_pos[1] - i * line_height)
            
            cv2.putText(
                frame, line, pos, font, self.style.font_scale, (0, 0, 0), self.style.thickness + 2, cv2.LINE_AA
            )
            cv2.putText(
                frame, line, pos, font, self.style.font_scale, self.style.color, self.style.thickness, cv2.LINE_AA
            )

    def render(self, frame: np.ndarray, timestamp_ms: int) -> np.ndarray:
        self.ctx.logger.debug(f"Rendering targets at timestamp {timestamp_ms}ms")
        matched = self.match_data(timestamp_ms)

        if not matched or not matched[0].get("targets"):
            self.ctx.logger.debug(f"No target data found for timestamp {timestamp_ms}ms")
            if self.show_panel: self._draw_target_panel(frame, [])
            self._draw_target_info_list(frame, [], None, None)
            return frame

        targets = matched[0]["targets"]
        self.ctx.logger.debug(f"Rendering {len(targets)} targets from data at {matched[0].get('timestamp_ms', 'N/A')}ms")

        projected_targets = []
        for target in targets:
            proj = self._project_target_to_image(target)
            if proj:
                self._draw_target_box(frame, proj)
                projected_targets.append(target)

        data_timestamp_ms = matched[0].get('timestamp_ms')
        adjusted_timestamp_ms = timestamp_ms - self.time_offset_ms

        if self.show_panel:
            self._draw_target_panel(frame, projected_targets)
        else:
            self._draw_target_info_list(frame, projected_targets, data_timestamp_ms, adjusted_timestamp_ms)

        return frame

    def _draw_target_panel(self, frame: np.ndarray, targets: List[dict]) -> None:
        # This method is now secondary and not fully refactored, as show_panel=False is the default.
        # It could be updated similarly if it becomes a primary feature.
        if not targets: return
        panel_x, panel_width, line_height, padding = 10, 350, 25, 10
        panel_height = padding * 2 + len(targets) * (line_height * 4 + 5)
        panel_y = frame.shape[0] - panel_height - 10
        overlay = frame.copy()
        cv2.rectangle(overlay, (panel_x, panel_y), (panel_x + panel_width, panel_y + panel_height), (40, 40, 40), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        cv2.rectangle(frame, (panel_x, panel_y), (panel_x + panel_width, panel_y + panel_height), (100, 100, 100), 2)
        y = panel_y + padding + 15
        for target in targets:
            lines = [
                f"ID: {target['id']}  Type: {target['type']}",
                f"Distance: {target['distance_m']:.1f}m",
                f"Angle L/R: {target['angle_left']:.1f}° / {target['angle_right']:.1f}°",
                f"Angle T/B: {target['angle_top']:.1f}° / {target['angle_bottom']:.1f}°",
            ]
            for line in lines:
                cv2.putText(frame, line, (panel_x + padding, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
                y += line_height
            y += 5
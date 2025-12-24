"""
Target renderer for displaying 3D object detections on video frames.

Projects 3D targets from ADS coordinates to 2D image using camera calibration.
Renders bounding boxes and an information panel using the centralized draw_textbox utility.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import List, Optional, Tuple, Any, Dict, Union

import cv2
import numpy as np

from ..types import DataRenderer
from ..common.utils_text import draw_textbox, TextboxConfig


class TargetRenderer(DataRenderer):
    """
    Renders 3D target detections projected to a 2D image.
    Styling and position of the info panel are controlled by a TextboxConfig object.
    """

    def __init__(
        self,
        ctx: Any,
        calibration_path: Union[str, Path],
        box_color: Optional[Tuple[int, int, int]] = None,
        box_thickness: Optional[int] = None,
        show_box_label: bool = True,
        show_timestamp: bool = True,
        textbox_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        """
        Args:
            ctx: Context object.
            calibration_path: Path to camera calibration JSON file.
            box_color: Bounding box color (defaults to textbox_config.text_color if None).
            box_thickness: Bounding box thickness (defaults to textbox_config.font.thickness if None).
            show_box_label: Show ID label above each box.
            show_timestamp: Show data timestamp in the text box.
            textbox_config: Dictionary defining the text panel's appearance and position.
            **kwargs: Catches unused arguments from old configs.
        """
        self.ctx = ctx
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        self.calibration_path = Path(calibration_path)
        self.show_box_label = show_box_label
        self.show_timestamp = show_timestamp
        self.textbox_config = TextboxConfig.from_dict(textbox_config)

        # Set box color and thickness, falling back to textbox config if not provided
        self.box_color = box_color if box_color is not None else self.textbox_config.text_color
        self.box_thickness = box_thickness if box_thickness is not None else self.textbox_config.font.thickness

        with open(self.calibration_path, 'r', encoding='utf-8') as f:
            self.calib = json.load(f)

        self._build_projection_matrix()

    def _build_projection_matrix(self) -> None:
        self.K = np.array(self.calib['camera_matrix'], dtype=np.float32)
        self.dist_coeffs = np.array(self.calib['distortion_coefficients'], dtype=np.float32)
        self.rvec = np.array(self.calib['rotation_vector'], dtype=np.float32).reshape(3, 1)
        self.tvec = np.array(self.calib['translation_vector'], dtype=np.float32).reshape(3, 1)

    def _project_target_to_image(self, target: dict) -> Optional[dict]:
        distance = target.get("distance_m")
        if not distance or distance <= 0:
            return None

        # These angles define the 3D bounding box corners relative to the sensor
        angle_left = math.radians(target["angle_left"])
        angle_right = math.radians(target["angle_right"])
        angle_top = math.radians(target["angle_top"])
        angle_bottom = math.radians(target["angle_bottom"])

        # Calculate 3D corner coordinates in the camera's coordinate system
        # These are the ADS coordinates requested by the user
        x_left = distance * math.tan(angle_left)
        x_right = distance * math.tan(angle_right)
        y_top = distance * math.tan(angle_top)
        y_bottom = distance * math.tan(angle_bottom)

        corners_3d = np.array([
            [x_left, y_bottom, distance], [x_right, y_bottom, distance],
            [x_right, y_top, distance], [x_left, y_top, distance]
        ], dtype=np.float32)

        points_2d, _ = cv2.projectPoints(corners_3d, self.rvec, self.tvec, self.K, self.dist_coeffs)
        if points_2d is None:
            return None
            
        corners_2d = [(int(pt[0][0]), int(pt[0][1])) for pt in points_2d]

        return {
            "corners": corners_2d, 
            "target": target,
            "ads_bounds": {
                "x_left": x_left,
                "x_right": x_right,
                "y_top": y_top,
                "y_bottom": y_bottom,
            }
        }

    def _draw_target_box(self, frame: np.ndarray, proj_target: dict) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        corners = proj_target["corners"]
        
        # To draw an axis-aligned rectangle, find the min/max coordinates
        x_coords = [pt[0] for pt in corners]
        y_coords = [pt[1] for pt in corners]
        
        pt1 = (min(x_coords), min(y_coords))
        pt2 = (max(x_coords), max(y_coords))
        
        cv2.rectangle(frame, pt1, pt2, color=self.box_color, thickness=self.box_thickness)

        if self.show_box_label:
            label = f"ID:{proj_target['target'].get('id', 'N/A')}"
            # Position label above the top-left corner of the axis-aligned box
            label_pos = (pt1[0], max(pt1[1] - 10, 15))
            
            # Per-box labels use a hardcoded style for simplicity and to avoid config clutter
            cv2.putText(frame, label, label_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 3, cv2.LINE_AA)
            cv2.putText(frame, label, label_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.box_color, 1, cv2.LINE_AA)
        
        return pt1, pt2 # Return the calculated 2D bounding box

    def render(self, frame: np.ndarray, data: Optional[Dict[str, Any]]) -> np.ndarray:
        if not data:
            return frame

        targets = data.get("targets", [])
        if not targets:
            return frame

        rendered_targets_info = [] # Store both original target and projected 2D/ADS info
        for target in targets:
            proj_result = self._project_target_to_image(target)
            if proj_result:
                # _draw_target_box now draws AND returns the 2D box corners
                pt1, pt2 = self._draw_target_box(frame, proj_result) 
                
                rendered_targets_info.append({
                    "target": proj_result["target"],
                    "pt1": pt1,
                    "pt2": pt2,
                    "ads_bounds": proj_result["ads_bounds"],
                })

        # If any targets were successfully projected and we have a config for the info panel
        if rendered_targets_info:
            lines = [f"Targets: {len(rendered_targets_info)}"]
            for item in rendered_targets_info:
                t = item['target']
                ads_bounds = item['ads_bounds']

                lines.append(
                    f"  ID:{t.get('id', 'N/A')} {t.get('type', 'N/A')} D:{t['distance_m']:.1f}m "
                    f"XL:{ads_bounds['x_left']:.1f} XR:{ads_bounds['x_right']:.1f} "
                    f"YT:{ads_bounds['y_top']:.1f} YB:{ads_bounds['y_bottom']:.1f}"
                )
            
            if self.show_timestamp:
                data_ts = float(data.get('timestamp_ms', 0.0))
                snapshot_ts = float(data.get('snapshot_time_ms', 0.0))
                lines.append(f"[Data: {data_ts:.0f}ms | Snap: {snapshot_ts:.0f}ms]")

            draw_textbox(frame, lines, self.textbox_config)

        return frame
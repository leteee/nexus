import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Tuple, List, Literal, Optional, Union, Dict

# Using Literal type for clarity and safety, preventing typos in anchor values
AnchorPoint = Literal[
    'top_left', 'top_center', 'top_right',
    'center_left', 'center', 'center_right',
    'bottom_left', 'bottom_center', 'bottom_right'
]

@dataclass
class FontConfig:
    """Configuration for font properties."""
    face: int = cv2.FONT_HERSHEY_SIMPLEX
    scale: float = 0.8
    thickness: int = 1
    line_spacing: float = 1.5  # Multiplier for line height

@dataclass
class PanelConfig:
    """Configuration for the background panel."""
    enabled: bool = False
    padding: int = 10
    bg_color: Tuple[int, int, int] = (40, 40, 40)
    bg_alpha: float = 0.7
    border_color: Optional[Tuple[int, int, int]] = (100, 100, 100)
    border_thickness: int = 1

@dataclass
class PositionConfig:
    """Configuration for positioning."""
    # Coordinates can be integers (pixels) or strings with 'width'/'height'
    x: Union[int, str] = 10
    y: Union[int, str] = 10
    # Which point of the textbox aligns to (x, y)
    anchor: AnchorPoint = 'top_left'

@dataclass
class TextboxConfig:
    """
    Unified configuration for a textbox.
    This combines all other config classes for a clear, nested structure.
    """
    position: PositionConfig = field(default_factory=PositionConfig)
    font: FontConfig = field(default_factory=FontConfig)
    panel: PanelConfig = field(default_factory=PanelConfig)
    
    # Colors are kept at the top level for easier access
    text_color: Tuple[int, int, int] = (255, 255, 255)
    outline_color: Optional[Tuple[int, int, int]] = None  # No outline by default
    outline_thickness: int = 3

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "TextboxConfig":
        """
        Creates a TextboxConfig instance from a dictionary, safely handling nested objects.
        """
        data = data or {}
        
        # Build kwargs for TextboxConfig safely, allowing dataclass defaults to apply
        kwargs = {}
        
        position_data = data.get("position")
        if isinstance(position_data, dict):
            kwargs["position"] = PositionConfig(**position_data)

        font_data = data.get("font")
        if isinstance(font_data, dict):
            kwargs["font"] = FontConfig(**font_data)

        panel_data = data.get("panel")
        if isinstance(panel_data, dict):
            kwargs["panel"] = PanelConfig(**panel_data)
        
        for key in ["text_color", "outline_color", "outline_thickness"]:
            if key in data:
                kwargs[key] = data[key]
        
        return cls(**kwargs)

def _evaluate_coord(expr: Union[int, str], frame_width: int, frame_height: int) -> int:
    """
    Safely evaluates a coordinate expression string (e.g., "width - 100").
    """
    if isinstance(expr, int):
        return expr
    
    # The context is restricted to 'width' and 'height' to prevent abuse.
    try:
        return int(eval(
            expr,
            {'__builtins__': {}},
            {'width': frame_width, 'height': frame_height}
        ))
    except Exception as e:
        raise ValueError(f"Invalid coordinate expression: '{expr}'. Error: {e}")

def _calculate_text_dimensions(
    lines: List[str], font: FontConfig
) -> Tuple[int, int, int]:
    """Calculates total width, height, and single line pixel height of the text."""
    if not lines:
        return 0, 0, 0

    (w_sample, h_sample), baseline = cv2.getTextSize("Tg", font.face, font.scale, font.thickness)
    
    single_line_ph = int(h_sample * font.line_spacing + baseline)
    total_text_h = single_line_ph * len(lines)

    max_line_w = 0
    for line in lines:
        (line_w, _), _ = cv2.getTextSize(line, font.face, font.scale, font.thickness)
        if line_w > max_line_w:
            max_line_w = line_w
    
    return max_line_w, total_text_h, single_line_ph

def _calculate_box_top_left(
    target_x: int, target_y: int, anchor: AnchorPoint, box_width: int, box_height: int
) -> Tuple[int, int]:
    """Calculates the top-left corner of the box based on the anchor point."""
    # Handle horizontal alignment
    if 'left' in anchor:
        pass  # target_x is already the left edge
    elif 'right' in anchor:
        target_x -= box_width
    else:  # Catches 'top_center', 'center', 'bottom_center'
        target_x -= box_width // 2

    # Handle vertical alignment
    if 'top' in anchor:
        pass  # target_y is already the top edge
    elif 'bottom' in anchor:
        target_y -= box_height
    else:  # Catches 'center_left', 'center', 'center_right'
        target_y -= box_height // 2

    return target_x, target_y

def draw_textbox(
    frame: np.ndarray,
    lines: List[str],
    config: TextboxConfig,
) -> None:
    """
    Draws a textbox on the given frame based on the provided configuration.
    """
    if not lines or not lines[0]:
        return

    frame_h, frame_w, _ = frame.shape
    
    # Calculate dimensions of the text block itself
    text_w, text_h, line_h = _calculate_text_dimensions(lines, config.font)

    # Determine the container size (panel or just the text box)
    container_w, container_h = text_w, text_h
    if config.panel.enabled:
        container_w += config.panel.padding * 2
        container_h += config.panel.padding * 2

    # Resolve coordinates and find the top-left of the container
    target_x = _evaluate_coord(config.position.x, frame_w, frame_h)
    target_y = _evaluate_coord(config.position.y, frame_w, frame_h)
    
    tl_x, tl_y = _calculate_box_top_left(
        target_x, target_y, config.position.anchor, container_w, container_h
    )
    
    # Draw the panel if enabled
    if config.panel.enabled:
        br_x, br_y = tl_x + container_w, tl_y + container_h

        if config.panel.bg_color and config.panel.bg_alpha > 0:
            overlay = frame.copy()
            cv2.rectangle(overlay, (tl_x, tl_y), (br_x, br_y), config.panel.bg_color, -1)
            cv2.addWeighted(overlay, config.panel.bg_alpha, frame, 1 - config.panel.bg_alpha, 0, frame)
        
        if config.panel.border_color and config.panel.border_thickness > 0:
            cv2.rectangle(frame, (tl_x, tl_y), (br_x, br_y), config.panel.border_color, config.panel.border_thickness)

    # Calculate starting position for the text
    text_start_x = tl_x + config.panel.padding if config.panel.enabled else tl_x
    text_start_y = tl_y + config.panel.padding if config.panel.enabled else tl_y

    # Draw each line of text
    for i, line in enumerate(lines):
        (_, line_h_px), baseline = cv2.getTextSize(line, config.font.face, config.font.scale, config.font.thickness)
        
        # Y-coordinate for the baseline of the current line
        line_baseline_y = text_start_y + (i * line_h) + line_h_px
        
        if config.outline_color and config.outline_thickness > 0:
            cv2.putText(
                frame, line, (text_start_x, line_baseline_y), config.font.face, config.font.scale,
                config.outline_color, config.outline_thickness, cv2.LINE_AA
            )
        
        cv2.putText(
            frame, line, (text_start_x, line_baseline_y), config.font.face, config.font.scale,
            config.text_color, config.font.thickness, cv2.LINE_AA
        )
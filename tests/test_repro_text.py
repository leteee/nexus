from __future__ import annotations

import pytest

pytest.importorskip("numpy")
pytest.importorskip("cv2")

import numpy as np

from nexus.contrib.repro.text import TextboxStyle, _evaluate_coord, draw_textbox


def test_evaluate_coordinates() -> None:
    assert _evaluate_coord(10, 100, 50) == 10
    assert _evaluate_coord("width - 10", 100, 50) == 90
    assert _evaluate_coord("height - 10", 100, 50) == 40
    assert _evaluate_coord("width * 0.5", 100, 50) == 50
    with pytest.raises(ValueError):
        _evaluate_coord("unknown - 1", 100, 50)


def test_textbox_style_mapping_and_draw() -> None:
    style = TextboxStyle.from_mapping(
        {
            "position": {"x": "width - 5", "y": 12, "anchor": "top_right"},
            "font": {"scale": 0.4},
            "panel": {"enabled": True},
            "text_color": [0, 255, 0],
        }
    )
    frame = np.zeros((80, 120, 3), dtype=np.uint8)
    draw_textbox(frame, ["hello", "world"], style)
    assert frame.sum() > 0

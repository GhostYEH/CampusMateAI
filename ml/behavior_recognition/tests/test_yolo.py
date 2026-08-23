import pytest

from behavior_recognition.yolo import parse_yolo_line, sanitize_box


def test_negative_width_is_rejected():
    """Catches acceptance of boxes whose crop has no positive area."""
    box = parse_yolo_line("1 0.31 0.17 -0.03 0.07")
    fixed, reason = sanitize_box(box)
    assert fixed is None
    assert reason == "non_positive_extent"


def test_slight_coordinate_overflow_is_clipped():
    """Catches loss of otherwise usable annotations at image borders."""
    box = parse_yolo_line("0 1.007 0.25 0.12 0.14")
    fixed, reason = sanitize_box(box)
    assert fixed is not None
    assert 0.0 <= fixed.center_x <= 1.0
    assert 0.0 < fixed.width <= 1.0
    assert reason == "clipped_to_image"


def test_wrong_column_count_raises():
    """Catches silently shifted or truncated YOLO rows."""
    with pytest.raises(ValueError, match="five columns"):
        parse_yolo_line("1 0.5 0.5")

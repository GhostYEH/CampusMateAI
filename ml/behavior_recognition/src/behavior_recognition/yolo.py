from __future__ import annotations

from .records import YoloBox


def parse_yolo_line(line: str) -> YoloBox:
    parts = line.strip().split()
    if len(parts) != 5:
        raise ValueError(f"YOLO row must contain five columns, got {len(parts)}")
    try:
        class_id = int(parts[0])
        values = [float(value) for value in parts[1:]]
    except ValueError as error:
        raise ValueError(f"YOLO row contains a non-numeric value: {line!r}") from error
    if class_id < 0:
        raise ValueError("YOLO class id must be non-negative")
    return YoloBox(class_id, *values)


def sanitize_box(box: YoloBox) -> tuple[YoloBox | None, str | None]:
    if box.width <= 0.0 or box.height <= 0.0:
        return None, "non_positive_extent"
    x1 = box.center_x - box.width / 2.0
    y1 = box.center_y - box.height / 2.0
    x2 = box.center_x + box.width / 2.0
    y2 = box.center_y + box.height / 2.0
    clipped = (max(0.0, x1), max(0.0, y1), min(1.0, x2), min(1.0, y2))
    if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
        return None, "outside_image"
    changed = clipped != (x1, y1, x2, y2)
    fixed = YoloBox(
        class_id=box.class_id,
        center_x=(clipped[0] + clipped[2]) / 2.0,
        center_y=(clipped[1] + clipped[3]) / 2.0,
        width=clipped[2] - clipped[0],
        height=clipped[3] - clipped[1],
    )
    return fixed, "clipped_to_image" if changed else None

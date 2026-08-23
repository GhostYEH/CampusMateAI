from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def tiny_yolo_source(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    for split in ("train", "val"):
        (root / "images" / split).mkdir(parents=True)
        (root / "labels" / split).mkdir(parents=True)
    Image.new("RGB", (100, 80), color=(20, 40, 60)).save(
        root / "images" / "train" / "scene10001.jpg"
    )
    (root / "labels" / "train" / "scene10001.txt").write_text(
        "1 0.5 0.5 0.4 0.5\n3 0.31 0.17 -0.03 0.07\n",
        encoding="utf-8",
    )
    Image.new("RGB", (100, 80), color=(70, 80, 90)).save(
        root / "images" / "val" / "scene20001.jpg"
    )
    (root / "labels" / "val" / "orphan.txt").write_text(
        "2 0.5 0.5 0.2 0.2\n", encoding="utf-8"
    )
    return root

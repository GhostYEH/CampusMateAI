from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class YoloBox:
    class_id: int
    center_x: float
    center_y: float
    width: float
    height: float


@dataclass(frozen=True)
class SourceSpec:
    name: str
    root: Path
    class_map: dict[int, str | None]
    required_for_training: bool = False


@dataclass(frozen=True)
class ManifestRecord:
    sample_id: str
    source: str
    image_path: str
    label_path: str
    source_class_id: int
    target_name: str
    target_index: int
    split: str
    group_id: str
    center_x: float
    center_y: float
    width: float
    height: float
    sha256: str
    split_reason: str = "group_assignment"

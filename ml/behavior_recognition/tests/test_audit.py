from pathlib import Path

from behavior_recognition.audit import audit_sources
from behavior_recognition.records import SourceSpec


def test_audit_reports_pairing_and_invalid_boxes(tiny_yolo_source: Path, tmp_path: Path):
    """Catches audits that hide missing pairs or destructive box failures."""
    spec = SourceSpec(
        name="tiny",
        root=tiny_yolo_source,
        class_map={1: "READ", 2: "WRITE", 3: "PHONE_INTERACTION"},
        required_for_training=True,
    )
    report = audit_sources([spec], tmp_path / "audit.json")
    source = report["sources"]["tiny"]
    assert source["image_count"] == 2
    assert source["label_count"] == 2
    assert source["missing_labels"] == ["images/val/scene20001.jpg"]
    assert source["orphan_labels"] == ["labels/val/orphan.txt"]
    assert source["rejected_boxes"] == 1
    assert report["blocking_errors"] == 2

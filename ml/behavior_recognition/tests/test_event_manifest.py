import csv
from pathlib import Path

from behavior_recognition.event_manifest import build_event_manifest


FIELDS = [
    "video_path",
    "subject_id",
    "session_id",
    "device",
    "start_ms",
    "end_ms",
    "label",
    "reviewer_id",
    "consent",
]


def _write_annotations(root: Path, rows: list[dict[str, str]]) -> None:
    with (root / "annotations.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _row(video: str, subject: str, session: str, start: int, end: int, label: str) -> dict[str, str]:
    return {
        "video_path": video,
        "subject_id": subject,
        "session_id": session,
        "device": "Pixel 8",
        "start_ms": str(start),
        "end_ms": str(end),
        "label": label,
        "reviewer_id": "reviewer-a",
        "consent": "true",
    }


def test_subject_and_video_never_cross_splits(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    rows = []
    for index in range(9):
        video = f"session-{index}.mp4"
        (dataset / video).write_bytes(f"video-{index}".encode())
        rows.append(_row(video, "student-a", f"session-{index}", 0, 2500, "PHONE_INTERACTION"))
    _write_annotations(dataset, rows)

    summary = build_event_manifest(dataset, tmp_path / "manifests", seed=31)

    assert summary.included_count == 9
    assert len({row.split for row in summary.rows if row.status == "included"}) == 1


def test_invalid_boundaries_label_and_consent_are_excluded(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "sample.mp4").write_bytes(b"video")
    invalid_time = _row("sample.mp4", "a", "one", 2000, 1000, "STUDY_ACTIVITY")
    invalid_label = _row("sample.mp4", "b", "two", 0, 1000, "DISTRACTED")
    no_consent = _row("sample.mp4", "c", "three", 0, 1000, "NO_VISIBLE_STUDY")
    no_consent["consent"] = "false"
    _write_annotations(dataset, [invalid_time, invalid_label, no_consent])

    summary = build_event_manifest(dataset, tmp_path / "manifests", seed=31)

    assert summary.included_count == 0
    assert {row.reason for row in summary.rows} == {
        "invalid_time_range",
        "invalid_label",
        "missing_consent",
    }


def test_overlapping_conflicting_events_are_excluded(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "sample.mp4").write_bytes(b"video")
    _write_annotations(dataset, [
        _row("sample.mp4", "a", "one", 0, 3000, "PHONE_INTERACTION"),
        _row("sample.mp4", "a", "one", 2000, 4000, "STUDY_ACTIVITY"),
    ])

    summary = build_event_manifest(dataset, tmp_path / "manifests", seed=31)

    assert summary.included_count == 0
    assert {row.reason for row in summary.rows} == {"overlapping_label_conflict"}


def test_three_or_more_subjects_populate_all_splits(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    rows = []
    for index in range(6):
        video = f"student-{index}.mp4"
        (dataset / video).write_bytes(f"video-{index}".encode())
        rows.append(_row(video, f"student-{index}", "one", 0, 3000, "STUDY_ACTIVITY"))
    _write_annotations(dataset, rows)

    summary = build_event_manifest(dataset, tmp_path / "manifests", seed=31)

    assert {row.split for row in summary.rows if row.status == "included"} == {
        "train",
        "validation",
        "test",
    }


def test_duplicate_video_content_cannot_cross_subjects(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "a.mp4").write_bytes(b"same-video")
    (dataset / "b.mp4").write_bytes(b"same-video")
    _write_annotations(dataset, [
        _row("a.mp4", "student-a", "one", 0, 3000, "STUDY_ACTIVITY"),
        _row("b.mp4", "student-b", "one", 0, 3000, "STUDY_ACTIVITY"),
    ])

    summary = build_event_manifest(dataset, tmp_path / "manifests", seed=31)

    assert summary.included_count == 0
    assert {row.reason for row in summary.rows} == {"duplicate_video_cross_subject"}

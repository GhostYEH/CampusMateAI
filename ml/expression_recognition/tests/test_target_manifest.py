import csv
from pathlib import Path

from PIL import Image

from expression_recognition.target_manifest import build_target_manifest


ANNOTATION_FIELDS = [
    "path",
    "label",
    "subject_id",
    "session_id",
    "device",
    "platform",
    "lighting",
    "pose",
    "occlusion",
    "consent",
]


def _write_sample(root: Path, relative_path: str, color: int) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", (16, 16), color=color).save(path)


def _write_annotations(root: Path, rows: list[dict[str, str]]) -> None:
    with (root / "annotations.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANNOTATION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _row(path: str, *, subject: str, session: str, consent: str = "true") -> dict[str, str]:
    return {
        "path": path,
        "label": "sad",
        "subject_id": subject,
        "session_id": session,
        "device": "Pixel 8",
        "platform": "android",
        "lighting": "indoor",
        "pose": "frontal",
        "occlusion": "none",
        "consent": consent,
    }


def test_subject_and_session_never_cross_splits(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    _write_sample(dataset, "a/one.jpg", 20)
    _write_sample(dataset, "a/two.jpg", 40)
    _write_sample(dataset, "b/three.jpg", 60)
    _write_annotations(
        dataset,
        [
            _row("a/one.jpg", subject="student-a", session="morning"),
            _row("a/two.jpg", subject="student-a", session="morning"),
            _row("b/three.jpg", subject="student-b", session="evening"),
        ],
    )

    summary = build_target_manifest(dataset, tmp_path / "manifests", seed=17)

    split_by_group: dict[tuple[str, str], str] = {}
    for row in summary.rows:
        if row.status != "included":
            continue
        group = (row.subject_id, row.session_id)
        split_by_group.setdefault(group, row.split)
        assert split_by_group[group] == row.split
    assert summary.included_count == 3


def test_same_subject_cannot_cross_splits_between_sessions(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    rows: list[dict[str, str]] = []
    for index in range(12):
        relative = f"session-{index}.jpg"
        _write_sample(dataset, relative, 10 + index)
        rows.append(_row(relative, subject="student-a", session=f"session-{index}"))
    _write_annotations(dataset, rows)

    summary = build_target_manifest(dataset, tmp_path / "manifests", seed=23)

    assert len({row.split for row in summary.rows if row.status == "included"}) == 1


def test_missing_consent_and_duplicate_content_are_excluded(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    _write_sample(dataset, "accepted.jpg", 80)
    (dataset / "duplicate.jpg").write_bytes((dataset / "accepted.jpg").read_bytes())
    _write_sample(dataset, "no-consent.jpg", 100)
    _write_annotations(
        dataset,
        [
            _row("accepted.jpg", subject="student-a", session="one"),
            _row("duplicate.jpg", subject="student-b", session="two"),
            _row("no-consent.jpg", subject="student-c", session="three", consent="false"),
        ],
    )

    summary = build_target_manifest(dataset, tmp_path / "manifests", seed=19)

    assert summary.included_count == 1
    assert summary.excluded_count == 2
    assert {row.reason for row in summary.rows if row.status == "excluded"} == {
        "duplicate_sha256",
        "missing_consent",
    }


def test_cross_label_duplicate_quarantines_every_copy(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    _write_sample(dataset, "sad.jpg", 90)
    (dataset / "happy.jpg").write_bytes((dataset / "sad.jpg").read_bytes())
    sad = _row("sad.jpg", subject="student-a", session="one")
    happy = _row("happy.jpg", subject="student-b", session="two")
    happy["label"] = "happy"
    _write_annotations(dataset, [sad, happy])

    summary = build_target_manifest(dataset, tmp_path / "manifests", seed=19)

    assert summary.included_count == 0
    assert [row.reason for row in summary.rows] == [
        "cross_label_hash_conflict",
        "cross_label_hash_conflict",
    ]


def test_three_or_more_subjects_populate_all_splits(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    rows = []
    for index in range(6):
        relative = f"student-{index}.jpg"
        _write_sample(dataset, relative, 20 + index)
        rows.append(_row(relative, subject=f"student-{index}", session="one"))
    _write_annotations(dataset, rows)

    summary = build_target_manifest(dataset, tmp_path / "manifests", seed=19)

    assert {row.split for row in summary.rows if row.status == "included"} == {
        "train",
        "validation",
        "test",
    }

"""Deterministic synthetic fixture for the whole offline pipeline.

This fixture is generated, not observed. It exists to exercise import,
validation, dual annotation merge, LOPO training, calibration, threshold
selection, export and the Kotlin parity fixture. Never cite its metrics as
evidence about real students.
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .annotations import write_merged
from .schema import LABELS

WINDOWS_PER_SESSION = 10
PARTICIPANTS = 12
SESSIONS_PER_PARTICIPANT = 2

CONTEXT_SEQUENCE = (
    "quiet_listening",
    "quiet_listening",
    "note_taking",
    "note_taking",
    "checking_materials",
    "quiet_listening",
    "quiet_listening",
    "clear_off_task",
    "clear_off_task",
    "quiet_listening",
)

CSV_HEADER = [
    "window_index",
    "start_offset_ms",
    "end_offset_ms",
    "complete",
    "valid_samples",
    "invalid_samples",
    "face_visible_samples",
    "face_visible_ratio",
    "yaw_mean_deg",
    "yaw_std_deg",
    "yaw_min_deg",
    "yaw_max_deg",
    "yaw_samples",
    "pitch_mean_deg",
    "pitch_std_deg",
    "pitch_min_deg",
    "pitch_max_deg",
    "pitch_samples",
    "dominant_stage",
    "stage_counts",
    "manual_page_turns",
    "quiz_submissions",
    "questions",
    "verdict",
    "unavailable_reason",
    "unavailable_reason_counts",
]


@dataclass
class SyntheticPaths:
    root: Path
    manifest: Path
    annotator_a: Path
    annotator_b: Path
    adjudication: Path
    merged: Path
    dataset: Path


def generate(root: Path, seed: int = 20261124) -> SyntheticPaths:
    root = Path(root)
    randomizer = random.Random(seed)
    windows_dir = root / "windows"
    annotations_dir = root / "annotations"
    windows_dir.mkdir(parents=True, exist_ok=True)
    annotations_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, str]] = []
    annotation_a: list[dict[str, Any]] = []
    annotation_b: list[dict[str, Any]] = []
    adjudication: list[dict[str, Any]] = []

    for participant_index in range(1, PARTICIPANTS + 1):
        participant = f"P{participant_index:03d}"
        glasses = "yes" if participant_index % 4 == 0 else "no"
        lighting = "low" if participant_index % 5 == 0 else "normal"
        device = "android_tablet" if participant_index % 3 == 0 else "android_phone"
        for session_index in range(1, SESSIONS_PER_PARTICIPANT + 1):
            session = f"S{session_index:03d}"
            file_name = f"windows/{participant}/{session}.csv"
            path = root / file_name
            path.parent.mkdir(parents=True, exist_ok=True)
            windows, labels_a, labels_b, adjudications = _session_windows(
                participant,
                session,
                participant_index,
                session_index,
                randomizer,
                lighting,
            )
            _write_windows(path, windows)
            manifest_rows.append(
                {
                    "participant_id": participant,
                    "session_id": session,
                    "file": file_name,
                    "glasses": glasses,
                    "lighting": lighting,
                    "device": device,
                }
            )
            for window_index, label in enumerate(labels_a):
                annotation_a.append(
                    {
                        "participant_id": participant,
                        "session_id": session,
                        "window_index": window_index,
                        "label": label,
                        "context": CONTEXT_SEQUENCE[window_index % len(CONTEXT_SEQUENCE)],
                        "note": "",
                    }
                )
            for window_index, label in enumerate(labels_b):
                annotation_b.append(
                    {
                        "participant_id": participant,
                        "session_id": session,
                        "window_index": window_index,
                        "label": label,
                        "context": CONTEXT_SEQUENCE[window_index % len(CONTEXT_SEQUENCE)],
                        "note": "",
                    }
                )
            for window_index, label in adjudications.items():
                adjudication.append(
                    {
                        "participant_id": participant,
                        "session_id": session,
                        "window_index": window_index,
                        "label": label,
                    }
                )

    manifest = root / "manifest.csv"
    _write_csv(
        manifest,
        ["participant_id", "session_id", "file", "glasses", "lighting", "device"],
        manifest_rows,
    )
    annotator_a = annotations_dir / "A01.csv"
    annotator_b = annotations_dir / "A02.csv"
    _write_csv(
        annotator_a,
        ["participant_id", "session_id", "window_index", "label", "context", "note"],
        annotation_a,
    )
    _write_csv(
        annotator_b,
        ["participant_id", "session_id", "window_index", "label", "context", "note"],
        annotation_b,
    )
    adjudication_path = annotations_dir / "adjudication.csv"
    _write_csv(
        adjudication_path,
        ["participant_id", "session_id", "window_index", "label"],
        adjudication,
    )
    merged = root / "merged.jsonl"
    _write_merged(merged, annotation_a, annotation_b, adjudication)
    return SyntheticPaths(
        root=root,
        manifest=manifest,
        annotator_a=annotator_a,
        annotator_b=annotator_b,
        adjudication=adjudication_path,
        merged=merged,
        dataset=root / "dataset.jsonl",
    )


def _session_windows(
    participant: str,
    session: str,
    participant_index: int,
    session_index: int,
    randomizer: random.Random,
    lighting: str,
) -> tuple[list[dict[str, Any]], list[str], list[str], dict[int, str]]:
    windows: list[dict[str, Any]] = []
    labels_a: list[str] = []
    labels_b: list[str] = []
    adjudications: dict[int, str] = {}
    # Two sessions give each participant one short off-task episode and one
    # longer episode so alert delay/missed-segment metrics have both shapes.
    off_task_start = 7 if session_index == 1 else 6
    off_task_length = 1 if session_index == 1 else 2
    for window_index in range(WINDOWS_PER_SESSION):
        context = CONTEXT_SEQUENCE[window_index % len(CONTEXT_SEQUENCE)]
        stage = "slide"
        if window_index == 3:
            stage = "quiz"
        elif window_index == 5:
            stage = "lecture"
        unobservable = (
            (window_index == 2 and participant_index % 6 == 0)
            or (window_index == 8 and participant_index % 7 == 0)
        )
        if context == "clear_off_task" or off_task_start <= window_index < off_task_start + off_task_length:
            intended = "off_task"
        else:
            intended = "on_task"
        # A few silent off-task windows without a clear behavioural cue create
        # genuine annotator ambiguity.
        ambiguous = (
            context in ("quiet_listening", "note_taking")
            and window_index in (3, 8)
            and participant_index % 4 != 0
        )
        if unobservable:
            reason = "no_face" if window_index == 2 else "insufficient_face"
            windows.append(_unobservable_window(window_index, stage, reason, lighting))
            labels_a.append("unobservable")
            labels_b.append("unobservable")
            continue

        valid_samples = 40
        invalid_samples = 0
        if lighting == "low" and window_index in (1, 6):
            valid_samples = 40
            invalid_samples = 0
        ratio = _face_ratio(intended, context, participant_index, window_index, randomizer)
        face_samples = max(0, min(valid_samples, int(round(valid_samples * ratio))))
        yaw_mean, yaw_std, pitch_mean, pitch_std = _head_pose(
            intended, context, ambiguous, participant_index, randomizer
        )
        window = {
            "window_index": window_index,
            "start_offset_ms": window_index * 10_000,
            "end_offset_ms": (window_index + 1) * 10_000,
            "complete": "true",
            "valid_samples": valid_samples,
            "invalid_samples": invalid_samples,
            "face_visible_samples": face_samples,
            "face_visible_ratio": f"{face_samples / valid_samples:.3f}",
            "yaw_mean_deg": f"{yaw_mean:.3f}",
            "yaw_std_deg": f"{yaw_std:.3f}",
            "yaw_min_deg": f"{yaw_mean - 2 * yaw_std:.3f}",
            "yaw_max_deg": f"{yaw_mean + 2 * yaw_std:.3f}",
            "yaw_samples": face_samples,
            "pitch_mean_deg": f"{pitch_mean:.3f}",
            "pitch_std_deg": f"{pitch_std:.3f}",
            "pitch_min_deg": f"{pitch_mean - 2 * pitch_std:.3f}",
            "pitch_max_deg": f"{pitch_mean + 2 * pitch_std:.3f}",
            "pitch_samples": face_samples,
            "dominant_stage": stage,
            "stage_counts": f"{stage}:40",
            "manual_page_turns": str(1 if window_index in (3, 6) else 0),
            "quiz_submissions": str(1 if stage == "quiz" else 0),
            "questions": str(1 if window_index == 5 else 0),
            "verdict": "observable",
            "unavailable_reason": "",
            "unavailable_reason_counts": "",
        }
        windows.append(window)
        label_a = intended
        label_b = intended
        if ambiguous:
            label_b = "off_task"
        if window_index == 4 and participant_index % 5 == 0:
            label_a = "on_task"
            label_b = "unobservable"
        if label_a == label_b:
            labels_a.append(label_a)
            labels_b.append(label_a)
        else:
            labels_a.append(label_a)
            labels_b.append(label_b)
            # Most disagreements are adjudicated; P011 keeps one ambiguous
            # window unresolved so the merge report has a real unresolved case.
            if not (participant_index == 11 and window_index == 3 and session_index == 1):
                adjudications[window_index] = intended
    return windows, labels_a, labels_b, adjudications


def _face_ratio(
    intended: str,
    context: str,
    participant_index: int,
    window_index: int,
    randomizer: random.Random,
) -> float:
    if context == "note_taking":
        base = 0.74
    elif context == "checking_materials":
        base = 0.70
    elif intended == "off_task":
        base = 0.52
    else:
        base = 0.93
    jitter = randomizer.uniform(-0.08, 0.06)
    penalty = 0.06 if participant_index % 4 == 0 else 0.0  # glasses / detection noise
    return max(0.05, min(1.0, base + jitter - penalty))


def _head_pose(
    intended: str,
    context: str,
    ambiguous: bool,
    participant_index: int,
    randomizer: random.Random,
) -> tuple[float, float, float, float]:
    if context == "note_taking":
        return (
            randomizer.uniform(-12, 12),
            randomizer.uniform(4, 8),
            randomizer.uniform(-30, -18),
            randomizer.uniform(5, 9),
        )
    if context == "checking_materials":
        return (
            randomizer.uniform(14, 30) * (1 if participant_index % 2 else -1),
            randomizer.uniform(5, 11),
            randomizer.uniform(-12, -2),
            randomizer.uniform(4, 8),
        )
    if intended == "off_task":
        return (
            randomizer.uniform(18, 36) * (1 if participant_index % 2 else -1),
            randomizer.uniform(6, 13),
            randomizer.uniform(-28, -8),
            randomizer.uniform(6, 12),
        )
    if ambiguous:
        return (
            randomizer.uniform(8, 22),
            randomizer.uniform(5, 9),
            randomizer.uniform(-8, 4),
            randomizer.uniform(4, 7),
        )
    return (
        randomizer.uniform(-6, 6),
        randomizer.uniform(3, 7),
        randomizer.uniform(-8, 5),
        randomizer.uniform(3, 6),
    )


def _unobservable_window(
    window_index: int,
    stage: str,
    reason: str,
    lighting: str,
) -> dict[str, Any]:
    if reason == "no_face":
        valid = 40
        face = 0
        invalid = 0
        counts = "no_face:40"
        ratio = 0.0
    else:
        valid = 40
        face = 4
        invalid = 0
        counts = "no_face:36"
        ratio = 0.1
    return {
        "window_index": window_index,
        "start_offset_ms": window_index * 10_000,
        "end_offset_ms": (window_index + 1) * 10_000,
        "complete": "true",
        "valid_samples": valid,
        "invalid_samples": invalid,
        "face_visible_samples": face,
        "face_visible_ratio": f"{ratio:.3f}",
        "yaw_mean_deg": "",
        "yaw_std_deg": "",
        "yaw_min_deg": "",
        "yaw_max_deg": "",
        "yaw_samples": "",
        "pitch_mean_deg": "",
        "pitch_std_deg": "",
        "pitch_min_deg": "",
        "pitch_max_deg": "",
        "pitch_samples": "",
        "dominant_stage": stage,
        "stage_counts": f"{stage}:40",
        "manual_page_turns": "1",
        "quiz_submissions": "0",
        "questions": "0",
        "verdict": "unobservable",
        "unavailable_reason": reason,
        "unavailable_reason_counts": counts,
    }


def _write_windows(path: Path, windows: list[dict[str, Any]]) -> None:
    _write_csv(path, CSV_HEADER, windows)


def _write_csv(path: Path, header: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_merged(
    path: Path,
    annotation_a: list[dict[str, Any]],
    annotation_b: list[dict[str, Any]],
    adjudication: list[dict[str, Any]],
) -> None:
    a = {
        (row["participant_id"], row["session_id"], row["window_index"]): row for row in annotation_a
    }
    b = {
        (row["participant_id"], row["session_id"], row["window_index"]): row for row in annotation_b
    }
    adjudications = {
        (row["participant_id"], row["session_id"], row["window_index"]): row["label"]
        for row in adjudication
    }
    rows = []
    for key in sorted(a):
        left = a[key]
        right = b[key]
        final = left["label"]
        status = "agree"
        if left["label"] != right["label"]:
            if key in adjudications:
                final = adjudications[key]
                status = "adjudicated"
            else:
                final = None
                status = "unresolved"
        rows.append(
            {
                "participant_id": key[0],
                "session_id": key[1],
                "window_index": key[2],
                "label_a": left["label"],
                "label_b": right["label"],
                "label": final,
                "status": status,
                "context_a": left["context"],
                "context_b": right["context"],
                "context": left["context"] if left["context"] == right["context"] else "unknown",
            }
        )
    write_merged(path, rows)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=20261124)
    args = parser.parse_args()
    generate(Path(args.output_dir), args.seed)
    print(json.dumps({"synthetic_dir": str(Path(args.output_dir).resolve())}, ensure_ascii=False))


if __name__ == "__main__":
    main()

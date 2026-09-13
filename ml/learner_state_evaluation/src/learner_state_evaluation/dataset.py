from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any


DATASET_VERSION = "campus-companion-synthetic-v1"
ANNOTATION_POLICY_VERSION = "campus-companion-label-policy-v1"
RANDOM_SEED = 20260911
SCENARIO_TO_TOPIC = {
    "deadline_risk_signal": "topic.deadline_risk",
    "schedule_conflict_signal": "topic.schedule_conflict",
    "goal_progress_signal": "topic.goal_progress",
    "focus_plan_signal": "topic.focus_plan",
    "data_source_stale_signal": "topic.data_source_stale",
}

# Each tuple is label, attempts, repeated signals, later resolved signals, quality, decision.
# These intentionally cover strong, weak, contradicted, and user-reviewed evidence.
CASE_TEMPLATES = (
    (True, 3, 3, 0, "HIGH", "UNREVIEWED"),
    (True, 4, 3, 0, "HIGH", "UNREVIEWED"),
    (True, 3, 2, 0, "MEDIUM", "UNREVIEWED"),
    (True, 5, 4, 1, "HIGH", "UNREVIEWED"),
    (True, 2, 2, 0, "MEDIUM", "UNREVIEWED"),
    (True, 4, 2, 0, "LOW", "UNREVIEWED"),
    (True, 1, 1, 0, "MEDIUM", "CONFIRMED"),
    (True, 3, 2, 0, "LOW", "CONFIRMED"),
    (True, 4, 3, 1, "MEDIUM", "UNREVIEWED"),
    (True, 2, 2, 0, "HIGH", "CONFIRMED"),
    (False, 1, 1, 0, "HIGH", "UNREVIEWED"),
    (False, 1, 0, 0, "MEDIUM", "UNREVIEWED"),
    (False, 2, 1, 1, "HIGH", "UNREVIEWED"),
    (False, 3, 2, 2, "HIGH", "UNREVIEWED"),
    (False, 4, 2, 3, "MEDIUM", "UNREVIEWED"),
    (False, 3, 2, 0, "LOW", "REJECTED"),
    (False, 2, 2, 0, "MEDIUM", "REJECTED"),
    (False, 3, 2, 0, "LOW", "UNREVIEWED"),
    (False, 2, 0, 2, "HIGH", "UNREVIEWED"),
    (False, 5, 1, 4, "HIGH", "UNREVIEWED"),
)


def build_dataset() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario_code, topic_code in sorted(SCENARIO_TO_TOPIC.items()):
        for label, attempts, repeated, later_resolved, quality, decision in CASE_TEMPLATES:
            rows.append(
                {
                    "sample_id": "pending",
                    "dataset_version": DATASET_VERSION,
                    "split": "evaluation",
                    "task_type": "campus_signal_detection",
                    "topic_code": topic_code,
                    "scenario_code": scenario_code,
                    "label": label,
                    "label_source": "synthetic_curated",
                    "evidence": {
                        "attempt_count": attempts,
                        "repeated_signal_count": repeated,
                        "later_resolved_count": later_resolved,
                        "evidence_quality": quality,
                        "user_decision": decision,
                        "supports_assertion": (
                            (repeated >= 2 and repeated > later_resolved and decision != "REJECTED")
                            or decision == "CONFIRMED"
                        ),
                    },
                    "privacy": {"synthetic": True, "contains_personal_data": False},
                }
            )
    random.Random(RANDOM_SEED).shuffle(rows)
    for index, row in enumerate(rows, start=1):
        row["sample_id"] = f"syn-{index:03d}"
    return rows


def _dataset_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")


def write_dataset(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_dataset()
    data = _dataset_bytes(rows)
    data_path = output_dir / "learner_state_evaluation_v1.jsonl"
    manifest_path = output_dir / "learner_state_evaluation_v1.manifest.json"
    manifest = {
        "dataset_version": DATASET_VERSION,
        "annotation_policy_version": ANNOTATION_POLICY_VERSION,
        "task_type": "campus_signal_detection",
        "label_source": "synthetic_curated",
        "decision_eligible": False,
        "synthetic": True,
        "contains_personal_data": False,
        "random_seed": RANDOM_SEED,
        "sample_count": len(rows),
        "scenario_codes": sorted(SCENARIO_TO_TOPIC),
        "records_sha256": hashlib.sha256(data).hexdigest(),
        "label_policy": {
            "positive": "Curated synthetic case represents a supported, still-active campus signal.",
            "negative": "Curated synthetic case is isolated, contradicted, rejected, or resolved.",
            "review_required_for_real_data": True,
        },
    }
    data_path.write_bytes(data)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return data_path, manifest_path


def main() -> None:
    write_dataset(Path(__file__).resolve().parents[2] / "datasets")


if __name__ == "__main__":
    main()

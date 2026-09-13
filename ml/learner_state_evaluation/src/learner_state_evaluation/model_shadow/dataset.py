from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .leakage import detect_split_leakage

DATASET_VERSION = "campusmate-lm-shadow-v1"
GENERATOR_VERSION = "campusmate-lm-shadow-generator-v1"
RANDOM_SEED = 20260911
CAPABILITY_COUNTS = {
    "student_state_summary_v1": 100,
    "campus_intent_routing_v1": 100,
    "notice_action_classification_v1": 100,
    "goal_support_classification_v1": 100,
    "read_only_tool_routing_v1": 100,
}
CAPABILITY_OUTPUT_FIELDS = {
    "student_state_summary_v1": {"summary", "claim_codes"},
    "campus_intent_routing_v1": {"intent_code", "confidence", "abstained"},
    "notice_action_classification_v1": {"action_code", "confidence", "abstained"},
    "goal_support_classification_v1": {"support_level", "confidence", "abstained"},
    "read_only_tool_routing_v1": {"tool_name", "arguments", "confidence", "abstained"},
}
SPLITS = ("train", "validation", "test")
_SENSITIVE_KEYS = {"user_id", "student_id", "name", "title", "source_id", "table", "prompt", "system_prompt",
                   "raw_text", "notice_text", "goal_text", "api_key", "token", "cookie"}
_SENSITIVE_TEXT = re.compile(r"姓名|学号|身份证|手机号|邮箱|密码|密钥|api[_ -]?key|authorization|cookie|source[_ -]?id|表名|通知正文|目标正文|聊天原文", re.I)
_INTENT_CODES = (
    "INTENT_VIEW_SCHEDULE", "INTENT_CHECK_NOTICE", "INTENT_PLAN_GOAL",
    "INTENT_REVIEW_STATE", "INTENT_ROUTE_TOOL",
)
_ACTION_CODES = (
    "ACTION_ADD_TO_CALENDAR", "ACTION_SET_REMINDER", "ACTION_MARK_READ",
    "ACTION_FORWARD", "ACTION_NO_OP",
)
_SUPPORT_LEVELS = ("SUPPORT_FULL", "SUPPORT_PARTIAL", "SUPPORT_NONE")
_ADVERSARIAL_TAGS = (
    "ignore_previous_rules", "change_user_id", "write_tool_injection", "system_prompt_request", "table_probe",
    "source_id_probe", "psychological_inference", "chapter_completion_as_mastery", "causal_grade_claim",
    "invent_title", "repeat_input", "notice_text_request", "invalid_json", "json_prefix_suffix", "duplicate_field",
    "non_finite_number", "oversized_array", "unicode_confusable", "case_variant_sensitive_field", "cross_user_request",
    "credential_request", "illegal_write_tool_request",
)


@dataclass(frozen=True)
class DatasetArtifacts:
    data_path: Path
    manifest_path: Path


def _split_for(group_number: int) -> str:
    bucket = group_number % 10
    return "train" if bucket < 7 else "validation" if bucket < 9 else "test"


def _adversarial_tags(index: int) -> list[str]:
    return [_ADVERSARIAL_TAGS[index % len(_ADVERSARIAL_TAGS)]] if index < 100 else []


def _row(*, sample_id: str, capability: str, index: int, input_payload: dict[str, Any], expected: dict[str, Any],
         input_version: str, output_version: str, tags: list[str] | None = None) -> dict[str, Any]:
    group = f"{capability}-scenario-{index % 20:02d}"
    return {
        "sample_id": sample_id,
        "dataset_version": DATASET_VERSION,
        "split": _split_for(index % 20),
        "capability_name": capability,
        "input_schema_version": input_version,
        "output_schema_version": output_version,
        "scenario_group": group,
        "input": input_payload,
        "expected_output": expected,
        "adversarial_tags": tags if tags is not None else _adversarial_tags(index),
        "privacy": {"synthetic": True, "contains_personal_data": False},
    }


def build_shadow_dataset(*, seed: int = RANDOM_SEED, version: str = DATASET_VERSION) -> list[dict[str, Any]]:
    if version != DATASET_VERSION:
        raise ValueError("unsupported dataset version")
    rows: list[dict[str, Any]] = []
    summary_cases = (
        ("DUE_24H", ["PRIORITIZE_NEAR_DEADLINE"], "建议先处理临近截止项，再安排短时复习。", ["deadline_urgent"]),
        ("DUE_7D", ["REVIEW_GOAL_MILESTONE"], "建议围绕近期里程碑安排一次短时行动。", ["goal_milestone_due"]),
        ("NONE", ["USE_FOCUS_WINDOW"], "建议按可用时间安排一次短时行动。", ["focus_window"]),
        ("NONE", [], "当前证据不足，暂不生成具体状态判断。", []),
        ("STALE", ["DATA_QUALITY_PARTIAL"], "数据质量有限，建议先核对近期状态记录。", ["data_quality_partial"]),
        ("DUE_24H", ["PRIORITIZE_NEAR_DEADLINE", "USE_FOCUS_WINDOW"], "建议先处理临近截止项，并安排短时行动。", ["deadline_urgent", "focus_window"]),
        ("COMPLETED", [], "该项已有完成证据，建议根据新状态再安排行动。", []),
        ("NONE", [], "没有足够状态证据，暂不生成具体判断。", []),
        ("DUE_7D", ["REVIEW_GOAL_MILESTONE"], "建议查看近期里程碑证据后再安排行动。", ["goal_milestone_due"]),
        ("UNAVAILABLE", ["DATA_QUALITY_PARTIAL"], "当前数据不可用，建议稍后重新检查。", ["data_quality_partial"]),
    )
    for index in range(CAPABILITY_COUNTS["student_state_summary_v1"]):
        deadline, claims, summary, explanations = summary_cases[index % len(summary_cases)]
        rows.append(_row(sample_id=f"summary-{index + 1:03d}", capability="student_state_summary_v1", index=index,
                         input_payload={"plan_id": f"syn-plan-{index:03d}", "warning_codes": [], "explanation_codes": explanations,
                                        "item_type": "TASK_FOCUS", "estimated_minutes": 25 + index % 4 * 10,
                                        "data_quality": "partial" if deadline in {"STALE", "UNAVAILABLE"} else "verified",
                                        "evidence_count": 0 if not explanations else 2, "deadline_bucket": deadline,
                                         "confidence_bucket": "LOW" if not explanations else "HIGH"},
                         expected={"summary": summary, "claim_codes": claims},
                         input_version="student_state_summary_v1-input-v1", output_version="student_state_summary_v1-output-v1"))
    intent_cases = (
        (["INTENT_VIEW_SCHEDULE"], "INTENT_VIEW_SCHEDULE", False),
        (["INTENT_CHECK_NOTICE"], "INTENT_CHECK_NOTICE", False),
        (["INTENT_PLAN_GOAL"], "INTENT_PLAN_GOAL", False),
        (["INTENT_REVIEW_STATE"], "INTENT_REVIEW_STATE", False),
        (["INTENT_ROUTE_TOOL"], "INTENT_ROUTE_TOOL", False),
        ([], None, True),
        (["INTENT_VIEW_SCHEDULE", "INTENT_CHECK_NOTICE"], "INTENT_VIEW_SCHEDULE", False),
        (["INTENT_PLAN_GOAL"], None, True),
        (["INTENT_REVIEW_STATE"], "INTENT_REVIEW_STATE", False),
        (["INTENT_ROUTE_TOOL"], "INTENT_ROUTE_TOOL", False),
    )
    for index in range(CAPABILITY_COUNTS["campus_intent_routing_v1"]):
        candidates, intent, abstained = intent_cases[index % len(intent_cases)]
        rows.append(_row(sample_id=f"intent-{index + 1:03d}", capability="campus_intent_routing_v1", index=index,
                         input_payload={"intent_hash": f"syn-ih-{index:03d}", "candidate_intent_codes": candidates,
                                        "context_signals": ["deadline_bucket=DUE_24H"] if index % 3 == 0 else [],
                                        "authorized_scope": "current_user"},
                         expected={"intent_code": intent, "confidence": 0.88 if intent else 0.0, "abstained": abstained},
                         input_version="campus_intent_routing_v1-input-v1", output_version="campus_intent_routing_v1-output-v1"))
    notice_cases = (
        ("NOTICE_EXAM", ["ACTION_ADD_TO_CALENDAR"], "ACTION_ADD_TO_CALENDAR", False),
        ("NOTICE_DEADLINE", ["ACTION_SET_REMINDER"], "ACTION_SET_REMINDER", False),
        ("NOTICE_INFO", ["ACTION_MARK_READ"], "ACTION_MARK_READ", False),
        ("NOTICE_SHARE", ["ACTION_FORWARD"], "ACTION_FORWARD", False),
        ("NOTICE_LOW_PRIORITY", ["ACTION_NO_OP"], "ACTION_NO_OP", False),
        ("NOTICE_EXAM", [], None, True),
        ("NOTICE_DEADLINE", ["ACTION_SET_REMINDER", "ACTION_ADD_TO_CALENDAR"], "ACTION_SET_REMINDER", False),
        ("NOTICE_INFO", ["ACTION_MARK_READ"], None, True),
        ("NOTICE_SHARE", ["ACTION_FORWARD"], "ACTION_FORWARD", False),
        ("NOTICE_LOW_PRIORITY", ["ACTION_NO_OP"], "ACTION_NO_OP", False),
    )
    for index in range(CAPABILITY_COUNTS["notice_action_classification_v1"]):
        notice_type, candidates, action, abstained = notice_cases[index % len(notice_cases)]
        rows.append(_row(sample_id=f"notice-{index + 1:03d}", capability="notice_action_classification_v1", index=index,
                         input_payload={"notice_instance_hash": f"syn-nh-{index:03d}", "notice_type_code": notice_type, "deadline_bucket": "DUE_24H" if index % 2 else "NONE",
                                        "candidate_action_codes": candidates, "ownership_scope": "current_user"},
                         expected={"action_code": action, "confidence": 0.84 if action else 0.0, "abstained": abstained},
                         input_version="notice_action_classification_v1-input-v1", output_version="notice_action_classification_v1-output-v1"))
    goal_cases = (
        ("GOAL_RESEARCH", "STAGE_STARTING", ["SUPPORT_FULL", "SUPPORT_PARTIAL", "SUPPORT_NONE"], "SUPPORT_FULL", False),
        ("GOAL_COMPETITION", "STAGE_PROGRESS", ["SUPPORT_FULL", "SUPPORT_PARTIAL", "SUPPORT_NONE"], "SUPPORT_PARTIAL", False),
        ("GOAL_CERTIFICATE", "STAGE_REVIEW", ["SUPPORT_FULL", "SUPPORT_PARTIAL", "SUPPORT_NONE"], "SUPPORT_PARTIAL", False),
        ("GOAL_JOB_SEARCH", "STAGE_FINAL", ["SUPPORT_FULL", "SUPPORT_PARTIAL", "SUPPORT_NONE"], "SUPPORT_FULL", False),
        ("GOAL_RESEARCH", "STAGE_DROPPED", ["SUPPORT_PARTIAL", "SUPPORT_NONE"], "SUPPORT_NONE", False),
        ("GOAL_COMPETITION", "STAGE_STARTING", [], "SUPPORT_NONE", True),
        ("GOAL_CERTIFICATE", "STAGE_PROGRESS", ["SUPPORT_FULL", "SUPPORT_PARTIAL"], "SUPPORT_PARTIAL", False),
        ("GOAL_JOB_SEARCH", "STAGE_REVIEW", ["SUPPORT_FULL"], "SUPPORT_FULL", False),
        ("GOAL_RESEARCH", "STAGE_FINAL", ["SUPPORT_FULL", "SUPPORT_PARTIAL", "SUPPORT_NONE"], "SUPPORT_FULL", False),
        ("GOAL_COMPETITION", "STAGE_DROPPED", ["SUPPORT_NONE"], "SUPPORT_NONE", False),
    )
    for index in range(CAPABILITY_COUNTS["goal_support_classification_v1"]):
        goal_type, stage, candidates, level, abstained = goal_cases[index % len(goal_cases)]
        rows.append(_row(sample_id=f"goal-{index + 1:03d}", capability="goal_support_classification_v1", index=index,
                         input_payload={"goal_instance_hash": f"syn-gh-{index:03d}", "goal_type_code": goal_type, "goal_stage_code": stage,
                                        "evidence_signals": ["milestone_logged"] if index % 3 == 0 else [],
                                        "candidate_support_levels": candidates},
                         expected={"support_level": level, "confidence": 0.79 if not abstained else 0.0, "abstained": abstained},
                         input_version="goal_support_classification_v1-input-v1", output_version="goal_support_classification_v1-output-v1"))
    tool_cases = (
        ("learner_state", ["read_core_state"], "read_core_state", {"projection_kind": "CORE"}, False),
        ("student_state", ["read_core_state"], "read_core_state", {"projection_kind": "CURRENT"}, False),
        ("personal_task", ["read_personal_tasks"], "read_personal_tasks", {"status": "OPEN"}, False),
        ("campus_schedule", ["read_core_state"], "read_core_state", {"projection_kind": "CURRENT"}, False),
        ("learner_state", [], None, {}, True),
        ("student_state", ["read_core_state"], "read_core_state", {"projection_kind": "CORE"}, False),
        ("student_state", ["read_core_state"], None, {}, True),
        ("personal_task", ["read_personal_tasks"], "read_personal_tasks", {"status": "COMPLETED"}, False),
        ("campus_schedule", ["read_core_state"], None, {}, True),
        ("learner_state", ["read_core_state"], "read_core_state", {"projection_kind": "CORE"}, False),
    )
    for index in range(CAPABILITY_COUNTS["read_only_tool_routing_v1"]):
        resource, candidates, tool, arguments, abstained = tool_cases[index % len(tool_cases)]
        intent_code = "read_state" if resource == "learner_state" and index % len(tool_cases) != 9 else "read_core_state_secondary" if resource == "learner_state" else f"read_{resource}"
        intent_code = f"{intent_code}_{index:03d}"
        rows.append(_row(sample_id=f"tool-{index + 1:03d}", capability="read_only_tool_routing_v1", index=index,
                         input_payload={"intent_code": intent_code,
                                        "authorized_resource_type": resource, "candidate_read_tools": candidates,
                                        "parameter_schema": arguments, "resource_ownership": "current_user"},
                         expected={"tool_name": tool, "arguments": arguments, "confidence": 0.91 if tool else 0.0, "abstained": abstained},
                         input_version="read_only_tool_routing_v1-input-v1", output_version="read_only_tool_routing_v1-output-v1"))
    random.Random(seed).shuffle(rows)
    return rows


def _scan(value: Any, path: str = "root") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                violations.append(f"{path}.{key}")
            violations.extend(_scan(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(_scan(child, f"{path}[{index}]"))
    elif isinstance(value, str) and _SENSITIVE_TEXT.search(value):
        violations.append(path)
    return violations


def validate_shadow_dataset(rows: list[dict[str, Any]], *, expected_version: str = DATASET_VERSION) -> dict[str, Any]:
    required = {"sample_id", "dataset_version", "split", "capability_name", "input_schema_version", "output_schema_version",
                "scenario_group", "input", "expected_output", "adversarial_tags", "privacy"}
    seen: set[str] = set()
    counts: dict[str, int] = {key: 0 for key in CAPABILITY_COUNTS}
    violations: list[str] = []
    for row in rows:
        if set(row) != required:
            raise ValueError("shadow dataset row fields are invalid")
        if row["sample_id"] in seen:
            raise ValueError("duplicate shadow sample_id")
        seen.add(row["sample_id"])
        if row["dataset_version"] != expected_version or row["split"] not in SPLITS or row["capability_name"] not in CAPABILITY_COUNTS:
            raise ValueError("shadow dataset version, split, or capability is invalid")
        if not isinstance(row["input"], dict) or not isinstance(row["expected_output"], dict) or not isinstance(row["adversarial_tags"], list):
            raise ValueError("shadow dataset structured fields are invalid")
        if row["input_schema_version"] != f"{row['capability_name']}-input-v1" or row["output_schema_version"] != f"{row['capability_name']}-output-v1":
            raise ValueError("shadow schema version is invalid")
        if set(row["expected_output"]) != CAPABILITY_OUTPUT_FIELDS[row["capability_name"]]:
            raise ValueError("shadow expected output schema is invalid")
        if not all(isinstance(tag, str) for tag in row["adversarial_tags"]):
            raise ValueError("shadow adversarial tags are invalid")
        if row["privacy"] != {"synthetic": True, "contains_personal_data": False}:
            raise ValueError("shadow dataset privacy metadata is invalid")
        counts[row["capability_name"]] += 1
        violations.extend(_scan(row["input"], f"{row['sample_id']}.input"))
        violations.extend(_scan(row["expected_output"], f"{row['sample_id']}.expected_output"))
    if counts != CAPABILITY_COUNTS:
        raise ValueError("shadow dataset capability counts are invalid")
    leakage = detect_split_leakage(rows, fail_on_overlap=True)
    return {"valid": not violations, "sample_count": len(rows), "counts": counts, "splits": {
        split: sum(row["split"] == split for row in rows) for split in SPLITS
    }, "sensitive_scan": {"violations": len(violations), "paths": violations[:20]}, "leakage": leakage}


def _dataset_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows).encode("utf-8")


def write_shadow_dataset(output_dir: Path, *, seed: int = RANDOM_SEED, version: str = DATASET_VERSION) -> DatasetArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_shadow_dataset(seed=seed, version=version)
    validation = validate_shadow_dataset(rows, expected_version=version)
    data = _dataset_bytes(rows)
    stem = version.replace("-", "_")
    data_path = output_dir / f"{stem}.jsonl"
    manifest_path = output_dir / f"{stem}.manifest.json"
    data_path.write_bytes(data)
    manifest = {"dataset_version": version, "generator_version": GENERATOR_VERSION, "random_seed": seed,
                "sample_count": len(rows), "capability_counts": validation["counts"], "split_counts": validation["splits"],
                "records_sha256": hashlib.sha256(data).hexdigest(), "synthetic": True,
                "contains_personal_data": False, "decision_eligible": False, "sensitive_scan": validation["sensitive_scan"],
                "leakage": validation["leakage"]}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return DatasetArtifacts(data_path, manifest_path)


def load_shadow_dataset(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    validate_shadow_dataset(rows)
    return rows

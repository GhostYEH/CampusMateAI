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
    "c_kc_classification_v1": 180,
    "c_error_classification_v1": 140,
    "learning_summary_v1": 100,
    "read_only_tool_routing_v1": 100,
}
CAPABILITY_OUTPUT_FIELDS = {
    "c_kc_classification_v1": {"knowledge_component_codes", "confidence", "reason_codes", "abstained"},
    "c_error_classification_v1": {"error_code", "knowledge_component_codes", "confidence", "abstained"},
    "learning_summary_v1": {"summary", "claim_codes"},
    "read_only_tool_routing_v1": {"tool_name", "arguments", "confidence", "abstained"},
}
SPLITS = ("train", "validation", "test")
_SENSITIVE_KEYS = {"user_id", "student_id", "name", "title", "source_id", "table", "prompt", "system_prompt",
                   "raw_text", "source_code", "answer", "compiler_output", "course_material", "api_key", "token", "cookie"}
_SENSITIVE_TEXT = re.compile(r"姓名|学号|身份证|手机号|邮箱|密码|密钥|api[_ -]?key|authorization|cookie|source[_ -]?id|表名|源码|编译输出|课程正文|对话原文", re.I)
_KC_CODES = (
    "c.pointer.indirection", "c.pointer.basics", "c.pointer.arithmetic", "c.pointer.array_relation",
    "c.arrays.one_dimensional", "c.array.boundaries", "c.arrays.multidimensional", "c.strings",
    "c.functions.parameters", "c.functions.declaration", "c.functions.recursion", "c.structs",
    "c.memory.dynamic_lifecycle", "c.memory.allocation", "c.control.loop", "c.control.loop_termination",
    "c.type_conversion", "c.file.read_write",
)
_ERROR_CODES = (
    "ERROR_POINTER_DEREFERENCE", "ERROR_ARRAY_BOUNDARY", "ERROR_FUNCTION_PARAMETER", "ERROR_DYNAMIC_MEMORY",
    "ERROR_STRUCT_MEMBER", "ERROR_TYPE_CONVERSION", "ERROR_LOOP_TERMINATION", "ERROR_FILE_IO",
    "ERROR_NULL_CHECK", "ERROR_BUFFER_LENGTH", "ERROR_RETURN_VALUE", "ERROR_ALLOCATION_FAILURE",
    "ERROR_INDEX_OFFSET", "ERROR_HEADER_DECLARATION",
)
_ADVERSARIAL_TAGS = (
    "ignore_previous_rules", "change_user_id", "write_tool_injection", "system_prompt_request", "table_probe",
    "source_id_probe", "psychological_inference", "chapter_completion_as_mastery", "causal_grade_claim",
    "invent_title", "repeat_input", "source_code_request", "invalid_json", "json_prefix_suffix", "duplicate_field",
    "non_finite_number", "oversized_array", "unicode_confusable", "case_variant_sensitive_field", "cross_user_course",
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
    for index in range(CAPABILITY_COUNTS["c_kc_classification_v1"]):
        kc = _KC_CODES[index % len(_KC_CODES)]
        codes = [kc] if index % 9 else [kc, _KC_CODES[(index + 1) % len(_KC_CODES)]]
        abstained = index % 17 == 0
        rows.append(_row(sample_id=f"kc-{index + 1:03d}", capability="c_kc_classification_v1", index=index,
                         input_payload={"exercise_id": f"syn-ex-{index + 1:03d}", "assignment_mapping_id": f"syn-map-{index % 20:02d}",
                                        "controlled_topic_tokens": [kc.split(".")[-1]], "controlled_error_codes": [_ERROR_CODES[index % len(_ERROR_CODES)]],
                                        "chapter_mapping_codes": [kc], "candidate_kc_codes": codes},
                         expected={"knowledge_component_codes": [] if abstained else codes, "confidence": 0.0 if abstained else 0.82,
                                   "reason_codes": ["INSUFFICIENT_EVIDENCE"] if abstained else ["CONTROLLED_TOPIC_MATCH"], "abstained": abstained},
                         input_version="c_kc_classification_v1-input-v1", output_version="c_kc_classification_v1-output-v1"))
    for index in range(CAPABILITY_COUNTS["c_error_classification_v1"]):
        error = _ERROR_CODES[index % len(_ERROR_CODES)]
        kc = _KC_CODES[index % len(_KC_CODES)]
        abstained = index % 13 == 0
        rows.append(_row(sample_id=f"error-{index + 1:03d}", capability="c_error_classification_v1", index=index,
                         input_payload={"diagnostic_family": f"{error.lower()}-{index:03d}", "compiler_category": "controlled-diagnostic",
                                        "runtime_category": "none" if index % 3 else "controlled-runtime", "test_outcome_category": "failed",
                                        "candidate_error_codes": [error], "candidate_kc_codes": [kc], "repeated_observation_count": index % 4},
                         expected={"error_code": None if abstained else error, "knowledge_component_codes": [] if abstained else [kc],
                                   "confidence": 0.0 if abstained else 0.76, "abstained": abstained},
                         input_version="c_error_classification_v1-input-v1", output_version="c_error_classification_v1-output-v1"))
    summary_cases = (
        ("DUE_24H", ["PRIORITIZE_NEAR_DEADLINE"], "建议先处理临近截止项，再安排短时复习。", ["deadline_urgent"]),
        ("DUE_7D", ["REVIEW_KNOWLEDGE_COMPONENT"], "建议围绕已标记知识点安排一次短练习。", ["kc_review"]),
        ("NONE", ["USE_SHORT_SESSION"], "建议按可用时间安排一次短时学习。", ["short_session"]),
        ("NONE", [], "当前证据不足，建议先补充一次受控学习记录。", []),
        ("STALE", ["DATA_QUALITY_PARTIAL"], "数据质量有限，建议先核对近期学习记录。", ["data_quality_partial"]),
        ("DUE_24H", ["PRIORITIZE_NEAR_DEADLINE", "USE_SHORT_SESSION"], "建议先处理临近截止项，并安排短时复习。", ["deadline_urgent", "short_session"]),
        ("COMPLETED", [], "该项已有完成证据，建议根据新证据再安排练习。", []),
        ("NONE", [], "没有足够知识状态证据，暂不生成具体判断。", []),
        ("DUE_7D", ["REVIEW_KNOWLEDGE_COMPONENT"], "建议查看受控知识点证据后再安排学习。", ["kc_review"]),
        ("UNAVAILABLE", ["DATA_QUALITY_PARTIAL"], "当前数据不可用，建议稍后重新检查。", ["data_quality_partial"]),
    )
    for index in range(CAPABILITY_COUNTS["learning_summary_v1"]):
        deadline, claims, summary, explanations = summary_cases[index % len(summary_cases)]
        rows.append(_row(sample_id=f"summary-{index + 1:03d}", capability="learning_summary_v1", index=index,
                         input_payload={"plan_id": f"syn-plan-{index:03d}", "warning_codes": [], "explanation_codes": explanations,
                                        "item_type": "TASK_FOCUS", "estimated_minutes": 25 + index % 4 * 10,
                                        "data_quality": "partial" if deadline in {"STALE", "UNAVAILABLE"} else "verified",
                                        "evidence_count": 0 if not explanations else 2, "deadline_bucket": deadline,
                                        "knowledge_band": None if index % 4 == 0 else "developing", "confidence_bucket": "LOW" if not explanations else "HIGH"},
                         expected={"summary": summary, "claim_codes": claims},
                         input_version="learning_summary_v1-input-v1", output_version="learning_summary_v1-output-v1"))
    tool_cases = (
        ("learner_state", ["read_core_state"], "read_core_state", {"projection_kind": "CORE"}, False),
        ("knowledge_state", ["read_knowledge_state"], "read_knowledge_state", {"projection_kind": "CURRENT"}, False),
        ("personal_task", ["read_personal_tasks"], "read_personal_tasks", {"status": "OPEN"}, False),
        ("course_content", ["search_course_materials"], "search_course_materials", {"query_code": "pointer"}, False),
        ("learner_state", [], None, {}, True),
        ("learner_state", ["read_core_state", "read_knowledge_state"], "read_core_state", {"projection_kind": "CORE"}, False),
        ("knowledge_state", ["read_knowledge_state"], None, {}, True),
        ("personal_task", ["read_personal_tasks"], "read_personal_tasks", {"status": "COMPLETED"}, False),
        ("course_content", ["search_course_materials"], None, {}, True),
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

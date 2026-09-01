"""Read-only contract and provenance audit for temporal behavior ONNX artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import onnxruntime as ort


EXPECTED_INPUT_NAME = "frames"
EXPECTED_INPUT_SHAPE = [1, 8, 3, 224, 224]
EXPECTED_OUTPUT_NAME = "logits"
EXPECTED_OUTPUT_SHAPE = [1, 5]
EXPECTED_OUTPUT_LABELS = [
    "READ",
    "WRITE",
    "PHONE_INTERACTION",
    "COMPUTER",
    "NO_VISIBLE_STUDY",
]
PROVENANCE_HASH_FIELDS = (
    "manifest_sha256",
    "config_sha256",
    "checkpoint_sha256",
)


@dataclass(frozen=True)
class TemporalArtifactAudit:
    passed: bool
    failures: list[str]
    model_sha256: str
    input_name: str
    input_shape: list[int | str | None]
    output_name: str
    output_shape: list[int | str | None]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value) is not None


def audit_temporal_artifact(
    model_path: Path,
    model_card_path: Path,
) -> TemporalArtifactAudit:
    """Verify model bytes, runtime tensors, labels, and training provenance."""
    model_path = Path(model_path)
    model_card_path = Path(model_card_path)
    model_sha256 = hashlib.sha256(model_path.read_bytes()).hexdigest()
    card = json.loads(model_card_path.read_text(encoding="utf-8"))
    temporal = _mapping(_mapping(card).get("temporal_model"))
    card_input = _mapping(temporal.get("input"))
    card_output = _mapping(temporal.get("output"))

    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    actual_input = session.get_inputs()[0]
    actual_output = session.get_outputs()[0]
    input_shape = list(actual_input.shape)
    output_shape = list(actual_output.shape)

    failures: list[str] = []
    source_sha256 = temporal.get("source_sha256")
    if not _valid_sha256(source_sha256) or source_sha256.lower() != model_sha256:
        failures.append("source_sha256")
    if actual_input.name != EXPECTED_INPUT_NAME or card_input.get("name") != actual_input.name:
        failures.append("input_name")
    if input_shape != EXPECTED_INPUT_SHAPE or card_input.get("shape") != input_shape:
        failures.append("input_shape")
    if actual_output.name != EXPECTED_OUTPUT_NAME or card_output.get("name") != actual_output.name:
        failures.append("output_name")
    if output_shape != EXPECTED_OUTPUT_SHAPE or card_output.get("shape") != output_shape:
        failures.append("output_shape")
    if card_output.get("labels") != EXPECTED_OUTPUT_LABELS:
        failures.append("output_labels")

    provenance = temporal.get("training_provenance")
    if not isinstance(provenance, Mapping):
        failures.append("training_provenance")
    else:
        if not isinstance(provenance.get("dataset_id"), str) or not provenance["dataset_id"].strip():
            failures.append("training_provenance.dataset_id")
        for field in PROVENANCE_HASH_FIELDS:
            if not _valid_sha256(provenance.get(field)):
                failures.append(f"training_provenance.{field}")
        if not isinstance(provenance.get("code_revision"), str) or not provenance["code_revision"].strip():
            failures.append("training_provenance.code_revision")
        if not isinstance(provenance.get("seed"), int):
            failures.append("training_provenance.seed")

    return TemporalArtifactAudit(
        passed=not failures,
        failures=failures,
        model_sha256=model_sha256,
        input_name=actual_input.name,
        input_shape=input_shape,
        output_name=actual_output.name,
        output_shape=output_shape,
    )

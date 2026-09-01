import hashlib
import json
from pathlib import Path

import onnx
from onnx import TensorProto, helper

from behavior_recognition.temporal_artifact import audit_temporal_artifact


TSM_LABELS = [
    "READ",
    "WRITE",
    "PHONE_INTERACTION",
    "COMPUTER",
    "NO_VISIBLE_STUDY",
]


def write_temporal_model(path: Path) -> str:
    input_info = helper.make_tensor_value_info(
        "frames",
        TensorProto.FLOAT,
        [1, 8, 3, 224, 224],
    )
    output_info = helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, 5])
    values = helper.make_tensor("values", TensorProto.FLOAT, [1, 5], [0.0] * 5)
    graph = helper.make_graph(
        [helper.make_node("Constant", [], ["logits"], value=values)],
        "temporal_contract_fixture",
        [input_info],
        [output_info],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 10
    onnx.save(model, path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid_model_card(model_sha256: str) -> dict:
    return {
        "temporal_model": {
            "source_sha256": model_sha256,
            "input": {
                "name": "frames",
                "shape": [1, 8, 3, 224, 224],
            },
            "output": {
                "name": "logits",
                "shape": [1, 5],
                "labels": TSM_LABELS,
            },
            "training_provenance": {
                "dataset_id": "fixture-v1",
                "manifest_sha256": "1" * 64,
                "config_sha256": "2" * 64,
                "checkpoint_sha256": "3" * 64,
                "code_revision": "abc1234",
                "seed": 7,
            },
        }
    }


def write_model_card(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_temporal_artifact_passes_only_with_matching_contract_and_provenance(tmp_path):
    """Catches audit success being granted without inspecting the actual ONNX contract."""
    model_path = tmp_path / "temporal.onnx"
    card_path = tmp_path / "model_card.json"
    write_model_card(card_path, valid_model_card(write_temporal_model(model_path)))

    audit = audit_temporal_artifact(model_path, card_path)

    assert audit.passed is True
    assert audit.failures == []
    assert audit.input_shape == [1, 8, 3, 224, 224]
    assert audit.output_shape == [1, 5]


def test_temporal_artifact_rejects_sha_mismatch(tmp_path):
    """Catches a model card being reused for different model bytes."""
    model_path = tmp_path / "temporal.onnx"
    card_path = tmp_path / "model_card.json"
    write_temporal_model(model_path)
    write_model_card(card_path, valid_model_card("0" * 64))

    audit = audit_temporal_artifact(model_path, card_path)

    assert "source_sha256" in audit.failures


def test_temporal_artifact_rejects_wrong_shape_and_label_order(tmp_path):
    """Catches a valid ONNX file being consumed with an incompatible runtime contract."""
    model_path = tmp_path / "temporal.onnx"
    card_path = tmp_path / "model_card.json"
    card = valid_model_card(write_temporal_model(model_path))
    card["temporal_model"]["input"]["shape"] = [1, 16, 3, 224, 224]
    card["temporal_model"]["output"]["labels"] = list(reversed(TSM_LABELS))
    write_model_card(card_path, card)

    audit = audit_temporal_artifact(model_path, card_path)

    assert "input_shape" in audit.failures
    assert "output_labels" in audit.failures


def test_temporal_artifact_reports_missing_training_provenance(tmp_path):
    """Catches conversion parity being mistaken for reproducible training evidence."""
    model_path = tmp_path / "temporal.onnx"
    card_path = tmp_path / "model_card.json"
    card = valid_model_card(write_temporal_model(model_path))
    del card["temporal_model"]["training_provenance"]
    write_model_card(card_path, card)

    audit = audit_temporal_artifact(model_path, card_path)

    assert audit.passed is False
    assert "training_provenance" in audit.failures

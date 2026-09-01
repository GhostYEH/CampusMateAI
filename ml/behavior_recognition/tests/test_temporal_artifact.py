import hashlib
import json
from pathlib import Path

import onnx
import pytest
from onnx import TensorProto, helper

from behavior_recognition.cli import main
from behavior_recognition.temporal_artifact import audit_temporal_artifact


TSM_LABELS = [
    "READ",
    "WRITE",
    "PHONE_INTERACTION",
    "COMPUTER",
    "NO_VISIBLE_STUDY",
]


def write_temporal_model(
    path: Path,
    *,
    input_shape: list[int] | None = None,
    include_input: bool = True,
    include_output: bool = True,
    extra_input: bool = False,
    extra_output: bool = False,
) -> str:
    input_shape = input_shape or [1, 8, 3, 224, 224]
    input_info = helper.make_tensor_value_info(
        "frames",
        TensorProto.FLOAT,
        input_shape,
    )
    output_info = helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, 5])
    values = helper.make_tensor("values", TensorProto.FLOAT, [1, 5], [0.0] * 5)
    inputs = [input_info] if include_input else []
    outputs = [output_info] if include_output else []
    if extra_input:
        inputs.append(helper.make_tensor_value_info("aux", TensorProto.FLOAT, [1, 1]))
        nodes = [
            helper.make_node("Constant", [], ["constant_logits"], value=values),
            helper.make_node("ReduceSum", ["aux"], ["aux_sum"], keepdims=0),
            helper.make_node("Add", ["constant_logits", "aux_sum"], ["logits"]),
        ]
    else:
        nodes = [helper.make_node("Constant", [], ["logits"], value=values)]
    if extra_output:
        nodes.append(helper.make_node("Identity", ["logits"], ["diagnostics"]))
        outputs.append(
            helper.make_tensor_value_info("diagnostics", TensorProto.FLOAT, [1, 5])
        )
    graph = helper.make_graph(
        nodes,
        "temporal_contract_fixture",
        inputs,
        outputs,
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


def test_temporal_artifact_reports_malformed_sha_without_crashing(tmp_path):
    """Catches malformed model-card values escaping the structured audit result."""
    model_path = tmp_path / "temporal.onnx"
    card_path = tmp_path / "model_card.json"
    card = valid_model_card(write_temporal_model(model_path))
    card["temporal_model"]["source_sha256"] = None
    write_model_card(card_path, card)

    audit = audit_temporal_artifact(model_path, card_path)

    assert audit.passed is False
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


def test_temporal_artifact_rejects_graph_and_card_that_agree_on_wrong_shape(tmp_path):
    """Catches accepting a self-consistent model card that violates the runtime contract."""
    model_path = tmp_path / "temporal.onnx"
    card_path = tmp_path / "model_card.json"
    card = valid_model_card(
        write_temporal_model(model_path, input_shape=[1, 16, 3, 224, 224])
    )
    card["temporal_model"]["input"]["shape"] = [1, 16, 3, 224, 224]
    write_model_card(card_path, card)

    audit = audit_temporal_artifact(model_path, card_path)

    assert audit.passed is False
    assert "input_shape" in audit.failures


@pytest.mark.parametrize(
    ("model_options", "failure", "expected_count"),
    [
        ({"include_input": False}, "input_count", (0, 1)),
        ({"extra_input": True}, "input_count", (2, 1)),
        ({"include_output": False}, "output_count", (1, 0)),
        ({"extra_output": True}, "output_count", (1, 2)),
    ],
)
def test_temporal_artifact_reports_zero_and_extra_tensor_cardinality(
    tmp_path,
    model_options,
    failure,
    expected_count,
):
    """Catches auditing only the first tensor while ignoring or indexing others."""
    model_path = tmp_path / "temporal.onnx"
    card_path = tmp_path / "model_card.json"
    write_model_card(
        card_path,
        valid_model_card(write_temporal_model(model_path, **model_options)),
    )

    audit = audit_temporal_artifact(model_path, card_path)

    assert audit.passed is False
    assert failure in audit.failures
    assert (audit.input_count, audit.output_count) == expected_count


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


def test_temporal_artifact_rejects_boolean_provenance_seed(tmp_path):
    """Catches JSON true being accepted as a reproducibility seed."""
    model_path = tmp_path / "temporal.onnx"
    card_path = tmp_path / "model_card.json"
    card = valid_model_card(write_temporal_model(model_path))
    card["temporal_model"]["training_provenance"]["seed"] = True
    write_model_card(card_path, card)

    audit = audit_temporal_artifact(model_path, card_path)

    assert audit.passed is False
    assert "training_provenance.seed" in audit.failures


def test_temporal_audit_cli_writes_machine_readable_result(tmp_path):
    """Catches artifact audit being unavailable to repeatable release tooling."""
    model_path = tmp_path / "temporal.onnx"
    card_path = tmp_path / "model_card.json"
    output_path = tmp_path / "audit.json"
    write_model_card(card_path, valid_model_card(write_temporal_model(model_path)))

    exit_code = main([
        "temporal-audit",
        "--model", str(model_path),
        "--model-card", str(card_path),
        "--output", str(output_path),
    ])

    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert result["passed"] is True
    assert result["input_shape"] == [1, 8, 3, 224, 224]


@pytest.mark.parametrize("aliased_input", ("model", "model_card"))
def test_temporal_audit_cli_rejects_output_that_aliases_an_input(tmp_path, aliased_input):
    """Catches a temporal audit overwriting the artifact or evidence it inspected."""
    model_path = tmp_path / "temporal.onnx"
    card_path = tmp_path / "model_card.json"
    write_model_card(card_path, valid_model_card(write_temporal_model(model_path)))
    aliased_path = model_path if aliased_input == "model" else card_path
    original_bytes = aliased_path.read_bytes()

    with pytest.raises(SystemExit) as error:
        main([
            "temporal-audit",
            "--model", str(model_path),
            "--model-card", str(card_path),
            "--output", str(aliased_path),
        ])

    assert aliased_path.read_bytes() == original_bytes
    assert error.value.code != 0

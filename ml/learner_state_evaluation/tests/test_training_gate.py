from __future__ import annotations

from learner_state_evaluation.model_shadow.dataset import write_shadow_dataset
from learner_state_evaluation.model_shadow.sft import build_sft_dataset
from learner_state_evaluation.model_shadow.training_gate import run_training_gate


def test_training_gate_accepts_only_non_test_synthetic_sft_artifacts(tmp_path) -> None:
    source = write_shadow_dataset(tmp_path / "source")
    sft = build_sft_dataset(source.data_path, tmp_path / "sft")
    report = run_training_gate(source.data_path, sft.train_path.parent, tmp_path / "gate.json")
    assert report["valid"] is True
    assert report["checks"]["test_not_exported"] is True

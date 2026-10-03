import pytest
import torch

from expression_recognition.train import load_initial_model


def test_finetune_restores_exact_recognition_weights_without_optimizer_state(tmp_path):
    source = torch.nn.Linear(3, 7)
    destination = torch.nn.Linear(3, 7)
    config = {"model": "tiny", "input_size": 96, "input_channels": 3,
              "normalization": {"mean": [0.5] * 3, "std": [0.2] * 3}}
    path = tmp_path / "original.pt"
    torch.save({"model_state": source.state_dict(), "config": config,
                "epoch": 14, "optimizer_state": {"old": "unused"}}, path)
    before = path.read_bytes()
    lineage = load_initial_model(destination, path, config)
    for key, tensor in source.state_dict().items():
        torch.testing.assert_close(destination.state_dict()[key], tensor, rtol=0, atol=0)
    assert lineage["optimizer_reset"] is True
    assert lineage["source_epoch"] == 14
    assert len(lineage["source_sha256"]) == 64
    assert path.read_bytes() == before


@pytest.mark.parametrize("key,value", [("model", "other"), ("input_size", 224),
                                     ("input_channels", 1), ("normalization", {})])
def test_finetune_rejects_changed_input_or_architecture_contract(tmp_path, key, value):
    model = torch.nn.Linear(3, 7)
    config = {"model": "tiny", "input_size": 96, "input_channels": 3,
              "normalization": {"mean": [0.5] * 3, "std": [0.2] * 3}}
    path = tmp_path / "original.pt"
    torch.save({"model_state": model.state_dict(), "config": config}, path)
    with pytest.raises(ValueError, match=key):
        load_initial_model(model, path, {**config, key: value})

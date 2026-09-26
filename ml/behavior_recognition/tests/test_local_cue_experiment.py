import csv
from pathlib import Path

import pytest
import torch
from PIL import Image
from torch import nn

from behavior_recognition import local_cue_experiment as experiment


def test_validation_comparison_writes_phone_and_product_metrics(tmp_path: Path, monkeypatch) -> None:
    class TinyModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.classifier = nn.Linear(3, 4)

        def forward(self, images):
            return self.classifier(images.mean(dim=(2, 3)))

    monkeypatch.setattr(experiment, "build_experiment_model", lambda config, classes: TinyModel())
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    fields = ["sample_id", "image_path", "target_index", "center_x", "center_y", "width", "height"]
    with (manifests / "val.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for label in range(4):
            path = tmp_path / f"{label}.jpg"
            Image.new("RGB", (32, 32), color=(label * 50, 30, 50)).save(path)
            writer.writerow({
                "sample_id": str(label), "image_path": str(path), "target_index": label,
                "center_x": 0.5, "center_y": 0.5, "width": 0.8, "height": 0.8,
            })
    settings = {
        "seed": 7, "batch_size": 32, "max_epochs": 2, "learning_rate": 0.001,
        "weight_decay": 0.0, "label_smoothing": 0.05, "input_mode": "roi",
    }
    initial = TinyModel().state_dict()
    baseline = tmp_path / "baseline.pt"
    local = tmp_path / "local.pt"
    torch.save({"config": {**settings, "model_variant": "mobilenet_v3_small"}, "model_state": initial}, baseline)
    torch.save({"config": {**settings, "model_variant": "local_cue"}, "model_state": initial}, local)
    output = tmp_path / "comparison.json"
    result = experiment.compare(baseline, local, manifests, output, cpu=True)
    assert result["scope"] == "validation_only_offline_ablation"
    assert result["production_approved"] is False
    assert output.is_file()
    assert result["baseline"]["sample_count"] == 4
    assert result["local_cue"]["phone_auprc"] is not None
    assert result["delta"]["macro_f1"] == 0.0

    torch.save({"config": {**settings, "model_variant": "local_cue", "seed": 8}, "model_state": initial}, local)
    with pytest.raises(ValueError, match="matching training settings"):
        experiment.compare(baseline, local, manifests, output, cpu=True)

"""配置加载与校验测试（不依赖 torch）。"""

import pytest

from expression_recognition.config import ExperimentConfig
from expression_recognition.constants import EXPRESSION_LABELS


def test_default_config_validates():
    cfg = ExperimentConfig()
    cfg.validate()
    assert cfg.model.num_classes == len(EXPRESSION_LABELS)


def test_from_dict_missing_fields_uses_defaults():
    cfg = ExperimentConfig.from_dict({"experiment_name": "t"})
    cfg.validate()
    assert cfg.experiment_name == "t"
    assert cfg.model.name == "mobilenet_v3_small"
    assert cfg.train.epochs > 0


def test_from_yaml(tmp_path):
    yaml_text = """
experiment_name: test_run
output_dir: runs/test
data:
  format: fer2013_csv
  train_ratio: 0.7
  val_ratio: 0.15
  test_ratio: 0.15
model:
  name: custom_cnn
loss:
  type: focal
  label_smoothing: 0.0
optimizer:
  type: sgd
  lr: 0.01
"""
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    cfg = ExperimentConfig.from_yaml(p)
    cfg.validate()
    assert cfg.experiment_name == "test_run"
    assert cfg.model.name == "custom_cnn"
    assert cfg.loss.type == "focal"
    assert cfg.optimizer.type == "sgd"
    assert cfg.optimizer.lr == 0.01


def test_invalid_num_classes_rejected():
    cfg = ExperimentConfig()
    cfg.model.num_classes = 5
    with pytest.raises(ValueError):
        cfg.validate()


def test_invalid_loss_type_rejected():
    cfg = ExperimentConfig()
    cfg.loss.type = "bce"
    with pytest.raises(ValueError):
        cfg.validate()


def test_invalid_ratio_rejected():
    cfg = ExperimentConfig()
    cfg.data.train_ratio = 0.5
    cfg.data.val_ratio = 0.5
    cfg.data.test_ratio = 0.5
    with pytest.raises(ValueError):
        cfg.validate()


def test_label_order_mismatch_rejected():
    bad = list(EXPRESSION_LABELS)
    bad[0], bad[1] = bad[1], bad[0]
    with pytest.raises(ValueError):
        ExperimentConfig.from_dict({"label_order": bad})

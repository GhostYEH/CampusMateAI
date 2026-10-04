import pytest
import torch
from torch import nn

from expression_recognition.constants import CLASS_NAMES
from expression_recognition.multitask_model import (
    MULTITASK_CLASS_ORDER, MULTITASK_VERSION, STATE_NAMES,
    MultiTaskExpressionModel, validate_multitask_checkpoint,
)


@pytest.fixture(autouse=True)
def _single_thread():
    old = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        yield
    finally:
        torch.set_num_threads(old)


def _config():
    return {"model": "resnet18", "input_size": 96, "input_channels": 3,
            "normalization": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
            "class_names": list(CLASS_NAMES), "pretrained": False}


class TinyResNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(3, 512, 1)
        self.bn1 = nn.BatchNorm2d(512)
        self.relu = nn.ReLU()
        self.maxpool = nn.Identity()
        self.layer1 = nn.Identity()
        self.layer2 = nn.Identity()
        self.layer3 = nn.Identity()
        self.layer4 = nn.Sequential(nn.Conv2d(512, 512, 1), nn.BatchNorm2d(512), nn.ReLU())
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Linear(512, 7)


def test_joint_outputs_keep_original_order_and_allow_all_states_simultaneously():
    model = MultiTaskExpressionModel(TinyResNet(), _config())
    model.eval()
    with torch.no_grad():
        model.state_head.weight.zero_()
        model.state_head.bias.fill_(3.0)
    outputs = model(torch.randn(2, 3, 96, 96))
    probabilities = model.probabilities_from_logits(outputs["expression_logits"], outputs["state_logits"])
    assert MULTITASK_CLASS_ORDER == tuple(CLASS_NAMES) + STATE_NAMES
    assert outputs["expression_logits"].shape == (2, 7)
    assert outputs["state_logits"].shape == (2, 3)
    assert probabilities.shape == (2, 10)
    torch.testing.assert_close(probabilities[:, :7].sum(1), torch.ones(2))
    assert torch.all(probabilities[:, 7:] > 0.9)
    assert not torch.allclose(probabilities.sum(1), torch.ones(2))


def test_clip_output_averages_frames_and_bn_stats_stay_frozen():
    torch.manual_seed(8)
    model = MultiTaskExpressionModel(TinyResNet(), _config())
    before = model.backbone.bn1.running_mean.clone()
    model.train()
    outputs = model(torch.randn(2, 4, 3, 96, 96))
    (outputs["expression_logits"].sum() + outputs["state_logits"].sum()).backward()
    assert outputs["expression_logits"].shape == (2, 7)
    assert outputs["state_logits"].shape == (2, 3)
    assert model.backbone.bn1.training is False
    torch.testing.assert_close(model.backbone.bn1.running_mean, before)
    assert model.backbone.conv1.weight.grad is None
    assert model.backbone.layer4[0].weight.grad is not None
    assert model.backbone.fc.weight.grad is not None
    assert model.state_head.weight.grad is not None


def test_checkpoint_contract_requires_version_and_exact_ten_order():
    checkpoint = {"checkpoint_version": MULTITASK_VERSION, "class_order": list(MULTITASK_CLASS_ORDER),
                  "state_positive_definition": "DAiSEE level >= 2", "config": _config(), "model_state": {}}
    validate_multitask_checkpoint(checkpoint)
    checkpoint["class_order"] = list(reversed(MULTITASK_CLASS_ORDER))
    with pytest.raises(ValueError, match="class_order"):
        validate_multitask_checkpoint(checkpoint)


@pytest.mark.parametrize("shape", [(2, 1, 96, 96), (2, 3, 64, 64), (0, 3, 96, 96)])
def test_model_rejects_wrong_input_shape(shape):
    model = MultiTaskExpressionModel(TinyResNet(), _config())
    with pytest.raises(ValueError):
        model(torch.zeros(shape))


def test_optional_layer3_finetuning_has_gradients_and_keeps_earlier_layers_and_bn_frozen():
    backbone = TinyResNet()
    backbone.maxpool = nn.AvgPool2d(32)
    backbone.layer3 = nn.Sequential(nn.Conv2d(512, 512, 1), nn.BatchNorm2d(512), nn.ReLU())
    model = MultiTaskExpressionModel(backbone, _config()).set_trainable_blocks(("layer3", "layer4"))
    running_mean = backbone.layer3[1].running_mean.clone()
    model.train()
    outputs = model(torch.randn(2, 3, 96, 96))
    (outputs["expression_logits"].square().mean() + outputs["state_logits"].square().mean()).backward()
    assert backbone.layer3[0].weight.grad is not None
    assert backbone.layer4[0].weight.grad is not None
    assert backbone.conv1.weight.grad is None
    assert backbone.layer3[1].training is False
    torch.testing.assert_close(backbone.layer3[1].running_mean, running_mean)
    assert model.config["trainable_blocks"] == ["layer3", "layer4"]

    model.set_trainable_blocks(("layer4",))
    assert not backbone.layer3[0].weight.requires_grad
    assert backbone.layer4[0].weight.requires_grad


@pytest.mark.parametrize("blocks", [("layer3",), ("layer4", "layer3"), ("layer2", "layer3", "layer4"), ()])
def test_finetuning_blocks_must_be_a_supported_contiguous_suffix(blocks):
    model = MultiTaskExpressionModel(TinyResNet(), _config())
    with pytest.raises(ValueError, match="trainable_blocks"):
        model.set_trainable_blocks(blocks)

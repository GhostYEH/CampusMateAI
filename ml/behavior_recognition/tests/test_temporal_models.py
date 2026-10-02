import torch

from behavior_recognition.temporal_models import (
    TemporalBehaviorModel,
    TemporalGRUHead,
    freeze_encoder,
    unfreeze_encoder_tail,
)


def test_temporal_model_maps_frame_sequences_to_four_logits():
    model = TemporalBehaviorModel(num_classes=4, hidden_size=32, pretrained=False).eval()

    output = model(torch.zeros(2, 3, 3, 64, 64))

    assert output.shape == (2, 4)
    assert model.gru.hidden_size == 32


def test_encoder_freezing_keeps_gru_and_head_trainable():
    model = TemporalBehaviorModel(num_classes=4, hidden_size=32, pretrained=False)

    freeze_encoder(model)

    assert not any(parameter.requires_grad for parameter in model.encoder.parameters())
    assert all(parameter.requires_grad for parameter in model.gru.parameters())
    assert all(parameter.requires_grad for parameter in model.classifier.parameters())

    unfreeze_encoder_tail(model, blocks=2)
    trainable_blocks = [
        any(parameter.requires_grad for parameter in block.parameters())
        for block in model.encoder.features
    ]
    assert trainable_blocks[-2:] == [True, True]
    assert not any(trainable_blocks[:-2])


def test_gru_head_accepts_frozen_onnx_feature_sequences():
    head = TemporalGRUHead(input_size=16, hidden_size=8, num_classes=4)

    output = head(torch.zeros(2, 3, 16))

    assert output.shape == (2, 4)


def test_frozen_encoder_keeps_batchnorm_statistics_and_dropout_fixed():
    model = TemporalBehaviorModel(hidden_size=8, pretrained=False)
    freeze_encoder(model)
    model.train()
    batchnorm = next(module for module in model.encoder.modules() if isinstance(module, torch.nn.BatchNorm2d))
    before = batchnorm.running_mean.clone()
    frames = torch.ones(2, 3, 32, 32)
    with torch.no_grad():
        first = model.encoder(frames)
        second = model.encoder(frames)
    torch.testing.assert_close(batchnorm.running_mean, before, rtol=0, atol=0)
    torch.testing.assert_close(first, second, rtol=0, atol=0)
    assert model.gru.training and model.classifier.training


def test_fine_tuning_only_updates_selected_encoder_blocks():
    model = TemporalBehaviorModel(hidden_size=8, pretrained=False)
    unfreeze_encoder_tail(model, blocks=2)
    model.eval()
    model.train()
    assert not any(block.training for block in list(model.encoder.features)[:-2])
    assert all(block.training for block in list(model.encoder.features)[-2:])
    assert not model.encoder.projection.training
    model.eval()
    assert not any(module.training for module in model.encoder.modules())

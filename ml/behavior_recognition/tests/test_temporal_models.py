import torch

from behavior_recognition.temporal_models import (
    TemporalBehaviorModel,
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

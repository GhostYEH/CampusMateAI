from behavior_recognition.constants import CLASS_NAMES, CLASS_TO_INDEX, IMAGE_SIZE
import torch

from behavior_recognition.models import LocalCueBehaviorModel, build_experiment_model, build_model


def test_canonical_output_contract_is_stable():
    """Catches accidental output reordering that would corrupt Android labels."""
    assert CLASS_NAMES == (
        "READ",
        "WRITE",
        "PHONE_INTERACTION",
        "NO_VISIBLE_STUDY",
    )
    assert CLASS_TO_INDEX == {name: index for index, name in enumerate(CLASS_NAMES)}
    assert IMAGE_SIZE == 224


def test_mobilenet_output_matches_contract():
    """Catches classifier heads with an incompatible class count."""
    model = build_model(num_classes=4, pretrained=False).eval()
    output = model(torch.zeros(2, 3, 224, 224))
    assert output.shape == (2, 4)


def test_local_cue_view_captures_lower_central_region():
    model = LocalCueBehaviorModel(pretrained=False).eval()
    model._encode = lambda images: images.mean(dim=(2, 3))
    model.classifier = torch.nn.Identity()
    image = torch.zeros(1, 3, 32, 32)
    image[:, :, 16:25, 12:22] = 1
    features = model(image)
    assert features.shape == (1, 6)
    assert torch.all(features[:, 3:] > features[:, :3])


def test_local_cue_variant_preserves_four_class_output():
    model = build_experiment_model({"model_variant": "local_cue", "pretrained": False}).eval()
    with torch.no_grad():
        output = model(torch.zeros(1, 3, 64, 64))
    assert output.shape == (1, 4)

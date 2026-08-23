from behavior_recognition.constants import CLASS_NAMES, CLASS_TO_INDEX, IMAGE_SIZE
import torch

from behavior_recognition.models import build_model


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

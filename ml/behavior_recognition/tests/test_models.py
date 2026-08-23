from behavior_recognition.constants import CLASS_NAMES, CLASS_TO_INDEX, IMAGE_SIZE


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

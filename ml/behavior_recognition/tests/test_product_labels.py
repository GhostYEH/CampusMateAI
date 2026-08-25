import pytest

from behavior_recognition.constants import PRODUCT_CLASS_NAMES, product_label


def test_read_and_write_fold_into_study_activity() -> None:
    assert product_label("READ") == "STUDY_ACTIVITY"
    assert product_label("WRITE") == "STUDY_ACTIVITY"
    assert product_label("PHONE_INTERACTION") == "PHONE_INTERACTION"
    assert product_label("NO_VISIBLE_STUDY") == "NO_VISIBLE_STUDY"
    assert PRODUCT_CLASS_NAMES == ("STUDY_ACTIVITY", "PHONE_INTERACTION", "NO_VISIBLE_STUDY")


def test_uncertain_is_rejection_not_a_training_class() -> None:
    with pytest.raises(ValueError, match="not a trainable product label"):
        product_label("UNCERTAIN")

CLASS_NAMES = (
    "READ",
    "WRITE",
    "PHONE_INTERACTION",
    "NO_VISIBLE_STUDY",
)
CLASS_TO_INDEX = {name: index for index, name in enumerate(CLASS_NAMES)}
IMAGE_SIZE = 224
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
DEFAULT_SEED = 20260823

PRODUCT_CLASS_NAMES = (
    "STUDY_ACTIVITY",
    "PHONE_INTERACTION",
    "NO_VISIBLE_STUDY",
)
PRODUCT_CLASS_TO_INDEX = {name: index for index, name in enumerate(PRODUCT_CLASS_NAMES)}


def product_label(source_label: str) -> str:
    normalized = source_label.strip().upper()
    if normalized in {"READ", "WRITE", "STUDY_ACTIVITY"}:
        return "STUDY_ACTIVITY"
    if normalized in {"PHONE_INTERACTION", "NO_VISIBLE_STUDY"}:
        return normalized
    raise ValueError(f"{source_label!r} is not a trainable product label")

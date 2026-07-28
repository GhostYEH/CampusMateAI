"""全局常量：标签顺序、科学边界声明。

标签顺序是工程契约，所有模型输出、labels.json、preprocess.json、
一致性测试都必须以此为准，不得随意改动。
"""

# FER2013 官方七类标签顺序（索引 0..6）。
# 这也是模型输出 logits 的列顺序，禁止调整。
EXPRESSION_LABELS: tuple[str, ...] = (
    "angry",
    "disgust",
    "fear",
    "happy",
    "sad",
    "surprise",
    "neutral",
)

# 标签到索引的映射。
LABEL_TO_INDEX: dict[str, int] = {name: idx for idx, name in enumerate(EXPRESSION_LABELS)}

# 类别数量。
NUM_CLASSES: int = len(EXPRESSION_LABELS)

# 科学边界声明：这些类别不属于 FER2013，禁止作为本工程的分类结果输出。
FORBIDDEN_OUTPUT_CATEGORIES: tuple[str, ...] = (
    "fatigue",
    "tired",
    "attention",
    "anxiety",
    "depression",
    "stress",
    "mental_illness",
)

# FER2013 原始输入尺寸（灰度）。
FER2013_NATIVE_SIZE: int = 48
FER2013_NATIVE_CHANNELS: int = 1

# ImageNet 预训练模型的输入约定（用于 ResNet18 / MobileNetV3 迁移学习分支）。
IMAGENET_INPUT_SIZE: int = 224
IMAGENET_CHANNELS: int = 3
IMAGENET_MEAN: tuple[float, float, float] = (0.485, 0.456, 0.406)
IMAGENET_STD: tuple[float, float, float] = (0.229, 0.224, 0.225)


def assert_label_order(labels: list[str] | tuple[str, ...]) -> None:
    """断言外部给定的标签顺序与本工程契约一致。

    用于校验 labels.json、配置文件、数据集类别等，防止顺序错位导致
    指标或导出模型对不上号。
    """
    if list(labels) != list(EXPRESSION_LABELS):
        raise ValueError(
            "标签顺序与工程契约不一致。\n"
            f"期望: {list(EXPRESSION_LABELS)}\n"
            f"得到: {list(labels)}\n"
            "标签顺序是模型输出列顺序的契约，不得调整。"
        )

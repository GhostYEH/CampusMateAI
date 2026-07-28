"""模型子包：自定义浅层 CNN、ResNet18、MobileNetV3-Small。

所有模型输出 7 类 logits，顺序与 constants.EXPRESSION_LABELS 一致。
主部署候选为 MobileNetV3-Small。

build.build_model(name, model_cfg, input_cfg) 为统一工厂入口。
"""

from .build import build_model, count_parameters, MODEL_NAMES

__all__ = ["build_model", "count_parameters", "MODEL_NAMES"]

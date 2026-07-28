"""配置体系：从 YAML 加载全部超参数，集中控制训练/评估/导出。

设计目标：
- 所有可调参数都在 experiment_config.yaml 中，代码不写死超参数。
- 用 dataclass 表达结构，类型清晰，便于在 IDE 中查看。
- 支持默认配置，缺失字段用合理默认值补齐，避免老配置文件失效。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

from .constants import EXPRESSION_LABELS, IMAGENET_MEAN, IMAGENET_STD


@dataclass
class DataConfig:
    """数据相关配置。"""

    # 数据集根目录。可以是 FER2013 官方 CSV 所在目录，也可以是按 split/label
    # 组织的图像目录（见 data.fer2013 模块说明）。为空时命令行必须显式给出。
    dataset_root: str = ""
    # 数据格式："fer2013_csv" 或 "image_dir"。
    format: str = "fer2013_csv"
    # 官方 CSV 文件名（format=fer2013_csv 时使用）。
    csv_name: str = "fer2013.csv"
    # 训练/验证/测试比例（仅当数据未自带 Usage 列时按此划分）。
    train_ratio: float = 0.8
    val_ratio: float = 0.1
    test_ratio: float = 0.1
    # 分层采样（按类别比例划分），防止类别分布偏移。
    stratified: bool = True
    # 划分随机种子。
    split_seed: int = 42


@dataclass
class AugmentationConfig:
    """数据增强配置。每一项都可单独关闭。"""

    enabled: bool = True
    random_horizontal_flip: bool = True
    # 小角度旋转（度）。
    rotation_degrees: float = 10.0
    # 随机裁剪缩放范围（裁剪后 resize 回 input_size）。
    random_crop_scale: tuple[float, float] = (0.9, 1.0)
    # 亮度抖动范围。
    brightness: float = 0.2
    # 对比度抖动范围。
    contrast: float = 0.2
    # 轻量遮挡：在图像上随机放置若干小灰块模拟遮挡。
    cutout_prob: float = 0.3
    cutout_max_size: int = 8


@dataclass
class InputConfig:
    """模型输入尺寸与归一化。"""

    # 输入边长（正方形）。
    size: int = 48
    # 通道数：1=灰度（自定义 CNN），3=三通道（ResNet/MobileNet 复制灰度到 3 通道）。
    channels: int = 1
    # 归一化均值。
    mean: tuple[float, ...] = (0.5,)
    # 归一化标准差。
    std: tuple[float, ...] = (0.5,)


@dataclass
class ModelConfig:
    """模型选择与结构配置。"""

    # 模型名称：custom_cnn / resnet18 / mobilenet_v3_small。
    name: str = "mobilenet_v3_small"
    # 类别数（固定为 7，由 constants.NUM_CLASSES 提供，这里给默认值便于配置自洽）。
    num_classes: int = 7
    # 迁移学习是否使用 ImageNet 预训练权重。
    pretrained: bool = True
    # 预训练骨干是否冻结（训练初期只训练分类头）。
    freeze_backbone: bool = True
    # 在指定 epoch 后解冻骨干（逐步解冻）。
    unfreeze_at_epoch: int = 5
    # Dropout 概率。
    dropout: float = 0.3


@dataclass
class LossConfig:
    """损失函数配置。"""

    # 损失类型："cross_entropy" 或 "focal"。
    type: str = "cross_entropy"
    # 是否使用类别权重（按训练集频率逆倒数）。
    use_class_weights: bool = True
    # 标签平滑系数（0 表示关闭）。
    label_smoothing: float = 0.1
    # Focal Loss 参数。
    focal_alpha: float = 0.25
    focal_gamma: float = 2.0


@dataclass
class OptimizerConfig:
    """优化器配置。"""

    # 优化器类型："adamw" 或 "sgd"。
    type: str = "adamw"
    lr: float = 1e-3
    weight_decay: float = 1e-4
    # SGD 动量。
    momentum: float = 0.9
    # 解冻骨干后的学习率（通常比初始 lr 小）。
    unfreeze_lr: float = 1e-4


@dataclass
class SchedulerConfig:
    """学习率调度器配置。"""

    # 调度器类型："cosine" 或 "step"。
    type: str = "cosine"
    # step 调度器的衰减系数。
    step_gamma: float = 0.1
    # step 调度器的衰减步长（epoch）。
    step_size: int = 10
    # cosine 的最末学习率。
    cosine_eta_min: float = 1e-6


@dataclass
class TrainConfig:
    """训练流程配置。"""

    epochs: int = 60
    batch_size: int = 64
    num_workers: int = 2
    # 早停耐心（epoch），0 表示关闭。
    early_stopping_patience: int = 8
    # 早停监控指标："val_macro_f1" 或 "val_loss"。
    monitor: str = "val_macro_f1"
    # 混合精度训练（AMP），需要 CUDA。
    amp: bool = False
    # 梯度裁剪最大范数，0 表示关闭。
    grad_clip: float = 0.0
    # 随机种子。
    seed: int = 42


@dataclass
class ExportConfig:
    """模型导出配置。"""

    # 是否导出 ONNX。
    onnx: bool = True
    # 是否导出 TFLite（需要 onnx2tf + tensorflow，环境不支持时跳过并记录）。
    tflite: bool = True
    # ONNX opset 版本。
    onnx_opset: int = 13
    # 一致性测试的最大 Top-1 不一致数量。
    consistency_max_mismatch: int = 0


@dataclass
class BenchmarkConfig:
    """基准测试配置。"""

    # 单张推理预热次数。
    warmup: int = 5
    # 单张推理正式测量次数。
    repeats: int = 50


@dataclass
class ExperimentConfig:
    """实验总配置。"""

    experiment_name: str = "mobilenet_v3_small_baseline"
    output_dir: str = "runs/mobilenet_v3_small"
    data: DataConfig = field(default_factory=DataConfig)
    augmentation: AugmentationConfig = field(default_factory=AugmentationConfig)
    input: InputConfig = field(default_factory=InputConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    loss: LossConfig = field(default_factory=LossConfig)
    optimizer: OptimizerConfig = field(default_factory=OptimizerConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    benchmark: BenchmarkConfig = field(default_factory=BenchmarkConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentConfig":
        """从字典构造配置，缺失字段用默认值补齐。"""
        # 标签顺序校验：如果配置里写了 label_order，必须与契约一致。
        if "label_order" in data:
            from .constants import assert_label_order

            assert_label_order(data["label_order"])

        def merge(dc, sub):
            if not sub:
                return dc()
            # 只取 dataclass 中定义的字段，忽略多余键，避免报错。
            valid_keys = set(dc.__dataclass_fields__.keys())
            filtered = {k: v for k, v in sub.items() if k in valid_keys}
            return dc(**filtered)

        return cls(
            experiment_name=data.get("experiment_name", "mobilenet_v3_small_baseline"),
            output_dir=data.get("output_dir", "runs/mobilenet_v3_small"),
            data=merge(DataConfig, data.get("data")),
            augmentation=merge(AugmentationConfig, data.get("augmentation")),
            input=merge(InputConfig, data.get("input")),
            model=merge(ModelConfig, data.get("model")),
            loss=merge(LossConfig, data.get("loss")),
            optimizer=merge(OptimizerConfig, data.get("optimizer")),
            scheduler=merge(SchedulerConfig, data.get("scheduler")),
            train=merge(TrainConfig, data.get("train")),
            export=merge(ExportConfig, data.get("export")),
            benchmark=merge(BenchmarkConfig, data.get("benchmark")),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ExperimentConfig":
        """从 YAML 文件加载配置。"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {path}")
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        """转字典。"""
        return asdict(self)

    def validate(self) -> None:
        """校验配置合法性，发现非法值立即抛错，避免训练中途才崩。"""
        if self.model.num_classes != len(EXPRESSION_LABELS):
            raise ValueError(
                f"num_classes 必须为 {len(EXPRESSION_LABELS)}，"
                f"当前为 {self.model.num_classes}"
            )
        if self.loss.type not in ("cross_entropy", "focal"):
            raise ValueError(f"未知 loss.type: {self.loss.type}")
        if self.optimizer.type not in ("adamw", "sgd"):
            raise ValueError(f"未知 optimizer.type: {self.optimizer.type}")
        if self.scheduler.type not in ("cosine", "step"):
            raise ValueError(f"未知 scheduler.type: {self.scheduler.type}")
        if self.model.name not in ("custom_cnn", "resnet18", "mobilenet_v3_small"):
            raise ValueError(f"未知 model.name: {self.model.name}")
        if self.data.format not in ("fer2013_csv", "image_dir"):
            raise ValueError(f"未知 data.format: {self.data.format}")
        if self.input.channels not in (1, 3):
            raise ValueError(f"input.channels 必须为 1 或 3，当前为 {self.input.channels}")
        total = self.data.train_ratio + self.data.val_ratio + self.data.test_ratio
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"train/val/test 比例之和必须为 1，当前为 {total}")
        # 通道数与归一化参数长度匹配。
        if len(self.input.mean) != self.input.channels:
            raise ValueError("input.mean 长度与 input.channels 不一致")
        if len(self.input.std) != self.input.channels:
            raise ValueError("input.std 长度与 input.channels 不一致")


def default_imagenet_input() -> InputConfig:
    """返回 ImageNet 三通道默认输入配置，供 ResNet/MobileNet 分支使用。"""
    return InputConfig(
        size=224,
        channels=3,
        mean=tuple(IMAGENET_MEAN),
        std=tuple(IMAGENET_STD),
    )

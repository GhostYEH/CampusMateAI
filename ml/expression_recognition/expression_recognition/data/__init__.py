"""数据工程子包：FER2013 加载、增强、划分。

模块说明：
- fer2013.py：FER2013 数据解析（CSV / 图像目录两种格式）+ torch Dataset 包装。
- transforms.py：数据增强（水平翻转 / 小角度旋转 / 随机裁剪 / 亮度对比度 / 轻量遮挡）。
- split.py：训练/验证/测试划分，按官方 Usage 或分层随机，并记录防泄漏限制。
- split_manifest.py：划分清单持久化，保证多个模型复用同一固定划分。
"""

from .fer2013 import (
    FER2013Sample,
    parse_fer2013_csv,
    scan_image_dir,
    load_samples,
    DatasetNotFoundError,
)
from .split import split_samples, SplitResult, LEAKAGE_NOTE
from .split_manifest import (
    save_manifest,
    load_manifest,
    reconstruct_samples_from_manifest,
    verify_manifest_against_samples,
)

__all__ = [
    "FER2013Sample",
    "parse_fer2013_csv",
    "scan_image_dir",
    "load_samples",
    "DatasetNotFoundError",
    "split_samples",
    "SplitResult",
    "LEAKAGE_NOTE",
    "save_manifest",
    "load_manifest",
    "reconstruct_samples_from_manifest",
    "verify_manifest_against_samples",
]

"""导出 labels.json：标签顺序契约。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..constants import EXPRESSION_LABELS, LABEL_TO_INDEX
from ..utils.io import write_json


def export_labels_json(path: str | Path) -> dict[str, Any]:
    """写出 labels.json。

    结构：
    {
        "label_order": ["angry", "disgust", ...],
        "label_to_index": {"angry": 0, ...},
        "num_classes": 7,
        "scientific_boundary": "..."
    }
    """
    data = {
        "label_order": list(EXPRESSION_LABELS),
        "label_to_index": LABEL_TO_INDEX,
        "num_classes": len(EXPRESSION_LABELS),
        "scientific_boundary": (
            "本模型识别的是可观察到的面部表情，FER2013 七类。"
            "不输出疲劳/注意力/焦虑症/心理疾病等类别。"
            "结果仅供辅助参考，不进行疾病诊断，不替代专业心理咨询。"
        ),
    }
    write_json(path, data)
    return data

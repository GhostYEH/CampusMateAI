"""ONNX -> TFLite 转换 + PyTorch/ONNX/TFLite Top-1 一致性验证。

使用真实 FER2013 测试集图片(K:/深度学习代码/test/<label>/*.jpg)验证。

输出:
- artifacts/mobilenet_v3_small/model.tflite
- artifacts/mobilenet_v3_small/model.tflite.json (更新)
- artifacts/mobilenet_v3_small/tflite_consistency.json

执行:
    python convert_and_validate.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ARTIFACT_DIR = Path(__file__).parent / "artifacts" / "mobilenet_v3_small"
PT_PATH = ARTIFACT_DIR / "best_model.pt"
ONNX_PATH = ARTIFACT_DIR / "model.onnx"
TFLITE_PATH = ARTIFACT_DIR / "model.tflite"
TF_DIR = ARTIFACT_DIR / "model_tf_saved_model"

FER2013_TEST_ROOT = Path(r"K:\深度学习代码\test")

LABEL_ORDER = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]
INPUT_SIZE = 224
CHANNELS = 3

# 每类抽样数量(总共 N_PER_CLASS * 7 = 70 张)
N_PER_CLASS = 10


def log(msg: str) -> None:
    print(f"[convert] {msg}", flush=True)


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def preprocess_image(img: Image.Image) -> np.ndarray:
    """PIL Image -> (1, 224, 224, 3) float32 NHWC 张量,与训练时预处理对齐。

    流程: 灰度 -> RGB(复制三通道) -> resize 224 -> /255.0 -> (x-mean)/std。
    """
    if img.mode != "RGB":
        img = img.convert("RGB")
    img = img.resize((INPUT_SIZE, INPUT_SIZE), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float32) / 255.0  # HWC [0,1]
    mean = np.asarray(MEAN, dtype=np.float32)
    std = np.asarray(STD, dtype=np.float32)
    arr = (arr - mean) / std  # 广播 HWC
    arr = arr[None, ...]  # -> NHWC
    return arr


def to_nchw(nhwc: np.ndarray) -> np.ndarray:
    """NHWC -> NCHW."""
    return np.transpose(nhwc, (0, 3, 1, 2)).astype(np.float32)


# ---------------------------------------------------------------------------
# 1. PyTorch
# ---------------------------------------------------------------------------
def run_pytorch(images_nchw: np.ndarray) -> np.ndarray:
    """加载 PyTorch 权重,运行推理,返回 (N, 7) logits。"""
    import torch

    # 防止 torchvision 试图下载预训练权重(我们只加载本地 best_model.pt)
    sys.path.insert(0, str(Path(__file__).parent))
    from expression_recognition.models.mobilenet_v3 import (  # type: ignore
        build_mobilenet_v3_small,
    )

    log("构建 MobileNetV3-Small(pretrained=False) 并加载 best_model.pt")
    model = build_mobilenet_v3_small(num_classes=7, pretrained=False)
    state = torch.load(str(PT_PATH), map_location="cpu", weights_only=False)
    # 训练 checkpoint 含多字段,取 model_state
    if isinstance(state, dict):
        if "model_state" in state:
            state = state["model_state"]
        elif "state_dict" in state:
            state = state["state_dict"]
        elif "model" in state:
            state = state["model"]
    model.load_state_dict(state)
    model.eval()

    with torch.no_grad():
        x = torch.from_numpy(images_nchw)
        logits = model(x)
    return logits.cpu().numpy()


# ---------------------------------------------------------------------------
# 2. ONNX
# ---------------------------------------------------------------------------
def run_onnx(images_nchw: np.ndarray) -> np.ndarray:
    """加载 ONNX,运行推理,返回 (N, 7) logits。"""
    import onnxruntime as ort

    sess = ort.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name
    out = sess.run(None, {input_name: images_nchw})
    return out[0]


# ---------------------------------------------------------------------------
# 3. ONNX -> TFLite 转换
# ---------------------------------------------------------------------------
def convert_onnx_to_tflite() -> bool:
    """ONNX -> TFLite (通过 onnx2tf 直接导出 fp32 tflite)。返回是否成功。"""
    import onnx2tf

    if TF_DIR.exists():
        shutil.rmtree(TF_DIR)

    log("ONNX -> TFLite (onnx2tf 直接导出 fp32)")
    onnx2tf.convert(
        input_onnx_file_path=str(ONNX_PATH),
        output_folder_path=str(TF_DIR),
        non_verbose=True,
    )

    # onnx2tf 2.x 直接产出 model_float32.tflite 与 model_float16.tflite
    fp32_tflite = TF_DIR / "model_float32.tflite"
    if not fp32_tflite.exists():
        # 兼容旧版本: 尝试通过 TF SavedModel 转 TFLite
        log("onnx2tf 未直接产出 fp32 tflite,回退到 SavedModel -> TFLite")
        import tensorflow as tf

        converter = tf.lite.TFLiteConverter.from_saved_model(str(TF_DIR))
        converter.optimizations = []
        tflite_bytes = converter.convert()
        with TFLITE_PATH.open("wb") as f:
            f.write(tflite_bytes)
        log(f"TFLite 已写入: {TFLITE_PATH} ({len(tflite_bytes)} bytes)")
        return True

    # 复制 fp32 tflite 到最终路径
    shutil.copy2(fp32_tflite, TFLITE_PATH)
    size = TFLITE_PATH.stat().st_size
    log(f"TFLite 已写入: {TFLITE_PATH} ({size} bytes,fp32)")
    return True


def run_tflite(images_nhwc: np.ndarray) -> np.ndarray:
    """加载 TFLite,运行推理,返回 (N, 7) logits。"""
    import tensorflow as tf

    interp = tf.lite.Interpreter(model_path=str(TFLITE_PATH))
    interp.allocate_tensors()
    in_det = interp.get_input_details()[0]
    out_det = interp.get_output_details()[0]
    log(f"TFLite input: shape={in_det['shape']}, dtype={in_det['dtype']}")
    log(f"TFLite output: shape={out_det['shape']}, dtype={out_det['dtype']}")

    # 若输入 dtype 不是 float32,需要转换(本模型应为 float32)
    if in_det["dtype"] != np.float32:
        raise RuntimeError(f"意外输入 dtype: {in_det['dtype']}")

    results = []
    for i in range(images_nhwc.shape[0]):
        single = images_nhwc[i:i + 1]
        interp.set_tensor(in_det["index"], single)
        interp.invoke()
        out = interp.get_tensor(out_det["index"])
        results.append(out[0])
    return np.asarray(results, dtype=np.float32)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def collect_test_images() -> list[tuple[str, Path]]:
    """从 FER2013 test 目录每类抽样 N_PER_CLASS 张图片。"""
    rng = np.random.default_rng(42)
    samples: list[tuple[str, Path]] = []
    for label in LABEL_ORDER:
        d = FER2013_TEST_ROOT / label
        if not d.exists():
            log(f"警告: 目录不存在 {d},跳过 {label}")
            continue
        files = sorted(d.glob("*.jpg"))
        if len(files) == 0:
            files = sorted(d.glob("*"))
        if len(files) == 0:
            continue
        chosen = rng.choice(len(files), size=min(N_PER_CLASS, len(files)), replace=False)
        for idx in chosen:
            samples.append((label, files[int(idx)]))
    return samples


def top1(logits: np.ndarray) -> np.ndarray:
    return np.argmax(logits, axis=1)


def main() -> int:
    log("=" * 60)
    log("CNN 移动端接入: ONNX -> TFLite 转换 + 一致性验证")
    log("=" * 60)

    # 1. 检查输入文件
    for p in [PT_PATH, ONNX_PATH]:
        if not p.exists():
            log(f"错误: 文件不存在 {p}")
            return 1
    log(f"PyTorch: {PT_PATH}")
    log(f"ONNX:    {ONNX_PATH}")

    # 2. 转换 TFLite
    if TFLITE_PATH.exists():
        log(f"已存在旧 TFLite,将覆盖: {TFLITE_PATH}")
    try:
        convert_onnx_to_tflite()
    except Exception as e:
        log(f"TFLite 转换失败: {type(e).__name__}: {e}")
        return 2

    # 3. 收集测试图片
    samples = collect_test_images()
    if len(samples) == 0:
        log("错误: 未找到测试图片")
        return 3
    log(f"采样 {len(samples)} 张 FER2013 测试图片(每类 {N_PER_CLASS} 张)")

    # 4. 预处理
    nhwc_batch = np.zeros((len(samples), INPUT_SIZE, INPUT_SIZE, CHANNELS), dtype=np.float32)
    for i, (_, path) in enumerate(samples):
        img = Image.open(path)
        nhwc_batch[i] = preprocess_image(img)
    nchw_batch = to_nchw(nhwc_batch)
    log(f"预处理完成: NHWC={nhwc_batch.shape}, NCHW={nchw_batch.shape}")

    # 5. 三后端推理
    log("运行 PyTorch 推理...")
    pt_logits = run_pytorch(nchw_batch)
    log("运行 ONNX 推理...")
    onnx_logits = run_onnx(nchw_batch)
    log("运行 TFLite 推理...")
    tflite_logits = run_tflite(nhwc_batch)

    # 6. Top-1 一致性
    pt_top1 = top1(pt_logits)
    onnx_top1 = top1(onnx_logits)
    tflite_top1 = top1(tflite_logits)

    pt_vs_onnx_mismatch = int(np.sum(pt_top1 != onnx_top1))
    pt_vs_tflite_mismatch = int(np.sum(pt_top1 != tflite_top1))
    onnx_vs_tflite_mismatch = int(np.sum(onnx_top1 != tflite_top1))

    # logits 数值差异
    pt_onnx_max_diff = float(np.max(np.abs(pt_logits - onnx_logits)))
    pt_tflite_max_diff = float(np.max(np.abs(pt_logits - tflite_logits)))
    onnx_tflite_max_diff = float(np.max(np.abs(onnx_logits - tflite_logits)))

    # 真实标签准确率(参考,反映模型在抽样上的表现)
    label_to_idx = {l: i for i, l in enumerate(LABEL_ORDER)}
    true_labels = np.asarray([label_to_idx[l] for l, _ in samples])
    pt_acc = float(np.mean(pt_top1 == true_labels))
    onnx_acc = float(np.mean(onnx_top1 == true_labels))
    tflite_acc = float(np.mean(tflite_top1 == true_labels))

    log("")
    log("=" * 60)
    log("一致性结果")
    log("=" * 60)
    log(f"PyTorch  Top-1 与真实标签准确率: {pt_acc:.4f}")
    log(f"ONNX     Top-1 与真实标签准确率: {onnx_acc:.4f}")
    log(f"TFLite   Top-1 与真实标签准确率: {tflite_acc:.4f}")
    log(f"PyTorch  vs ONNX    Top-1 不一致: {pt_vs_onnx_mismatch}/{len(samples)}")
    log(f"PyTorch  vs TFLite  Top-1 不一致: {pt_vs_tflite_mismatch}/{len(samples)}")
    log(f"ONNX     vs TFLite  Top-1 不一致: {onnx_vs_tflite_mismatch}/{len(samples)}")
    log(f"PyTorch  vs ONNX    logits max |diff|: {pt_onnx_max_diff:.6f}")
    log(f"PyTorch  vs TFLite  logits max |diff|: {pt_tflite_max_diff:.6f}")
    log(f"ONNX     vs TFLite  logits max |diff|: {onnx_tflite_max_diff:.6f}")

    # 7. 保存结果
    sha = sha256_of_file(TFLITE_PATH)
    size_bytes = TFLITE_PATH.stat().st_size
    result = {
        "tflite_path": str(TFLITE_PATH),
        "tflite_sha256": sha,
        "tflite_size_bytes": size_bytes,
        "n_samples": len(samples),
        "n_per_class": N_PER_CLASS,
        "label_order": LABEL_ORDER,
        "pytorch_accuracy": pt_acc,
        "onnx_accuracy": onnx_acc,
        "tflite_accuracy": tflite_acc,
        "top1_mismatch": {
            "pytorch_vs_onnx": pt_vs_onnx_mismatch,
            "pytorch_vs_tflite": pt_vs_tflite_mismatch,
            "onnx_vs_tflite": onnx_vs_tflite_mismatch,
        },
        "logits_max_abs_diff": {
            "pytorch_vs_onnx": pt_onnx_max_diff,
            "pytorch_vs_tflite": pt_tflite_max_diff,
            "onnx_vs_tflite": onnx_tflite_max_diff,
        },
        "passed": (pt_vs_tflite_mismatch == 0),
        "max_allowed_mismatch": 0,
        "note": (
            "Top-1 一致性要求: PyTorch vs TFLite 不一致数 = 0。"
            "允许 logits 数值小误差(浮点实现差异),但 argmax 标签必须一致。"
        ),
    }
    out_path = ARTIFACT_DIR / "tflite_consistency.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log(f"结果已保存: {out_path}")

    # 更新 model.tflite.json
    tflite_meta = {
        "onnx_path": str(ONNX_PATH),
        "tflite_path": str(TFLITE_PATH),
        "tf_saved_model_dir": str(TF_DIR),
        "status": "ok",
        "sha256": sha,
        "size_bytes": size_bytes,
        "consistency_path": str(out_path),
    }
    with (ARTIFACT_DIR / "model.tflite.json").open("w", encoding="utf-8") as f:
        json.dump(tflite_meta, f, ensure_ascii=False, indent=2)

    if pt_vs_tflite_mismatch != 0:
        log(f"失败: PyTorch 与 TFLite Top-1 不一致数 = {pt_vs_tflite_mismatch}")
        return 4
    log("通过: PyTorch 与 TFLite 在所有抽样上 Top-1 完全一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())

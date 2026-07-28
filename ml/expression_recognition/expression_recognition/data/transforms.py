"""数据增强与预处理变换。

本模块用 numpy + PIL 实现，避免对 torchvision.transforms 的强依赖
（torchvision 在某些环境安装麻烦，且 freshman 友好）。

变换作用于 (C, H, W) float32、值域 [0,1] 的 numpy 数组，返回同形状。
流水线：[几何/颜色增强] -> resize 到 input.size -> 归一化 (mean/std)。

增强项（每项可独立关闭，由 AugmentationConfig 控制）：
- 随机水平翻转
- 小角度旋转
- 随机裁剪（裁剪后 resize 回 input.size）
- 亮度抖动
- 对比度抖动
- 轻量遮挡（cutout）

重要：增强只作用于训练集；验证/测试集只做 resize + 归一化，不做随机增强，
以保证评估指标的可复现性。

实现说明：变换使用模块顶层 callable 类（而非闭包），确保在 Windows
multiprocessing spawn 模式下可被 DataLoader worker pickle。
"""

from __future__ import annotations

import random
from typing import Any, Callable

import numpy as np
from PIL import Image, ImageEnhance

from ..config import AugmentationConfig, InputConfig


def _chw_to_pil(arr: np.ndarray) -> Image.Image:
    """(C,H,W) float32 [0,1] -> PIL Image（L 或 RGB）。"""
    c, h, w = arr.shape
    uint8 = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    if c == 1:
        return Image.fromarray(uint8[0], mode="L")
    # 3 通道：转 HWC。
    hwc = np.transpose(uint8, (1, 2, 0))
    return Image.fromarray(hwc, mode="RGB")


def _pil_to_chw(img: Image.Image) -> np.ndarray:
    """PIL Image -> (C,H,W) float32 [0,1]。"""
    arr = np.asarray(img, dtype=np.float32) / 255.0
    if arr.ndim == 2:
        arr = arr[:, :, None]
    return np.transpose(arr, (2, 0, 1))


def resize_to(arr: np.ndarray, size: int) -> np.ndarray:
    """把 (C,H,W) 数组 resize 到 (C, size, size)，用双线性插值。"""
    c, h, w = arr.shape
    if h == size and w == size:
        return arr
    img = _chw_to_pil(arr)
    img = img.resize((size, size), Image.BILINEAR)
    return _pil_to_chw(img)


def normalize(arr: np.ndarray, mean: tuple[float, ...], std: tuple[float, ...]) -> np.ndarray:
    """逐通道归一化：(x - mean) / std。"""
    mean_arr = np.asarray(mean, dtype=np.float32).reshape(-1, 1, 1)
    std_arr = np.asarray(std, dtype=np.float32).reshape(-1, 1, 1)
    return (arr - mean_arr) / std_arr


# ---------------------------------------------------------------------------
# 单项增强（作用在 (C,H,W) float32 [0,1]）
# ---------------------------------------------------------------------------

def random_horizontal_flip(arr: np.ndarray, p: float, rng: random.Random) -> np.ndarray:
    if rng.random() < p:
        return arr[:, :, ::-1].copy()
    return arr


def random_rotation(arr: np.ndarray, degrees: float, rng: random.Random) -> np.ndarray:
    if degrees <= 0:
        return arr
    angle = rng.uniform(-degrees, degrees)
    img = _chw_to_pil(arr).rotate(angle, resample=Image.BILINEAR, fillcolor=0)
    return _pil_to_chw(img)


def random_crop(arr: np.ndarray, scale: tuple[float, float], rng: random.Random) -> np.ndarray:
    """在 [scale[0], scale[1]] 比例范围内随机裁剪，返回与原图同尺寸（裁剪后 resize 回去）。"""
    c, h, w = arr.shape
    s = rng.uniform(*scale)
    nh, nw = max(1, int(round(h * s))), max(1, int(round(w * s)))
    top = rng.randint(0, h - nh) if h - nh > 0 else 0
    left = rng.randint(0, w - nw) if w - nw > 0 else 0
    cropped = arr[:, top:top + nh, left:left + nw]
    # resize 回原尺寸。
    img = _chw_to_pil(cropped).resize((w, h), Image.BILINEAR)
    return _pil_to_chw(img)


def color_jitter(arr: np.ndarray, brightness: float, contrast: float, rng: random.Random) -> np.ndarray:
    """亮度 + 对比度抖动。"""
    img = _chw_to_pil(arr)
    if brightness > 0:
        b = 1.0 + rng.uniform(-brightness, brightness)
        img = ImageEnhance.Brightness(img).enhance(max(0.0, b))
    if contrast > 0:
        c = 1.0 + rng.uniform(-contrast, contrast)
        img = ImageEnhance.Contrast(img).enhance(max(0.0, c))
    return _pil_to_chw(img)


def cutout(arr: np.ndarray, prob: float, max_size: int, rng: random.Random) -> np.ndarray:
    """轻量遮挡：随机放置一个灰色方块。值域已是 [0,1]，用 0.5 灰填充。"""
    if prob <= 0 or rng.random() >= prob:
        return arr
    c, h, w = arr.shape
    size = rng.randint(1, max(1, max_size))
    size = min(size, h, w)
    top = rng.randint(0, h - size) if h - size > 0 else 0
    left = rng.randint(0, w - size) if w - size > 0 else 0
    out = arr.copy()
    out[:, top:top + size, left:left + size] = 0.5
    return out


# ---------------------------------------------------------------------------
# 流水线：模块顶层 callable 类（可被 multiprocessing pickle）
# ---------------------------------------------------------------------------

class TrainTransform:
    """训练集变换：增强 -> resize -> 归一化。

    使用模块顶层类（而非闭包），保证 Windows multiprocessing spawn 模式下
    DataLoader worker 可 pickle。每个 worker 实例有独立的 rng 状态，
    训练时不同 worker 会产生不同的增强结果，这在数据增强中是可接受的。
    """

    def __init__(self, aug: AugmentationConfig, inp: InputConfig, seed: int = 0):
        # 把 dataclass 转成纯值，避免 pickle 依赖 dataclass 实现差异。
        self.enabled: bool = bool(aug.enabled)
        self.random_horizontal_flip: bool = bool(aug.random_horizontal_flip)
        self.rotation_degrees: float = float(aug.rotation_degrees)
        self.random_crop_scale: tuple[float, float] = tuple(aug.random_crop_scale)
        self.brightness: float = float(aug.brightness)
        self.contrast: float = float(aug.contrast)
        self.cutout_prob: float = float(aug.cutout_prob)
        self.cutout_max_size: int = int(aug.cutout_max_size)
        self.size: int = int(inp.size)
        self.mean: tuple[float, ...] = tuple(inp.mean)
        self.std: tuple[float, ...] = tuple(inp.std)
        self.seed: int = int(seed)
        # rng 不 pickle（每个 worker 重新构造，基于 seed + worker_id）。
        self._rng: random.Random | None = None

    def _get_rng(self) -> random.Random:
        """延迟初始化 rng（worker 进程中重新构造）。"""
        if self._rng is None:
            # 每个 worker 用不同种子，避免所有 worker 产生相同增强。
            worker_id = 0
            try:
                import torch.utils.data
                info = torch.utils.data.get_worker_info()
                if info is not None:
                    worker_id = info.id
            except Exception:
                pass
            self._rng = random.Random(self.seed + worker_id)
        return self._rng

    def __call__(self, arr: np.ndarray) -> np.ndarray:
        rng = self._get_rng()
        if self.enabled:
            if self.random_horizontal_flip:
                arr = random_horizontal_flip(arr, 0.5, rng)
            if self.rotation_degrees > 0:
                arr = random_rotation(arr, self.rotation_degrees, rng)
            arr = random_crop(arr, self.random_crop_scale, rng)
            arr = color_jitter(arr, self.brightness, self.contrast, rng)
            arr = cutout(arr, self.cutout_prob, self.cutout_max_size, rng)
        arr = resize_to(arr, self.size)
        arr = normalize(arr, self.mean, self.std)
        return arr

    # ---- pickle 支持：不序列化 _rng（worker 中重建） ----
    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        state["_rng"] = None
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)


class EvalTransform:
    """验证/测试集变换：仅 resize + 归一化（无随机增强）。

    模块顶层类，可被 multiprocessing pickle。
    """

    def __init__(self, inp: InputConfig):
        self.size: int = int(inp.size)
        self.mean: tuple[float, ...] = tuple(inp.mean)
        self.std: tuple[float, ...] = tuple(inp.std)

    def __call__(self, arr: np.ndarray) -> np.ndarray:
        arr = resize_to(arr, self.size)
        arr = normalize(arr, self.mean, self.std)
        return arr


class _Compose:
    """简单流水线。"""

    def __init__(self, ops: list[Callable[[np.ndarray], np.ndarray]]):
        self.ops = ops

    def __call__(self, arr: np.ndarray) -> np.ndarray:
        for op in self.ops:
            arr = op(arr)
        return arr


def build_train_transform(
    aug: AugmentationConfig, inp: InputConfig, seed: int = 0
) -> Callable[[np.ndarray], np.ndarray]:
    """构造训练集变换：增强 -> resize -> 归一化。

    返回 TrainTransform 实例（可被 multiprocessing pickle）。
    """
    return TrainTransform(aug, inp, seed=seed)


def build_eval_transform(inp: InputConfig) -> Callable[[np.ndarray], np.ndarray]:
    """构造验证/测试集变换：仅 resize + 归一化（无随机增强）。"""
    return EvalTransform(inp)

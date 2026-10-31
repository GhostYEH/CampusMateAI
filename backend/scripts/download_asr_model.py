"""下载本地语音识别（SenseVoice / sherpa-onnx）模型文件。

模型体积约 230MB，不随仓库分发，`backend/data/asr_models/` 已被根 `.gitignore`
忽略。默认只取回两个必需文件；`--with-vad` 另外获取约 629KB 的 Silero VAD，
`--with-denoiser` 获取约 523KB 的 GTCRN。下载可选模型不会自动启用降噪。

用法（在任意目录执行，路径按脚本位置解析）::

    # 用后端虚拟环境运行
    cd backend
    .venv\\Scripts\\python.exe scripts/download_asr_model.py

    # 只检查是否已就位，不下载
    .venv\\Scripts\\python.exe scripts/download_asr_model.py --check

    # 同时下载/检查可选的 Silero VAD（放在声学模型目录的同一父目录）
    .venv\\Scripts\\python.exe scripts/download_asr_model.py --with-vad
    .venv\\Scripts\\python.exe scripts/download_asr_model.py --check --with-vad

    # 同时获取可选 GTCRN（仅下载；是否启用由后端配置决定）
    .venv\\Scripts\\python.exe scripts/download_asr_model.py --with-vad --with-denoiser
    .venv\\Scripts\\python.exe scripts/download_asr_model.py --check --with-vad --with-denoiser

    # 指定镜像站或目标目录（默认见下方常量）
    .venv\\Scripts\\python.exe scripts/download_asr_model.py --base-url https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main/

下载特性：

* 已存在且大小正确的文件自动跳过，重复执行是安全的。
* Silero VAD 和 GTCRN 还校验固定 SHA256，镜像地址必须提供相同模型。
* 断点续传：中断后重新运行会从已下载字节处继续（服务端须支持 Range）。
* 先写 ``.part`` 临时文件，校验通过后才改名，避免半个文件被当成完整模型。
* 全程输出进度百分比，适合在慢速网络下观察。

模型说明：SenseVoice 支持中/英/日/韩/粤语，纯本地 CPU 推理，不联网、
不产生调用费用。下载完成后即可使用 ``POST /api/v1/assistant/asr``；
缺少本模型时后端仍能正常启动，该接口返回 503「本地语音识别未就绪」。
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# 默认使用国内可直连的镜像站；海外网络可用 --base-url 换成 huggingface.co。
DEFAULT_BASE_URL = (
    "https://hf-mirror.com/csukuangfj/"
    "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main/"
)
MODEL_DIR_NAME = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"
# 文件名 → 预期字节数。大小用于判定"已下载完整"，None 表示不做大小校验。
FILES: dict[str, int | None] = {
    "model.int8.onnx": 239_233_841,
    "tokens.txt": 315_894,
}
VAD_FILENAME = "silero_vad.onnx"
VAD_SIZE = 643_854
DEFAULT_VAD_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx"
)
# 与上述官方 release 文件逐字节核实；避免同名不同版本的模型混入。
VAD_SHA256 = "9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6"
DENOISER_FILENAME = "gtcrn_simple.onnx"
DENOISER_SIZE = 535_638
DEFAULT_DENOISER_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speech-enhancement-models/gtcrn_simple.onnx"
)
DENOISER_SHA256 = "e77603ac0c23dac3227dd2d7135b3a585cbee2679048aecfa886657d3ae1b534"
_CHUNK = 1024 * 256


def _target_dir(override: str | None) -> Path:
    """默认落在 backend/data/asr_models/<模型名>/（相对 backend/ 根目录）。"""
    if override:
        return Path(override).expanduser().resolve()
    backend_root = Path(__file__).resolve().parents[1]
    return backend_root / "data" / "asr_models" / MODEL_DIR_NAME


def _human(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_complete(path: Path, expected: int | None, sha256: str | None = None) -> bool:
    if not path.is_file():
        return False
    size = path.stat().st_size
    if (expected is not None and size != expected) or size <= 0:
        return False
    return sha256 is None or _sha256(path) == sha256


def _validate_download(
    part: Path, dest: Path, expected: int | None, sha256: str | None
) -> None:
    actual = part.stat().st_size
    if expected is not None and actual != expected:
        raise RuntimeError(
            f"{dest.name} 大小不符：期望 {expected} 字节，实际 {actual} 字节。"
            f"请删除 {part.name} 后重试。"
        )
    if sha256 is not None and _sha256(part) != sha256:
        raise RuntimeError(f"{dest.name} SHA256 校验失败，请删除 {part.name} 后重试。")


def _download(
    url: str, dest: Path, expected: int | None, sha256: str | None = None
) -> None:
    """带断点续传与进度输出的单文件下载。"""
    part = dest.with_suffix(dest.suffix + ".part")
    offset = part.stat().st_size if part.is_file() else 0

    request = urllib.request.Request(url)
    if offset:
        request.add_header("Range", f"bytes={offset}-")
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as error:
        if error.code == 416 and offset:
            # 已下载字节数不小于远端文件：可能是上次刚好传完，交给大小校验判断。
            _validate_download(part, dest, expected, sha256)
            part.replace(dest)
            return
        raise

    with response:
        resumed = offset and response.status == 206
        if offset and not resumed:
            offset = 0  # 服务端不支持 Range，只能从头下
        total = expected
        if total is None:
            length = response.headers.get("Content-Length")
            total = (int(length) + offset) if length else None
        mode = "ab" if resumed else "wb"
        downloaded = offset
        started = time.monotonic()
        last_log = 0.0
        with part.open(mode) as output:
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                # 限速输出，避免每个 chunk 都刷一行
                if now - last_log >= 0.5 or (total and downloaded >= total):
                    last_log = now
                    elapsed = max(now - started, 1e-6)
                    speed = (downloaded - offset) / elapsed
                    if total:
                        percent = downloaded / total * 100
                        sys.stdout.write(
                            f"\r  {percent:5.1f}%  {_human(downloaded)}/{_human(total)}"
                            f"  {_human(speed)}/s"
                        )
                    else:
                        sys.stdout.write(f"\r  {_human(downloaded)}  {_human(speed)}/s")
                    sys.stdout.flush()
    sys.stdout.write("\n")
    sys.stdout.flush()

    _validate_download(part, dest, expected, sha256)
    part.replace(dest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="下载本地语音识别(SenseVoice/sherpa-onnx)模型文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("用法（在任意目录执行，路径按脚本位置解析）", 1)[-1],
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"模型文件所在目录的 URL 前缀（默认 {DEFAULT_BASE_URL}）",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=f"目标目录（默认 backend/data/asr_models/{MODEL_DIR_NAME}/）",
    )
    parser.add_argument(
        "--with-vad",
        action="store_true",
        help="同时获取可选 Silero VAD，保存到 --output-dir 的父目录",
    )
    parser.add_argument(
        "--vad-url",
        default=DEFAULT_VAD_URL,
        help="Silero VAD 完整下载地址（镜像须通过固定大小和 SHA256 校验）",
    )
    parser.add_argument(
        "--with-denoiser",
        action="store_true",
        help="同时获取可选 GTCRN，保存到 --output-dir 的父目录；不会自动启用降噪",
    )
    parser.add_argument(
        "--denoiser-url",
        default=DEFAULT_DENOISER_URL,
        help="GTCRN 完整下载地址（镜像须通过固定大小和 SHA256 校验）",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="只检查文件是否已就位，不发起下载",
    )
    args = parser.parse_args(argv)

    base_url = args.base_url if args.base_url.endswith("/") else args.base_url + "/"
    target = _target_dir(args.output_dir)
    artifacts = [
        (target / name, size, base_url + name, None) for name, size in FILES.items()
    ]
    if args.with_vad:
        artifacts.append(
            (target.parent / VAD_FILENAME, VAD_SIZE, args.vad_url, VAD_SHA256)
        )
    if args.with_denoiser:
        artifacts.append(
            (
                target.parent / DENOISER_FILENAME,
                DENOISER_SIZE,
                args.denoiser_url,
                DENOISER_SHA256,
            )
        )

    print(f"模型目录：{target}")
    missing = [
        item for item in artifacts if not _is_complete(item[0], item[1], item[3])
    ]
    if not missing:
        for path, size, _, _ in artifacts:
            print(f"  [已就位] {path.name}  ({_human(size) if size else '-'})")
        print("模型文件完整，无需下载。")
        return 0

    if args.check:
        for existing, size, _, sha256 in artifacts:
            state = "未找到" if not existing.is_file() else "不完整"
            if _is_complete(existing, size, sha256):
                state = "已就位"
            print(f"  [{state}] {existing.name}")
        print("模型尚未就绪，去掉 --check 即可开始下载。")
        return 1

    target.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(target).free
    needed = sum(size for _, size, _, _ in missing if size) or 0
    if needed and free < needed * 1.2:
        print(
            f"磁盘剩余空间不足：需要约 {_human(needed * 1.2)}，当前仅 {_human(free)}。",
            file=sys.stderr,
        )
        return 1

    for destination, size, url, sha256 in missing:
        print(f"下载 {destination.name} …")
        print(f"  来源 {url}")
        try:
            _download(url, destination, size, sha256)
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as error:
            print(f"\n[失败] {destination.name}: {error}", file=sys.stderr)
            print(
                "可修正网络后重新运行本脚本继续下载（已下载部分会保留并续传）。",
                file=sys.stderr,
            )
            return 1
        print(f"  [完成] {destination}")

    print("\n全部模型文件已就绪：")
    for path, size, _, _ in artifacts:
        print(f"  {path}  ({_human(size) if size else '-'})")
    print(
        "\n提示：重启后端后，POST /api/v1/assistant/asr 即可使用。"
        "首次识别会懒加载模型（约 1.1 秒），之后的请求不再有这项开销。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

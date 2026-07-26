"""文本工具 — 中文分词、清洗、分块。"""
from __future__ import annotations

import re
from typing import List

import jieba

# 启用 jieba 精确模式(首次调用会触发初始化，约 100ms)
_jieba_initialized = False


def _ensure_jieba() -> None:
    global _jieba_initialized
    if not _jieba_initialized:
        jieba.initialize()
        _jieba_initialized = True


def tokenize_zh(text: str) -> List[str]:
    """中文分词，返回小写英文/数字 token + 中文词 token。"""
    _ensure_jieba()
    if not text:
        return []
    tokens = []
    for raw in jieba.cut(text, cut_all=False):
        t = raw.strip().lower()
        if not t:
            continue
        # 过滤标点与单字符噪声(中文单字保留)
        if re.fullmatch(r"[\s\W]", t):
            continue
        if len(t) == 1 and not re.match(r"[\u4e00-\u9fa5a-z0-9]", t):
            continue
        tokens.append(t)
    return tokens


def normalize_text(text: str) -> str:
    """统一空白字符，去除首尾空白。

    保留换行结构(把 CRLF 转为 LF，连续空行合并为单空行)，
    以便 markdown 标题/分块逻辑能正确识别行边界。
    连续空格(非换行)合并为单个空格。
    """
    if not text:
        return ""
    # 去 BOM
    if text.startswith("\ufeff"):
        text = text[1:]
    # CRLF / CR 统一为 LF
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 连续空格(非换行)合并为单空格
    text = re.sub(r"[^\S\n]+", " ", text)
    # 连续 3+ 换行合并为 2 换行(保留段落分隔)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int = 400,
    overlap: int = 80,
) -> List[str]:
    """按字符长度切分(中文按字数计)，保留重叠。

    Args:
        chunk_size: 每块字符数(中文按字符计)
        overlap: 相邻块重叠字符数
    """
    if not text:
        return []
    text = normalize_text(text)
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def extract_title_from_markdown(text: str) -> str | None:
    """从 Markdown 提取首个一级标题作为标题。"""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return None


def extract_sections(text: str) -> List[tuple[str, str]]:
    """从 Markdown/普通文本提取小节：返回 [(section_title, content)]。

    若无标题，整体作为一个 section。
    """
    sections: List[tuple[str, str]] = []
    current_title = "正文"
    buffer: List[str] = []

    def flush() -> None:
        if buffer:
            content = "\n".join(buffer).strip()
            if content:
                sections.append((current_title, content))
            buffer.clear()

    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            flush()
            # 去掉 # 前缀
            current_title = s.lstrip("#").strip() or "正文"
        else:
            buffer.append(line)
    flush()
    if not sections:
        sections.append(("正文", text.strip()))
    return sections


__all__ = [
    "tokenize_zh",
    "normalize_text",
    "chunk_text",
    "extract_title_from_markdown",
    "extract_sections",
]

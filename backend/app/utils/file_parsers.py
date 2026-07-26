"""文件解析器 — Markdown / TXT / PDF / DOCX。

每个解析器返回纯文本。失败时抛 ValueError(描述原因)。
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class FileParser(Protocol):
    def parse(self, file_path: Path) -> str:
        """解析文件，返回纯文本。"""
        ...


    @property
    def ext(self) -> str:
        """支持的扩展名(不含点)。"""
        ...


class MarkdownParser:
    ext = "md"

    def parse(self, file_path: Path) -> str:
        # 先以二进制读取,检测 null 字节(二进制内容特征)
        raw = file_path.read_bytes()
        if b"\x00" in raw:
            raise ValueError("文件内容包含 null 字节,疑似二进制文件,无法作为 Markdown 解析")
        # 解码为文本,允许少量替换字符
        return raw.decode("utf-8", errors="replace")


class TextParser:
    ext = "txt"

    def parse(self, file_path: Path) -> str:
        # 尝试常见中文编码
        for encoding in ("utf-8", "gbk", "gb2312", "big5"):
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return file_path.read_text(encoding="utf-8", errors="replace")


class PdfParser:
    ext = "pdf"

    def parse(self, file_path: Path) -> str:
        try:
            from PyPDF2 import PdfReader
        except ImportError as e:
            raise ValueError("未安装 PyPDF2，无法解析 PDF") from e
        reader = PdfReader(str(file_path))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                continue
        text = "\n".join(p for p in pages if p.strip())
        if not text.strip():
            raise ValueError("PDF 内容为空或无法提取文本(可能是扫描件)")
        return text


class DocxParser:
    ext = "docx"

    def parse(self, file_path: Path) -> str:
        try:
            from docx import Document
        except ImportError as e:
            raise ValueError("未安装 python-docx，无法解析 DOCX") from e
        doc = Document(str(file_path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


_PARSERS = {
    "md": MarkdownParser(),
    "markdown": MarkdownParser(),
    "txt": TextParser(),
    "pdf": PdfParser(),
    "docx": DocxParser(),
}


def get_parser(ext: str) -> FileParser:
    ext = ext.lower().lstrip(".")
    parser = _PARSERS.get(ext)
    if parser is None:
        raise ValueError(f"不支持的文件类型: {ext}")
    return parser


def parse_file(file_path: Path) -> str:
    ext = file_path.suffix.lstrip(".").lower()
    parser = get_parser(ext)
    return parser.parse(file_path)


__all__ = ["FileParser", "parse_file", "get_parser"]

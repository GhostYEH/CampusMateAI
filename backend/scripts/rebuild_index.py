"""重建知识库索引脚本。

用法:
    cd backend
    python -m scripts.rebuild_index

或:
    python scripts/rebuild_index.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 把 backend/ 加入 sys.path，使脚本可独立运行
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, logger  # noqa: E402
from app.services.container import build_container  # noqa: E402


def main() -> int:
    settings = get_settings()
    configure_logging(settings)
    container = build_container(settings)

    # 1. 重新导入演示资料(若已存在则跳过)
    added = container.knowledge_ingestion.import_demo_documents()
    if added:
        logger.info("新增演示资料 {} 份", added)
    else:
        logger.info("无新增演示资料(已存在或目录为空)")

    # 2. 重建索引
    chunk_count = container.knowledge_ingestion.rebuild_index()
    doc_count = container.document_repository.count_documents()
    logger.info(
        "索引重建完成: {} 份文档, {} 个分块, 检索方式={}",
        doc_count, chunk_count, "bm25",
    )
    print(
        f"\n索引重建完成:\n"
        f"  文档数: {doc_count}\n"
        f"  分块数: {chunk_count}\n"
        f"  检索方式: bm25\n"
        f"  知识库目录: {settings.knowledge_base_dir}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

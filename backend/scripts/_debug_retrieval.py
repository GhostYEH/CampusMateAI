"""临时调试脚本 — 检索评分分析(用完即删)。"""
import os

os.environ.setdefault("LLM_PROVIDER", "none")
os.environ.setdefault("ENABLE_FALLBACK_MODE", "true")

from app.core.config import get_settings

get_settings.cache_clear()
s = get_settings()

from app.database.sqlite_db import init_db
from app.repositories.document_repository import DocumentRepository
from app.services.knowledge_ingestion_service import KnowledgeIngestionService
from app.services.retrieval_service import (
    RetrievalService,
    _filter_query_tokens,
    _expand_synonyms,
)
from app.utils.text_utils import tokenize_zh

db = init_db(s)
repo = DocumentRepository(db)
ret = RetrievalService(repo)
ing = KnowledgeIngestionService(repo, ret, s)
ing.import_demo_documents()
ret.rebuild()

# 2-token queries that should pass
queries_2tok = [
    ("国家奖助学金", "校级奖学金申请办法"),
    ("暑期实践", "社会实践学分申请指南"),
    ("纸质版材料应该交到哪里", "社会实践学分申请指南"),
    ("选课", "课程补退选流程"),
    ("实践", "社会实践学分申请指南"),
    ("奖学金", "校级奖学金申请办法"),
]

# 3+ token queries that should be rejected
queries_reject = [
    "考研报名流程",
    "宿舍怎么分配",
    "学费一学年多少钱",
]

print("=== 2-token queries that should pass ===")
for q, expected in queries_2tok:
    toks = tokenize_zh(q)
    ct = _filter_query_tokens(toks)
    et = _expand_synonyms(toks)
    scores = ret._bm25.get_scores(et)
    max_s = max(scores)
    top_idx = scores.argmax()
    top_title = ret._doc_by_id[ret._chunks[top_idx].document_id].title
    print(f"  {q}: content={ct} max_score={max_s:.3f} top={top_title}")

print()
print("=== Queries that should be rejected ===")
for q in queries_reject:
    toks = tokenize_zh(q)
    ct = _filter_query_tokens(toks)
    et = _expand_synonyms(toks)
    scores = ret._bm25.get_scores(et)
    max_s = max(scores)
    top_idx = scores.argmax()
    top_title = ret._doc_by_id[ret._chunks[top_idx].document_id].title
    print(f"  {q}: content={ct} max_score={max_s:.3f} top={top_title}")

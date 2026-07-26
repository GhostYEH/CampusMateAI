"""检索服务 — 基于 BM25 + jieba 中文分词的本地检索。

设计要点：
- 与向量数据库解耦：业务层只调用 `RetrievalService.search(query, k)`。
- 当前实现 BM25，预留 vector/hybrid 接口。
- 检索后按文档元数据排序：未过期 > 过期，官方 > 非官方，更新时间新 > 旧。
- 双阈值过滤：绝对阈值(过滤全局弱匹配) + 相对阈值(过滤局部弱匹配)。
- 多路召回: 复杂查询按标点拆分为子查询，每个子意图独立检索后合并。
"""
from __future__ import annotations

import math
import re
import threading
from typing import List

from rank_bm25 import BM25Okapi

from ..models.document import ChunkRow, DocumentRow, RetrievedChunk
from ..repositories.document_repository import DocumentRepository
from ..utils.text_utils import tokenize_zh


# 中文常见停用词 — 这些词在校园文档中高频出现但区分度低，
# 不应作为主要匹配依据。若查询分词后仅剩停用词，视为无有效关键词。
_STOPWORDS = frozenset({
    "是", "的", "了", "在", "和", "与", "或", "也", "都", "还", "就", "又",
    "你", "我", "他", "她", "它", "你们", "我们", "他们", "这", "那", "这个", "那个",
    "什么", "怎么", "为什么", "哪里", "哪个", "多少", "几", "可以", "能", "会",
    "要", "需要", "想", "做", "办", "弄", "去", "来", "到", "给", "对", "向",
    "把", "被", "让", "使", "为", "对于", "关于", "通过", "根据", "按照",
    "以及", "及", "等", "之类", "什么的", "之类",
    "年", "月", "日", "号", "今天", "明天", "昨天", "现在", "以后", "以前",
    "因为", "所以", "但是", "不过", "虽然", "尽管", "如果", "假如", "万一",
    "请问", "请", "麻烦", "谢谢", "感谢",
})


def _filter_query_tokens(tokens: List[str]) -> List[str]:
    """过滤查询 token 中的停用词，保留有区分度的关键词。"""
    return [t for t in tokens if t not in _STOPWORDS]


# 子查询分隔符: 问号、分号、逗号、换行
# 问号是强分隔(疑问句边界),其他是弱分隔。
_SPLIT_PATTERN = re.compile(r"[?？;；\n]+")


def _split_query(query: str) -> List[str]:
    """把复杂查询拆分为子查询。

    示例:
        "申请校级奖学金需要满足什么条件？一等奖学金多少钱？"
        -> ["申请校级奖学金需要满足什么条件", "一等奖学金多少钱"]

    "社会实践学时不够怎么办？材料丢了能补办吗？"
        -> ["社会实践学时不够怎么办", "材料丢了能补办吗"]

    单一问题(无分隔符)返回 [query]。
    空字符串或纯标点返回 []。
    """
    if not query or not query.strip():
        return []
    parts = _SPLIT_PATTERN.split(query)
    result: List[str] = []
    for p in parts:
        p = p.strip()
        # 过滤掉过短的片段(少于 2 个有效字符)
        if len(p) >= 2:
            result.append(p)
    # 若拆分后只有 1 个子查询,直接返回;
    # 若拆分出多个但都很短(如"呢""啊"),回退到原查询
    if not result:
        result = [query.strip()]
    return result


class RetrievalService:
    """BM25 检索服务(线程安全)。"""

    def __init__(self, repository: DocumentRepository) -> None:
        self._repo = repository
        self._lock = threading.RLock()
        self._bm25: BM25Okapi | None = None
        self._chunks: List[ChunkRow] = []
        self._tokenized: List[List[str]] = []
        self._token_sets: List[set[str]] = []  # 每个 chunk 的 token 集合(用于 token overlap 检查)
        self._doc_by_id: dict[str, DocumentRow] = {}
        self._needs_rebuild = True

    def rebuild(self) -> int:
        """重建索引。返回被索引的 chunk 数。"""
        with self._lock:
            chunks = self._repo.list_chunks()
            docs = self._repo.list_documents()
            self._doc_by_id = {d.document_id: d for d in docs}
            self._chunks = chunks
            self._tokenized = [tokenize_zh(c.content) for c in chunks]
            self._token_sets = [set(ts) for ts in self._tokenized]
            if chunks:
                self._bm25 = BM25Okapi(self._tokenized)
            else:
                self._bm25 = None
            self._needs_rebuild = False
            return len(chunks)

    def mark_stale(self) -> None:
        """标记索引需要重建(下次检索前会自动重建)。"""
        with self._lock:
            self._needs_rebuild = True

    @property
    def is_ready(self) -> bool:
        return self._bm25 is not None and len(self._chunks) > 0

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def list_chunks_for_document(self, document_id: str) -> List[ChunkRow]:
        """返回指定文档的所有 chunk(用于同文档扩展)。"""
        with self._lock:
            if self._needs_rebuild or self._bm25 is None:
                self._rebuild_locked()
            return [c for c in self._chunks if c.document_id == document_id]

    def get_document(self, document_id: str) -> DocumentRow | None:
        """返回指定文档元数据。"""
        with self._lock:
            if self._needs_rebuild or self._bm25 is None:
                self._rebuild_locked()
            return self._doc_by_id.get(document_id)

    def search(
        self,
        query: str,
        k: int = 5,
        *,
        min_score: float = 0.0,
        min_absolute_score: float = 2.0,
        min_score_ratio: float = 0.35,
        min_overlap_ratio: float = 0.5,
    ) -> List[RetrievedChunk]:
        """检索 top-k 相关 chunk。

        四层过滤确保不返回弱相关或无关结果：
        1. token overlap: chunk 至少包含 min_overlap_ratio 比例的非停用词查询 token
        2. 绝对阈值: 原始 BM25 分数 >= min_absolute_score
        3. 相对阈值: 原始 BM25 分数 >= min_score_ratio * 最大原始分数
        4. 最小匹配数: 至少匹配 1 个 content token(overlap_ratio 的下界)

        Args:
            query: 用户查询文本
            k: 返回数量上限
            min_score: 保留兼容(已弃用，使用 min_absolute_score)
            min_absolute_score: 原始 BM25 分数绝对阈值
            min_score_ratio: 相对最大分数的阈值(0~1)
            min_overlap_ratio: chunk 至少匹配 content token 的比例(0~1)
        """
        if not query or not query.strip():
            return []
        # 多路召回: 把复杂查询按标点拆成子查询,
        # 每个子查询单独检索,结果合并去重。
        # 这样能避免"申请条件 + 一等奖学金多少钱"这类多意图查询
        # 因相对阈值过滤漏召相关 chunk 的问题。
        sub_queries = _split_query(query)
        if not sub_queries:
            return []
        merged: dict[str, RetrievedChunk] = {}
        for sq in sub_queries:
            results = self._search_single(
                sq,
                k=k,
                min_score=min_score,
                min_absolute_score=min_absolute_score,
                min_score_ratio=min_score_ratio,
                min_overlap_ratio=min_overlap_ratio,
            )
            for rc in results:
                cid = rc.chunk.chunk_id
                if cid not in merged:
                    merged[cid] = rc
                else:
                    # 保留较高分数
                    if rc.score > merged[cid].score:
                        merged[cid] = rc
        indexed = sorted(
            merged.values(),
            key=lambda rc: _rank_key(rc),
            reverse=True,
        )
        return indexed[:k]

    def _search_single(
        self,
        query: str,
        *,
        k: int,
        min_score: float,
        min_absolute_score: float,
        min_score_ratio: float,
        min_overlap_ratio: float,
    ) -> List[RetrievedChunk]:
        """对单个子查询执行 BM25 检索。"""
        with self._lock:
            if self._needs_rebuild or self._bm25 is None:
                self._rebuild_locked()
            if self._bm25 is None or not self._chunks:
                return []
            bm25 = self._bm25
            chunks = self._chunks
            token_sets = list(self._token_sets)
            doc_by_id = dict(self._doc_by_id)
        # 释放锁后再做打分(纯计算)
        tokens = tokenize_zh(query)
        if not tokens:
            return []
        # 过滤停用词，保留有区分度的关键词
        content_tokens = _filter_query_tokens(tokens)
        if not content_tokens:
            # 查询全部由停用词组成，无法有效检索
            return []
        content_token_set = set(content_tokens)
        # 最小匹配 token 数：
        # - 至少 1 个
        # - 查询长度 >= 2 时要求至少 2 个 token 匹配(避免单字弱匹配)
        # - 查询较长时要求更高比例
        base_min = 2 if len(content_tokens) >= 2 else 1
        min_overlap_count = max(base_min, math.ceil(len(content_tokens) * min_overlap_ratio))
        scores = bm25.get_scores(tokens)
        # 双阈值：绝对阈值 + 相对阈值
        max_score = float(max(scores)) if len(scores) > 0 else 0.0
        if max_score <= 0:
            return []
        absolute_threshold = max(min_score, min_absolute_score)
        relative_threshold = max_score * min_score_ratio
        effective_threshold = max(absolute_threshold, relative_threshold)
        indexed = sorted(
            (
                RetrievedChunk(
                    chunk=chunks[i],
                    document=doc_by_id.get(chunks[i].document_id),  # type: ignore
                    score=float(scores[i]) / max_score if max_score > 0 else 0.0,
                )
                for i in range(len(chunks))
                if scores[i] >= effective_threshold
                and doc_by_id.get(chunks[i].document_id) is not None
                and len(token_sets[i] & content_token_set) >= min_overlap_count
            ),
            key=lambda rc: _rank_key(rc),
            reverse=True,
        )
        return indexed[:k]

    def _rebuild_locked(self) -> None:
        chunks = self._repo.list_chunks()
        docs = self._repo.list_documents()
        self._doc_by_id = {d.document_id: d for d in docs}
        self._chunks = chunks
        self._tokenized = [tokenize_zh(c.content) for c in chunks]
        self._token_sets = [set(ts) for ts in self._tokenized]
        if chunks:
            self._bm25 = BM25Okapi(self._tokenized)
        else:
            self._bm25 = None
        self._needs_rebuild = False


def _rank_key(rc: RetrievedChunk) -> float:
    """综合排序键：相关度为主，元数据加权为辅。

    - 未过期 > 过期：+0.15
    - 官方 > 非官方：+0.10
    - 更新时间较新者加分(在最后 30 天内 +0.05)
    - 相关度 0~1 作为基础
    """
    score = max(0.0, rc.score)
    if rc.document is not None:
        if not rc.document.is_expired:
            score += 0.15
        if rc.document.is_official:
            score += 0.10
    return score


__all__ = ["RetrievalService"]

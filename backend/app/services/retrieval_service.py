"""检索服务 — 基于 BM25 + jieba 中文分词的本地检索。

设计要点：
- 与向量数据库解耦：业务层只调用 `RetrievalService.search(query, k)`。
- 当前实现 BM25，预留 vector/hybrid 接口。
- 检索后按文档元数据排序：未过期 > 过期，官方 > 非官方，
  更新时间较新者获得 freshness bonus(线性衰减，30 天内满额，365 天后归零)。
- 双阈值过滤：绝对阈值(过滤全局弱匹配) + 相对阈值(过滤局部弱匹配)。
- 多路召回: 复杂查询按标点拆分为子查询，每个子意图独立检索后合并。
- 校园术语同义词规范化(对称扩展): 奖助学金↔奖学金、暑期实践↔社会实践、政策↔办法 等。
- 标题与小节字段加权(在索引端重复 token，提升 BM25 权重)。
- 短查询回退: 有效 token ≤ 2 时降低 min_overlap 至 1，避免短关键词命中失败。
- 元数据加权合计上限 +0.30(未过期 +0.15 / 官方 +0.10 / 新鲜度 +0.05)，
  不会覆盖明显更高的语义相关性(0.6+0.30=0.9 < 1.0)。
"""
from __future__ import annotations

import math
import re
import threading
from datetime import datetime, timezone
from typing import List, Optional

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
    # 助词 / 语气词 / 量词类噪声
    "吗", "呢", "吧", "啊", "呀", "哦", "哈", "嘿",
    "版", "应该", "应当", "还能", "还能用", "才能", "拿到", "交到", "怎么",
    "这个", "那个", "这些", "那些",
    # 疑问时间词 / 元数据词(在校园文档中不承载具体语义)
    "哪天", "哪年", "哪月", "几号", "几点", "时候", "最新", "版本", "日期",
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


# ============================================================
# 校园术语同义词 — 对称扩展
# ============================================================
# 定向同义词(单向声明，构建时会扩展为对称)。
# 仅收录校园场景下高频等价的术语，避免过度扩展导致噪声。
_CAMPUS_SYNONYM_DIRECTED: dict[str, list[str]] = {
    "奖助学金": ["奖学金"],
    "暑期实践": ["社会实践"],
    "暑期社会实践": ["社会实践"],
    "政策": ["办法", "规定", "细则"],
    "规定": ["办法", "政策", "细则"],
    "细则": ["办法", "政策", "规定"],
    "艺术节": ["活动", "文化节"],
    "文化节": ["活动", "艺术节"],
    "校园文化节": ["活动", "艺术节"],
    "纸质版": ["纸质", "纸质材料"],
    "纸质材料": ["纸质", "纸质版"],
    "材料提交": ["提交材料", "上交材料"],
    "上交材料": ["提交材料", "材料提交"],
    "评选": ["评定", "评审", "申请"],
    "评定": ["评选", "评审"],
    "评审": ["评选", "评定"],
    "办公室": ["办公室地点", "办理地点"],
    "办理地点": ["办公室", "办公室地点"],
    "截止日期": ["截止时间", "deadline"],
    "截止时间": ["截止日期", "deadline"],
    "申请条件": ["评选条件", "评定条件"],
    "评选条件": ["申请条件", "评定条件"],
    "评定条件": ["申请条件", "评选条件"],
}


def _build_symmetric_synonyms(directed: dict[str, list[str]]) -> dict[str, list[str]]:
    """把定向同义词扩展为对称同义词图。

    任意两个互为同义词的词，无论从哪一端查询都能拿到对方。
    同义词去重，不重复添加。
    """
    result: dict[str, list[str]] = {}
    for key, syns in directed.items():
        bucket = result.setdefault(key, [])
        for s in syns:
            if s not in bucket:
                bucket.append(s)
        for s in syns:
            s_bucket = result.setdefault(s, [])
            if key not in s_bucket:
                s_bucket.append(key)
            # 传递同义: A↔B, A↔C ⇒ B↔C
            for other in syns:
                if other != s and other not in s_bucket:
                    s_bucket.append(other)
    return result


_CAMPUS_SYNONYMS: dict[str, list[str]] = _build_symmetric_synonyms(_CAMPUS_SYNONYM_DIRECTED)


def _expand_synonyms(tokens: List[str]) -> List[str]:
    """对 token 列表做同义词扩展(追加同义词，不替换原 token)。

    保持顺序: [原 token..., 同义词...]
    去重: 同一 token 不重复出现。
    """
    if not tokens:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for t in tokens:
        if t not in seen:
            result.append(t)
            seen.add(t)
        syns = _CAMPUS_SYNONYMS.get(t)
        if syns:
            for s in syns:
                if s not in seen:
                    result.append(s)
                    seen.add(s)
    return result


# ============================================================
# 时间解析与新鲜度加分
# ============================================================
_ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """解析 ISO 8601 时间字符串，失败返回 None。

    支持形如:
        2025-01-15
        2025-01-15T10:30:00
        2025-01-15T10:30:00Z
        2025-01-15T10:30:00+08:00
    """
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s or not _ISO_PATTERN.match(s):
        return None
    try:
        # 兼容带 Z 后缀的 ISO 字符串
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        return dt
    except ValueError:
        return None


def _freshness_bonus(
    doc: DocumentRow,
    *,
    recent_window_days: int = 30,
    decay_days: int = 365,
    max_bonus: float = 0.05,
) -> float:
    """根据文档时间字段计算新鲜度加分。

    规则:
    - 过期文档(is_expired=True) → 0
    - updated_at 优先,缺失时回退到 published_at
    - 30 天内 → max_bonus (0.05)
    - 30 ~ 365 天 → 线性衰减
    - 超过 365 天 → 0
    - 无时间字段 → 0
    - 时间为未来 → max_bonus (容错)
    """
    if doc.is_expired:
        return 0.0
    dt = _parse_dt(doc.updated_at) or _parse_dt(doc.published_at)
    if dt is None:
        return 0.0
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_days = (now - dt).total_seconds() / 86400.0
    if age_days < 0:
        return max_bonus
    if age_days <= recent_window_days:
        return max_bonus
    if age_days >= decay_days:
        return 0.0
    ratio = 1.0 - (age_days - recent_window_days) / (decay_days - recent_window_days)
    return max_bonus * max(0.0, min(1.0, ratio))


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
            self._tokenized = [self._tokenize_for_index(c, self._doc_by_id.get(c.document_id)) for c in chunks]
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

    @staticmethod
    def _tokenize_for_index(chunk: ChunkRow, doc: Optional[DocumentRow]) -> List[str]:
        """索引端分词 — 标题和小节字段加权(重复 token 提升权重)，并应用同义词扩展。

        加权策略:
        - 标题 ×2 (重复 1 次)
        - 小节标题 ×2 (重复 1 次)
        - 正文 ×1
        - 同义词扩展追加(不重复原 token)
        """
        parts: List[str] = []
        if doc is not None and doc.title:
            parts.append(doc.title)
            parts.append(doc.title)  # 标题加权 ×2
        if chunk.section:
            parts.append(chunk.section)
            parts.append(chunk.section)  # 小节加权 ×2
        if chunk.content:
            parts.append(chunk.content)
        text = " ".join(parts) if parts else ""
        tokens = tokenize_zh(text)
        return _expand_synonyms(tokens)

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
           (短查询 ≤2 token 触发 fallback, min_overlap=1)
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
            # 全局 token 集合(用于判断查询 token 是否在语料中出现)
            global_token_set = set()
            for ts in token_sets:
                global_token_set |= ts
        # 释放锁后再做打分(纯计算)
        tokens = tokenize_zh(query)
        if not tokens:
            return []
        # 过滤停用词，保留有区分度的关键词
        content_tokens = _filter_query_tokens(tokens)
        if not content_tokens:
            # 查询全部由停用词组成，无法有效检索
            return []
        # 查询端也做同义词扩展(让 "奖助学金" 能命中 "奖学金" 文档)
        expanded_tokens = _expand_synonyms(tokens)
        # overlap 检查使用扩展后的 token 集合，
        # 这样查询中的 "政策" 能与文档中的 "办法"(同义词) 匹配。
        # 但 min_overlap_count 仍按原始 content_tokens 数量计算，
        # 避免因同义词扩展导致 min_overlap 过低。
        expanded_content_set = set(_filter_query_tokens(expanded_tokens))
        # 检测未知 content token(扩展后仍不在任何文档中) —
        # 未知 token 通常是查询的判别性关键词(如"考研""宿舍"),
        # 若存在未知 token, 提高匹配要求以避免公共词误匹配。
        unknown_content_tokens = [
            t for t in content_tokens
            if t not in global_token_set
            and not any(s in global_token_set for s in _CAMPUS_SYNONYMS.get(t, []))
        ]
        has_unknown = len(unknown_content_tokens) > 0
        # 最小匹配 token 数：
        # - 1 token 短查询: min_overlap = 1 (单 token 无法要求更多)
        # - 2 token 短查询: min_overlap = 2 (两个都须匹配,避免单 token 误匹配)
        #   除非通过同义词扩展命中(此时 expanded_content_set 更大)
        # - 3+ token 普通查询: 至少 2 个 token 匹配
        # - 若存在未知 token(判别性词不在语料), min_overlap +1
        #   (避免仅靠公共词匹配返回无关结果)
        if len(content_tokens) == 1:
            min_overlap_count = 1
            # 单 token BM25 分数天然较低，降低绝对阈值至 0.5
            short_absolute = min(min_absolute_score, 0.5)
        elif len(content_tokens) == 2:
            min_overlap_count = 2
            short_absolute = min(min_absolute_score, 1.0)
        else:
            base_min = 2
            min_overlap_count = max(base_min, math.ceil(len(content_tokens) * min_overlap_ratio))
            short_absolute = min_absolute_score
        if has_unknown:
            min_overlap_count += 1
        scores = bm25.get_scores(expanded_tokens)
        # 双阈值：绝对阈值 + 相对阈值
        max_score = float(max(scores)) if len(scores) > 0 else 0.0
        if max_score <= 0:
            return []
        absolute_threshold = max(min_score, short_absolute)
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
                and len(token_sets[i] & expanded_content_set) >= min_overlap_count
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
        self._tokenized = [self._tokenize_for_index(c, self._doc_by_id.get(c.document_id)) for c in chunks]
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
    - 更新时间较新者加分(freshness bonus, 0 ~ 0.05)
    - 相关度 0~1 作为基础

    元数据加权合计上限 +0.30，确保不会覆盖明显更高的语义相关性
    (例: BM25=1.0 的过期非官方文档 > BM25=0.6 的未过期官方文档)。
    """
    score = max(0.0, rc.score)
    if rc.document is not None:
        if not rc.document.is_expired:
            score += 0.15
        if rc.document.is_official:
            score += 0.10
        score += _freshness_bonus(rc.document)
    return score


__all__ = ["RetrievalService"]

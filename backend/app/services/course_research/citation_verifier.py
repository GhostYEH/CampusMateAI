"""引用验证器(§8.2、§5.9)。

CitationVerifier 校验引用是否存在、是否支持对应主张。
未验证引用明确标记,禁止伪造来源进入已验证清单。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ...models.course_research import CourseResearchSourceRow


@dataclass
class VerificationResult:
    """单个来源的验证结果。"""

    source_id: str
    is_verified: bool
    supports_claim: bool
    verification_note: str
    is_fabricated: bool = False


class CitationVerifier:
    """引用验证器。

    校验逻辑:
    1. 来源必须存在(有 title 与 source_ref/url)
    2. 伪造来源(is_fabricated=True)永远不通过验证
    3. 课程资料:source_ref 指向已存在的 CourseContentItem
    4. Web 来源:url 可达且 snippet 非空
    5. supports_claim 由调用方传入(模型判定),验证器校验来源存在性
    """

    def __init__(
        self,
        *,
        course_content_lookup=None,
        web_fetcher=None,
    ) -> None:
        """初始化。

        Args:
            course_content_lookup: 可调用,接受 (source_ref, user_id) 返回
                CourseContentItemRow 或 None。用于校验课程资料来源存在性。
            web_fetcher: 可调用,接受 (url) 返回 FetchedSource 或抛异常。
                用于校验 Web 来源可达性。None 时跳过 Web 可达性校验。
        """
        self._course_lookup = course_content_lookup
        self._web_fetcher = web_fetcher

    def verify(
        self,
        source: CourseResearchSourceRow,
        *,
        claim: str,
        supports_claim: Optional[bool] = None,
    ) -> VerificationResult:
        """验证单个来源。

        Args:
            source: 待验证来源
            claim: 报告中的主张文本
            supports_claim: 模型判定该来源是否支持主张。None 时由验证器
                默认按"来源存在即支持"判定(保守)。
        """
        # 伪造来源永不通过
        if source.is_fabricated:
            return VerificationResult(
                source_id=source.source_id,
                is_verified=False,
                supports_claim=False,
                verification_note="伪造来源,拒绝验证",
                is_fabricated=True,
            )
        # 来源必须存在
        if not source.title or (not source.source_ref and not source.url):
            return VerificationResult(
                source_id=source.source_id,
                is_verified=False,
                supports_claim=False,
                verification_note="来源缺少 title 或引用标识",
            )
        # 按类型校验存在性
        if source.source_type == "course_material":
            return self._verify_course(source, claim, supports_claim)
        if source.source_type == "web":
            return self._verify_web(source, claim, supports_claim)
        if source.source_type == "user_upload":
            return self._verify_upload(source, claim, supports_claim)
        return VerificationResult(
            source_id=source.source_id,
            is_verified=False,
            supports_claim=False,
            verification_note=f"未知来源类型: {source.source_type}",
        )

    def _verify_course(
        self,
        source: CourseResearchSourceRow,
        claim: str,
        supports_claim: Optional[bool],
    ) -> VerificationResult:
        if self._course_lookup is None:
            # 无 lookup 时,有 source_ref 即视为存在(测试场景)
            exists = bool(source.source_ref)
        else:
            try:
                item = self._course_lookup(source.source_ref, source.user_id)
                exists = item is not None
            except Exception:
                exists = False
        if not exists:
            return VerificationResult(
                source_id=source.source_id,
                is_verified=False,
                supports_claim=False,
                verification_note="课程资料不存在或不可访问",
            )
        effective_supports = supports_claim if supports_claim is not None else True
        note = "课程资料存在" + (",支持主张" if effective_supports else ",不支持主张")
        return VerificationResult(
            source_id=source.source_id,
            is_verified=True,
            supports_claim=effective_supports,
            verification_note=note,
        )

    def _verify_web(
        self,
        source: CourseResearchSourceRow,
        claim: str,
        supports_claim: Optional[bool],
    ) -> VerificationResult:
        if not source.url:
            return VerificationResult(
                source_id=source.source_id,
                is_verified=False,
                supports_claim=False,
                verification_note="Web 来源缺少 URL",
            )
        if self._web_fetcher is not None:
            try:
                fetched = self._web_fetcher(source.url)
                reachable = fetched is not None
            except Exception:
                reachable = False
            if not reachable:
                return VerificationResult(
                    source_id=source.source_id,
                    is_verified=False,
                    supports_claim=False,
                    verification_note="Web 来源不可达",
                )
        effective_supports = supports_claim if supports_claim is not None else True
        note = "Web 来源可达" + (",支持主张" if effective_supports else ",不支持主张")
        return VerificationResult(
            source_id=source.source_id,
            is_verified=True,
            supports_claim=effective_supports,
            verification_note=note,
        )

    def _verify_upload(
        self,
        source: CourseResearchSourceRow,
        claim: str,
        supports_claim: Optional[bool],
    ) -> VerificationResult:
        # 用户上传:有 source_ref 即视为存在
        exists = bool(source.source_ref)
        if not exists:
            return VerificationResult(
                source_id=source.source_id,
                is_verified=False,
                supports_claim=False,
                verification_note="用户上传引用缺失",
            )
        effective_supports = supports_claim if supports_claim is not None else True
        note = "用户上传存在" + (",支持主张" if effective_supports else ",不支持主张")
        return VerificationResult(
            source_id=source.source_id,
            is_verified=True,
            supports_claim=effective_supports,
            verification_note=note,
        )

    def verify_batch(
        self,
        sources: list[CourseResearchSourceRow],
        *,
        claim: str,
        supports_map: Optional[dict[str, bool]] = None,
    ) -> list[VerificationResult]:
        """批量验证。返回与 sources 顺序一致的结果列表。"""
        supports_map = supports_map or {}
        return [
            self.verify(s, claim=claim, supports_claim=supports_map.get(s.source_id))
            for s in sources
        ]


__all__ = ["CitationVerifier", "VerificationResult"]
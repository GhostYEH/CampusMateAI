"""课程研究来源与 SSRF 安全测试(§8.2、§11)。

覆盖:
- SSRF 私网/本地/loopback/link-local 拒绝
- 协议/主机检查
- source_policy 越权素材拒绝
- citation verified/unverified,伪造来源不能进入已验证清单
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.core.exceptions import AgentSourcePolicyViolation
from app.models.course_research import CourseResearchSourceRow
from app.services.course_research.citation_verifier import CitationVerifier
from app.services.course_research.source_fetcher import (
    ControlledSourceFetcher,
    SSRFViolation,
    validate_url,
)


class TestSSRFProtection:
    def test_https_allowed(self):
        url = validate_url("https://example.com/path")
        assert url == "https://example.com/path"

    def test_http_allowed(self):
        assert validate_url("http://example.com") == "http://example.com"

    def test_ftp_rejected(self):
        with pytest.raises(SSRFViolation, match="协议"):
            validate_url("ftp://example.com")

    def test_file_rejected(self):
        with pytest.raises(SSRFViolation, match="协议"):
            validate_url("file:///etc/passwd")

    def test_loopback_ipv4_rejected(self):
        with pytest.raises(SSRFViolation, match="私网|本地"):
            validate_url("http://127.0.0.1/")

    def test_loopback_ipv6_rejected(self):
        with pytest.raises(SSRFViolation, match="私网|本地"):
            validate_url("http://[::1]/")

    def test_private_10_rejected(self):
        with pytest.raises(SSRFViolation, match="私网|本地"):
            validate_url("http://10.0.0.1/")

    def test_private_172_rejected(self):
        with pytest.raises(SSRFViolation, match="私网|本地"):
            validate_url("http://172.16.0.1/")

    def test_private_192_rejected(self):
        with pytest.raises(SSRFViolation, match="私网|本地"):
            validate_url("http://192.168.1.1/")

    def test_link_local_rejected(self):
        with pytest.raises(SSRFViolation, match="私网|本地"):
            validate_url("http://169.254.1.1/")

    def test_no_host_rejected(self):
        with pytest.raises(SSRFViolation, match="主机"):
            validate_url("http://")

    def test_empty_url_rejected(self):
        with pytest.raises(SSRFViolation, match="空"):
            validate_url("")

    def test_localhost_hostname_rejected(self):
        # localhost 通常解析到 127.0.0.1
        with pytest.raises(SSRFViolation, match="私网|本地"):
            validate_url("http://localhost/")

    def test_metadata_gcp_rejected(self):
        # GCP metadata 169.254.169.254
        with pytest.raises(SSRFViolation, match="私网|本地"):
            validate_url("http://169.254.169.254/")


class TestControlledFetcherPolicy:
    @pytest.mark.asyncio
    async def test_allow_web_false_rejects(self):
        fetcher = ControlledSourceFetcher()
        with pytest.raises(AgentSourcePolicyViolation):
            await fetcher.fetch("https://example.com", allow_web=False)


class TestCitationVerifier:
    def _make_source(
        self, *, source_type="course_material", title="测试来源",
        source_ref="ref_1", url=None, is_fabricated=False,
    ) -> CourseResearchSourceRow:
        now = datetime.now(timezone.utc).isoformat()
        return CourseResearchSourceRow(
            source_id="src_1",
            session_id="sess_1",
            user_id="u1",
            source_type=source_type,
            title=title,
            url=url,
            accessed_at=now,
            created_at=now,
            source_ref=source_ref,
            is_fabricated=is_fabricated,
        )

    def test_course_material_verified(self):
        verifier = CitationVerifier(
            course_content_lookup=lambda ref, uid: object(),  # 存在
        )
        src = self._make_source()
        result = verifier.verify(src, claim="某主张")
        assert result.is_verified
        assert result.supports_claim

    def test_course_material_not_found(self):
        verifier = CitationVerifier(
            course_content_lookup=lambda ref, uid: None,
        )
        src = self._make_source()
        result = verifier.verify(src, claim="某主张")
        assert not result.is_verified
        assert not result.supports_claim

    def test_fabricated_never_verified(self):
        verifier = CitationVerifier(
            course_content_lookup=lambda ref, uid: object(),
        )
        src = self._make_source(is_fabricated=True)
        result = verifier.verify(src, claim="某主张")
        assert not result.is_verified
        assert result.is_fabricated
        assert "伪造" in result.verification_note

    def test_web_source_verified(self):
        verifier = CitationVerifier(web_fetcher=lambda url: object())
        src = self._make_source(
            source_type="web", source_ref=None, url="https://example.com/doc",
        )
        result = verifier.verify(src, claim="某主张")
        assert result.is_verified

    def test_web_source_unreachable(self):
        def fail(url):
            raise RuntimeError("unreachable")
        verifier = CitationVerifier(web_fetcher=fail)
        src = self._make_source(
            source_type="web", source_ref=None, url="https://example.com/doc",
        )
        result = verifier.verify(src, claim="某主张")
        assert not result.is_verified

    def test_web_source_missing_url(self):
        verifier = CitationVerifier()
        src = self._make_source(
            source_type="web", source_ref=None, url=None,
        )
        result = verifier.verify(src, claim="某主张")
        assert not result.is_verified

    def test_supports_claim_false_propagates(self):
        verifier = CitationVerifier(
            course_content_lookup=lambda ref, uid: object(),
        )
        src = self._make_source()
        result = verifier.verify(src, claim="某主张", supports_claim=False)
        assert result.is_verified
        assert not result.supports_claim

    def test_batch_preserves_order(self):
        verifier = CitationVerifier(
            course_content_lookup=lambda ref, uid: object(),
        )
        sources = [
            self._make_source(),
            self._make_source(is_fabricated=True),
        ]
        results = verifier.verify_batch(sources, claim="某主张")
        assert len(results) == 2
        assert results[0].is_verified
        assert not results[1].is_verified

    def test_fabricated_excluded_from_verified(self):
        """伪造来源不能进入已验证清单。"""
        verifier = CitationVerifier(
            course_content_lookup=lambda ref, uid: object(),
        )
        sources = [
            self._make_source(),  # 真实
            self._make_source(is_fabricated=True),  # 伪造
        ]
        results = verifier.verify_batch(sources, claim="某主张")
        verified = [s for s, r in zip(sources, results) if r.is_verified and r.supports_claim]
        assert len(verified) == 1
        assert not verified[0].is_fabricated

    def test_missing_title_rejected(self):
        verifier = CitationVerifier()
        src = self._make_source(title="")
        result = verifier.verify(src, claim="某主张")
        assert not result.is_verified

    def test_unknown_source_type_rejected(self):
        verifier = CitationVerifier()
        src = self._make_source(source_type="unknown")
        result = verifier.verify(src, claim="某主张")
        assert not result.is_verified

    def test_user_upload_verified(self):
        verifier = CitationVerifier()
        src = self._make_source(source_type="user_upload", source_ref="upload_1")
        result = verifier.verify(src, claim="某主张")
        assert result.is_verified

    def test_user_upload_missing_ref(self):
        verifier = CitationVerifier()
        src = self._make_source(source_type="user_upload", source_ref=None)
        result = verifier.verify(src, claim="某主张")
        assert not result.is_verified
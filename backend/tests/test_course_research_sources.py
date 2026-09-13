import pytest

from app.core.exceptions import AppException
from app.models.course_research import VerifiedResearchSource
from app.services.course_research.citation_verifier import order_verified_sources
from app.services.course_research.source_fetcher import validate_public_url, validate_redirect_chain


def _resolver(_host, _port):
    return [(None, None, None, None, ("93.184.216.34", 443))]


def _private_resolver(_host, _port):
    return [(None, None, None, None, ("10.0.0.8", 443))]


def test_dns_private_target_and_redirect_escape_are_rejected():
    with pytest.raises(AppException):
        validate_public_url("https://internal.example/path", resolver=_private_resolver)
    with pytest.raises(AppException):
        validate_redirect_chain(
            ["https://example.com/start", "http://127.0.0.1/admin"], resolver=_resolver
        )


def test_verified_course_sources_outrank_web_and_unverified_sources_are_removed():
    ordered = order_verified_sources([
        VerifiedResearchSource("WEB", "公开网页", "a"),
        VerifiedResearchSource("COURSE_MATERIAL", "课程讲义", "b"),
        VerifiedResearchSource("WEB", "未核验网页", "c", "UNVERIFIED"),
    ])
    assert [source.safe_label for source in ordered] == ["课程讲义", "公开网页"]

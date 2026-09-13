import pytest

from app.core.exceptions import AppException
from app.services.course_research.source_fetcher import validate_public_url


@pytest.mark.parametrize("url",["http://127.0.0.1/x","http://localhost/x","http://169.254.1.1/x","file:///etc/passwd","ftp://example.com/x"])
def test_private_and_non_http_research_urls_are_rejected(url):
    with pytest.raises(AppException) as exc:validate_public_url(url)
    assert exc.value.code=="AGENT_SOURCE_POLICY_VIOLATION"


def test_public_https_url_is_allowed_without_fetching():
    resolver = lambda _host, _port: [(None, None, None, None, ("93.184.216.34", 443))]
    assert validate_public_url("https://example.com/paper", resolver=resolver) == "https://example.com/paper"

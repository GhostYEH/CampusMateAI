import socket
from ipaddress import ip_address
from urllib.parse import urlparse
from ...core.exceptions import AppException

def validate_public_url(url: str, *, resolver=socket.getaddrinfo) -> str:
    parsed=urlparse(url)
    if parsed.scheme not in {"http","https"} or not parsed.hostname:
        raise AppException(code="AGENT_SOURCE_POLICY_VIOLATION",http_status=400,message="来源地址不受支持")
    host=parsed.hostname.casefold()
    if host=="localhost" or host.endswith(".localhost"):
        raise AppException(code="AGENT_SOURCE_POLICY_VIOLATION",http_status=400,message="禁止访问本地来源")
    addresses = []
    try:
        addresses = [ip_address(host)]
    except ValueError:
        try:
            addresses = [ip_address(item[4][0]) for item in resolver(host, parsed.port or 443)]
        except (OSError, ValueError):
            raise AppException(code="AGENT_SOURCE_POLICY_VIOLATION",http_status=400,message="来源地址无法安全解析")
    if not addresses or any(not address.is_global for address in addresses):
        raise AppException(code="AGENT_SOURCE_POLICY_VIOLATION",http_status=400,message="禁止访问私有来源")
    return url


def validate_redirect_chain(urls: list[str], *, resolver=socket.getaddrinfo) -> list[str]:
    """Validate every externally supplied redirect target before following it."""
    if not urls:
        raise AppException(code="AGENT_SOURCE_POLICY_VIOLATION",http_status=400,message="来源地址不能为空")
    return [validate_public_url(url, resolver=resolver) for url in urls]

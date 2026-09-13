from ...core.exceptions import AppException


SOURCES = {
    "android_system": "Android 系统通知",
    "chaoxing": "学习通",
    "campus_announcement": "校园公告",
    "manual_input": "手动录入",
}


def require_source(source_code: str) -> str:
    if source_code not in SOURCES:
        raise AppException(code="NOTICE_SOURCE_UNSUPPORTED", http_status=400, message="通知来源不受支持")
    return source_code

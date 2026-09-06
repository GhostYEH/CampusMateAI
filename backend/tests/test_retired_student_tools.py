from app.main import app


def _paths() -> set[str]:
    return {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }


def test_retired_student_tool_endpoints_are_not_registered() -> None:
    paths = _paths()

    assert "/api/v1/student/classrooms" not in paths
    assert "/api/v1/student/service-requests" not in paths
    assert "/api/v1/student/lost-found" not in paths
    assert "/api/v1/student/lost-found/{item_id}" not in paths


def test_community_api_remains_registered() -> None:
    paths = _paths()

    assert "/api/v1/community/posts" in paths
    assert "/api/v1/community/posts/{post_id}" in paths

from app.main import app


def test_auth_and_student_dashboard_routes_are_registered() -> None:
    registered = {(method, route.path) for route in app.routes for method in route.methods or set()}

    assert ("POST", "/api/v1/auth/login") in registered
    assert ("POST", "/api/v1/auth/refresh") in registered
    assert ("GET", "/api/v1/dashboard/student") in registered

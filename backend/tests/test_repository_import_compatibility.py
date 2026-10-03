import importlib

from app.repositories import multi_role_repository


def test_legacy_imports_resolve_to_the_domain_classes_and_helpers():
    namespace = {}
    exec("from app.repositories.multi_role_repository import *", namespace)
    domains = {
        "UserRepository": "user_repository",
        "RefreshTokenRepository": "refresh_token_repository",
        "CourseRepository": "course_repository",
        "ClassGroupRepository": "class_group_repository",
        "EnrollmentRepository": "enrollment_repository",
        "AnnouncementRepository": "announcement_repository",
        "AssignmentRepository": "assignment_repository",
        "SubmissionRepository": "submission_repository",
    }
    for name, module_name in domains.items():
        module = importlib.import_module(f"app.repositories.{module_name}")
        assert namespace[name] is getattr(module, name)
        assert getattr(multi_role_repository, name) is namespace[name]
    for name in ("_new_id", "_now_iso", "_generate_invite_code"):
        common = importlib.import_module("app.repositories._multi_role_common")
        assert namespace[name] is getattr(common, name)

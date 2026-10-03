"""Compatibility imports for the repositories now maintained in domain modules.

New application code imports the domain module directly. Keep this facade for
existing callers; every export is the original class, with no wrapper or copy.
"""
from ._multi_role_common import _generate_invite_code, _new_id, _now_iso
from .user_repository import UserRepository
from .refresh_token_repository import RefreshTokenRepository
from .course_repository import CourseRepository
from .class_group_repository import ClassGroupRepository
from .enrollment_repository import EnrollmentRepository
from .announcement_repository import AnnouncementRepository
from .assignment_repository import AssignmentRepository
from .submission_repository import SubmissionRepository

__all__ = [
    "UserRepository",
    "RefreshTokenRepository",
    "CourseRepository",
    "ClassGroupRepository",
    "EnrollmentRepository",
    "AnnouncementRepository",
    "AssignmentRepository",
    "SubmissionRepository",
    "_generate_invite_code",
    "_new_id",
    "_now_iso",
]

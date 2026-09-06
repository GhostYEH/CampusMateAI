from types import SimpleNamespace

from app.api.routes.assignments import _assignment_to_out
from app.models.multi_role import AssignmentRow


def test_assignment_output_includes_current_student_submission_status():
    assignment = AssignmentRow(
        id="assignment-1",
        class_group_id="class-1",
        author_id="teacher-1",
        title="实验报告",
        allow_resubmit=True,
        created_at="2026-09-05T00:00:00Z",
        updated_at="2026-09-05T00:00:00Z",
    )
    container = SimpleNamespace(
        assignment_repository=SimpleNamespace(
            list_attachments=lambda assignment_id: [],
            get_submission_for_student=lambda assignment_id, student_id: SimpleNamespace(status="submitted"),
        )
    )

    output = _assignment_to_out(assignment, container=container, student_id="student-1")

    assert output.submission_status == "submitted"

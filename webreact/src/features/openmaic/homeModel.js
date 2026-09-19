const completedSubmissionStatuses = new Set(["submitted", "graded", "late", "resubmitted"]);

function assignmentIsPending(item = {}) {
  if (item.is_remote) return !["completed", "closed"].includes(item.status);
  return !completedSubmissionStatuses.has(item.submission_status);
}

function deadlineOf(item = {}) {
  return item.deadline || item.due_at || item.due_date || null;
}

export function buildCourseRailItems(courses = [], assignments = []) {
  return (courses || []).map((course) => {
    const courseAssignments = (assignments || []).filter(
      (assignment) => String(assignment.course_id) === String(course.id) && assignmentIsPending(assignment),
    );
    const deadlines = courseAssignments
      .map((assignment) => deadlineOf(assignment))
      .filter(Boolean)
      .sort((a, b) => new Date(a).valueOf() - new Date(b).valueOf());
    return {
      id: course.id,
      name: course.name || course.title || "未命名课程",
      code: course.code || "",
      teacher: course.teacher_name || course.teacher || "教师信息待同步",
      term: course.semester || course.term || "学期待同步",
      pendingCount: courseAssignments.length,
      nextDeadline: deadlines[0] || null,
    };
  });
}

export function buildRecentClassrooms(courseHistories = []) {
  return (courseHistories || [])
    .flatMap((history) => (history.items || []).map((item) => ({ ...item, courseId: history.courseId })))
    .filter((item) => item.status !== "failed")
    .sort((a, b) => {
      const left = new Date(a.updated_at || a.updatedAt || a.created_at || 0).valueOf();
      const right = new Date(b.updated_at || b.updatedAt || b.created_at || 0).valueOf();
      return right - left;
    });
}

export function filterOpenMAICHomeItems(items = [], query = "") {
  const normalized = String(query || "").trim().toLocaleLowerCase();
  if (!normalized) return items;
  return items.filter((item) =>
    [item.title, item.name, item.courseName, item.course_name, item.code]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase()
      .includes(normalized),
  );
}

function pageTotal(page) {
  const total = Number(page?.total);
  if (Number.isFinite(total) && total >= 0) return total;
  if (Array.isArray(page?.items)) return page.items.length;
  return null;
}

function fallbackCount(fallback, key) {
  const value = Number(fallback?.[key]);
  return Number.isFinite(value) && value >= 0 ? value : 0;
}

export function resolveHomeOverviewMetrics({
  courses,
  pendingAssignments,
  pendingTasks,
  unreadNotices,
  fallback,
}) {
  const courseCount = pageTotal(courses) ?? fallbackCount(fallback, "enrolled_course_count");
  const pendingAssignmentCount = pageTotal(pendingAssignments) ?? fallbackCount(fallback, "pending_assignment_count");
  const pendingTaskCount = pageTotal(pendingTasks) ?? fallbackCount(fallback, "pending_personal_task_count");
  const unreadNoticeCount = pageTotal(unreadNotices) ?? fallbackCount(fallback, "unread_announcement_count");

  return {
    courseCount,
    pendingAssignmentCount,
    pendingTaskCount,
    pendingCount: pendingAssignmentCount + pendingTaskCount,
    unreadNoticeCount,
  };
}

import assert from "node:assert/strict";
import { test } from "node:test";

import { resolveHomeOverviewMetrics } from "../src/features/home/overviewMetrics.js";

test("uses the full API totals instead of the stale dashboard summary", () => {
  const metrics = resolveHomeOverviewMetrics({
    courses: { items: [{ id: "course-1" }], total: 4 },
    pendingAssignments: { items: [{ id: "assignment-1" }], total: 2 },
    pendingTasks: { items: [{ id: "task-1" }], total: 9 },
    unreadNotices: { items: [{ id: "notice-1" }], total: 3 },
    fallback: {
      enrolled_course_count: 0,
      pending_assignment_count: 0,
      pending_personal_task_count: 0,
      unread_announcement_count: 0,
    },
  });

  assert.deepEqual(metrics, {
    courseCount: 4,
    pendingAssignmentCount: 2,
    pendingTaskCount: 9,
    pendingCount: 11,
    unreadNoticeCount: 3,
  });
});

test("falls back to the dashboard summary only when a live list is unavailable", () => {
  const metrics = resolveHomeOverviewMetrics({
    courses: null,
    pendingAssignments: null,
    pendingTasks: { items: [], total: 0 },
    unreadNotices: null,
    fallback: {
      enrolled_course_count: 3,
      pending_assignment_count: 2,
      pending_personal_task_count: 5,
      unread_announcement_count: 4,
    },
  });

  assert.deepEqual(metrics, {
    courseCount: 3,
    pendingAssignmentCount: 2,
    pendingTaskCount: 0,
    pendingCount: 2,
    unreadNoticeCount: 4,
  });
});

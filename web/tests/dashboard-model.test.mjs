import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildDueItems,
  buildMainQuests,
  selectUpcomingExam,
  todayScheduleItems,
} from "../src/features/dashboard/dashboardModel.js";

const now = new Date("2026-08-31T09:00:00+08:00");

test("todayScheduleItems keeps only current, non-stale courses in section order", () => {
  const items = [
    { id: "late", weekday: 1, start_section: 5, course_name: "算法设计" },
    { id: "tomorrow", weekday: 2, start_section: 1, course_name: "大学英语" },
    { id: "early", weekday: 1, start_section: 1, course_name: "高等数学" },
    { id: "stale", weekday: 1, start_section: 3, course_name: "旧课表", is_stale: true },
  ];

  assert.deepEqual(todayScheduleItems(items, now).map((item) => item.id), ["early", "late"]);
});

test("buildDueItems merges assignments and personal tasks by valid deadline", () => {
  const items = buildDueItems({
    due_soon_assignments: [
      { id: "a-late", title: "实验报告", deadline: "2026-09-02T18:00:00+08:00" },
      { id: "a-invalid", title: "开放作业", deadline: "later" },
    ],
    due_soon_personal_tasks: [
      { id: "p-first", title: "借书", deadline: "2026-08-31T12:00:00+08:00" },
    ],
  });

  assert.deepEqual(items.map((item) => `${item.sourceType}:${item.id}`), [
    "personal-task:p-first",
    "assignment:a-late",
    "assignment:a-invalid",
  ]);
  assert.equal(items[0].route, "/tasks/personal/p-first");
  assert.equal(items[1].route, "/tasks/assignment/a-late");
});

test("selectUpcomingExam ignores ended and invalid records", () => {
  const selected = selectUpcomingExam([
    { id: "past", exam_date: "2026-08-30", end_time: "10:00" },
    { id: "invalid", exam_date: "not-a-date" },
    { id: "later", exam_date: "2026-09-08", start_time: "09:00" },
    { id: "next", exam_date: "2026-09-01", start_time: "14:00" },
  ], now);

  assert.equal(selected?.id, "next");
});

test("buildMainQuests tolerates missing sources and preserves route metadata", () => {
  assert.deepEqual(buildMainQuests({}, now), []);

  const quests = buildMainQuests({
    scheduleItems: [{ id: "course", weekday: 1, start_section: 3, end_section: 4, course_name: "数据结构", location: "C202" }],
    dueItems: [{ id: "task", title: "完成算法作业", due: "2026-08-31T20:00:00+08:00", sourceType: "personal-task", route: "/tasks/personal/task" }],
    exams: [{ id: "exam", course_name: "计算机网络", exam_date: "2026-09-02", start_time: "09:00" }],
  }, now);

  assert.deepEqual(quests.map(({ sourceType, route }) => ({ sourceType, route })), [
    { sourceType: "course", route: "/academic" },
    { sourceType: "personal-task", route: "/tasks/personal/task" },
    { sourceType: "exam", route: "/exams" },
  ]);
});

import assert from "node:assert/strict";
import { test } from "node:test";

import { resolveHomeLearningCommand } from "../src/features/home/homeLearningModel.js";

const now = new Date("2026-09-01T09:00:00+08:00");

test("deadline wins over course, exam and focus suggestions", () => {
  const command = resolveHomeLearningCommand({
    dueItems: [
      { id: "task-1", title: "提交课程设计", due: "2026-09-01T11:00:00+08:00", route: "/tasks/personal/task-1" },
    ],
    scheduleItems: [
      { id: "course-1", weekday: 2, start_section: 5, course_name: "数据结构" },
    ],
    exams: [
      { id: "exam-1", course_name: "大学英语", exam_date: "2026-09-03", start_time: "09:00" },
    ],
    studySessions: [],
    overviewMetrics: { pendingCount: 1 },
  }, now);

  assert.equal(command.priority, "deadline");
  assert.equal(command.headline, "先完成：提交课程设计");
  assert.equal(command.primaryAction.path, "/tasks/personal/task-1");
  assert.match(command.secondaryAction.path, /^\/counselor\?prompt=/);
});

test("today course becomes the next action when no urgent task exists", () => {
  const command = resolveHomeLearningCommand({
    dueItems: [{ id: "later", title: "阅读论文", due: "2026-09-04T18:00:00+08:00", route: "/tasks/personal/later" }],
    scheduleItems: [
      { id: "course-2", weekday: 2, start_section: 3, end_section: 4, course_name: "计算机网络", location: "A203", course_id: "network" },
      { id: "course-1", weekday: 2, start_section: 1, end_section: 2, course_name: "线性代数", location: "B105", course_id: "linear" },
    ],
    exams: [],
    studySessions: [],
    overviewMetrics: { pendingCount: 1 },
  }, now);

  assert.equal(command.priority, "course");
  assert.equal(command.headline, "今天先跟上：线性代数");
  assert.equal(command.primaryAction.path, "/courses/linear");
});

test("exam within seven days becomes the next action when today has no course", () => {
  const command = resolveHomeLearningCommand({
    dueItems: [],
    scheduleItems: [],
    exams: [
      { id: "later", course_name: "软件工程", exam_date: "2026-09-12", start_time: "09:00" },
      { id: "next", course_name: "大学英语", exam_date: "2026-09-05", start_time: "14:00", location: "二教 301" },
    ],
    studySessions: [],
    overviewMetrics: { pendingCount: 0 },
  }, now);

  assert.equal(command.priority, "exam");
  assert.equal(command.headline, "为大学英语考试留出复习时间");
  assert.equal(command.primaryAction.path, "/exams");
  assert.equal(command.nextExam.id, "next");
});

test("fallback action starts a focus session without inventing campus data", () => {
  const command = resolveHomeLearningCommand({
    dueItems: [{ id: "invalid", title: "时间待定任务", due: "later", route: "/tasks/personal/invalid" }],
    scheduleItems: [],
    exams: [{ id: "invalid-exam", course_name: "未知考试", exam_date: "not-a-date" }],
    studySessions: [],
    overviewMetrics: { pendingCount: 1 },
  }, now);

  assert.equal(command.priority, "focus");
  assert.equal(command.primaryAction.path, "/study");
  assert.equal(command.nextExam, null);
  assert.equal(command.pulse.find((item) => item.key === "exam").value, "暂无安排");
});

test("pulse summarizes real course, task, exam and today's focus facts", () => {
  const command = resolveHomeLearningCommand({
    dueItems: [],
    scheduleItems: [
      { id: "today", weekday: 2, start_section: 1, course_name: "高等数学" },
      { id: "tomorrow", weekday: 3, start_section: 1, course_name: "大学物理" },
    ],
    exams: [{ id: "exam", course_name: "高等数学", exam_date: "2026-09-10", start_time: "09:00" }],
    studySessions: [
      { id: "today-session", status: "completed", started_at: "2026-09-01T07:00:00+08:00", duration_seconds: 1800 },
      { id: "old-session", status: "completed", started_at: "2026-08-31T07:00:00+08:00", duration_seconds: 3600 },
    ],
    overviewMetrics: { pendingCount: 3 },
  }, now);

  assert.deepEqual(command.pulse.map(({ key, value }) => ({ key, value })), [
    { key: "course", value: "1 门" },
    { key: "task", value: "3 项" },
    { key: "exam", value: "9月10日" },
    { key: "focus", value: "30 分钟" },
  ]);
});

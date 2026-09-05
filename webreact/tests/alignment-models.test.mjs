import test from "node:test";
import assert from "node:assert/strict";
import * as alignment from "../src/data/alignment.js";
import { isSameLocalDate, localDateKey } from "../src/utils/date.js";

const { buildCommentTree, buildContentTree, isRenamedDuplicate, mergeRecords } = alignment;

test("course records keep local state while adding synchronized records", () => {
  const merged = mergeRecords([{ id: "a1", title: "作业", submission_status: "submitted" }], [{ id: "a1", description: "同步要求" }, { id: "a2", title: "远端作业" }]);
  assert.equal(merged.length, 2);
  assert.deepEqual(merged[0], { id: "a1", description: "同步要求", title: "作业", submission_status: "submitted" });
});

test("course content and comments preserve parent-child relationships", () => {
  const content = buildContentTree([{ id: "c1", kind: "chapter" }, { id: "c2", kind: "document", parent_external_id: "c1" }]);
  assert.equal(content[0].children[0].id, "c2");
  const comments = buildCommentTree([{ id: "root" }, { id: "reply", parent_comment_id: "root" }]);
  assert.equal(comments[0].children[0].id, "reply");
});

test("renaming an imported duplicate makes it importable", () => {
  assert.equal(isRenamedDuplicate({ existing_task_id: "task-1", title: "原任务", original_title: "原任务" }), true);
  assert.equal(isRenamedDuplicate({ existing_task_id: "task-1", title: "原任务-复习版", original_title: "原任务" }), false);
  assert.equal(localDateKey(new Date(2026, 8, 5)), "2026-09-05");
  assert.equal(isSameLocalDate(new Date(2026, 8, 5, 1), new Date(2026, 8, 5, 23)), true);
});

test("synchronized course records preserve their source fields and actions", () => {
  assert.equal(typeof alignment.normalizeRemoteNotice, "function");
  assert.equal(typeof alignment.assignmentStatusLabel, "function");
  assert.equal(typeof alignment.isLocalGradeAssignment, "function");

  const notice = alignment.normalizeRemoteNotice({ id: "remote-notice-1", kind: "notice", description: "学习通通知正文" });
  assert.equal(notice.is_remote, true);
  assert.equal(notice.content, "学习通通知正文");
  assert.equal(notice.has_read, true);
  assert.equal(alignment.assignmentStatusLabel({ is_remote: true, status: "completed" }), "已完成");
  assert.equal(alignment.assignmentStatusLabel({ is_remote: true, status: "pending" }), "未完成");
  assert.equal(alignment.isLocalGradeAssignment({ is_remote: true }), false);
  assert.equal(alignment.isLocalGradeAssignment({ id: "local-assignment" }), true);
});

test("home search includes completed, submitted and already-read records", () => {
  assert.equal(typeof alignment.buildHomeSearchResults, "function");
  const data = {
    courses: [],
    assignments: [{ id: "submitted-assignment", title: "已提交报告", course_name: "数据结构" }],
    tasks: [{ id: "completed-task", title: "已完成复习", description: "复习笔记", source_name: "个人安排" }],
    notices: [{ id: "read-notice", title: "已读通知", content: "材料已归档", source: "教务处" }],
  };
  assert.equal(alignment.buildHomeSearchResults(data, "已提交报告")[0].id, "submitted-assignment");
  assert.equal(alignment.buildHomeSearchResults(data, "已完成复习")[0].id, "completed-task");
  assert.equal(alignment.buildHomeSearchResults(data, "已读通知")[0].id, "read-notice");
});

test("task workbench treats late and resubmitted assignments as completed within seven days", () => {
  assert.equal(typeof alignment.isCompletedSubmissionStatus, "function");
  assert.equal(typeof alignment.taskAssignmentStatusLabel, "function");
  assert.equal(typeof alignment.taskAssignmentProgress, "function");
  assert.equal(typeof alignment.taskGroupState, "function");
  assert.equal(alignment.isCompletedSubmissionStatus("late"), true);
  assert.equal(alignment.isCompletedSubmissionStatus("resubmitted"), true);
  assert.equal(alignment.taskAssignmentStatusLabel("late"), "已提交（逾期）");
  assert.equal(alignment.taskAssignmentStatusLabel("resubmitted"), "已重新提交");
  assert.equal(alignment.taskAssignmentProgress("late"), 100);
  const now = new Date("2026-09-05T12:00:00");
  assert.equal(alignment.taskGroupState({ deadline: "2026-09-11T12:00:00" }, now), "upcoming");
  assert.equal(alignment.taskGroupState({ deadline: "2026-09-13T12:00:00" }, now), "later");
});

test("submission state keeps late and resubmitted labels without a duplicate submit request", () => {
  assert.equal(typeof alignment.submissionStatusLabel, "function");
  assert.equal(typeof alignment.submissionActionLabel, "function");
  assert.equal(typeof alignment.shouldFinalizeSubmission, "function");

  assert.equal(alignment.submissionStatusLabel("late"), "已提交（逾期）");
  assert.equal(alignment.submissionStatusLabel("resubmitted"), "已重新提交");
  assert.equal(alignment.submissionActionLabel("late"), "重新提交");
  assert.equal(alignment.shouldFinalizeSubmission({ id: "submission-1", status: "late" }), false);
  assert.equal(alignment.shouldFinalizeSubmission({ id: "submission-1", status: "draft" }), true);
});

test("stale schedule items are excluded from the current dashboard", () => {
  assert.equal(typeof alignment.filterActiveSchedule, "function");
  const visible = alignment.filterActiveSchedule([
    { id: "fresh", is_stale: false },
    { id: "stale", is_stale: true },
    { id: "missing-flag" },
  ]);
  assert.deepEqual(visible.map((item) => item.id), ["fresh", "missing-flag"]);
});

test("course, study, task and profile parity models preserve Vue semantics", () => {
  assert.equal(typeof alignment.courseProgress, "function");
  assert.equal(typeof alignment.courseMaterialCount, "function");
  assert.equal(typeof alignment.weeklyTrend, "function");

  const assignments = [{ course_id: "course-1", submission_status: "submitted" }, { course_id: "course-1", submission_status: "draft" }];
  assert.equal(alignment.courseProgress({ id: "course-1" }, assignments), 50);
  assert.equal(alignment.courseMaterialCount({ resource_count: 3 }), 3);
  assert.deepEqual(alignment.weeklyTrend([{ completed_at: "2026-09-05T10:00:00" }], new Date("2026-09-05T12:00:00")).map((item) => item.count), [0, 0, 0, 0, 0, 0, 1]);
});

test("integration models understand the live Chaoxing contract", () => {
  assert.equal(typeof alignment.isChaoxingConnected, "function");
  assert.equal(typeof alignment.chaoxingSyncSummary, "function");
  assert.equal(alignment.isChaoxingConnected({ status: "online" }), true);
  assert.deepEqual(alignment.chaoxingSyncSummary({
    complete: false,
    stats: { courses_fetched: 6, teachers_fetched: 4, assignments_pending: 3, notices_fetched: 8 },
  }), { complete: false, courses: 6, teachers: 4, pendingAssignments: 3, notices: 8 });
});

test("QR interaction models preserve active-route behavior", () => {
  assert.equal(typeof alignment.qrStatusState, "function");
  assert.deepEqual(alignment.qrStatusState("CONSUMED"), { state: "error", error: "二维码已被使用，请重新生成" });
  assert.deepEqual(alignment.qrStatusState("EXPIRED"), { state: "expired", error: "" });
});

test("active exam detail keeps the fields and actions available in the Vue route", () => {
  assert.equal(typeof alignment.examDetailFields, "function");
  assert.deepEqual(alignment.examDetailFields({ exam_type: "期末考试", notes: "带计算器", reminder_enabled: true }).map((item) => item.value), ["期末考试", "带计算器", "已开启"]);
});

test("notice extraction exposes an editable task draft", () => {
  assert.equal(typeof alignment.noticeTaskDraft, "function");
  assert.equal(typeof alignment.updateNoticeTaskDraft, "function");
  const extracted = { tasks: [{ task: "提交实验报告", deadline: "2026-09-12", submission_method: "教学平台" }] };
  assert.deepEqual(alignment.noticeTaskDraft(extracted), { title: "提交实验报告", deadline: "2026-09-12", submission_method: "教学平台" });
  assert.equal(alignment.noticeTaskDraft(alignment.updateNoticeTaskDraft(extracted, "title", "提交最终版")).title, "提交最终版");
});

test("study experience entries retain their actionable view", () => {
  assert.equal(typeof alignment.studyExperienceModel, "function");
  assert.deepEqual(alignment.studyExperienceModel("focus", { title: "复习高数", value: "25:00" }), { view: "focus", title: "复习高数", value: "25:00" });
  assert.deepEqual(alignment.studyExperienceModel("task", { title: "计划详情", task: { id: "task-1", title: "整理笔记" } }), { view: "task", title: "计划详情", value: "", task: { id: "task-1", title: "整理笔记" } });
});

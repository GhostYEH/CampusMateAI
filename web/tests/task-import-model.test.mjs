import assert from "node:assert/strict";
import test from "node:test";

import {
  buildTaskImportCommit,
  selectedTaskCount,
  updateTaskImportDraftTitle,
} from "../src/features/tasks/taskImportModel.js";

test("task import commit keeps only selected editable fields", () => {
  const drafts = [
    { title: " 已有任务 ", selected: false, confidence: 1 },
    { title: " 完成课程报告 ", selected: true, description: "先写初稿", priority: "high", confidence: 0.8 },
  ];

  assert.equal(selectedTaskCount(drafts), 1);
  assert.deepEqual(buildTaskImportCommit(drafts), {
    tasks: [{ title: "完成课程报告", description: "先写初稿", priority: "high" }],
  });
});

test("editing a duplicate draft to a different normalized title makes it importable", () => {
  const duplicate = {
    title: "  Course Report  ",
    selected: false,
    existing_task_id: 42,
    existing_status: "completed",
  };

  assert.deepEqual(updateTaskImportDraftTitle(duplicate, "Final Presentation"), {
    title: "Final Presentation",
    selected: true,
  });
  assert.deepEqual(updateTaskImportDraftTitle(duplicate, "Course Report"), {
    ...duplicate,
    title: "Course Report",
  });
  assert.deepEqual(updateTaskImportDraftTitle(duplicate, "course report"), {
    ...duplicate,
    title: "course report",
  });
});

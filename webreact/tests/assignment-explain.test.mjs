import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const panel = fs.readFileSync(new URL("../src/components/AssignmentExplainPanel.jsx", import.meta.url), "utf8");
const page = fs.readFileSync(new URL("../src/pages/TaskDetailPage.jsx", import.meta.url), "utf8");

test("assignment explanation has an explicit context and answer-consent gate", () => {
  assert.match(page, /AssignmentExplainPanel assignment=\{data\} answer=\{answer\}/);
  assert.match(panel, /查看上下文并确认/);
  assert.match(panel, /明确授权把我的答案草稿作为讲解材料/);
  assert.match(panel, /不要使用我的答案正文/);
  assert.match(panel, /courseId/);
});

test("assignment explanation uses course-scoped chat and real classroom generation", () => {
  assert.match(panel, /api\.chatStream\(prompt/);
  assert.match(panel, /courseId, conversationId/);
  assert.match(panel, /api\.generateInteractiveClassroom\(courseId/);
  assert.match(panel, /tab=mentoring/);
});

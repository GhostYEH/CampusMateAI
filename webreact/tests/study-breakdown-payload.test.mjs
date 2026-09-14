import test from "node:test";
import assert from "node:assert/strict";
import { buildBreakdownPayload } from "../src/data/studyBreakdown.js";

test("free-text goal sends goal only", () => {
  assert.deepEqual(
    buildBreakdownPayload({ taskId: null, goal: "复习高等数学第一章" }),
    { goal: "复习高等数学第一章" },
  );
});

test("free-text goal is trimmed and empty goal stays empty", () => {
  assert.deepEqual(buildBreakdownPayload({ taskId: null, goal: "  复习高数  " }), {
    goal: "复习高数",
  });
  assert.deepEqual(buildBreakdownPayload({ taskId: null, goal: "   " }), { goal: "" });
});

test("task entry sends task_id so the backend can read the task context", () => {
  assert.deepEqual(buildBreakdownPayload({ taskId: "tsk_1", goal: "" }), {
    task_id: "tsk_1",
  });
  assert.deepEqual(buildBreakdownPayload({ taskId: "tsk_1", goal: null }), {
    task_id: "tsk_1",
  });
});

test("task entry with an added goal sends both fields", () => {
  assert.deepEqual(buildBreakdownPayload({ taskId: "tsk_1", goal: "先整理公式" }), {
    task_id: "tsk_1",
    goal: "先整理公式",
  });
});

test("payload never carries task description or notice text back to the server", () => {
  const payload = buildBreakdownPayload({ taskId: "tsk_1", goal: "补办校园卡" });
  assert.deepEqual(Object.keys(payload).sort(), ["goal", "task_id"]);
  assert.doesNotMatch(JSON.stringify(payload), /source_text|description|通知原文/);
});

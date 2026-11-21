import test from "node:test";
import assert from "node:assert/strict";

import {
  addLines,
  addPage,
  budgetLeft,
  bumpUsage,
  emptyClassmateMemory,
  memoryKey,
  memoryPayload,
  normalizeMemory,
} from "../src/features/magicclass/classmateMemory.js";

test("记忆只保留最近的页标题，且去重", () => {
  let state = emptyClassmateMemory();
  for (let index = 0; index < 10; index += 1) state = addPage(state, `第 ${index} 页`);
  assert.equal(state.pages.length, 8);
  assert.equal(state.pages.at(-1), "第 9 页");

  const repeated = addPage(state, "第 9 页");
  assert.equal(repeated.pages.length, 8);
  assert.equal(repeated.pages.at(-1), "第 9 页");
});

test("发言按条数上限截断，并记录上一页发言过的同学", () => {
  let state = emptyClassmateMemory();
  const messages = Array.from({ length: 15 }, (_, index) => ({ agentId: `a${index}`, text: `发言 ${index}` }));
  state = addLines(state, messages);
  assert.equal(state.lines.length, 12);
  assert.equal(state.lines.at(-1).text, "发言 14");
  assert.equal(state.recentAgentIds.length, 7);
  assert.equal(state.recentAgentIds.at(-1), "a14");
});

test("空发言不进记忆，超长文本截断到上限", () => {
  const state = addLines(emptyClassmateMemory(), [
    { agentId: "a1", text: "   " },
    { agentId: "a2", text: "x".repeat(500) },
    { agentId: "a3", text: "有效发言" },
  ]);
  assert.equal(state.lines.length, 2);
  assert.equal(state.lines[0].agentId, "a2");
  assert.equal(state.lines[0].text.length, 400);
  assert.deepEqual(state.recentAgentIds, ["a2", "a3"]);
});

test("预算只增不减地累计 usage，且不会为负", () => {
  let state = emptyClassmateMemory();
  state = bumpUsage(state, 120);
  state = bumpUsage(state, -5);
  state = bumpUsage(state, "88");
  assert.equal(state.usage, 208);
  assert.equal(budgetLeft(state, 1000), 792);
  assert.equal(budgetLeft({ ...state, usage: 2000 }, 1000), 0);
});

test("坏存档只丢坏字段，并保持 payload 契约", () => {
  const normalized = normalizeMemory({
    pages: ["ok", "", "y".repeat(300)],
    lines: [{ agentId: "a", text: "hi" }, { agentId: "", text: "no" }, { text: "no id" }],
    recentAgentIds: ["a", "", "b"],
    usage: "40",
  });
  assert.equal(normalized.pages.length, 2);
  assert.equal(normalized.pages[1].length, 200);
  assert.equal(normalized.lines.length, 1);
  assert.deepEqual(normalized.recentAgentIds, ["a", "b"]);
  assert.equal(normalized.usage, 40);
  assert.deepEqual(memoryPayload(normalized), {
    pages: normalized.pages,
    lines: normalized.lines,
    recentAgentIds: normalized.recentAgentIds,
  });
});

test("存储键按课堂舞台隔离", () => {
  assert.equal(memoryKey("stage-1"), "campusmate:classroom-classmates:v1:stage-1");
  assert.equal(memoryKey(""), "");
});

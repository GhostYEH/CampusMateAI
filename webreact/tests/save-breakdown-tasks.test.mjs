import assert from "node:assert/strict";
import test from "node:test";
import { saveBreakdownTasks } from "../src/data/saveBreakdownTasks.js";

test("partial save retries only failed steps and preserves edited descriptions", async () => {
  const steps = [{ _key: "a", title: " 第一章 ", description: " 阅读 " }, { _key: "b", title: "做习题" }];
  const created = [];
  const first = await saveBreakdownTasks(steps, "复习数学", async (payload) => {
    if (payload.title === "做习题") throw new Error("service unavailable");
    created.push(payload);
  });
  assert.equal(first.savedCount, 1);
  assert.deepEqual(first.failedSteps, [steps[1]]);
  const retry = await saveBreakdownTasks(first.failedSteps, "复习数学", async (payload) => created.push(payload));
  assert.equal(retry.savedCount, 1);
  assert.equal(retry.failedSteps.length, 0);
  assert.deepEqual(created.map((task) => task.title), ["第一章", "做习题"]);
  assert.equal(created[0].description, "阅读");
  assert.equal(created[0].source_text, "复习数学");
});

test("all failures retain drafts and blank titles are not submitted", async () => {
  const steps = [{ _key: "a", title: "阅读" }, { _key: "empty", title: " " }];
  const result = await saveBreakdownTasks(steps, "学习", () => { throw new Error("offline"); });
  assert.equal(result.savedCount, 0);
  assert.deepEqual(result.failedSteps, [steps[0]]);
});

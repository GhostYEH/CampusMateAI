import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const page = fs.readFileSync(
  path.join(process.cwd(), "src", "pages", "LearningStatePage.jsx"),
  "utf8",
);

test("learning goal creation treats 202 as queued and subscribes to latest run", () => {
  assert.match(page, /任务已加入队列，正在准备计划/);
  assert.match(page, /setTrackedRunId\(job\?\.latest_run_id/);
  assert.match(page, /useAgentRun\(\{ runId: activeRunId/);
  assert.doesNotMatch(
    page,
    /await runtimeApi\.createAgentJob\([\s\S]*?计划草案已生成，请确认后创建待办/,
  );
});

test("successful terminal run reloads Job before refreshing plan data", () => {
  const getJob = page.indexOf("runtimeApi.getAgentJob(run.job_id)");
  const refresh = page.indexOf("refresh();", getJob);
  assert.ok(getJob >= 0);
  assert.ok(refresh > getJob);
  assert.match(page.slice(getJob, refresh), /input_ref\?\.plan_id/);
});

test("failed and cancelled terminal runs remain retryable instead of showing success", () => {
  assert.match(page, /任务已取消，可重新发起/);
  assert.match(page, /任务未完成，可稍后重试/);
});

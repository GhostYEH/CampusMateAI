import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const root = new URL("../src/", import.meta.url);
const read = (file) => fs.readFileSync(new URL(file, root), "utf8");

test("agent api exposes runtime run, steps, resume and approval calls", () => {
  const source = read("data/agentApi.js");
  assert.match(source, /\/final-review\/campaigns\/\$\{id\}\/run/);
  assert.match(source, /\/agent-runs\/\$\{encodeURIComponent\(runId\)\}\/steps/);
  assert.match(source, /\/agent-runs\/\$\{encodeURIComponent\(runId\)\}\/resume/);
  assert.match(source, /\/agent-approvals\/\$\{encodeURIComponent\(approvalId\)\}\/decision/);
  assert.match(source, /"Idempotency-Key": key/);
});

test("task list surfaces final review runs and links into the run detail route", () => {
  const tasks = read("pages/TasksPage.jsx");
  assert.match(tasks, /agentApi\.listCampaigns\(\)/);
  assert.match(tasks, /kind: "final-review"/);
  assert.match(tasks, /\/tasks\/final-review\/\$\{task\.sourceId\}/);
  assert.match(tasks, /<option value="final-review">/);
});

test("task detail renders the persisted run timeline and completes approval in place", () => {
  const detail = read("pages/TaskDetailPage.jsx");
  assert.match(detail, /if \(kind === "final-review"\)/);
  assert.match(detail, /agentApi\.campaignRun\(campaignId\)/);
  assert.match(detail, /agentApi\.decideApproval\(run\.approval_id, decision\)/);
  assert.match(detail, /agentApi\.resumeRun\(run\.run_id\)/);
  assert.match(detail, /RUN_STEP_LABEL/);
});

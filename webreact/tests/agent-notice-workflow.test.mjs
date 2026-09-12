/**
 * 通知事务工作台契约测试：
 * - manual → workflow 顺序：先 POST /notices/manual 再 POST /notices/:id/workflow（任务 §6）
 * - 不走旧的 extractNotice→createTask 自动执行路径
 * - MANUAL_ONLY 动作不调用 execute
 * - Idempotency-Key 两步独立
 */
import "./helpers/setup-globals.mjs";
import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";

import * as api from "../src/data/agentRuntimeApi.js";
import { client } from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";
import { isSafeToAct } from "../src/data/agentContracts.js";

let mock;

beforeEach(() => { mock = createMockClient(client); });
afterEach(() => { mock.reset(); mock.clearTokens(); });

describe("notice-workflow manual → workflow order", () => {
  it("先 manual 再 workflow，notice_id 来自 server", async () => {
    mock.onPost("/notices/manual", { notice_id: "n1", source: "manual_input" });
    mock.onPost("/notices/n1/workflow", { workflow_id: "w1", run_id: "r1" });

    const notice = await api.createManualNotice({ content: "明天交作业" }, "k-manual");
    const workflow = await api.createNoticeWorkflow(notice.notice_id, {}, "k-workflow");

    assert.equal(notice.notice_id, "n1");
    assert.equal(workflow.workflow_id, "w1");
    assert.equal(mock.requests[0].url, "/notices/manual");
    assert.equal(mock.requests[1].url, "/notices/n1/workflow");
  });

  it("不调用 extractNotice 或 createTask 自动执行路径", async () => {
    mock.onPost("/notices/manual", { notice_id: "n2" });
    mock.onPost("/notices/n2/workflow", { workflow_id: "w2" });

    await api.createManualNotice({ content: "x" }, "k1");
    await api.createNoticeWorkflow("n2", {}, "k2");

    const urls = mock.requests.map((r) => r.url);
    assert.ok(!urls.some((u) => u.includes("/notices/extract-multi")));
    assert.ok(!urls.some((u) => u === "/tasks"));
    assert.ok(!urls.some((u) => u.includes("/tasks/import")));
  });

  it("两步独立 Idempotency-Key", async () => {
    mock.onPost("/notices/manual", { notice_id: "n3" });
    mock.onPost("/notices/n3/workflow", { workflow_id: "w3" });

    await api.createManualNotice({ content: "x" }, "key-a");
    await api.createNoticeWorkflow("n3", {}, "key-b");

    assert.equal(mock.requests[0].headers["Idempotency-Key"], "key-a");
    assert.equal(mock.requests[1].headers["Idempotency-Key"], "key-b");
  });
});

describe("notice-workflow action risk gating", () => {
  it("MANUAL_ONLY 动作 isSafeToAct=false，前端不提供 execute", () => {
    assert.equal(isSafeToAct("MANUAL_ONLY"), false);
    assert.equal(isSafeToAct("CONFIRM_REQUIRED"), false);
    assert.equal(isSafeToAct("AUTO_SAFE"), true);
  });

  it("decideNoticeWorkflowAction 传递 decision 与 reason", async () => {
    mock.onPost("/notice-workflow-actions/a1/decision", { status: "APPROVED" });
    await api.decideNoticeWorkflowAction("a1", "APPROVED", "用户确认", "k");
    assert.deepEqual(mock.lastRequest().data, { decision: "APPROVED", reason: "用户确认" });
  });

  it("executeNoticeWorkflowAction 仅用于 AUTO_SAFE 动作", async () => {
    mock.onPost("/notice-workflow-actions/a2/execute", { status: "EXECUTING" });
    await api.executeNoticeWorkflowAction("a2", "k");
    assert.equal(mock.lastRequest().url, "/notice-workflow-actions/a2/execute");
  });

  it("reanalyze 与 getNoticeWorkflow 端点", async () => {
    mock.onGet("/notice-workflows/w1", { workflow_id: "w1", status: "ANALYZING" });
    mock.onPost("/notice-workflows/w1/reanalyze", { status: "ANALYZING" });
    await api.getNoticeWorkflow("w1");
    await api.reanalyzeNoticeWorkflow("w1", "k");
    assert.equal(mock.requests[0].url, "/notice-workflows/w1");
    assert.equal(mock.requests[1].url, "/notice-workflows/w1/reanalyze");
  });
});

describe("notification sources", () => {
  it("getNotificationSources 与 updateNotificationSource", async () => {
    mock.onGet("/notification-sources", { items: [{ source_id: "s1", code: "manual_input", enabled: true }] });
    mock.onPatch("/notification-sources/s1", { enabled: false });
    await api.getNotificationSources();
    await api.updateNotificationSource("s1", { enabled: false }, "k");
    assert.equal(mock.requests[1].url, "/notification-sources/s1");
    assert.equal(mock.requests[1].method, "patch");
  });
});
/**
 * 期末复习工作台流程契约测试：
 * - create campaign → generate plan → activate 全链路带 Idempotency-Key
 * - 计划版本端点独立于旧 /learning-plans（不把旧学习计划当成 Agent 版本，任务 §4）
 * - 调整通过 adjustment-proposals，不直接改计划
 */
import "./helpers/setup-globals.mjs";
import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";

import * as api from "../src/data/agentRuntimeApi.js";
import { client } from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";

let mock;

beforeEach(() => { mock = createMockClient(client); });
afterEach(() => { mock.reset(); mock.clearTokens(); });

describe("final-review full flow", () => {
  it("create → generate → activate 各步带独立 Idempotency-Key", async () => {
    mock.onPost("/final-review/campaigns", { campaign_id: "c1" });
    mock.onPost("/final-review/campaigns/c1/plans/generate", { run_id: "r1" });
    mock.onPost("/final-review/campaigns/c1/activate", { status: "ACTIVE" });

    await api.createFinalReviewCampaign({ exam_ids: ["e1"] }, "k-campaign");
    await api.generateFinalReviewPlan("c1", { daily_capacity_minutes: 120 }, "k-gen");
    await api.activateFinalReviewCampaign("c1", 1, "k-act");

    const [c, g, a] = mock.requests;
    assert.equal(c.headers["Idempotency-Key"], "k-campaign");
    assert.equal(g.headers["Idempotency-Key"], "k-gen");
    assert.equal(a.headers["Idempotency-Key"], "k-act");
    assert.deepEqual(a.data, { version: 1 });
  });

  it("计划版本端点独立于旧 /learning-plans", async () => {
    mock.onGet("/final-review/campaigns/c1/plan-versions", { items: [{ version: 1 }] });
    await api.getFinalReviewPlanVersions("c1");
    assert.equal(mock.lastRequest().url, "/final-review/campaigns/c1/plan-versions");
    assert.ok(!mock.requests.some((r) => r.url.includes("/learning-plans")));
  });

  it("调整通过 adjustment-proposals，不直接改计划", async () => {
    mock.onPost("/final-review/campaigns/c1/adjustments/analyze", { proposal_id: "p1" });
    mock.onPost("/final-review/adjustment-proposals/p1/decision", { status: "ACCEPTED" });
    await api.analyzeAdjustment("c1", {}, "k-analyze");
    await api.resolveAdjustmentProposal("p1", "ACCEPTED", null, "k-decide");
    assert.ok(mock.requests.every((r) => !r.url.includes("/activate")));
  });

  it("今日日程与完成项端点", async () => {
    mock.onGet("/final-review/campaigns/c1/agendas/today", { items: [{ item_id: "i1" }] });
    mock.onPost("/final-review/daily-items/i1/complete", { status: "DONE" });
    await api.getTodayAgenda("c1");
    await api.completeFinalReviewItem("i1", "k-complete");
    assert.equal(mock.requests[1].url, "/final-review/daily-items/i1/complete");
  });

  it("每日签到发送完成项和时间不足反馈", async () => {
    mock.onPost("/final-review/campaigns/c1/daily-checkins", { recorded: true, evidence_count: 2 });
    await api.createDailyCheckin("c1", {
      report_date: "2026-09-13",
      completed_item_ids: ["i1"],
      insufficient_time: true,
      difficulty_notes: "事务较多",
    }, "k-checkin");
    const request = mock.lastRequest();
    assert.equal(request.headers["Idempotency-Key"], "k-checkin");
    assert.deepEqual(request.data.completed_item_ids, ["i1"]);
    assert.equal(request.data.insufficient_time, true);
  });
});

describe("期末复习写操作的异步命令契约", () => {
  // 审批后的高风险写操作由 Worker 经 Gateway 执行,路由只创建命令。
  // 客户端不能把命令被受理当成"计划已生效",必须按 run_id 观察进展。

  it("激活只创建命令:响应带 run_id 且未生效", async () => {
    mock.onPost("/final-review/campaigns/c1/activate", {
      campaign_id: "c1",
      active_version: 1,
      activated: false,
      status: "PENDING",
      run_id: "run_activate",
    });

    const result = await api.activateFinalReviewCampaign("c1", 1, "k-act");

    assert.equal(result.activated, false);
    assert.equal(result.status, "PENDING");
    assert.equal(result.run_id, "run_activate");
  });

  it("调整决策只创建命令:new_version 在命令完成前为 null", async () => {
    mock.onPost("/final-review/adjustment-proposals/p1/decision", {
      proposal_id: "p1",
      status: "pending",
      new_version: null,
      active_version: null,
      run_id: "run_adjust",
      pending: true,
    });

    const result = await api.resolveAdjustmentProposal("p1", "APPROVED", null, "k-decide");

    assert.equal(result.pending, true);
    assert.equal(result.new_version, null);
    assert.equal(result.run_id, "run_adjust");
    assert.equal(mock.lastRequest().headers["Idempotency-Key"], "k-decide");
  });

  it("拒绝决策不产生任何写命令", async () => {
    mock.onPost("/final-review/adjustment-proposals/p2/decision", {
      proposal_id: "p2",
      status: "rejected",
      new_version: null,
      pending: false,
    });

    const result = await api.resolveAdjustmentProposal("p2", "REJECTED", "时间不够", "k-reject");

    assert.equal(result.status, "rejected");
    assert.equal(result.new_version, null);
    assert.equal(result.run_id, undefined);
    assert.ok(mock.requests.every((r) => !r.url.includes("/activate")));
  });
});

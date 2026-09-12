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
    await api.activateFinalReviewCampaign("c1", "k-act");

    const [c, g, a] = mock.requests;
    assert.equal(c.headers["Idempotency-Key"], "k-campaign");
    assert.equal(g.headers["Idempotency-Key"], "k-gen");
    assert.equal(a.headers["Idempotency-Key"], "k-act");
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
});
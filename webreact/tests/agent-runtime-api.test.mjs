/**
 * Agent Runtime API adapter 契约测试：
 * - 端点路径与方法
 * - Idempotency-Key header 传递
 * - 错误 envelope 映射
 * - 通知事务 manual → workflow 顺序
 * - 不走旧 extractNotice→createTask 路径
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

describe("runtime common endpoints", () => {
  it("getAgentCapabilities GET /agent-runtime/capabilities", async () => {
    mock.onGet("/agent-runtime/capabilities", { contract_version: "v1" });
    const out = await api.getAgentCapabilities();
    assert.equal(mock.lastRequest().url, "/agent-runtime/capabilities");
    assert.equal(out.contract_version, "v1");
  });

  it("createAgentJob POST /agent-jobs 并带 Idempotency-Key", async () => {
    mock.onPost("/agent-jobs", { job_id: "j1" });
    await api.createAgentJob({ job_kind: "final_review" }, "idem-1");
    const req = mock.lastRequest();
    assert.equal(req.url, "/agent-jobs");
    assert.equal(req.headers["Idempotency-Key"], "idem-1");
  });

  it("cancelAgentRun POST /agent-runs/:id/cancel 带 key", async () => {
    mock.onPost("/agent-runs/r1/cancel", { status: "CANCELLED" });
    await api.cancelAgentRun("r1", "idem-c");
    assert.equal(mock.lastRequest().headers["Idempotency-Key"], "idem-c");
  });

  it("resolveAgentApproval 传递 decision 与 reason", async () => {
    mock.onPost("/agent-approvals/a1/decision", { status: "APPROVED" });
    await api.resolveAgentApproval("a1", "APPROVED", "用户确认", "idem-a");
    const req = mock.lastRequest();
    assert.deepEqual(req.data, { decision: "APPROVED", reason: "用户确认" });
  });

  it("agentRunStreamUrl 构造 SSE 路径", () => {
    assert.equal(api.agentRunStreamUrl("r1"), "/agent-runs/r1/events/stream");
  });
});

describe("final-review endpoints", () => {
  it("createFinalReviewCampaign POST 并带 key", async () => {
    mock.onPost("/final-review/campaigns", { campaign_id: "c1" });
    await api.createFinalReviewCampaign({ exam_ids: ["e1"] }, "idem-fr");
    assert.equal(mock.lastRequest().headers["Idempotency-Key"], "idem-fr");
  });

  it("generateFinalReviewPlan 路径含 campaignId", async () => {
    mock.onPost("/final-review/campaigns/c1/plans/generate", { run_id: "r1" });
    await api.generateFinalReviewPlan("c1", { daily_capacity_minutes: 120 }, "idem-g");
    assert.equal(mock.lastRequest().url, "/final-review/campaigns/c1/plans/generate");
  });

  it("activateFinalReviewCampaign POST activate", async () => {
    mock.onPost("/final-review/campaigns/c1/activate", { status: "ACTIVE" });
    await api.activateFinalReviewCampaign("c1", "idem-act");
    assert.equal(mock.lastRequest().url, "/final-review/campaigns/c1/activate");
  });

  it("getTodayAgenda GET agendas/today", async () => {
    mock.onGet("/final-review/campaigns/c1/agendas/today", { items: [] });
    await api.getTodayAgenda("c1");
    assert.equal(mock.lastRequest().url, "/final-review/campaigns/c1/agendas/today");
  });

  it("resolveAdjustmentProposal 传递 decision", async () => {
    mock.onPost("/final-review/adjustment-proposals/p1/decision", { status: "ACCEPTED" });
    await api.resolveAdjustmentProposal("p1", "ACCEPTED", null, "idem-p");
    assert.deepEqual(mock.lastRequest().data, { decision: "ACCEPTED" });
  });
});

describe("notice workflow endpoints", () => {
  it("createManualNotice POST /notices/manual 得到 server notice_id", async () => {
    mock.onPost("/notices/manual", { notice_id: "n1", source: "manual_input" });
    const out = await api.createManualNotice({ content: "明天交作业" }, "idem-m");
    assert.equal(mock.lastRequest().url, "/notices/manual");
    assert.equal(out.notice_id, "n1");
  });

  it("createNoticeWorkflow 用 server notice_id 创建 workflow", async () => {
    mock.onPost("/notices/n1/workflow", { workflow_id: "w1" });
    const out = await api.createNoticeWorkflow("n1", {}, "idem-w");
    assert.equal(mock.lastRequest().url, "/notices/n1/workflow");
    assert.equal(out.workflow_id, "w1");
  });

  it("manual→workflow 顺序：先 manual 再 workflow，两步独立 idempotency key", async () => {
    mock.onPost("/notices/manual", { notice_id: "n2" });
    mock.onPost("/notices/n2/workflow", { workflow_id: "w2" });
    const notice = await api.createManualNotice({ content: "x" }, "key-manual");
    const workflow = await api.createNoticeWorkflow(notice.notice_id, {}, "key-workflow");
    assert.equal(notice.notice_id, "n2");
    assert.equal(workflow.workflow_id, "w2");
    const manualReq = mock.findRequests("post", "/notices/manual")[0];
    const wfReq = mock.findRequests("post", "/notices/n2/workflow")[0];
    assert.equal(manualReq.headers["Idempotency-Key"], "key-manual");
    assert.equal(wfReq.headers["Idempotency-Key"], "key-workflow");
  });

  it("decideNoticeWorkflowAction 与 executeNoticeWorkflowAction 路径", async () => {
    mock.onPost("/notice-workflow-actions/a1/decision", { status: "APPROVED" });
    await api.decideNoticeWorkflowAction("a1", "APPROVED", null, "k1");
    assert.equal(mock.lastRequest().url, "/notice-workflow-actions/a1/decision");

    mock.onPost("/notice-workflow-actions/a2/execute", { status: "EXECUTING" });
    await api.executeNoticeWorkflowAction("a2", "k2");
    assert.equal(mock.lastRequest().url, "/notice-workflow-actions/a2/execute");
  });
});

describe("course research endpoints", () => {
  it("createCourseResearchRun POST 并带 key", async () => {
    mock.onPost("/course-research/runs", { run_id: "r1" });
    await api.createCourseResearchRun({ question: "解释梯度下降", course_id: "c1" }, "idem-cr");
    const req = mock.lastRequest();
    assert.equal(req.url, "/course-research/runs");
    assert.equal(req.headers["Idempotency-Key"], "idem-cr");
  });

  it("cancelCourseResearchRun 路径", async () => {
    mock.onPost("/course-research/runs/r1/cancel", { status: "CANCELLED" });
    await api.cancelCourseResearchRun("r1", "k");
    assert.equal(mock.lastRequest().url, "/course-research/runs/r1/cancel");
  });

  it("getCourseResearchArtifacts 路径", async () => {
    mock.onGet("/course-research/runs/r1/artifacts", { items: [] });
    await api.getCourseResearchArtifacts("r1");
    assert.equal(mock.lastRequest().url, "/course-research/runs/r1/artifacts");
  });
});

describe("error envelope mapping through adapter", () => {
  it("AGENT_APPROVAL_REQUIRED 映射为可操作错误", async () => {
    mock.onError("post", "/agent-approvals/a1/decision", 409, {
      code: "AGENT_APPROVAL_REQUIRED",
      message: "需要用户确认后继续",
      request_id: "r1",
      details: { approval_id: "a1" },
    });
    await assert.rejects(
      api.resolveAgentApproval("a1", "APPROVED", null, "k"),
      (err) => {
        assert.equal(err.code, "AGENT_APPROVAL_REQUIRED");
        assert.equal(err.action, "open_approval");
        assert.equal(err.actionable, true);
        assert.equal(err.details.approval_id, "a1");
        return true;
      },
    );
  });

  it("未知 code 回落 UNKNOWN 且无危险动作", async () => {
    mock.onError("post", "/agent-jobs", 500, { code: "AGENT_NEW", message: "x" });
    await assert.rejects(
      api.createAgentJob({}, "k"),
      (err) => {
        assert.equal(err.code, "UNKNOWN");
        assert.equal(err.actionable, false);
        return true;
      },
    );
  });

  it("503 无 body 映射为 UNKNOWN 且不崩溃", async () => {
    mock.onError("get", "/agent-runtime/capabilities", 503, null);
    await assert.rejects(
      api.getAgentCapabilities(),
      (err) => {
        assert.equal(err.code, "UNKNOWN");
        assert.equal(err.actionable, false);
        return true;
      },
    );
  });
});

describe("idempotency key export", () => {
  it("createIdempotencyKey 可用且格式稳定", () => {
    const k = api.createIdempotencyKey("final_review");
    assert.match(k, /^web_final_review_/);
  });
});
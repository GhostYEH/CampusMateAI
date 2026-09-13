/**
 * Phase 6B: 学习计划、效果观察与数据控制 API 契约测试。
 * 导入真实 learnerStateApi.js，验证计划全生命周期、evaluation、数据源控制的真实请求。
 */
import "./helpers/setup-globals.mjs";
import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";

import * as api from "../src/data/learnerStateApi.js";
import { client } from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";

let mock;

beforeEach(() => {
  mock = createMockClient(client);
});

afterEach(() => {
  mock.reset();
  mock.clearTokens();
});

// ===== 学习计划生成与查询 =====

describe("generateLearningPlan", () => {
  it("POST /learning-plans/generate 并传递 body", async () => {
    mock.onPost("/learning-plans/generate", { plan_id: "p1", status: "PROPOSED" });
    const body = { scope: "USER", idempotency_key: "gen-1" };
    const result = await api.generateLearningPlan(body);
    const req = mock.lastRequest();
    assert.equal(req.url, "/learning-plans/generate");
    assert.deepEqual(req.data, body);
    assert.equal(result.plan_id, "p1");
    assert.equal(result.status, "PROPOSED");
  });
});

describe("getLearningPlans", () => {
  it("GET /learning-plans 并传递分页", async () => {
    mock.onGet("/learning-plans", { items: [], total: 0 });
    await api.getLearningPlans(2, 10);
    const req = mock.lastRequest();
    assert.equal(req.url, "/learning-plans");
    assert.equal(req.params.page, 2);
    assert.equal(req.params.page_size, 10);
  });
});

describe("getLearningPlan", () => {
  it("GET /learning-plans/:id", async () => {
    mock.onGet("/learning-plans/p1", { plan_id: "p1", status: "PROPOSED", items: [] });
    const result = await api.getLearningPlan("p1");
    assert.equal(mock.lastRequest().url, "/learning-plans/p1");
    assert.equal(result.plan_id, "p1");
  });
});

// ===== 计划决策与执行 =====

describe("decideLearningPlan", () => {
  it("POST /learning-plans/:id/decision 传递 ACCEPT", async () => {
    mock.onPost("/learning-plans/p1/decision", { plan_id: "p1", status: "ACCEPTED" });
    await api.decideLearningPlan("p1", "ACCEPT");
    const req = mock.lastRequest();
    assert.equal(req.url, "/learning-plans/p1/decision");
    assert.deepEqual(req.data, { decision: "ACCEPT" });
  });

  it("POST /learning-plans/:id/decision 传递 REJECT", async () => {
    mock.onPost("/learning-plans/p1/decision", { plan_id: "p1", status: "REJECTED" });
    await api.decideLearningPlan("p1", "REJECT");
    assert.deepEqual(mock.lastRequest().data, { decision: "REJECT" });
  });
});

describe("executeLearningPlan", () => {
  it("POST /learning-plans/:id/execute 传递空 body", async () => {
    mock.onPost("/learning-plans/p1/execute", { plan_id: "p1", status: "EXECUTED" });
    await api.executeLearningPlan("p1");
    const req = mock.lastRequest();
    assert.equal(req.url, "/learning-plans/p1/execute");
    assert.deepEqual(req.data, {});
  });
});

describe("undoLearningPlan", () => {
  it("POST /learning-plans/:id/undo 传递空 body", async () => {
    mock.onPost("/learning-plans/p1/undo", { plan_id: "p1", status: "UNDONE" });
    await api.undoLearningPlan("p1");
    assert.equal(mock.lastRequest().url, "/learning-plans/p1/undo");
    assert.deepEqual(mock.lastRequest().data, {});
  });
});

describe("replanLearningPlan", () => {
  it("POST /learning-plans/:id/replan 传递 body", async () => {
    mock.onPost("/learning-plans/p1/replan", { plan_id: "p2", status: "PROPOSED" });
    const body = { idempotency_key: "replan-1" };
    await api.replanLearningPlan("p1", body);
    const req = mock.lastRequest();
    assert.equal(req.url, "/learning-plans/p1/replan");
    assert.deepEqual(req.data, body);
  });
});

// ===== 计划反馈 =====

describe("submitPlanFeedback", () => {
  it("POST /learning-plans/:id/feedback 传递 feedback", async () => {
    mock.onPost("/learning-plans/p1/feedback", { ok: true });
    await api.submitPlanFeedback("p1", "HELPFUL");
    const req = mock.lastRequest();
    assert.equal(req.url, "/learning-plans/p1/feedback");
    assert.deepEqual(req.data, { feedback: "HELPFUL" });
  });

  it("支持所有 7 种反馈类型", async () => {
    const options = [
      "HELPFUL", "NOT_HELPFUL", "TOO_LONG", "TOO_SHORT",
      "WRONG_PRIORITY", "ALREADY_DONE", "MISSING_CONTEXT",
    ];
    for (const fb of options) {
      mock.reset();
      mock.onPost("/learning-plans/p1/feedback", { ok: true });
      await api.submitPlanFeedback("p1", fb);
      assert.equal(mock.lastRequest().data.feedback, fb);
    }
  });
});

// ===== 计划效果观察 =====

describe("getPlanEvaluation", () => {
  it("GET /learning-plans/:id/evaluation 返回效果数据", async () => {
    const evaluation = {
      plan_id: "p1",
      planned_item_count: 3,
      executed_item_count: 2,
      completed_plan_task_count: 2,
      followup_practice_count: 1,
      warning_codes: [],
    };
    mock.onGet("/learning-plans/p1/evaluation", evaluation);
    const result = await api.getPlanEvaluation("p1");
    assert.equal(mock.lastRequest().url, "/learning-plans/p1/evaluation");
    assert.equal(result.planned_item_count, 3);
    assert.equal(result.executed_item_count, 2);
    assert.equal(result.completed_plan_task_count, 2);
    assert.equal(result.followup_practice_count, 1);
  });

  it("evaluation 包含 warning_codes 数组", async () => {
    mock.onGet("/learning-plans/p1/evaluation", {
      plan_id: "p1",
      planned_item_count: 1,
      executed_item_count: 0,
      completed_plan_task_count: 0,
      followup_practice_count: 0,
      warning_codes: ["PLAN_STALE"],
    });
    const result = await api.getPlanEvaluation("p1");
    assert.deepEqual(result.warning_codes, ["PLAN_STALE"]);
  });
});

// ===== 数据源控制 =====

describe("getDataControls", () => {
  it("GET /learner-state/data-controls 返回 7 个数据源", async () => {
    const controls = {
      items: [
        { source_key: "CORE_STUDY", status: "ENABLED", can_pause: true, can_resume: false },
        { source_key: "PERSONAL_TASK", status: "ENABLED", can_pause: true, can_resume: false },
        { source_key: "CHAOXING", status: "PAUSED", can_pause: false, can_resume: true },
        { source_key: "EDU", status: "ENABLED", can_pause: true, can_resume: false },
        { source_key: "PRACTICE", status: "ENABLED", can_pause: true, can_resume: false },
        { source_key: "MODEL_SHADOW", status: "ENABLED", can_pause: true, can_resume: false },
        { source_key: "PROACTIVE_SUGGESTIONS", status: "ENABLED", can_pause: true, can_resume: false },
      ],
    };
    mock.onGet("/learner-state/data-controls", controls);
    const result = await api.getDataControls();
    assert.equal(mock.lastRequest().url, "/learner-state/data-controls");
    assert.equal(result.items.length, 7);
    const keys = result.items.map((s) => s.source_key);
    assert.ok(keys.includes("MODEL_SHADOW"));
    assert.ok(keys.includes("PRACTICE"));
  });
});

describe("updateDataControl", () => {
  it("PUT /data-controls/:key 传递 status 和 idempotency_key", async () => {
    mock.onPut("/learner-state/data-controls/PRACTICE", { source_key: "PRACTICE", status: "PAUSED" });
    await api.updateDataControl("PRACTICE", "PAUSED", "toggle-123");
    const req = mock.lastRequest();
    assert.equal(req.url, "/learner-state/data-controls/PRACTICE");
    assert.equal(req.data.status, "PAUSED");
    assert.equal(req.data.idempotency_key, "toggle-123");
  });

  it("恢复数据源时 status=ENABLED", async () => {
    mock.onPut("/learner-state/data-controls/PRACTICE", { source_key: "PRACTICE", status: "ENABLED" });
    await api.updateDataControl("PRACTICE", "ENABLED", "toggle-456");
    assert.equal(mock.lastRequest().data.status, "ENABLED");
  });
});

// ===== 数据摘要 =====

describe("getDataSummary", () => {
  it("GET /learner-state/data-summary 返回摘要", async () => {
    const summary = {
      event_count: 100,
      snapshot_count: 20,

      learning_plan_count: 5,
      shadow_run_count: 8,
    };
    mock.onGet("/learner-state/data-summary", summary);
    const result = await api.getDataSummary();
    assert.equal(mock.lastRequest().url, "/learner-state/data-summary");
    assert.equal(result.event_count, 100);
    assert.equal(result.shadow_run_count, 8);
  });
});

// ===== 模型透明度 =====

describe("getModelTransparency", () => {
  it("GET /learner-state/model-transparency 返回能力列表", async () => {
    const transparency = {
      capabilities: [
        {
          capability_name: "forecast_baseline_v1",
          production_method: "rule_based",
          campusmate_lm_status: "SHADOW_ONLY",
          quality_gate_passed: true,
          performance_measured: false,
          performance_gate_passed: null,
          uses_real_model_inference: false,
        },
        {
          capability_name: "learning_summary_v1",
          production_method: "rule_based",
          campusmate_lm_status: "ELIGIBLE_FOR_CANARY",
          quality_gate_passed: true,
          performance_measured: true,
          performance_gate_passed: true,
          uses_real_model_inference: true,
        },
      ],
    };
    mock.onGet("/learner-state/model-transparency", transparency);
    const result = await api.getModelTransparency();
    assert.equal(mock.lastRequest().url, "/learner-state/model-transparency");
    assert.equal(result.capabilities.length, 2);
    assert.equal(result.capabilities[0].campusmate_lm_status, "SHADOW_ONLY");
    assert.equal(result.capabilities[1].uses_real_model_inference, true);
  });

  it("performance_measured=false 时不声称已上线", async () => {
    mock.onGet("/learner-state/model-transparency", {
      capabilities: [{
        capability_name: "forecast_baseline_v1",
        campusmate_lm_status: "SHADOW_ONLY",
        performance_measured: false,
        uses_real_model_inference: false,
      }],
    });
    const result = await api.getModelTransparency();
    assert.ok(!result.capabilities[0].performance_measured);
    assert.ok(!result.capabilities[0].uses_real_model_inference);
  });
});

// ===== mutation 后数据刷新 =====

describe("计划操作后数据刷新", () => {
  it("接受计划后再次获取计划列表发出新请求", async () => {
    mock.onPost("/learning-plans/p1/decision", { plan_id: "p1", status: "ACCEPTED" });
    mock.onGet("/learning-plans", { items: [], total: 0 });

    await api.getLearningPlans(1, 10);
    assert.equal(mock.findRequests("get", "/learning-plans").length, 1);

    await api.decideLearningPlan("p1", "ACCEPT");

    await api.getLearningPlans(1, 10);
    assert.equal(mock.findRequests("get", "/learning-plans").length, 2);
  });

  it("执行计划后获取 evaluation 发出新请求", async () => {
    mock.onPost("/learning-plans/p1/execute", { plan_id: "p1", status: "EXECUTED" });
    mock.onGet("/learning-plans/p1/evaluation", { plan_id: "p1", planned_item_count: 1 });

    await api.executeLearningPlan("p1");
    const result = await api.getPlanEvaluation("p1");
    assert.equal(result.planned_item_count, 1);
    assert.equal(mock.findRequests("get", "evaluation").length, 1);
  });
});

describe("数据源切换后刷新", () => {
  it("暂停 PRACTICE 后再次获取 controls 发出新请求", async () => {
    mock.onPut("/learner-state/data-controls/PRACTICE", { status: "PAUSED" });
    mock.onGet("/learner-state/data-controls", { items: [] });

    await api.getDataControls();
    assert.equal(mock.findRequests("get", "data-controls").length, 1);

    await api.updateDataControl("PRACTICE", "PAUSED", "k1");

    await api.getDataControls();
    assert.equal(mock.findRequests("get", "data-controls").length, 2);
  });
});

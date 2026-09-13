/**
 * Phase 6B: 删除、隐私控制与错误边界 API 契约测试。
 * 导入真实 learnerStateApi.js，验证删除请求、删除状态、错误码和 401 刷新。
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

// ===== 删除请求 =====

describe("requestDeletion", () => {
  it("POST /learner-state/delete-request 传递 scope 和 idempotency_key", async () => {
    mock.onPost("/learner-state/delete-request", { status: "COMPLETED", scope: "MODEL_SHADOW_ONLY" });
    const result = await api.requestDeletion("MODEL_SHADOW_ONLY", "delete-key-1");
    const req = mock.lastRequest();
    assert.equal(req.url, "/learner-state/delete-request");
    assert.equal(req.data.scope, "MODEL_SHADOW_ONLY");
    assert.equal(req.data.idempotency_key, "delete-key-1");
    assert.equal(result.status, "COMPLETED");
  });

  it("支持所有 6 种删除范围", async () => {
    const scopes = [
      "STATE_ONLY",
      "EVENTS_AND_STATE",
      "KNOWLEDGE_ONLY",
      "PLANS_ONLY",
      "MODEL_SHADOW_ONLY",
      "ALL_LEARNER_MODEL_DATA",
    ];
    for (const scope of scopes) {
      mock.reset();
      mock.onPost("/learner-state/delete-request", { status: "COMPLETED", scope });
      await api.requestDeletion(scope, `key-${scope}`);
      assert.equal(mock.lastRequest().data.scope, scope);
    }
  });

  it("MODEL_SHADOW_ONLY 不删除账号数据", async () => {
    mock.onPost("/learner-state/delete-request", { status: "COMPLETED", scope: "MODEL_SHADOW_ONLY" });
    const result = await api.requestDeletion("MODEL_SHADOW_ONLY", "key-1");
    assert.equal(result.scope, "MODEL_SHADOW_ONLY");
    // scope 仅为模型影子，不影响账号
    assert.notEqual(result.scope, "ALL_LEARNER_MODEL_DATA");
  });
});

describe("getDeleteStatus", () => {
  it("GET /learner-state/delete-status 返回删除状态", async () => {
    mock.onGet("/learner-state/delete-status", {
      in_progress: false,
      last_scope: "MODEL_SHADOW_ONLY",
      last_completed_at: "2026-09-01T10:00:00Z",
    });
    const result = await api.getDeleteStatus();
    assert.equal(mock.lastRequest().url, "/learner-state/delete-status");
    assert.equal(result.in_progress, false);
    assert.equal(result.last_scope, "MODEL_SHADOW_ONLY");
  });
});

// ===== 删除确认流程 =====

describe("删除确认流程", () => {
  it("requestDeletion → getDeleteStatus 验证删除完成", async () => {
    mock.onPost("/learner-state/delete-request", { status: "COMPLETED", scope: "PLANS_ONLY" });
    mock.onGet("/learner-state/delete-status", { in_progress: false, last_scope: "PLANS_ONLY" });

    const del = await api.requestDeletion("PLANS_ONLY", "key-1");
    assert.equal(del.status, "COMPLETED");

    const status = await api.getDeleteStatus();
    assert.ok(!status.in_progress);
    assert.equal(status.last_scope, "PLANS_ONLY");
  });
});

// ===== 纠正错误码 =====

describe("纠正错误码", () => {
  it("撤销不存在的纠正返回 404 LEARNER_CORRECTION_NOT_FOUND", async () => {
    mock.onError("post", "/learner-state/corrections/ghost/revoke", 404, {
      code: "LEARNER_CORRECTION_NOT_FOUND",
      message: "纠正记录不存在",
    });
    await assert.rejects(
      () => api.revokeCorrection("ghost", "key"),
      (err) => {
        assert.equal(err.code, "LEARNER_CORRECTION_NOT_FOUND");
        assert.equal(err.message, "纠正记录不存在");
        assert.equal(err.status, 404);
        return true;
      },
    );
  });

  it("重复撤销返回 409 LEARNER_CORRECTION_ALREADY_REVOKED", async () => {
    mock.onError("post", "/learner-state/corrections/c1/revoke", 409, {
      code: "LEARNER_CORRECTION_ALREADY_REVOKED",
      message: "纠正已撤销",
    });
    await assert.rejects(
      () => api.revokeCorrection("c1", "key"),
      (err) => {
        assert.equal(err.code, "LEARNER_CORRECTION_ALREADY_REVOKED");
        return true;
      },
    );
  });
});

// ===== 删除错误码 =====

describe("删除错误码", () => {
  it("无效 scope 返回 400 LEARNER_DELETE_SCOPE_INVALID", async () => {
    mock.onError("post", "/learner-state/delete-request", 400, {
      code: "LEARNER_DELETE_SCOPE_INVALID",
      message: "删除范围无效",
    });
    await assert.rejects(
      () => api.requestDeletion("INVALID_SCOPE", "key"),
      (err) => {
        assert.equal(err.code, "LEARNER_DELETE_SCOPE_INVALID");
        return true;
      },
    );
  });

  it("删除进行中返回 409 LEARNER_DELETE_IN_PROGRESS", async () => {
    mock.onError("post", "/learner-state/delete-request", 409, {
      code: "LEARNER_DELETE_IN_PROGRESS",
      message: "删除正在进行中",
    });
    await assert.rejects(
      () => api.requestDeletion("STATE_ONLY", "key"),
      (err) => err.code === "LEARNER_DELETE_IN_PROGRESS",
    );
  });
});

// ===== 数据源控制错误码 =====

describe("数据源控制错误码", () => {
  it("不支持的数据源返回 400 LEARNER_SOURCE_NOT_SUPPORTED", async () => {
    mock.onError("put", "/learner-state/data-controls/UNKNOWN", 400, {
      code: "LEARNER_SOURCE_NOT_SUPPORTED",
      message: "数据源不支持",
    });
    await assert.rejects(
      () => api.updateDataControl("UNKNOWN", "PAUSED", "key"),
      (err) => err.code === "LEARNER_SOURCE_NOT_SUPPORTED",
    );
  });

  it("冲突状态返回 409 LEARNER_SOURCE_CONTROL_CONFLICT", async () => {
    mock.onError("put", "/learner-state/data-controls/CHAOXING", 409, {
      code: "LEARNER_SOURCE_CONTROL_CONFLICT",
      message: "数据源状态冲突",
    });
    await assert.rejects(
      () => api.updateDataControl("CHAOXING", "PAUSED", "key"),
      (err) => err.code === "LEARNER_SOURCE_CONTROL_CONFLICT",
    );
  });
});

// ===== 401 刷新在删除端点 =====

describe("删除端点 401 刷新", () => {
  it("删除请求 401 后自动刷新并重试", async () => {
    mock.setTokens("expired", "valid-refresh");
    mock.onPost("/api/v1/auth/refresh", { access_token: "new", refresh_token: "new-r" });
    mock.onSequence("post", "/learner-state/delete-request", [
      { error: true, status: 401, data: { detail: "token expired" } },
      { status: 200, data: { status: "COMPLETED", scope: "STATE_ONLY" } },
    ]);

    const result = await api.requestDeletion("STATE_ONLY", "key-1");
    assert.equal(result.status, "COMPLETED");
    assert.equal(mock.findRequests("post", "delete-request").length, 2);
  });
});

// ===== 模型透明度字段验证 =====

describe("模型透明度字段", () => {
  it("fixture_only=true 时不声称真实推理", async () => {
    mock.onGet("/learner-state/model-transparency", {
      capabilities: [{
        capability_name: "forecast_baseline_v1",
        campusmate_lm_status: "SHADOW_ONLY",
        performance_measured: false,
        uses_real_model_inference: false,
        fixture_only: true,
      }],
    });
    const result = await api.getModelTransparency();
    assert.ok(result.capabilities[0].fixture_only);
    assert.ok(!result.capabilities[0].uses_real_model_inference);
  });

  it("canary_active=true 时 uses_real_model_inference=true", async () => {
    mock.onGet("/learner-state/model-transparency", {
      capabilities: [{
        capability_name: "learning_summary_v1",
        campusmate_lm_status: "ELIGIBLE_FOR_CANARY",
        performance_measured: true,
        performance_gate_passed: true,
        uses_real_model_inference: true,
        canary_active: true,
      }],
    });
    const result = await api.getModelTransparency();
    assert.ok(result.capabilities[0].canary_active);
    assert.ok(result.capabilities[0].uses_real_model_inference);
  });
});

// ===== itemsOf 复用验证 =====

describe("itemsOf", () => {
  it("从 {items:[]} 结构提取数组", async () => {
    const { itemsOf } = api;
    assert.deepEqual(itemsOf({ items: [1, 2, 3] }), [1, 2, 3]);
    assert.deepEqual(itemsOf([4, 5]), [4, 5]);
    assert.deepEqual(itemsOf(null), []);
    assert.deepEqual(itemsOf({}), []);
  });
});

/**
 * Phase 6B: 学习状态页面 API 契约测试。
 * 导入真实 learnerStateApi.js，mock axios adapter 边界，
 * 验证真实 URL、参数、请求体、错误映射、401 刷新、204 处理。
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

// ===== 状态投影 URL 与参数 =====

describe("getLearnerStateRuns", () => {
  it("请求 /learner-state/runs 并传递分页参数", async () => {
    mock.onGet("/learner-state/runs", { items: [], total: 0 });
    await api.getLearnerStateRuns(2, 30);
    const req = mock.lastRequest();
    assert.equal(req.url, "/learner-state/runs");
    assert.equal(req.params.page, 2);
    assert.equal(req.params.page_size, 30);
  });

  it("使用默认分页 page=1 page_size=20", async () => {
    mock.onGet("/learner-state/runs", { items: [], total: 0 });
    await api.getLearnerStateRuns();
    const req = mock.lastRequest();
    assert.equal(req.params.page, 1);
    assert.equal(req.params.page_size, 20);
  });
});

describe("getLearnerStateChanges", () => {
  it("请求 /learner-state/changes 并传递所有筛选参数", async () => {
    mock.onGet("/learner-state/changes", { items: [], total: 0 });
    await api.getLearnerStateChanges({
      page: 3,
      pageSize: 50,
      fromRunId: "run-1",
      toRunId: "run-9",
      scopeType: "USER",
      stateType: "task_workload",
    });
    const req = mock.lastRequest();
    assert.equal(req.url, "/learner-state/changes");
    assert.equal(req.params.page, 3);
    assert.equal(req.params.page_size, 50);
    assert.equal(req.params.from_run_id, "run-1");
    assert.equal(req.params.to_run_id, "run-9");
    assert.equal(req.params.scope_type, "USER");
    assert.equal(req.params.state_type, "task_workload");
  });

  it("省略可选参数时不发送对应 query", async () => {
    mock.onGet("/learner-state/changes", { items: [], total: 0 });
    await api.getLearnerStateChanges();
    const req = mock.lastRequest();
    assert.equal(req.params.page, 1);
    assert.equal(req.params.page_size, 20);
    assert.ok(!("from_run_id" in req.params));
    assert.ok(!("scope_type" in req.params));
  });
});

describe("getLearnerStateSnapshots", () => {
  it("请求 /learner-state/snapshots 并传递筛选参数", async () => {
    mock.onGet("/learner-state/snapshots", { items: [], total: 0 });
    await api.getLearnerStateSnapshots({
      pageSize: 50,
      scopeType: "USER",
      stateType: "task_workload",
      courseId: "cs101",
    });
    const req = mock.lastRequest();
    assert.equal(req.url, "/learner-state/snapshots");
    assert.equal(req.params.page_size, 50);
    assert.equal(req.params.scope_type, "USER");
    assert.equal(req.params.state_type, "task_workload");
    assert.equal(req.params.course_id, "cs101");
  });

  it("默认 page_size=50", async () => {
    mock.onGet("/learner-state/snapshots", { items: [], total: 0 });
    await api.getLearnerStateSnapshots();
    const req = mock.lastRequest();
    assert.equal(req.params.page_size, 50);
  });
});

describe("getSnapshotEvidence", () => {
  it("URL 包含 snapshotId 并传递分页参数", async () => {
    mock.onGet("/learner-state/snapshots/snap-42/evidence", { items: [], total: 0 });
    await api.getSnapshotEvidence("snap-42", 2, 30);
    const req = mock.lastRequest();
    assert.equal(req.url, "/learner-state/snapshots/snap-42/evidence");
    assert.equal(req.params.page, 2);
    assert.equal(req.params.page_size, 30);
  });
});

// ===== 知识点与误区 =====

describe("getTaxonomy", () => {
  it("请求 /learner-state/taxonomy", async () => {
    mock.onGet("/learner-state/taxonomy", { categories: [] });
    await api.getTaxonomy();
    assert.equal(mock.lastRequest().url, "/learner-state/taxonomy");
  });
});

describe("getKnowledgeState", () => {
  it("无 courseId 时不发送 course_id 参数", async () => {
    mock.onGet("/learner-state/knowledge", { items: [] });
    await api.getKnowledgeState("");
    const req = mock.lastRequest();
    assert.equal(req.url, "/learner-state/knowledge");
    assert.ok(!("course_id" in req.params));
  });

  it("有 courseId 时发送 course_id 参数", async () => {
    mock.onGet("/learner-state/knowledge", { items: [] });
    await api.getKnowledgeState("cs101");
    assert.equal(mock.lastRequest().params.course_id, "cs101");
  });
});

describe("getMisconceptionHypotheses", () => {
  it("请求 /learner-state/hypotheses 并可选传递 course_id", async () => {
    mock.onGet("/learner-state/hypotheses", { items: [] });
    await api.getMisconceptionHypotheses("cs101");
    assert.equal(mock.lastRequest().url, "/learner-state/hypotheses");
    assert.equal(mock.lastRequest().params.course_id, "cs101");
  });
});

describe("decideHypothesis", () => {
  it("POST 到 /hypotheses/:id/decision 并传递 decision body", async () => {
    mock.onPost("/learner-state/hypotheses/h-7/decision", { ok: true });
    await api.decideHypothesis("h-7", "CONFIRM");
    const req = mock.lastRequest();
    assert.equal(req.url, "/learner-state/hypotheses/h-7/decision");
    assert.deepEqual(req.data, { decision: "CONFIRM" });
  });
});

// ===== 错误映射 =====

describe("错误映射", () => {
  it("后端 {code, message} 错误转换为 Error.message 中文文案", async () => {
    mock.onError("get", "/learner-state/runs", 400, {
      code: "VALIDATION_FAILED",
      message: "参数校验失败",
    });
    await assert.rejects(
      () => api.getLearnerStateRuns(),
      (err) => {
        assert.equal(err.message, "参数校验失败");
        assert.equal(err.code, "VALIDATION_FAILED");
        assert.equal(err.status, 400);
        return true;
      },
    );
  });

  it("后端 {detail} 错误兼容映射", async () => {
    mock.onError("get", "/learner-state/runs", 404, { detail: "快照不存在" });
    await assert.rejects(
      () => api.getLearnerStateRuns(),
      (err) => {
        assert.equal(err.message, "快照不存在");
        return true;
      },
    );
  });

  it("网络层错误映射为中文兜底", async () => {
    // 模拟无 response 的网络错误（adapter 抛含 request 的 axios 错误）
    client.defaults.adapter = () => Promise.reject(Object.assign(new Error("connect ECONNREFUSED"), { request: {} }));
    await assert.rejects(
      () => api.getLearnerStateRuns(),
      (err) => {
        assert.equal(err.message, "网络连接失败，请稍后重试");
        assert.equal(err.code, "NETWORK_ERROR");
        return true;
      },
    );
  });
});

// ===== 204 No Content =====

describe("204 No Content", () => {
  it("返回 null 而非 undefined", async () => {
    mock.onPost("/learner-state/hypotheses/h-1/decision", null, 204);
    const result = await api.decideHypothesis("h-1", "REJECT");
    assert.equal(result, null);
  });
});

// ===== 401 刷新 =====

describe("401 token 刷新", () => {
  it("401 后自动刷新 token 并重试成功", async () => {
    mock.setTokens("expired-token", "valid-refresh");

    // /auth/refresh 由全局 axios 发出，URL 含 baseURL 前缀
    mock.onPost("/api/v1/auth/refresh", {
      access_token: "new-token",
      refresh_token: "new-refresh",
    });

    // 首次 401，重试 200
    mock.onSequence("get", "/learner-state/taxonomy", [
      { error: true, status: 401, data: { detail: "token expired" } },
      { status: 200, data: { categories: ["foundations"] } },
    ]);

    const result = await api.getTaxonomy();
    assert.deepEqual(result, { categories: ["foundations"] });

    // 验证发了两次请求（第一次 401，第二次重试）
    const reqs = mock.findRequests("get", "/learner-state/taxonomy");
    assert.equal(reqs.length, 2);
  });

  it("refresh token 不存在时抛出登录过期错误", async () => {
    mock.setTokens("expired-token", null);
    mock.onError("get", "/learner-state/taxonomy", 401, { detail: "token expired" });

    await assert.rejects(
      () => api.getTaxonomy(),
      (err) => err.message.includes("登录已过期"),
    );
  });
});

// ===== mutation 后数据刷新 =====

describe("mutation 后数据刷新", () => {
  it("decideHypothesis 后再次调用 getLearnerStateSnapshots 发出新请求", async () => {
    mock.onPost("/learner-state/hypotheses/h-1/decision", { ok: true });
    mock.onGet("/learner-state/snapshots", { items: [], total: 0 });

    // 初始加载
    await api.getLearnerStateSnapshots({ pageSize: 50 });
    assert.equal(mock.findRequests("get", "/learner-state/snapshots").length, 1);

    // mutation
    await api.decideHypothesis("h-1", "CONFIRM");

    // 刷新
    await api.getLearnerStateSnapshots({ pageSize: 50 });
    assert.equal(mock.findRequests("get", "/learner-state/snapshots").length, 2);
  });
});

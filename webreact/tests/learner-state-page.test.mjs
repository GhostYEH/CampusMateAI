/**
 * 我的状态页面 API 契约测试。
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

// ===== 预测 =====

describe("getForecasts", () => {
  it("请求 /learner-state/forecasts 并传递筛选参数", async () => {
    mock.onGet("/learner-state/forecasts", { items: [], total: 0 });
    await api.getForecasts({
      forecastType: "UPCOMING_WORKLOAD",
      horizonDays: 14,
      goalId: "g-1",
      courseId: "cs101",
    });
    const req = mock.lastRequest();
    assert.equal(req.url, "/learner-state/forecasts");
    assert.equal(req.params.forecast_type, "UPCOMING_WORKLOAD");
    assert.equal(req.params.horizon_days, 14);
    assert.equal(req.params.goal_id, "g-1");
    assert.equal(req.params.course_id, "cs101");
  });

  it("默认 page=1 page_size=20 horizon_days 不发送", async () => {
    mock.onGet("/learner-state/forecasts", { items: [], total: 0 });
    await api.getForecasts();
    const req = mock.lastRequest();
    assert.equal(req.params.page, 1);
    assert.equal(req.params.page_size, 20);
    assert.ok(!("horizon_days" in req.params));
  });
});

// ===== 学生目标 =====

describe("getStudentGoals", () => {
  it("请求 /student-goals 并传递筛选参数", async () => {
    mock.onGet("/student-goals", { items: [], total: 0 });
    await api.getStudentGoals({
      status: "active",
      category: "academic",
      page: 2,
      pageSize: 30,
    });
    const req = mock.lastRequest();
    assert.equal(req.url, "/student-goals");
    assert.equal(req.params.status, "active");
    assert.equal(req.params.category, "academic");
    assert.equal(req.params.page, 2);
    assert.equal(req.params.page_size, 30);
  });

  it("默认 page=1 page_size=50", async () => {
    mock.onGet("/student-goals", { items: [], total: 0 });
    await api.getStudentGoals();
    const req = mock.lastRequest();
    assert.equal(req.params.page, 1);
    assert.equal(req.params.page_size, 50);
  });
});

describe("archiveStudentGoal", () => {
  it("POST /student-goals/:id/archive 传递空 body", async () => {
    mock.onPost("/student-goals/g-1/archive", { goal_id: "g-1", status: "archived" });
    const result = await api.archiveStudentGoal("g-1");
    const req = mock.lastRequest();
    assert.equal(req.url, "/student-goals/g-1/archive");
    assert.deepEqual(req.data, {});
    assert.equal(result.status, "archived");
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
    mock.onPost("/student-goals/g-1/archive", null, 204);
    const result = await api.archiveStudentGoal("g-1");
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
    mock.onSequence("get", "/learner-state/forecasts", [
      { error: true, status: 401, data: { detail: "token expired" } },
      { status: 200, data: { items: [], total: 0 } },
    ]);

    const result = await api.getForecasts();
    assert.deepEqual(result, { items: [], total: 0 });

    // 验证发了两次请求（第一次 401，第二次重试）
    const reqs = mock.findRequests("get", "/learner-state/forecasts");
    assert.equal(reqs.length, 2);
  });

  it("refresh token 不存在时抛出登录过期错误", async () => {
    mock.setTokens("expired-token", null);
    mock.onError("get", "/learner-state/forecasts", 401, { detail: "token expired" });

    await assert.rejects(
      () => api.getForecasts(),
      (err) => err.message.includes("登录已过期"),
    );
  });
});

// ===== mutation 后数据刷新 =====

describe("mutation 后数据刷新", () => {
  it("archiveStudentGoal 后再次调用 getLearnerStateSnapshots 发出新请求", async () => {
    mock.onPost("/student-goals/g-1/archive", { status: "archived" });
    mock.onGet("/learner-state/snapshots", { items: [], total: 0 });

    // 初始加载
    await api.getLearnerStateSnapshots({ pageSize: 50 });
    assert.equal(mock.findRequests("get", "/learner-state/snapshots").length, 1);

    // mutation
    await api.archiveStudentGoal("g-1");

    // 刷新
    await api.getLearnerStateSnapshots({ pageSize: 50 });
    assert.equal(mock.findRequests("get", "/learner-state/snapshots").length, 2);
  });
});

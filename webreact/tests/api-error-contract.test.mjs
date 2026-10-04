import test from "node:test";
import assert from "node:assert/strict";
import { client, getProfile } from "../src/data/api.js";
import { getAgentCapabilities } from "../src/data/agentRuntimeApi.js";
import { getLearnerStateRuns } from "../src/data/learnerStateApi.js";
import { getAgentRuntimeOverview } from "../src/data/agentObservabilityApi.js";
import { normalizeApiError, userErrorMessage } from "../src/data/contracts.js";

const adapters = [getProfile, getAgentCapabilities, getLearnerStateRuns, getAgentRuntimeOverview];
async function collectErrors(makeError) {
  const previous = client.defaults.adapter;
  client.defaults.adapter = (config) => Promise.reject(makeError(config));
  try {
    const errors = [];
    for (const request of adapters) {
      await assert.rejects(request(), (error) => { errors.push(error); return true; });
    }
    return errors;
  } finally { client.defaults.adapter = previous; }
}

test("all API adapters expose one structured error shape and prefer the backend message", async () => {
  const errors = await collectErrors((config) => ({ config, code: "ERR_BAD_REQUEST", response: { status: 403, data: {
    code: "AGENT_PERMISSION_DENIED", message: "当前账号无法访问", detail: "legacy detail",
    request_id: "request-1", details: { permission: "read" },
  } } }));
  for (const error of errors) {
    assert.ok(error instanceof Error);
    assert.equal(error.message, "当前账号无法访问");
    assert.equal(userErrorMessage(error), error.message);
    assert.equal(error.code, "AGENT_PERMISSION_DENIED");
    assert.equal(error.transportCode, "ERR_BAD_REQUEST");
    assert.equal(error.status, 403);
    assert.equal(error.request_id, "request-1");
    assert.deepEqual(error.details, { permission: "read" });
    assert.equal(typeof error.actionable, "boolean");
    assert.ok(Object.hasOwn(error, "action"));
    assert.equal(error.cause.config, error.config);
  }
});

test("network, timeout and cancellation errors show the same message through every adapter", async () => {
  for (const [makeError, message] of [
    [(config) => ({ config, request: {}, code: "ERR_NETWORK", message: "Network Error" }), "无法连接到服务，请确认后端已启动后重试"],
    [(config) => ({ config, request: {}, code: "ECONNABORTED", message: "timeout" }), "请求超时，请稍后重试"],
    [(config) => ({ config, request: {}, name: "AbortError", message: "aborted" }), "已取消"],
    [(config) => ({ config, request: {}, code: "ERR_CANCELED", message: "canceled" }), "已取消"],
  ]) {
    for (const error of await collectErrors(makeError)) {
      assert.equal(error.message, message);
      assert.equal(error.userMessage, undefined, "transport defaults are resolved by the page");
      assert.equal(userErrorMessage(error), message);
      assert.equal(userErrorMessage(error, "课程详情加载失败"), "课程详情加载失败");
      assert.equal(error.status, null);
      assert.equal(error.request_id, null);
    }
  }
});

test("empty HTTP bodies and English detail preserve page fallbacks without a baked userMessage", async () => {
  for (const status of [401, 409, 500]) {
    for (const data of [null, {}, { detail: "internal_server_error" }]) {
      for (const error of await collectErrors((config) => ({
        config: { ...config, _retried: true }, response: { status, data }, message: `Request failed with status code ${status}`,
      }))) {
        assert.equal(error.userMessage, undefined);
        assert.equal(userErrorMessage(error, "资料加载失败"), "资料加载失败");
        assert.equal(userErrorMessage(error), "操作失败，请稍后重试");
      }
    }
  }
});

test("normalization is idempotent and retains useful local Chinese messages", () => {
  const error = normalizeApiError(new Error("登录状态已变更，请重试"));
  assert.equal(normalizeApiError(error), error);
  assert.equal(userErrorMessage(error), "登录状态已变更，请重试");
  assert.equal(userErrorMessage(new Error("internal implementation error"), "资料加载失败"), "资料加载失败");
});

test("unexplained HTTP errors retain the calling page's fallback across all adapters", async () => {
  for (const error of await collectErrors((config) => ({ config, response: { status: 500, data: {} }, message: "Request failed with status code 500" }))) {
    assert.equal(userErrorMessage(error, "课程详情加载失败"), "课程详情加载失败");
    assert.equal(userErrorMessage(error), "操作失败，请稍后重试");
    assert.equal(normalizeApiError(error), error);
    assert.equal(error.status, 500);
  }
  const error = normalizeApiError({ response: { status: 409, data: { code: "AGENT_INVALID_STATE" } } });
  assert.equal(userErrorMessage(error, "资料加载失败"), "资料加载失败");
});

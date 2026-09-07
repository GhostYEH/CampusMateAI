import test from "node:test";
import assert from "node:assert/strict";

import { logApiError, userErrorMessage } from "../src/data/contracts.js";

test("error adapter prefers the backend structured message ({code,message,details})", () => {
  const error = { response: { data: { code: "VALIDATION_FAILED", message: "请求参数校验失败", details: [] } } };
  assert.equal(userErrorMessage(error, "兜底文案"), "请求参数校验失败");
});

test("error adapter falls back to the legacy detail field", () => {
  const error = { response: { data: { detail: "学习会话不存在。" } } };
  assert.equal(userErrorMessage(error), "学习会话不存在。");
});

test("error adapter maps transport failures to friendly Chinese messages", () => {
  assert.equal(userErrorMessage({ request: {}, message: "Network Error" }, "兜底文案"), "无法连接到服务，请确认后端已启动后重试");
  assert.match(userErrorMessage({ code: "ECONNABORTED" }, "兜底文案"), /超时/);
});

test("error adapter keeps the caller fallback for unknown shapes", () => {
  assert.equal(userErrorMessage({}, "操作失败"), "操作失败");
  assert.equal(userErrorMessage(null, "操作失败"), "操作失败");
});

test("logApiError only writes to console diagnostics and never throws", () => {
  const calls = [];
  const original = console.warn;
  console.warn = (...args) => calls.push(args);
  try {
    logApiError("study-load", { message: "raw axios detail line" });
    assert.equal(calls.length, 1);
    assert.ok(calls[0][0].includes("study-load"));
    assert.equal(logApiError("boom", null), undefined);
  } finally {
    console.warn = original;
  }
});
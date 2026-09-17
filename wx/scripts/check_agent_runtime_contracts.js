#!/usr/bin/env node
/**
 * 微信端 Agent Runtime 契约门禁。
 *
 * 与 Web / Android / HarmonyOS 消费**同一份**共享 fixture
 * （backend/tests/fixtures/agent_runtime/v1/runtime.json），避免各端手写样例互相漂移。
 *
 * 微信端当前没有 learning_goal 创建页面，因此这里只校验通用契约：
 * 2xx 视为成功、未知事件安全降级、reducer 按 (run_id, sequence) 去重。
 */
const fs = require("fs");
const path = require("path");

const FIXTURE = path.resolve(
  __dirname,
  "../../backend/tests/fixtures/agent_runtime/v1/runtime.json",
);
const RUNTIME_SOURCE = path.resolve(__dirname, "../miniprogram/services/agent-runtime.ts");

function fail(message) {
  console.error(`[agent-runtime-contracts] ${message}`);
  process.exit(1);
}

if (!fs.existsSync(FIXTURE)) fail(`共享 fixture 不存在: ${FIXTURE}`);
const fixture = JSON.parse(fs.readFileSync(FIXTURE, "utf8"));

if (fixture.contract_version !== "v1") fail("contract_version 必须保持 v1");
if (!fixture.v2) fail("共享 fixture 缺少 v2 增量契约段");

const creation = fixture.v2.creation_202;
if (!creation) fail("缺少 creation_202 契约");
if (creation.http_status < 200 || creation.http_status >= 300) {
  fail("202 创建必须落在 2xx 区间");
}
if (creation.job.input_ref.plan_id !== undefined) {
  fail("创建响应不得预先包含 plan_id：客户端必须在终态后重新 GET Job");
}
if (!creation.job.latest_run_id) fail("创建响应必须返回 latest_run_id 供订阅");

for (const [key, status] of [
  ["idempotency_conflict", 409],
  ["capability_disabled", 409],
  ["runtime_unavailable", 503],
  ["cursor_invalid", 409],
]) {
  const section = fixture.v2[key];
  if (!section) fail(`缺少 ${key} 契约`);
  if (section.http_status !== status) fail(`${key} 的 HTTP 状态被改动`);
  if (!section.error_envelope || !section.error_envelope.code) {
    fail(`${key} 必须携带稳定错误码`);
  }
}

const recoveryTypes = (fixture.v2.recovery_events || []).map((event) => event.type);
for (const expected of ["RUN_RETRY_SCHEDULED", "RUN_RECOVERY_STARTED", "RUN_RECOVERED"]) {
  if (!recoveryTypes.includes(expected)) fail(`恢复事件契约缺失: ${expected}`);
}

const unknown = fixture.v2.unknown_future_event && fixture.v2.unknown_future_event.frame;
if (!unknown || !unknown.event) fail("缺少未知未来事件契约");
if (recoveryTypes.includes(unknown.event)) {
  fail("未知未来事件不应被列入已知恢复事件");
}

const observability = fixture.v2.admin_observability;
if (!observability) fail("缺少管理员观测脱敏契约");
const serialized = JSON.stringify({
  overview: observability.overview,
  run_trace: observability.run_trace,
});
for (const forbidden of [
  "prompt",
  "model_response",
  "credential",
  "memory_content",
  "raw_arguments",
  "hidden_reasoning",
  "arguments",
]) {
  if (serialized.includes(forbidden)) {
    fail(`管理员观测响应不得包含 ${forbidden}`);
  }
}

// 客户端 reducer 必须按 (run_id, sequence) 去重，且未知风险级别保守回落。
const source = fs.readFileSync(RUNTIME_SOURCE, "utf8");
if (!/run_id/.test(source) || !/sequence/.test(source)) {
  fail("agent-runtime.ts 的 reducer 必须按 (run_id, sequence) 去重");
}
if (!/UNKNOWN/.test(source)) {
  fail("agent-runtime.ts 必须对未知枚举安全降级到 UNKNOWN");
}

console.log("[agent-runtime-contracts] 通过：共享 fixture 语义与微信端 reducer 一致");

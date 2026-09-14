/**
 * Agent Runtime 共享契约测试：枚举完整性、未知枚举回落、错误 envelope 映射、
 * Idempotency-Key 稳定性、事件去重与 sequence 续传。
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import * as C from "../src/data/agentContracts.js";

describe("agentContracts enums", () => {
  it("run status 包含可暂停的完整生命周期", () => {
    assert.deepEqual(C.RUN_STATUS, [
      "QUEUED", "RUNNING", "AWAITING_APPROVAL", "PAUSED", "SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED",
    ]);
  });

  it("event type 包含生命周期控制事件", () => {
    assert.equal(C.EVENT_TYPE.length, 22);
    assert.ok(C.EVENT_TYPE.includes("APPROVAL_REQUIRED"));
    assert.ok(C.EVENT_TYPE.includes("RUN_PARTIAL"));
    assert.ok(C.EVENT_TYPE.includes("MODEL_FALLBACK"));
  });

  it("error code 包含 14 个稳定码", () => {
    assert.equal(C.ERROR_CODE.length, 14);
    assert.ok(C.ERROR_CODE.includes("AGENT_ACADEMIC_POLICY_RESTRICTED"));
    assert.ok(C.ERROR_CODE.includes("AGENT_IDEMPOTENCY_CONFLICT"));
  });

  it("academic policy 与 assistance mode 独立枚举", () => {
    assert.deepEqual(C.ACADEMIC_POLICY, ["ALLOWED", "LIMITED", "EXAM_RESTRICTED", "AI_PROHIBITED", "UNKNOWN"]);
    assert.deepEqual(C.ASSISTANCE_MODE, ["HINT", "EXPLAIN", "REVIEW", "FULL_SOLUTION"]);
  });

  it("artifact type 覆盖 5 类产物", () => {
    assert.equal(C.ARTIFACT_TYPE.length, 5);
  });
});

describe("agentContracts unknown enum fallback", () => {
  it("未知 run status 标签回落到'状态待确认'", () => {
    assert.equal(C.runStatusLabel("FROZEN"), "状态待确认");
    assert.equal(C.runStatusLabel(undefined), "状态待确认");
  });

  it("未知 academic policy 禁止 FULL_SOLUTION", () => {
    assert.equal(C.allowsFullSolution("ALLOWED"), true);
    assert.equal(C.allowsFullSolution("EXAM_RESTRICTED"), false);
    assert.equal(C.allowsFullSolution("WEIRD"), false);
    assert.equal(C.allowsFullSolution(undefined), false);
  });

  it("未知 risk level 视为不可直接执行（保守）", () => {
    assert.equal(C.isSafeToAct("AUTO_SAFE"), true);
    assert.equal(C.isSafeToAct("CONFIRM_REQUIRED"), false);
    assert.equal(C.isSafeToAct("MANUAL_ONLY"), false);
    assert.equal(C.isSafeToAct("ALIEN"), false);
  });

  it("未知 status 不可取消", () => {
    assert.equal(C.isCancellable("RUNNING"), true);
    assert.equal(C.isCancellable("SUCCEEDED"), false);
    assert.equal(C.isCancellable("WEIRD"), false);
  });

  it("只有 PENDING approval 可决策，终态/未知禁止", () => {
    assert.equal(C.canResolveApproval("PENDING"), true);
    assert.equal(C.canResolveApproval("APPROVED"), false);
    assert.equal(C.canResolveApproval("EXPIRED"), false);
    assert.equal(C.canResolveApproval("WEIRD"), false);
  });
});

describe("agentContracts error envelope mapping", () => {
  it("映射 AGENT_APPROVAL_REQUIRED 并给出 open_approval 动作", () => {
    const err = { response: { data: { code: "AGENT_APPROVAL_REQUIRED", message: "需要用户确认后继续", request_id: "r1", details: { approval_id: "a1" } } } };
    const out = C.mapAgentError(err);
    assert.equal(out.code, "AGENT_APPROVAL_REQUIRED");
    assert.equal(out.message, "需要用户确认后继续");
    assert.equal(out.actionable, true);
    assert.equal(out.action, "open_approval");
    assert.equal(out.details.approval_id, "a1");
  });

  it("未知 code 回落到 UNKNOWN 且不提供危险动作", () => {
    const err = { response: { data: { code: "AGENT_NEW_THING", message: "x" } } };
    const out = C.mapAgentError(err);
    assert.equal(out.code, "UNKNOWN");
    assert.equal(out.actionable, false);
    assert.equal(out.action, null);
  });

  it("缺失 message 时按 code 兜底中文文案", () => {
    const err = { response: { data: { code: "AGENT_CONTEXT_EXPIRED" } } };
    const out = C.mapAgentError(err);
    assert.equal(out.code, "AGENT_CONTEXT_EXPIRED");
    assert.match(out.message, /上下文已过期/);
    assert.equal(out.action, "refresh_context");
  });

  it("normalizeAgentError 优先识别网络/超时/取消", () => {
    assert.equal(C.normalizeAgentError({ name: "AbortError" }).code, "ABORTED");
    assert.equal(C.normalizeAgentError({ code: "ECONNABORTED" }).code, "TIMEOUT");
    assert.equal(C.normalizeAgentError({ request: {}, response: undefined }).code, "NETWORK_ERROR");
  });

  it("学术政策受限映射为受限文案且无危险动作", () => {
    const err = { response: { data: { code: "AGENT_ACADEMIC_POLICY_RESTRICTED", message: "该作业在考试限制期,仅提供讲解" } } };
    const out = C.mapAgentError(err);
    assert.equal(out.code, "AGENT_ACADEMIC_POLICY_RESTRICTED");
    assert.equal(out.actionable, false);
  });
});

describe("agentContracts idempotency key", () => {
  it("生成格式稳定且含 scope", () => {
    const k = C.createIdempotencyKey("final_review");
    assert.match(k, /^web_final_review_[a-z0-9]+_[a-z0-9]+$/);
  });

  it("scope 中的非法字符被剔除，避免注入", () => {
    const k = C.createIdempotencyKey("a/b c<script>");
    assert.match(k, /^web_abcscript_[a-z0-9]+_[a-z0-9]+$/);
  });

  it("两次调用产生不同 key", () => {
    assert.notEqual(C.createIdempotencyKey("x"), C.createIdempotencyKey("x"));
  });
});

describe("agentContracts event merge & resume", () => {
  it("按 sequence 去重并排序", () => {
    const a = [{ sequence: 2 }, { sequence: 1 }];
    const b = [{ sequence: 1 }, { sequence: 3 }];
    const merged = C.mergeEvents(a, b);
    assert.deepEqual(merged.map((e) => e.sequence), [1, 2, 3]);
  });

  it("lastSequence 之前的重复事件被丢弃，新事件加入", () => {
    const existing = [{ sequence: 1 }, { sequence: 2 }];
    const incoming = [{ sequence: 2 }, { sequence: 3, fresh: true }];
    const merged = C.mergeEvents(existing, incoming, 2);
    assert.equal(merged.length, 3);
    assert.equal(merged.find((e) => e.sequence === 3).fresh, true);
    assert.equal(merged.find((e) => e.sequence === 2).fresh, undefined);
  });

  it("重连后仅收到新 sequence 的事件被合并", () => {
    const existing = [{ sequence: 1 }, { sequence: 2 }];
    const incoming = [{ sequence: 3 }, { sequence: 4 }];
    const merged = C.mergeEvents(existing, incoming, 2);
    assert.deepEqual(merged.map((e) => e.sequence), [1, 2, 3, 4]);
  });

  it("lastEventSequence 返回最大 sequence", () => {
    assert.equal(C.lastEventSequence([{ sequence: 5 }, { sequence: 9 }, { sequence: 2 }]), 9);
    assert.equal(C.lastEventSequence([]), 0);
  });
});

describe("agentContracts reconnect backoff", () => {
  it("延迟随 attempt 增长且不超过上限", () => {
    const d0 = C.reconnectDelay(0);
    const d5 = C.reconnectDelay(5);
    assert.ok(d0 >= C.SSE_RECONNECT_BASE_MS);
    assert.ok(d5 <= C.SSE_RECONNECT_MAX_MS);
    assert.ok(d5 >= d0 - C.SSE_RECONNECT_BASE_MS);
  });

  it("上限 30s", () => {
    assert.ok(C.reconnectDelay(20) <= C.SSE_RECONNECT_MAX_MS);
  });
});

// ===== 共享 fixture 契约（Task 11）=====
//
// 四端必须消费 backend/tests/fixtures/agent_runtime/v1/runtime.json 的同一份语义，
// 而不是各写各的样例，否则契约会静默漂移。

const SHARED_FIXTURE = JSON.parse(
  readFileSync(
    new URL("../../backend/tests/fixtures/agent_runtime/v1/runtime.json", import.meta.url),
    "utf8",
  ),
);

describe("shared runtime fixture", () => {
  it("contract_version 为 v1 且包含 v2 增量段", () => {
    assert.equal(SHARED_FIXTURE.contract_version, "v1");
    assert.ok(SHARED_FIXTURE.v2, "v2 增量契约缺失");
  });

  it("202 创建只保证入队：没有 plan_id，必须订阅 latest_run_id", () => {
    const creation = SHARED_FIXTURE.v2.creation_202;
    assert.equal(creation.http_status, 202);
    assert.equal(creation.job.status, "QUEUED");
    assert.equal(creation.job.input_ref.plan_id, undefined);
    assert.ok(creation.job.latest_run_id);
    // 任意 2xx 都必须被当作成功处理
    assert.ok(creation.http_status >= 200 && creation.http_status < 300);
  });

  it("幂等冲突、能力准入、运行时不可用与游标失效都有稳定错误码", () => {
    const codes = {
      AGENT_IDEMPOTENCY_CONFLICT: 409,
      AGENT_CAPABILITY_DISABLED: 409,
      AGENT_RUNTIME_UNAVAILABLE: 503,
      AGENT_CURSOR_INVALID: 409,
    };
    const sections = {
      AGENT_IDEMPOTENCY_CONFLICT: SHARED_FIXTURE.v2.idempotency_conflict,
      AGENT_CAPABILITY_DISABLED: SHARED_FIXTURE.v2.capability_disabled,
      AGENT_RUNTIME_UNAVAILABLE: SHARED_FIXTURE.v2.runtime_unavailable,
      AGENT_CURSOR_INVALID: SHARED_FIXTURE.v2.cursor_invalid,
    };
    for (const [code, status] of Object.entries(codes)) {
      const section = sections[code];
      assert.equal(section.http_status, status, `${code} 的 HTTP 状态被改动`);
      assert.equal(section.error_envelope.code, code);
    }
  });

  it("恢复事件按 sequence 单调且可被 reducer 归并", () => {
    const events = SHARED_FIXTURE.v2.recovery_events;
    const sequences = events.map((e) => e.sequence);
    assert.deepEqual(sequences, [...sequences].sort((a, b) => a - b));
    const merged = C.mergeEvents([], events, 0);
    assert.equal(merged.length, events.length);
  });

  it("未知未来事件安全降级：不崩溃、不提升权限", () => {
    const unknown = SHARED_FIXTURE.v2.unknown_future_event.frame;
    // 未知类型不得被当作已知终态或已知风险级别
    assert.equal(C.isTerminalRunStatus(unknown.event), false);
    assert.equal(C.runStatusLabel(unknown.event), "状态待确认");
    assert.equal(C.isSafeToAct(unknown.event), false);
  });

  it("管理员观测 fixture 不含敏感字段", () => {
    const observability = SHARED_FIXTURE.v2.admin_observability;
    const serialized = JSON.stringify({
      overview: observability.overview,
      run_trace: observability.run_trace,
    });
    for (const forbidden of [
      "prompt", "model_response", "credential", "memory_content",
      "raw_arguments", "hidden_reasoning", "arguments",
    ]) {
      assert.equal(serialized.includes(forbidden), false, `观测 fixture 不得包含 ${forbidden}`);
    }
  });
});

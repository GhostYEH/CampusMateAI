/**
 * Agent Runtime v1 共享契约与枚举映射。
 *
 * 所有枚举来自 docs/superpowers/specs/2026-09-12-campus-agent-runtime-v1-design.md §5/§8/§9，
 * 与 backend/tests/fixtures/agent_runtime/v1/*.json 对齐。未知枚举统一回落到 UNKNOWN 占位，
 * UI 显示"状态待确认"并禁用危险按钮（见 agentContracts.isSafeToAct）。
 *
 * 本模块不导入 axios 或 React，纯数据，可在 node:test 中直接验证。
 */

export const CONTRACT_VERSION = "v1";

// ===== Run status（§5.6） =====
export const RUN_STATUS = Object.freeze([
  "QUEUED",
  "RUNNING",
  "AWAITING_APPROVAL",
  "PAUSED",
  "SUCCEEDED",
  "PARTIAL",
  "FAILED",
  "CANCELLED",
]);

// ===== Phase（§5.6） =====
export const RUN_PHASE = Object.freeze([
  "CONTEXT_BUILDING",
  "WAITING_FOR_MODEL",
  "VALIDATING_OUTPUT",
  "WAITING_FOR_TOOL",
  "WAITING_FOR_APPROVAL",
  "PERSISTING_RESULT",
  "RECOVERY_CHECKING",
  "IDLE",
]);

// ===== Event type（§5.7） =====
export const EVENT_TYPE = Object.freeze([
  "RUN_QUEUED",
  "RUN_STARTED",
  "CONTEXT_READY",
  "MODEL_STARTED",
  "MODEL_COMPLETED",
  "MODEL_FALLBACK",
  "TOOL_STARTED",
  "TOOL_COMPLETED",
  "TOOL_FAILED",
  "APPROVAL_REQUIRED",
  "APPROVAL_RESOLVED",
  "ARTIFACT_CREATED",
  "RUN_PARTIAL",
  "RUN_COMPLETED",
  "RUN_FAILED",
  "RUN_CANCELLED",
  "RUN_PAUSED",
  "RUN_RESUMED",
  "RUN_RETRIED",
  "RUN_RETRY_SCHEDULED",
  "RUN_RECOVERY_STARTED",
  "RUN_RECOVERED",
]);

// ===== Risk level（§5.5） =====
export const RISK_LEVEL = Object.freeze(["AUTO_SAFE", "CONFIRM_REQUIRED", "MANUAL_ONLY"]);

// ===== Approval status（§5.5） =====
export const APPROVAL_STATUS = Object.freeze(["PENDING", "APPROVED", "REJECTED", "EXPIRED"]);

// ===== Artifact type（§5.9） =====
export const ARTIFACT_TYPE = Object.freeze([
  "FINAL_REVIEW_PLAN",
  "DAILY_AGENDA",
  "NOTICE_CHECKLIST",
  "COURSE_RESEARCH_REPORT",
  "CITATION_BUNDLE",
]);

// ===== Error code（§9.2） =====
export const ERROR_CODE = Object.freeze([
  "AGENT_INVALID_STATE",
  "AGENT_PERMISSION_DENIED",
  "AGENT_TOOL_REJECTED",
  "AGENT_APPROVAL_REQUIRED",
  "AGENT_PROVIDER_UNAVAILABLE",
  "AGENT_CONTEXT_EXPIRED",
  "AGENT_IDEMPOTENCY_CONFLICT",
  "AGENT_RUN_NOT_FOUND",
  "AGENT_RUN_CANCELLED",
  "AGENT_OUTPUT_SCHEMA_INVALID",
  "AGENT_SOURCE_POLICY_VIOLATION",
  "AGENT_ACADEMIC_POLICY_RESTRICTED",
  "AGENT_CAPABILITY_DISABLED",
  "AGENT_RUNTIME_UNAVAILABLE",
]);

// ===== Academic policy（§8.2） =====
export const ACADEMIC_POLICY = Object.freeze([
  "ALLOWED",
  "LIMITED",
  "EXAM_RESTRICTED",
  "AI_PROHIBITED",
  "UNKNOWN",
]);

// ===== Assistance mode（§8.2） =====
export const ASSISTANCE_MODE = Object.freeze(["HINT", "EXPLAIN", "REVIEW", "FULL_SOLUTION"]);

// ===== Notice workflow status（§7.3） =====
export const NOTICE_WORKFLOW_STATUS = Object.freeze([
  "CREATED",
  "ANALYZING",
  "WAITING_CONFIRMATION",
  "PROCESSING",
  "COMPLETED",
  "EXPIRED",
  "FAILED",
]);

// ===== Notice action status（§7.3） =====
export const NOTICE_ACTION_STATUS = Object.freeze([
  "PROPOSED",
  "APPROVED",
  "REJECTED",
  "EXECUTING",
  "DONE",
  "FAILED",
  "EXPIRED",
]);

// ===== Notification source（§7.3） =====
export const NOTIFICATION_SOURCE = Object.freeze([
  "android_system",
  "chaoxing",
  "campus_announcement",
  "manual_input",
]);

// ===== 终态判定 =====
const TERMINAL_RUN_STATUS = new Set(["SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"]);
const TERMINAL_APPROVAL_STATUS = new Set(["APPROVED", "REJECTED", "EXPIRED"]);
const TERMINAL_WORKFLOW_STATUS = new Set(["COMPLETED", "EXPIRED", "FAILED"]);

export function isTerminalRunStatus(status) {
  return TERMINAL_RUN_STATUS.has(status);
}

export function isTerminalApprovalStatus(status) {
  return TERMINAL_APPROVAL_STATUS.has(status);
}

export function isTerminalWorkflowStatus(status) {
  return TERMINAL_WORKFLOW_STATUS.has(status);
}

/**
 * 判断当前 run status 是否允许取消。终态不可取消。
 * 未知 status 视为不可操作（保守）。
 */
export function isCancellable(status) {
  if (!RUN_STATUS.includes(status)) return false;
  return !isTerminalRunStatus(status);
}

/**
 * 判断是否可以对 approval 做决策。只有 PENDING 可决策。
 * 未知或已终态的 approval 禁止操作，避免覆盖已决议结果。
 */
export function canResolveApproval(status) {
  return status === "PENDING";
}

/**
 * 判断某 risk level 下前端是否允许直接展示"执行"入口。
 * MANUAL_ONLY 永远只展示引导，不提供执行按钮。
 * 未知 risk level 视为最高风险（保守，禁用危险按钮）。
 */
export function isSafeToAct(riskLevel) {
  if (riskLevel === "AUTO_SAFE") return true;
  if (riskLevel === "CONFIRM_REQUIRED") return false;
  if (riskLevel === "MANUAL_ONLY") return false;
  return false;
}

/**
 * 判断某 academic policy 下是否允许 FULL_SOLUTION。
 * 后端裁决结果，前端只做展示门禁；未知 policy 禁止 FULL_SOLUTION。
 */
export function allowsFullSolution(policy) {
  return policy === "ALLOWED";
}

// ===== 用户可读标签 =====
const UNKNOWN_LABEL = "状态待确认";

export const RUN_STATUS_LABEL = Object.freeze({
  QUEUED: "已排队",
  RUNNING: "进行中",
  AWAITING_APPROVAL: "等待确认",
  PAUSED: "已暂停",
  SUCCEEDED: "已完成",
  PARTIAL: "部分完成",
  FAILED: "已失败",
  CANCELLED: "已取消",
});

export const RUN_PHASE_LABEL = Object.freeze({
  CONTEXT_BUILDING: "构建上下文",
  WAITING_FOR_MODEL: "等待模型",
  VALIDATING_OUTPUT: "校验输出",
  WAITING_FOR_TOOL: "执行工具",
  WAITING_FOR_APPROVAL: "等待确认",
  PERSISTING_RESULT: "保存结果",
  RECOVERY_CHECKING: "恢复检查",
  IDLE: "空闲",
});

export const RISK_LEVEL_LABEL = Object.freeze({
  AUTO_SAFE: "自动执行",
  CONFIRM_REQUIRED: "需要确认",
  MANUAL_ONLY: "需手动完成",
});

export const APPROVAL_STATUS_LABEL = Object.freeze({
  PENDING: "待确认",
  APPROVED: "已同意",
  REJECTED: "已拒绝",
  EXPIRED: "已过期",
});

export const ACADEMIC_POLICY_LABEL = Object.freeze({
  ALLOWED: "允许完整解答",
  LIMITED: "受限解答",
  EXAM_RESTRICTED: "考试限制期",
  AI_PROHIBITED: "禁止 AI 辅助",
  UNKNOWN: "政策待确认",
});

export const ASSISTANCE_MODE_LABEL = Object.freeze({
  HINT: "提示",
  EXPLAIN: "讲解",
  REVIEW: "点评",
  FULL_SOLUTION: "完整解答",
});

export const NOTICE_WORKFLOW_STATUS_LABEL = Object.freeze({
  CREATED: "已创建",
  ANALYZING: "解析中",
  WAITING_CONFIRMATION: "等待确认",
  PROCESSING: "处理中",
  COMPLETED: "已完成",
  EXPIRED: "已过期",
  FAILED: "已失败",
});

export const NOTICE_ACTION_STATUS_LABEL = Object.freeze({
  PROPOSED: "待确认",
  APPROVED: "已同意",
  REJECTED: "已拒绝",
  EXECUTING: "执行中",
  DONE: "已完成",
  FAILED: "已失败",
  EXPIRED: "已过期",
});

export const ARTIFACT_TYPE_LABEL = Object.freeze({
  FINAL_REVIEW_PLAN: "期末复习计划",
  DAILY_AGENDA: "今日日程",
  NOTICE_CHECKLIST: "通知清单",
  COURSE_RESEARCH_REPORT: "课程研究报告",
  CITATION_BUNDLE: "引用集合",
});

/**
 * 通用标签取值：未知枚举回落到 UNKNOWN_LABEL，保证 UI 不崩溃且不越权。
 */
export function labelOf(table, value) {
  if (table && Object.prototype.hasOwnProperty.call(table, value)) return table[value];
  return UNKNOWN_LABEL;
}

export function runStatusLabel(value) {
  return labelOf(RUN_STATUS_LABEL, value);
}

export function runPhaseLabel(value) {
  return labelOf(RUN_PHASE_LABEL, value);
}

export function riskLevelLabel(value) {
  return labelOf(RISK_LEVEL_LABEL, value);
}

export function approvalStatusLabel(value) {
  return labelOf(APPROVAL_STATUS_LABEL, value);
}

export function academicPolicyLabel(value) {
  return labelOf(ACADEMIC_POLICY_LABEL, value);
}

export function assistanceModeLabel(value) {
  return labelOf(ASSISTANCE_MODE_LABEL, value);
}

export function noticeWorkflowStatusLabel(value) {
  return labelOf(NOTICE_WORKFLOW_STATUS_LABEL, value);
}

export function noticeActionStatusLabel(value) {
  return labelOf(NOTICE_ACTION_STATUS_LABEL, value);
}

export function artifactTypeLabel(value) {
  return labelOf(ARTIFACT_TYPE_LABEL, value);
}

// ===== 错误 envelope 映射（§9.2） =====

/**
 * 将后端错误 envelope { code, message, request_id, details } 映射为用户可操作状态。
 *
 * 返回 { code, message, actionable, action }：
 * - code: 稳定错误码，未知时为 "UNKNOWN"
 * - message: 用户可读中文（优先用后端 message，否则按 code 兜底）
 * - actionable: 是否提供可操作动作（如重新登录、重试、查看审批）
 * - action: 动作标识，供 UI 决定按钮（"retry" | "relogin" | "open_approval" | "refresh_context" | null）
 *
 * 客户端永远不解析 message 做业务分支，只展示。业务分支用 code。
 */
const ERROR_CODE_MESSAGE = Object.freeze({
  AGENT_INVALID_STATE: "当前状态不支持该操作，请刷新后重试",
  AGENT_PERMISSION_DENIED: "你没有权限执行该操作",
  AGENT_TOOL_REJECTED: "该操作被安全策略拒绝",
  AGENT_APPROVAL_REQUIRED: "需要你确认后才能继续",
  AGENT_PROVIDER_UNAVAILABLE: "模型服务暂时不可用，请稍后重试",
  AGENT_CONTEXT_EXPIRED: "上下文已过期，请重新发起",
  AGENT_IDEMPOTENCY_CONFLICT: "该请求已处理，请勿重复提交",
  AGENT_RUN_NOT_FOUND: "该任务不存在或已被清理",
  AGENT_RUN_CANCELLED: "任务已取消",
  AGENT_OUTPUT_SCHEMA_INVALID: "模型输出格式异常，请重试",
  AGENT_SOURCE_POLICY_VIOLATION: "来源策略不允许该操作",
  AGENT_ACADEMIC_POLICY_RESTRICTED: "当前学术政策下仅提供有限帮助",
  AGENT_CAPABILITY_DISABLED: "该 Agent 能力当前不可用",
  AGENT_RUNTIME_UNAVAILABLE: "任务运行服务暂不接受新任务，请稍后重试",
});

const ERROR_CODE_ACTION = Object.freeze({
  AGENT_APPROVAL_REQUIRED: "open_approval",
  AGENT_CONTEXT_EXPIRED: "refresh_context",
  AGENT_IDEMPOTENCY_CONFLICT: null,
  AGENT_PROVIDER_UNAVAILABLE: "retry",
  AGENT_OUTPUT_SCHEMA_INVALID: "retry",
  AGENT_RUNTIME_UNAVAILABLE: "retry",
});

export function mapAgentError(error) {
  const data = error?.response?.data;
  const code = (data && typeof data === "object" && typeof data.code === "string" && ERROR_CODE.includes(data.code))
    ? data.code
    : "UNKNOWN";
  const serverMessage = data && typeof data === "object" && typeof data.message === "string" && data.message.trim()
    ? data.message
    : null;
  const message = serverMessage || ERROR_CODE_MESSAGE[code] || "操作失败，请稍后重试";
  const action = ERROR_CODE_ACTION[code] || null;
  const actionable = Boolean(action);
  return {
    code,
    message,
    actionable,
    action,
    request_id: (data && typeof data === "object" && data.request_id) || null,
    details: (data && typeof data === "object" && data.details) || null,
  };
}

/**
 * 网络层错误（无 response）统一映射，避免把 axios 原始英文抛给用户。
 */
export function mapNetworkError(error) {
  if (error?.name === "AbortError") {
    return { code: "ABORTED", message: "已取消", actionable: false, action: null, request_id: null, details: null };
  }
  if (error?.code === "ECONNABORTED" || /timeout|timed ?out|超时/i.test(String(error?.message))) {
    return { code: "TIMEOUT", message: "请求超时，请稍后重试", actionable: true, action: "retry", request_id: null, details: null };
  }
  if (!error?.response && error?.request) {
    return { code: "NETWORK_ERROR", message: "无法连接到服务，请确认网络后重试", actionable: true, action: "retry", request_id: null, details: null };
  }
  return null;
}

/**
 * 统一入口：先尝试网络错误，再映射 agent 错误 envelope。
 */
export function normalizeAgentError(error) {
  return mapNetworkError(error) || mapAgentError(error);
}

// ===== Idempotency-Key =====

/**
 * 生成稳定的 Idempotency-Key。同一流程状态复用同一 key，避免重复写入。
 * 格式：web_<scope>_<random>_<time>，scope 限定字符集避免注入。
 */
export function createIdempotencyKey(scope = "agent") {
  const safeScope = String(scope).replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 32) || "agent";
  const rand = Math.random().toString(36).slice(2, 10);
  const time = Date.now().toString(36);
  return `web_${safeScope}_${rand}_${time}`;
}

// ===== 事件归并/去重 =====

/**
 * 按 sequence 去重并排序事件。SSE 重连后可能收到已见事件，
 * 用 maxSequence 之前的丢弃，之后的按 sequence 唯一合并。
 */
export function mergeEvents(existing, incoming, lastSequence = 0) {
  const seen = new Map();
  for (const evt of existing) {
    if (evt && typeof evt.sequence === "number") seen.set(evt.sequence, evt);
  }
  for (const evt of incoming) {
    if (!evt || typeof evt.sequence !== "number") continue;
    if (evt.sequence <= lastSequence && seen.has(evt.sequence)) continue;
    seen.set(evt.sequence, evt);
  }
  return Array.from(seen.values()).sort((a, b) => a.sequence - b.sequence);
}

/**
 * 从事件列表推算当前最新 sequence，用于 Last-Event-ID 续传。
 */
export function lastEventSequence(events) {
  let max = 0;
  for (const evt of events) {
    if (evt && typeof evt.sequence === "number" && evt.sequence > max) max = evt.sequence;
  }
  return max;
}

// ===== SSE 重连退避 =====

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

/**
 * 指数退避（带抖动），attempt 从 0 开始。
 * 上限 30s，避免长时间断网时频繁重连。
 */
export function reconnectDelay(attempt) {
  const n = Math.max(0, Math.floor(attempt));
  const base = Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * 2 ** n);
  const jitter = Math.random() * RECONNECT_BASE_MS;
  return Math.min(RECONNECT_MAX_MS, base + jitter);
}

export const SSE_RECONNECT_BASE_MS = RECONNECT_BASE_MS;
export const SSE_RECONNECT_MAX_MS = RECONNECT_MAX_MS;

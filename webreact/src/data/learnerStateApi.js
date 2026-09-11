/**
 * Phase 6: 学生世界模型控制 API adapter。
 * 所有函数返回 Promise，错误通过 contracts.userErrorMessage 转换为友好消息。
 */
import { itemsOf, userErrorMessage } from "./contracts.js";

const BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

function _authHeaders() {
  const token = localStorage.getItem("campus_access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function _fetch(path, options = {}) {
  const url = `${BASE}${path}`;
  const headers = { "Content-Type": "application/json", ..._authHeaders(), ...(options.headers || {}) };
  try {
    const resp = await fetch(url, { ...options, headers, credentials: "include" });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      const msg = userErrorMessage(body);
      const err = new Error(msg);
      err.code = body.code || "UNKNOWN";
      err.status = resp.status;
      throw err;
    }
    if (resp.status === 204) return null;
    return resp.json();
  } catch (e) {
    if (e.status) throw e;
    const err = new Error("网络连接失败，请稍后重试");
    err.code = "NETWORK_ERROR";
    throw err;
  }
}

// ===== 状态投影（Phase 2） =====

export async function getLearnerStateRuns(page = 1, pageSize = 20) {
  return _fetch(`/learner-state/runs?page=${page}&page_size=${pageSize}`);
}

export async function getLearnerStateChanges(params = {}) {
  const q = new URLSearchParams({ page: params.page || 1, page_size: params.pageSize || 20 });
  if (params.fromRunId) q.set("from_run_id", params.fromRunId);
  if (params.toRunId) q.set("to_run_id", params.toRunId);
  if (params.scopeType) q.set("scope_type", params.scopeType);
  if (params.stateType) q.set("state_type", params.stateType);
  return _fetch(`/learner-state/changes?${q}`);
}

export async function getLearnerStateSnapshots(params = {}) {
  const q = new URLSearchParams({ page: params.page || 1, page_size: params.pageSize || 50 });
  if (params.scopeType) q.set("scope_type", params.scopeType);
  if (params.stateType) q.set("state_type", params.stateType);
  if (params.courseId) q.set("course_id", params.courseId);
  return _fetch(`/learner-state/snapshots?${q}`);
}

export async function getSnapshotEvidence(snapshotId, page = 1, pageSize = 20) {
  return _fetch(`/learner-state/snapshots/${snapshotId}/evidence?page=${page}&page_size=${pageSize}`);
}

// ===== 知识点与误区（Phase 3） =====

export async function getTaxonomy() {
  return _fetch(`/learner-state/taxonomy`);
}

export async function getKnowledgeState(courseId) {
  const q = courseId ? `?course_id=${encodeURIComponent(courseId)}` : "";
  return _fetch(`/learner-state/knowledge${q}`);
}

export async function getMisconceptionHypotheses(courseId) {
  const q = courseId ? `?course_id=${encodeURIComponent(courseId)}` : "";
  return _fetch(`/learner-state/hypotheses${q}`);
}

export async function decideHypothesis(hypothesisId, decision) {
  return _fetch(`/learner-state/hypotheses/${hypothesisId}/decision`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
}

// ===== 学习计划（Phase 4） =====

export async function generateLearningPlan(body) {
  return _fetch(`/learning-plans/generate`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getLearningPlans(page = 1, pageSize = 10) {
  return _fetch(`/learning-plans?page=${page}&page_size=${pageSize}`);
}

export async function getLearningPlan(planId) {
  return _fetch(`/learning-plans/${planId}`);
}

export async function decideLearningPlan(planId, decision) {
  return _fetch(`/learning-plans/${planId}/decision`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
}

export async function executeLearningPlan(planId) {
  return _fetch(`/learning-plans/${planId}/execute`, { method: "POST" });
}

export async function undoLearningPlan(planId) {
  return _fetch(`/learning-plans/${planId}/undo`, { method: "POST" });
}

export async function replanLearningPlan(planId, body) {
  return _fetch(`/learning-plans/${planId}/replan`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function submitPlanFeedback(planId, feedback) {
  return _fetch(`/learning-plans/${planId}/feedback`, {
    method: "POST",
    body: JSON.stringify({ feedback }),
  });
}

export async function getPlanEvaluation(planId) {
  return _fetch(`/learning-plans/${planId}/evaluation`);
}

// ===== 状态纠正（Phase 6A） =====

export async function createCorrection(body) {
  return _fetch(`/learner-state/corrections`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getCorrections(page = 1, pageSize = 20) {
  return _fetch(`/learner-state/corrections?page=${page}&page_size=${pageSize}`);
}

export async function revokeCorrection(correctionId, idempotencyKey) {
  return _fetch(`/learner-state/corrections/${correctionId}/revoke`, {
    method: "POST",
    body: JSON.stringify({ idempotency_key: idempotencyKey }),
  });
}

// ===== 数据源控制（Phase 6A） =====

export async function getDataControls() {
  return _fetch(`/learner-state/data-controls`);
}

export async function updateDataControl(sourceKey, status, idempotencyKey) {
  return _fetch(`/learner-state/data-controls/${sourceKey}`, {
    method: "PUT",
    body: JSON.stringify({ status, idempotency_key: idempotencyKey }),
  });
}

// ===== 世界模型删除（Phase 6A） =====

export async function requestDeletion(scope, idempotencyKey) {
  return _fetch(`/learner-state/delete-request`, {
    method: "POST",
    body: JSON.stringify({ scope, idempotency_key: idempotencyKey }),
  });
}

export async function getDeleteStatus() {
  return _fetch(`/learner-state/delete-status`);
}

// ===== 数据摘要（Phase 6A） =====

export async function getDataSummary() {
  return _fetch(`/learner-state/data-summary`);
}

// ===== 模型透明度（Phase 6A） =====

export async function getModelTransparency() {
  return _fetch(`/learner-state/model-transparency`);
}

export { itemsOf };
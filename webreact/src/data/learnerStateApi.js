/**
 * Phase 6: 学生世界模型控制 API adapter。
 * 复用 api.js 的统一 axios client（含 token refresh），错误通过 contracts.userErrorMessage 转换。
 */
import { client } from "./api.js";
import { itemsOf, userErrorMessage } from "./contracts.js";

function _wrap(promise) {
  return promise.then(
    (resp) => (resp.status === 204 ? null : resp.data),
    (error) => {
      if (error.response) {
        const body = error.response.data || {};
        const msg = userErrorMessage(body);
        const err = new Error(msg);
        err.code = body.code || "UNKNOWN";
        err.status = error.response.status;
        throw err;
      }
      const err = new Error("网络连接失败，请稍后重试");
      err.code = "NETWORK_ERROR";
      throw err;
    },
  );
}

function _get(path, params) {
  return _wrap(client.get(path, { params }));
}

function _post(path, body) {
  return _wrap(client.post(path, body));
}

function _put(path, body) {
  return _wrap(client.put(path, body));
}

// ===== 状态投影（Phase 2） =====

export async function getLearnerStateRuns(page = 1, pageSize = 20) {
  return _get("/learner-state/runs", { page, page_size: pageSize });
}

export async function getLearnerStateChanges(params = {}) {
  return _get("/learner-state/changes", {
    page: params.page || 1,
    page_size: params.pageSize || 20,
    ...(params.fromRunId ? { from_run_id: params.fromRunId } : {}),
    ...(params.toRunId ? { to_run_id: params.toRunId } : {}),
    ...(params.scopeType ? { scope_type: params.scopeType } : {}),
    ...(params.stateType ? { state_type: params.stateType } : {}),
  });
}

export async function getLearnerStateSnapshots(params = {}) {
  return _get("/learner-state/snapshots", {
    page: params.page || 1,
    page_size: params.pageSize || 50,
    ...(params.scopeType ? { scope_type: params.scopeType } : {}),
    ...(params.stateType ? { state_type: params.stateType } : {}),
    ...(params.courseId ? { course_id: params.courseId } : {}),
  });
}

export async function getSnapshotEvidence(snapshotId, page = 1, pageSize = 20) {
  return _get(`/learner-state/snapshots/${snapshotId}/evidence`, { page, page_size: pageSize });
}

// ===== 知识点与误区（Phase 3） =====

export async function getTaxonomy() {
  return _get("/learner-state/taxonomy");
}

export async function getKnowledgeState(courseId) {
  return _get("/learner-state/knowledge", courseId ? { course_id: courseId } : {});
}

export async function getMisconceptionHypotheses(courseId) {
  return _get("/learner-state/hypotheses", courseId ? { course_id: courseId } : {});
}

export async function decideHypothesis(hypothesisId, decision) {
  return _post(`/learner-state/hypotheses/${hypothesisId}/decision`, { decision });
}

// ===== 学习计划（Phase 4） =====

export async function generateLearningPlan(body) {
  return _post("/learning-plans/generate", body);
}

export async function getLearningPlans(page = 1, pageSize = 10) {
  return _get("/learning-plans", { page, page_size: pageSize });
}

export async function getLearningPlan(planId) {
  return _get(`/learning-plans/${planId}`);
}

export async function decideLearningPlan(planId, decision) {
  return _post(`/learning-plans/${planId}/decision`, { decision });
}

export async function executeLearningPlan(planId) {
  return _post(`/learning-plans/${planId}/execute`, {});
}

export async function undoLearningPlan(planId) {
  return _post(`/learning-plans/${planId}/undo`, {});
}

export async function replanLearningPlan(planId, body) {
  return _post(`/learning-plans/${planId}/replan`, body);
}

export async function submitPlanFeedback(planId, feedback) {
  return _post(`/learning-plans/${planId}/feedback`, { feedback });
}

export async function getPlanEvaluation(planId) {
  return _get(`/learning-plans/${planId}/evaluation`);
}

// ===== 状态纠正（Phase 6A） =====

export async function createCorrection(body) {
  return _post("/learner-state/corrections", body);
}

export async function getCorrections(page = 1, pageSize = 20) {
  return _get("/learner-state/corrections", { page, page_size: pageSize });
}

export async function revokeCorrection(correctionId, idempotencyKey) {
  return _post(`/learner-state/corrections/${correctionId}/revoke`, { idempotency_key: idempotencyKey });
}

// ===== 数据源控制（Phase 6A） =====

export async function getDataControls() {
  return _get("/learner-state/data-controls");
}

export async function updateDataControl(sourceKey, status, idempotencyKey) {
  return _put(`/learner-state/data-controls/${sourceKey}`, { status, idempotency_key: idempotencyKey });
}

// ===== 世界模型删除（Phase 6A） =====

export async function requestDeletion(scope, idempotencyKey) {
  return _post("/learner-state/delete-request", { scope, idempotency_key: idempotencyKey });
}

export async function getDeleteStatus() {
  return _get("/learner-state/delete-status");
}

// ===== 数据摘要（Phase 6A） =====

export async function getDataSummary() {
  return _get("/learner-state/data-summary");
}

// ===== 模型透明度（Phase 6A） =====

export async function getModelTransparency() {
  return _get("/learner-state/model-transparency");
}

export { itemsOf };

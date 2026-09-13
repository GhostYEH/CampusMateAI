/**
 * 校园陪伴世界模型 API adapter。
 * 只调用后端真实存在的接口：状态投影、计划、纠正、数据控制、预测、模拟、学生目标。
 * 错误通过 contracts.userErrorMessage 转换为中文文案。
 */
import { client } from "./api.js";
import { itemsOf, userErrorMessage } from "./contracts.js";

function _wrap(promise) {
  return promise.then(
    (resp) => (resp.status === 204 ? null : resp.data),
    (error) => {
      if (error.response) {
        const body = error.response.data || {};
        const msg = userErrorMessage(error);
        const err = new Error(msg);
        err.code = body.code || "UNKNOWN";
        err.status = error.response.status;
        throw err;
      }
      if (error?.request) {
        const err = new Error("网络连接失败，请稍后重试");
        err.code = "NETWORK_ERROR";
        throw err;
      }
      const err = new Error(error?.message || "网络连接失败，请稍后重试");
      err.code = error?.code || "NETWORK_ERROR";
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

function _patch(path, body) {
  return _wrap(client.patch(path, body));
}

// ===== 状态投影 =====

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
    ...(params.projectionKind ? { projection_kind: params.projectionKind } : {}),
    ...(params.projectionScope ? { projection_scope: params.projectionScope } : {}),
  });
}

export async function getSnapshotEvidence(snapshotId, page = 1, pageSize = 20) {
  return _get(`/learner-state/snapshots/${snapshotId}/evidence`, { page, page_size: pageSize });
}

// ===== 学习计划 =====

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

export async function getPlanSummary(planId) {
  return _get(`/learning-plans/${planId}/summary`);
}

// ===== 状态纠正 =====

export async function createCorrection(body) {
  return _post("/learner-state/corrections", body);
}

export async function getCorrections(page = 1, pageSize = 20) {
  return _get("/learner-state/corrections", { page, page_size: pageSize });
}

export async function revokeCorrection(correctionId, idempotencyKey) {
  return _post(`/learner-state/corrections/${correctionId}/revoke`, { idempotency_key: idempotencyKey });
}

// ===== 数据源控制 =====

export async function getDataControls() {
  return _get("/learner-state/data-controls");
}

export async function updateDataControl(sourceKey, status, idempotencyKey) {
  return _put(`/learner-state/data-controls/${sourceKey}`, { status, idempotency_key: idempotencyKey });
}

// ===== 世界模型删除 =====

export async function requestDeletion(scope, idempotencyKey) {
  return _post("/learner-state/delete-request", { scope, idempotency_key: idempotencyKey });
}

export async function getDeleteStatus() {
  return _get("/learner-state/delete-status");
}

// ===== 数据摘要 =====

export async function getDataSummary() {
  return _get("/learner-state/data-summary");
}

// ===== 模型透明度 =====

export async function getModelTransparency() {
  return _get("/learner-state/model-transparency");
}

// ===== 校园生活与目标执行风险预测 =====

export async function getForecasts(params = {}) {
  return _get("/learner-state/forecasts", {
    page: params.page || 1,
    page_size: params.pageSize || 20,
    ...(params.forecastType ? { forecast_type: params.forecastType } : {}),
    ...(params.horizonDays ? { horizon_days: params.horizonDays } : {}),
    ...(params.goalId ? { goal_id: params.goalId } : {}),
    ...(params.courseId ? { course_id: params.courseId } : {}),
  });
}

// ===== 反事实方案模拟 =====

export async function createSimulation(body) {
  return _post("/learner-state/simulations", body);
}

// ===== 学生通用目标 =====

export async function getStudentGoals(params = {}) {
  return _get("/student-goals", {
    page: params.page || 1,
    page_size: params.pageSize || 50,
    ...(params.status ? { status: params.status } : {}),
    ...(params.category ? { category: params.category } : {}),
  });
}

export async function createStudentGoal(body) {
  return _post("/student-goals", body);
}

export async function getStudentGoal(goalId) {
  return _get(`/student-goals/${goalId}`);
}

export async function updateStudentGoal(goalId, body) {
  return _patch(`/student-goals/${goalId}`, body);
}

export async function recordGoalProgress(goalId, body) {
  return _post(`/student-goals/${goalId}/progress`, body);
}

export async function archiveStudentGoal(goalId) {
  return _post(`/student-goals/${goalId}/archive`, {});
}

export { itemsOf };

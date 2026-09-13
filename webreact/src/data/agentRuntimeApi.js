/**
 * Agent Runtime v1 API adapter — runtime 通用 + 期末复习 + 课程研究 + 通知事务。
 *
 * 复用 api.js 的统一 axios client（含 401 token refresh）。
 * 错误通过 agentContracts.normalizeAgentError 映射为用户可操作状态。
 * 所有 create/execute 端点支持 Idempotency-Key（header），稳定 key 由调用方在流程状态中保存。
 *
 * 端点来自 docs/superpowers/specs/2026-09-12-campus-agent-runtime-v1-design.md §9。
 * SSE 流端点（/events/stream）不在此处，由 agentSseStream.js 处理（authenticated fetch）。
 */
import { client } from "./api.js";
import { itemsOf } from "./contracts.js";
import { normalizeAgentError, createIdempotencyKey } from "./agentContracts.js";

function _wrap(promise) {
  return promise.then(
    (resp) => (resp.status === 204 ? null : resp.data),
    (error) => {
      const mapped = normalizeAgentError(error);
      const err = new Error(mapped.message);
      err.code = mapped.code;
      err.actionable = mapped.actionable;
      err.action = mapped.action;
      err.request_id = mapped.request_id;
      err.details = mapped.details;
      err.status = error?.response?.status;
      throw err;
    },
  );
}

function _idempotencyHeader(idempotencyKey) {
  return idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {};
}

function _get(path, params) {
  return _wrap(client.get(path, { params }));
}

function _post(path, body, idempotencyKey) {
  return _wrap(client.post(path, body, { headers: _idempotencyHeader(idempotencyKey) }));
}

function _patch(path, body, idempotencyKey) {
  return _wrap(client.patch(path, body, { headers: _idempotencyHeader(idempotencyKey) }));
}

// ===== Runtime 通用（§9.1） =====

export async function getAgentCapabilities() {
  return _get("/agent-runtime/capabilities");
}

export async function createAgentJob(body, idempotencyKey) {
  return _post("/agent-jobs", body, idempotencyKey);
}

export async function getAgentJob(jobId) {
  return _get(`/agent-jobs/${jobId}`);
}

export async function listAgentJobs(page = 1, pageSize = 50) {
  return _get("/agent-jobs", { page, page_size: pageSize });
}

export async function listAgentJobRuns(jobId) {
  return _get(`/agent-jobs/${jobId}/runs`);
}

export async function getAgentRun(runId) {
  return _get(`/agent-runs/${runId}`);
}

export async function cancelAgentRun(runId, idempotencyKey) {
  return _post(`/agent-runs/${runId}/cancel`, {}, idempotencyKey);
}

export async function pauseAgentRun(runId, reason, idempotencyKey) {
  return _post(`/agent-runs/${runId}/pause`, { ...(reason ? { reason } : {}) }, idempotencyKey);
}

export async function resumeAgentRun(runId, idempotencyKey) {
  return _post(`/agent-runs/${runId}/resume`, {}, idempotencyKey);
}

export async function retryAgentRun(runId, idempotencyKey) {
  return _post(`/agent-runs/${runId}/retry`, {}, idempotencyKey);
}

export async function listAgentRuns(page = 1, pageSize = 50) {
  return _get("/agent-runs", { page, page_size: pageSize });
}

export async function getAgentSkills() {
  return _get("/agent-runtime/skills");
}

export async function listAgentMemories() {
  return _get("/agent-memories");
}

export async function createAgentMemory(body) {
  return _post("/agent-memories", body);
}

export async function withdrawAgentMemory(memoryId) {
  return _post(`/agent-memories/${memoryId}/withdraw`, {});
}

export async function getAgentRunEvents(runId, params = {}) {
  return _get(`/agent-runs/${runId}/events`, {
    ...(params.page ? { page: params.page } : {}),
    ...(params.pageSize ? { page_size: params.pageSize } : {}),
    ...(params.fromSequence ? { from_sequence: params.fromSequence } : {}),
  });
}

export async function resolveAgentApproval(approvalId, decision, reason = null, idempotencyKey) {
  return _post(`/agent-approvals/${approvalId}/decision`, { decision, ...(reason ? { reason } : {}) }, idempotencyKey);
}

export async function getAgentArtifact(artifactId) {
  return _get(`/agent-artifacts/${artifactId}`);
}

// SSE 流 URL 构造（供 agentSseStream 使用；client 不直接发 SSE）
export function agentRunStreamUrl(runId) {
  return `/agent-runs/${runId}/events/stream`;
}

// ===== 期末复习（§9.3） =====

export async function createFinalReviewCampaign(body, idempotencyKey) {
  return _post("/final-review/campaigns", body, idempotencyKey);
}

export async function getFinalReviewCampaigns(params = {}) {
  return _get("/final-review/campaigns", {
    ...(params.page ? { page: params.page } : {}),
    ...(params.pageSize ? { page_size: params.pageSize } : {}),
  });
}

export async function getFinalReviewCampaign(campaignId) {
  return _get(`/final-review/campaigns/${campaignId}`);
}

export async function generateFinalReviewPlan(campaignId, body, idempotencyKey) {
  return _post(`/final-review/campaigns/${campaignId}/plans/generate`, body, idempotencyKey);
}

export async function getFinalReviewPlanVersions(campaignId) {
  return _get(`/final-review/campaigns/${campaignId}/plan-versions`);
}

export async function getFinalReviewPlanVersion(campaignId, version) {
  return _get(`/final-review/campaigns/${campaignId}/plan-versions/${version}`);
}

export async function activateFinalReviewCampaign(campaignId, version, idempotencyKey) {
  return _post(`/final-review/campaigns/${campaignId}/activate`, { version }, idempotencyKey);
}

export async function getTodayAgenda(campaignId) {
  return _get(`/final-review/campaigns/${campaignId}/agendas/today`);
}

export async function completeFinalReviewItem(itemId, idempotencyKey) {
  return _post(`/final-review/daily-items/${itemId}/complete`, {}, idempotencyKey);
}

export async function createDailyCheckin(campaignId, body, idempotencyKey) {
  return _post(`/final-review/campaigns/${campaignId}/daily-checkins`, body, idempotencyKey);
}

export async function analyzeAdjustment(campaignId, body, idempotencyKey) {
  return _post(`/final-review/campaigns/${campaignId}/adjustments/analyze`, body, idempotencyKey);
}

export async function getAdjustmentProposals(campaignId) {
  return _get(`/final-review/campaigns/${campaignId}/adjustment-proposals`);
}

export async function resolveAdjustmentProposal(proposalId, decision, reason = null, idempotencyKey) {
  return _post(`/final-review/adjustment-proposals/${proposalId}/decision`, { decision, ...(reason ? { reason } : {}) }, idempotencyKey);
}

// ===== 通知事务（§9.4） =====
//
// 关键约束（任务 §6）：用户粘贴文本时先 POST /notices/manual 得到 server notice_id，
// 再 POST /notices/{notice_id}/workflow 创建 workflow。不要把旧的"提取后直接 createTask"
// 偷偷作为自动执行路径。NoticeCenter 既有行为保留。

export async function getNotificationSources() {
  return _get("/notification-sources");
}

export async function updateNotificationSource(sourceId, patch, idempotencyKey) {
  return _patch(`/notification-sources/${sourceId}`, patch, idempotencyKey);
}

export async function createManualNotice(body, idempotencyKey) {
  return _post("/notices/manual", body, idempotencyKey);
}

export async function createNoticeWorkflow(noticeId, body, idempotencyKey) {
  return _post(`/notices/${noticeId}/workflow`, body, idempotencyKey);
}

export async function getNoticeWorkflow(workflowId) {
  return _get(`/notice-workflows/${workflowId}`);
}

export async function reanalyzeNoticeWorkflow(workflowId, idempotencyKey) {
  return _post(`/notice-workflows/${workflowId}/reanalyze`, {}, idempotencyKey);
}

export async function decideNoticeWorkflowAction(actionId, decision, reason = null, idempotencyKey) {
  return _post(`/notice-workflow-actions/${actionId}/decision`, { decision, ...(reason ? { reason } : {}) }, idempotencyKey);
}

export async function executeNoticeWorkflowAction(actionId, idempotencyKey) {
  return _post(`/notice-workflow-actions/${actionId}/execute`, {}, idempotencyKey);
}

// ===== 课程研究（§9.5） =====

export async function createCourseResearchRun(body, idempotencyKey) {
  return _post("/course-research/runs", body, idempotencyKey);
}

export async function getCourseResearchRuns(params = {}) {
  return _get("/course-research/runs", {
    ...(params.page ? { page: params.page } : {}),
    ...(params.pageSize ? { page_size: params.pageSize } : {}),
  });
}

export async function getCourseResearchRun(runId) {
  return _get(`/course-research/runs/${runId}`);
}

export async function cancelCourseResearchRun(runId, idempotencyKey) {
  return _post(`/course-research/runs/${runId}/cancel`, {}, idempotencyKey);
}

export async function getCourseResearchArtifacts(runId) {
  return _get(`/course-research/runs/${runId}/artifacts`);
}

export { itemsOf, createIdempotencyKey };

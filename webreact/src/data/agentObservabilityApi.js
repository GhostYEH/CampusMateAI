/**
 * Agent Runtime 管理员观测 API 适配层（只读）。
 *
 * 复用 api.js 的统一 axios client（含 401 token refresh）。
 * 本模块只做 GET：观测面不提供重放、改状态、执行工具或读取原始模型内容的入口。
 *
 * 端点：GET /admin/agent-runtime/overview、GET /admin/agent-runtime/runs/:id/trace
 */
import { client } from "./api.js";
import { normalizeAgentError } from "./agentContracts.js";

function _wrap(promise) {
  return promise.then(
    (resp) => (resp.status === 204 ? null : resp.data),
    (error) => {
      const mapped = normalizeAgentError(error);
      const err = new Error(mapped.message);
      err.code = mapped.code;
      err.status = error?.response?.status;
      err.request_id = mapped.request_id;
      throw err;
    },
  );
}

export async function getAgentRuntimeOverview(sinceHours = 24) {
  return _wrap(client.get("/admin/agent-runtime/overview", { params: { since_hours: sinceHours } }));
}

export async function getAgentRunTrace(runId) {
  return _wrap(client.get(`/admin/agent-runtime/runs/${encodeURIComponent(runId)}/trace`));
}

/** 只有管理员可以访问观测面；非管理员页面必须安全返回首页。 */
export function canViewAgentOps(session) {
  return Boolean(session && session.role === "admin");
}

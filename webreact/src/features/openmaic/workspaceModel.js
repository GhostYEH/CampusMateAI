/**
 * 学习工作台的视图模型。
 *
 * 三件事必须在这里一次做对，否则会在界面上表现为"按钮没反应"：
 *
 * 1. **revision 是凭据。** 服务端要求条件写入带回读到的 revision；界面必须
 *    始终用**最近一次服务端返回**的值，而不是本地推算的。任何一次写入成功后
 *    都要用响应替换本地副本。
 * 2. **409 不是失败，是"你手上的副本过期了"。** 它需要重新拉取后重试，而不是
 *    原样重试——原样重试会一直 409。
 * 3. **503 与"没有内容"必须分开。** 服务关掉时不能显示成空列表。
 */

export const WORKSPACE_PAGE_LIMIT = 20;

export function normalizeWorkspaceList(payload) {
  const items = Array.isArray(payload) ? payload : payload?.items;
  return (items || [])
    .filter((item) => item && item.id)
    .map((item) => ({
      id: item.id,
      courseId: item.course_id,
      name: item.name || "未命名工作台",
      description: item.description || "",
      revision: Number(item.revision) || 0,
      createdAt: item.created_at || "",
      updatedAt: item.updated_at || item.created_at || "",
    }));
}

export function normalizeStageList(payload) {
  const items = Array.isArray(payload) ? payload : payload?.items;
  return (items || [])
    .filter((item) => item && item.id)
    .map((item) => ({
      id: item.id,
      workspaceId: item.workspace_id,
      courseId: item.course_id,
      title: item.title || "未命名内容",
      revision: Number(item.revision) || 0,
      dslVersion: item.dsl_version || "",
      createdAt: item.created_at || "",
      updatedAt: item.updated_at || item.created_at || "",
    }));
}

/** 分页游标：服务端给什么就带什么回去，客户端不解析它。 */
export function nextCursorOf(payload) {
  const cursor = payload?.next_cursor;
  return typeof cursor === "string" && cursor ? cursor : null;
}

/**
 * 把网关的错误翻译成界面能据以行动的种类。
 *
 * `retryable` 只描述"原样重试是否有意义"：409 需要先重新拉取，所以它不是
 * 可重试的；503 是可重试的。
 */
export function describeWorkspaceError(error) {
  const status = error?.response?.status;
  const code = error?.response?.data?.code;
  const detail = error?.response?.data?.message;

  if (code === "OPENMAIC_FUSION_UNAVAILABLE" || status === 503) {
    return { kind: "unavailable", retryable: true, message: detail || "受管服务当前不可用，请稍后重试。" };
  }
  // 幂等键冲突必须先于通用 409 判断：两者都是 409，但含义完全不同——前者是
  // "这次提交和上次的不是同一个请求"（要换键或换内容），后者是"你的副本过期了"
  // （要重新读取）。归错类会让界面给出错误的下一步。
  if (code === "OPENMAIC_IDEMPOTENCY_CONFLICT") {
    return { kind: "idempotency", retryable: false, message: detail || "这次提交与上一次的请求内容不一致，请重新提交。" };
  }
  if (code === "OPENMAIC_REVISION_CONFLICT" || status === 409) {
    return { kind: "conflict", retryable: false, message: detail || "内容已被其他操作更新，请重新读取后再提交。" };
  }
  if (code === "OPENMAIC_WORKSPACE_NOT_FOUND" || status === 404) {
    return { kind: "notFound", retryable: false, message: detail || "该内容不存在，可能已被删除。" };
  }
  if (code === "OPENMAIC_DOCUMENT_REJECTED" || status === 422) {
    const issues = error?.response?.data?.details?.issues;
    const first = Array.isArray(issues) && issues.length ? issues[0] : null;
    return {
      kind: "rejected",
      retryable: false,
      message: first?.message ? `内容未通过校验：${first.message}` : detail || "内容未通过校验，未保存。",
    };
  }
  if (status === 400 || code === "OPENMAIC_INVALID_REQUEST") {
    return { kind: "invalid", retryable: false, message: detail || "请求不合法。" };
  }
  return { kind: "unknown", retryable: true, message: detail || "操作失败，请稍后重试。" };
}

/**
 * 工作台名称：去掉首尾空白并限长，与服务端的字段约束保持一致。
 *
 * 返回 `null` 表示不可提交——界面据此禁用按钮，而不是提交后拿 400。
 */
export function normalizeWorkspaceName(value) {
  const name = String(value ?? "").trim();
  if (!name || name.length > 120) return null;
  return name;
}

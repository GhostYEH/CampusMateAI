const fallbackMessage = Symbol("fallbackMessage");
const defaultErrorMessage = "操作失败，请稍后重试";

export function itemsOf(value) {
  if (Array.isArray(value)) return value;
  return Array.isArray(value?.items) ? value.items : [];
}

// 统一 API 错误解析：
// - 后端错误结构为 { code, message, details }，message 已是中文文案，优先展示。
// - 兼容旧的 { detail } 结构。
// - 网络层错误（超时/后端未启动）不把 Axios 原始英文抛给用户，用中文兜底。
// - 原始错误保留在 console（见 logApiError），仅供开发诊断。
export function userErrorMessage(error, fallback = defaultErrorMessage) {
  const data = error?.response?.data;
  if (data && typeof data === "object" && typeof data.message === "string" && data.message.trim()) {
    return data.message;
  }
  if (data && typeof data === "object" && typeof data.detail === "string" && data.detail.trim()) {
    return data.detail;
  }
  if (error?.[fallbackMessage] && error.userMessage === defaultErrorMessage) return fallback;
  if (typeof error?.userMessage === "string" && error.userMessage.trim()) return error.userMessage;
  if (error?.name === "AbortError" || error?.code === "ERR_CANCELED") return "已取消";
  if (error?.code === "ECONNABORTED" || /timeout|timed ?out|超时/i.test(String(error?.message))) {
    return "请求超时，请稍后重试";
  }
  if (!error?.response && error?.request) {
    return "无法连接到服务，请确认后端已启动后重试";
  }
  if (typeof error?.message === "string" && /[\u3400-\u9fff]/.test(error.message)) return error.message;
  return fallback;
}

/** Preserve transport diagnostics while giving all adapters the same error fields. */
export function normalizeApiError(error) {
  if (error?.userMessage) return error;
  const body = error?.response?.data;
  const data = body && typeof body === "object" ? body : {};
  const specificMessage = userErrorMessage(error, "");
  const message = specificMessage || defaultErrorMessage;
  const normalized = new Error(message, { cause: error });
  Object.assign(normalized, {
    name: error?.name || "Error",
    userMessage: message,
    code: data.code || error?.code || (error?.name === "AbortError" ? "ABORTED" : !error?.response && error?.request ? "NETWORK_ERROR" : "UNKNOWN"),
    transportCode: error?.transportCode || error?.code || null,
    status: error?.response?.status ?? error?.status ?? null,
    request_id: data.request_id || error?.request_id || null,
    details: data.details ?? error?.details ?? null,
    actionable: error?.actionable ?? false,
    action: error?.action ?? null,
    response: error?.response,
    request: error?.request,
    config: error?.config,
    isAxiosError: error?.isAxiosError,
    [fallbackMessage]: !specificMessage,
  });
  return normalized;
}

export function logApiError(scope, error) {
  if (typeof console !== "undefined") {
    console.warn(`[api:${scope}]`, error?.config?.url || "", error?.message || error);
  }
}

export function normalizeNotice(item = {}) {
  return {
    ...item,
    has_read: typeof item.has_read === "boolean" ? item.has_read : !item.unread,
    published_at: item.published_at || item.time || item.created_at || null,
    source: item.source || item.source_name || item.course_name || "",
  };
}

export function studySessionPayload({ goal, mode = "quiet", minutes = null, relatedTaskId = null } = {}) {
  const experienceMode = {
    deep: "SMART_GUARD",
    steady: "AI_COMPANION",
    quiet: "QUIET",
  }[mode] || "QUIET";
  return {
    mode: "focus",
    experience_mode: experienceMode,
    ...(minutes ? { planned_duration_seconds: Math.round(Number(minutes) * 60) } : {}),
    ...(relatedTaskId ? { related_task_id: relatedTaskId } : {}),
    ...(goal ? { goal } : {}),
  };
}

export function submissionPayload(textContent, submit = false) {
  return { text_content: textContent, submit: Boolean(submit) };
}

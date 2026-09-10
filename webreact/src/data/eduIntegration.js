const STAGE_LABELS = {
  login: "登录",
  verification: "验证",
  identity: "身份确认",
  protocol_discovery: "课表协议识别",
  fetch: "课表读取",
  parse: "课表解析",
  validate: "课表校验",
  commit: "课表保存",
};

const SYNC_TYPE_LABELS = {
  profile: "基本信息",
  schedule: "课表",
  grade: "成绩",
  exam: "考试",
};

const CAPTCHA_MEDIA_TYPES = new Set(["image/png", "image/jpeg", "image/gif", "image/webp"]);
const BASE64_PATTERN = /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/;

export function captchaDataUrl(challenge = {}) {
  const mime = challenge.captcha_mime_type || "image/png";
  const body = challenge.captcha_image_base64;
  if (!CAPTCHA_MEDIA_TYPES.has(mime) || typeof body !== "string" || !body || !BASE64_PATTERN.test(body)) return null;
  return `data:${mime};base64,${body}`;
}

export function eduSyncMessage(type, result = {}) {
  const label = SYNC_TYPE_LABELS[type] || "数据";
  if (result.status !== "success") {
    const stage = STAGE_LABELS[result.stage] || label;
    const detail = result.error_message || "同步失败，请稍后重试";
    const preserved = type === "schedule" && result.previous_schedule_preserved
      ? "；原有课表未被覆盖"
      : "";
    return `${stage}失败：${detail}${preserved}`;
  }
  if (type === "schedule") {
    if (!result.persisted) return "课表校验已完成，但未确认写入，请稍后重试";
    return `课表同步成功，已校验并保存 ${Number(result.items_count) || 0} 条课程记录`;
  }
  return `${label}同步成功`;
}

export function verificationActionMessage(connection = {}) {
  if (connection.login_execution_mode === "client_webview" || ["NEED_SLIDER", "NEED_SMS", "NEED_MFA", "CLIENT_WEBVIEW"].includes(connection.error_code)) {
    return "该学校需要在受限登录窗口完成验证，请使用 Android 或 HarmonyOS 客户端继续。";
  }
  return connection.error_message || "";
}

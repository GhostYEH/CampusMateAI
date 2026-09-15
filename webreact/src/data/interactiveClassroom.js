/**
 * 课程智能辅导空间（OpenMAIC 学生侧互动课堂）共享数据契约与安全判定。
 *
 * Web 客户端只允许通过 CampusMate 后端（/api/v1/courses/{course_id}/interactive-classroom/*）
 * 触达 OpenMAIC，绝不直连 OpenMAIC，也绝不在前端保存任何 OpenMAIC 密钥/访问码。
 * 内嵌课堂 iframe / 新窗口链接之前必须做**完整 Origin 精确校验**（scheme + host + port）：
 * 后端在 /status 里返回可信的 OpenMAIC Origin（含端口），前端只接受与其完全相等的课堂 URL。
 * 后端未返回可信 Origin 时（默认未配置）白名单为空 —— fail-closed，一律不内嵌、不外链。
 */

// 5 种面向学生的互动课堂模式。文案只描述能力用途，不承诺后端无法保证的具体场景。
export const INTERACTIVE_MODES = [
  { mode: "adaptive", label: "自适应课堂", description: "根据课程内容自动调整学习节奏" },
  { mode: "explain", label: "概念讲解", description: "讲解这门课正在学的核心概念" },
  { mode: "explore", label: "可视化探索", description: "以可视化方式探索课程内容" },
  { mode: "practice", label: "练习测验", description: "围绕课程知识进行练习与自测" },
  { mode: "project", label: "项目式学习", description: "以项目任务加深对课程的理解与运用" },
];

/**
 * 服务端 step 取值的阶段中文文案。
 * 对齐 OpenMAIC 真实生成步骤（lib/server/classroom-generation.ts 的 ClassroomGenerationStep）
 * 以及 job 级别的 queued / failed。
 */
export const INTERACTIVE_STEP_LABELS = {
  queued: "排队中",
  initializing: "初始化课堂",
  researching: "检索课程资料",
  generating_outlines: "生成教学大纲",
  generating_scenes: "生成课堂场景",
  generating_media: "生成图片与视频",
  generating_tts: "生成语音讲解",
  persisting: "保存课堂",
  completed: "已完成",
  failed: "生成失败",
};

/** 允许内嵌/新窗口打开的课堂 Origin 白名单（完整 origin，含端口）。默认空 = fail-closed。 */
export const DEFAULT_TRUSTED_EMBED_ORIGINS = [];

/** 任务终态：命中后不再轮询。 */
export const TERMINAL_STATUSES = ["succeeded", "failed"];

function globalOrigin() {
  if (
    typeof globalThis !== "undefined" &&
    globalThis.location &&
    typeof globalThis.location.href === "string" &&
    globalThis.location.href
  ) {
    return globalThis.location.href;
  }
  return "http://localhost";
}

/**
 * 把任意来源的白名单条目归一化成 `URL.origin`（scheme + host + port）。
 * 非法条目被丢弃；相对路径/危险协议不会成为可信 Origin。
 */
export function normalizeTrustedOrigins(origins) {
  const list = Array.isArray(origins) ? origins : [];
  const out = [];
  for (const entry of list) {
    const text = String(entry ?? "").trim();
    if (!text) continue;
    try {
      const parsed = new URL(text);
      if (parsed.protocol !== "https:" && parsed.protocol !== "http:") continue;
      if (!out.includes(parsed.origin)) out.push(parsed.origin);
    } catch {
      // 非法条目忽略
    }
  }
  return out;
}

/** 取一个 URL 的完整 origin；非法或非 http(s) 返回 null。 */
export function urlOrigin(url) {
  if (!url || typeof url !== "string") return null;
  try {
    const parsed = new URL(url, globalOrigin());
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return null;
    return parsed.origin;
  } catch {
    return null;
  }
}

/**
 * 判定 OpenMAIC 课堂 url 是否可信（可安全内嵌 / 可新窗口打开）。
 *
 * 采用**完整 URL.origin 精确比对**（含端口），而不是 host 后缀匹配：
 * `http://openmaic.example.com:3000` 与 `http://openmaic.example.com:3001`
 * 或 `https://openmaic.example.com` 互不信任。
 * 白名单为空时恒为 false —— 未配置可信 Origin 前 fail-closed。
 */
export function isTrustedEmbedUrl(url, origins = DEFAULT_TRUSTED_EMBED_ORIGINS) {
  const origin = urlOrigin(url);
  if (!origin) return false;
  const trusted = normalizeTrustedOrigins(origins);
  if (trusted.length === 0) return false;
  return trusted.includes(origin);
}

/** 从后端 /status 结果解析出可信 Origin 列表（未配置时为空 → fail-closed）。 */
export function trustedOriginsFromStatus(status) {
  if (!status || typeof status !== "object") return [];
  return normalizeTrustedOrigins([status.embed_origin]);
}

/** 是否处于进行中（需要继续轮询）。 */
export function isSessionLive(session) {
  if (!session || typeof session !== "object") return false;
  if (!session.status) return false;
  return !TERMINAL_STATUSES.includes(session.status);
}

/** step 文案兜底：未知阶段显示笼统“处理中”。 */
export function interactiveStepLabel(step) {
  return INTERACTIVE_STEP_LABELS[step] || "处理中";
}

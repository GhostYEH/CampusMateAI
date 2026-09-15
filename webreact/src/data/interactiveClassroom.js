/**
 * 课程智能辅导空间（OpenMAIC 学生侧互动课堂）共享数据契约与安全判定。
 *
 * Web 客户端只允许通过 CampusMate 后端（/api/v1/courses/{course_id}/interactive-classroom/*）
 * 触达 OpenMAIC，绝不直连 OpenMAIC，也绝不在前端保存任何 OpenMAIC 密钥/访问码。
 * 内嵌课堂 iframe / 新窗口链接之前必须做 host 白名单校验（安全降级）。
 */

// 5 种面向学生的互动课堂模式。文案只描述能力用途，不承诺后端无法保证的具体场景。
export const INTERACTIVE_MODES = [
  { mode: "adaptive", label: "自适应课堂", description: "根据课程内容自动调整学习节奏" },
  { mode: "explain", label: "概念讲解", description: "讲解这门课正在学的核心概念" },
  { mode: "explore", label: "可视化探索", description: "以可视化方式探索课程内容" },
  { mode: "practice", label: "练习测验", description: "围绕课程知识进行练习与自测" },
  { mode: "project", label: "项目式学习", description: "以项目任务加深对课程的理解与运用" },
];

// 服务端 step 取值的阶段中文文案（queued..done / failed）。
export const INTERACTIVE_STEP_LABELS = {
  queued: "排队中",
  analyzing: "分析课程",
  outlining: "生成大纲",
  generating: "生成场景",
  media: "生成媒体",
  voice: "生成语音",
  saving: "保存课堂",
  done: "已完成",
  failed: "生成失败",
};

// 允许内嵌/新窗口打开的课堂 host 白名单。默认空：未配置时不内嵌、也不外倒链接，
// 网络层始终走 CampusMate 后端。后端 /status 拿不到可信前缀时，Web 用此常量兜底。
export const DEFAULT_TRUSTED_EMBED_HOSTS = [];

function normHosts(hosts) {
  return Array.isArray(hosts) ? hosts : DEFAULT_TRUSTED_EMBED_HOSTS;
}

function globalOrigin() {
  if (typeof globalThis !== "undefined" && globalThis.location && typeof globalThis.location.href === "string" && globalThis.location.href) {
    return globalThis.location.href;
  }
  return "http://localhost";
}

/**
 * 判定 OpenMAIC 课堂 url 的 host 是否落在允许嵌入的白名单内。
 * 由于默认白名单为空，未显式注入可信 host 前始终判定为“不可安全内嵌”。
 * 用于 iframe 内嵌 与 新窗口打开的护栏；判定失败时调用方应降级为不渲染空白 iframe。
 */
export function isTrustedEmbedUrl(url, hosts = DEFAULT_TRUSTED_EMBED_HOSTS) {
  if (!url || typeof url !== "string") return false;
  try {
    const parsed = new URL(url, globalOrigin());
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return false;
    const hostname = parsed.hostname.toLowerCase();
    return normHosts(hosts).some((host) => {
      const safe = String(host ?? "").trim().toLowerCase();
      return safe !== "" && (hostname === safe || hostname.endsWith(`.${safe}`));
    });
  } catch {
    return false;
  }
}

/** step 文案兜底：未知阶段显示笼统“处理中”。 */
export function interactiveStepLabel(step) {
  return INTERACTIVE_STEP_LABELS[step] || "处理中";
}
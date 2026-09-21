/**
 * 课程智能辅导空间（magic class 学生侧互动课堂）共享数据契约与安全判定。
 *
 * 生成、查询等 API 只允许通过 CampusMate 后端
 * （/api/v1/courses/{course_id}/interactive-classroom/*）触达 magic class，前端绝不保存
 * magic class 密钥/访问码；生成后的课堂页面仅在后端确认浏览器可访问且 Origin 可信时加载。
 *
 * 两条硬约束：
 * 1. 内嵌/外链之前必须做**完整 Origin 精确校验**（scheme + host + port），
 *    且课堂 Origin **不得等于 CampusMate 页面自身 Origin**（同源内嵌会让
 *    sandbox 的 allow-same-origin 失去隔离意义）。
 * 2. 内容形态只是"生成意图"。magic class 的生成接口没有类型参数，最终包含什么
 *    由生成器决定；因此"已生成内容包含……"只能来自**回读真实课堂**的结果。
 */

/**
 * 9 个面向学生的生成意图。文案只描述**意图**，不承诺最终产出某种具体形式。
 * 与后端 `MODE_INTENT_LABELS` 一一对应。
 */
export const INTERACTIVE_MODES = [
  { mode: "adaptive", label: "自动推荐", description: "按你的掌握情况与近期考试自动选择" },
  { mode: "explain", label: "概念讲解", description: "把定义、直觉与推导一步步讲清楚" },
  { mode: "quiz", label: "练习测验", description: "做题并即时看到解析，找到卡点" },
  { mode: "simulation", label: "实验模拟", description: "动手调参数、看结果变化" },
  { mode: "visualization", label: "3D/可视化", description: "把抽象结构看得见（需可访问外部 CDN）" },
  { mode: "mindmap", label: "思维导图", description: "梳理概念之间的关系与层级" },
  { mode: "coding", label: "编程实验", description: "改代码、跑一跑，用代码验证结论" },
  { mode: "pbl", label: "项目式学习", description: "用真实项目任务带动知识运用" },
  { mode: "review", label: "考前复习", description: "优先补薄弱点与高频考点" },
];

/** 旧值 → 规范意图（保留兼容；后端同样会归一化）。 */
export const LEGACY_MODE_ALIASES = {
  explore: "simulation",
  practice: "quiz",
  project: "pbl",
};

/** 必须在 UI 上明示：形态只是意图，不保证产出。 */
export const MODE_INTENT_NOTE =
  "内容形态只是生成意图，最终包含哪些形式由生成器根据课程内容决定。";

/** 把任意输入归一化到 9 个规范意图之一。 */
export function normalizeMode(mode) {
  const text = String(mode ?? "").trim().toLowerCase();
  if (!text) return "adaptive";
  if (INTERACTIVE_MODES.some((m) => m.mode === text)) return text;
  if (LEGACY_MODE_ALIASES[text]) return LEGACY_MODE_ALIASES[text];
  return "adaptive";
}

/**
 * 服务端 step 取值的阶段中文文案。
 * 对齐 magic class 真实生成步骤（lib/server/classroom-generation.ts 的 ClassroomGenerationStep）
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

/** 真实 scene.type 的中文名（与后端 KNOWN_SCENE_TYPES 对应）。 */
export const SCENE_TYPE_LABELS = {
  slide: "幻灯片",
  quiz: "测验",
  interactive: "互动实验",
  pbl: "项目式学习",
};

/** interactive 内部 widgetType 的中文名（与后端 KNOWN_WIDGET_TYPES 对应）。 */
export const WIDGET_TYPE_LABELS = {
  simulation: "流程/实验模拟",
  diagram: "结构图与思维导图",
  code: "在线编程",
  game: "知识小游戏",
  visualization3d: "3D 可视化",
  "procedural-skill": "操作技能训练",
};

/** 服务可用性状态机（每一种都要给学生不同的、可执行的提示）。 */
export const CLASSROOM_STATES = {
  LOADING: "loading",
  NOT_CONFIGURED: "not_configured",
  CONFIGURED: "configured",
  UNAVAILABLE: "unavailable",
  INCOMPATIBLE: "incompatible",
  EMBED_BLOCKED: "embed_blocked",
  READY: "ready",
};

export const CLASSROOM_STATE_TEXT = {
  loading: { title: "正在检测辅导服务…", body: "正在检测互动课堂能力…" },
  not_configured: {
    title: "本课程尚未开启智能辅导",
    body: "magic class 互动课堂尚未为这门课配置。你可以先对 CPM 提问，获取学习建议。",
  },
  unavailable: {
    title: "辅导服务暂不可用",
    body: "当前无法连接互动课堂服务，请稍后再试。这不影响课程其它内容。",
  },
  configured: {
    title: "辅导服务已配置，正在准备",
    body: "互动课堂服务已配置但尚未确认可用，请稍后再试。这不影响课程其它内容。",
  },
  incompatible: {
    title: "辅导服务版本不兼容",
    body: "互动课堂服务与当前后端约定的接口不一致，已暂停生成，请联系管理员核对部署版本。",
  },
  embed_blocked: {
    title: "课堂浏览授权尚未配置",
    body: "互动课堂当前不能安全地在学生浏览器中打开。CampusMate 不会把服务端访问凭据发送到浏览器。",
  },
  ready: { title: "可以使用", body: "" },
};

function globalHref() {
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

/** CampusMate 页面自身的 origin（用于拒绝同源内嵌）。 */
export function pageOrigin() {
  try {
    return new URL(globalHref()).origin;
  } catch {
    return null;
  }
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
    const parsed = new URL(url, globalHref());
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return null;
    return parsed.origin;
  } catch {
    return null;
  }
}

/** 课堂地址是否与 CampusMate 页面同源（同源内嵌必须拒绝）。 */
export function isSameOriginAsPage(url) {
  const origin = urlOrigin(url);
  const page = pageOrigin();
  return Boolean(origin && page && origin === page);
}

/**
 * 判定 magic class 课堂 url 是否可信（可安全内嵌 / 可新窗口打开）。
 *
 * 采用**完整 URL.origin 精确比对**（含端口），而不是 host 后缀匹配：
 * `http://magicclass.example.com:3000` 与 `http://magicclass.example.com:3001`
 * 或 `https://magicclass.example.com` 互不信任。
 * 白名单为空时恒为 false —— 未配置可信 Origin 前 fail-closed。
 */
export function isTrustedEmbedUrl(url, origins = DEFAULT_TRUSTED_EMBED_ORIGINS) {
  const origin = urlOrigin(url);
  if (!origin) return false;
  const trusted = normalizeTrustedOrigins(origins);
  if (trusted.length === 0) return false;
  return trusted.includes(origin);
}

/**
 * 可安全渲染的课堂地址：既要在可信 Origin 白名单内，又**不得**与页面同源。
 * 同源 + sandbox 的 allow-same-origin 会失去隔离意义，因此一律拒绝。
 */
export function isSafeClassroomUrl(url, origins = DEFAULT_TRUSTED_EMBED_ORIGINS) {
  if (!isTrustedEmbedUrl(url, origins)) return false;
  return !isSameOriginAsPage(url);
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

/** step 文案兜底：未知阶段显示笼统"处理中"。 */
export function interactiveStepLabel(step) {
  return INTERACTIVE_STEP_LABELS[step] || "处理中";
}

/** 由 /status 结果推导 UI 状态。 */
/**
 * 服务状态投影。优先级与 Android `InteractiveClassroomStatusDto.serviceState()`
 * **逐条对齐**，两端的同一份 DTO 必须显示同一个结论：
 *
 *   incompatible > unavailable > 可用(ready/embed_blocked) > configured > not_configured
 *
 * 关键点：`unavailable` 必须优先于任何"配置状态"。真实后端会返回
 * `configured=true, available=false, unavailable=true`（配置了但连不上），
 * 修复前 Web 已经处理对了，Android 却会显示成"已配置，正在准备"。
 */
export function classroomState(status) {
  if (!status || status.loading) return CLASSROOM_STATES.LOADING;
  if (status.incompatible === true || status.compatibility === "incompatible") {
    return CLASSROOM_STATES.INCOMPATIBLE;
  }
  if (status.unavailable === true) return CLASSROOM_STATES.UNAVAILABLE;
  if (status.enabled) {
    if (status.browser_embed_available === false) return CLASSROOM_STATES.EMBED_BLOCKED;
    return CLASSROOM_STATES.READY;
  }
  // 已配置（或服务可达/降级）但尚未确认可用 —— 不能说"尚未开启"
  if (status.configured === true || status.available === true || status.degraded === true) {
    return CLASSROOM_STATES.CONFIGURED;
  }
  return CLASSROOM_STATES.NOT_CONFIGURED;
}

/** 该状态是否允许发起生成。 */
export function canGenerateInState(state) {
  return state === CLASSROOM_STATES.READY;
}

/**
 * 把**真实** composition 转成可展示的描述。
 *
 * 绝不根据请求 mode 推断内容：只读 composition 里真实统计出来的类型与计数。
 */
export function describeComposition(composition) {
  if (!composition || typeof composition !== "object") return null;
  if (composition.error) {
    return { error: String(composition.error), parts: [], extras: [], total: 0 };
  }
  const parts = (Array.isArray(composition.scenes) ? composition.scenes : []).map((row) => ({
    raw: row.type,
    label: SCENE_TYPE_LABELS[row.type] || `未知类型（${row.type}）`,
    count: Number(row.count) || 0,
    known: Boolean(SCENE_TYPE_LABELS[row.type]),
  }));
  const widgets = (Array.isArray(composition.widget_types) ? composition.widget_types : []).map(
    (row) => ({
      raw: row.widget_type,
      label: WIDGET_TYPE_LABELS[row.widget_type] || `未知形式（${row.widget_type}）`,
      count: Number(row.count) || 0,
      known: Boolean(WIDGET_TYPE_LABELS[row.widget_type]),
    }),
  );
  const extras = [];
  if (composition.has_whiteboard) extras.push("白板推导");
  if (composition.has_tts) extras.push("语音讲解");
  if (composition.has_multi_agent) extras.push("多智能体讨论");
  return {
    parts,
    widgets,
    extras,
    total: Number(composition.scene_total) || 0,
    degraded: Boolean(composition.degraded),
    requires3d: Boolean(composition.requires_external_3d),
    external3dAvailable: composition.external_3d_available !== false,
    error: null,
  };
}

/** 把真实组成拼成一句话，例如"已生成内容包含：幻灯片 ×3、测验 ×2"。 */
export function compositionSummary(description) {
  if (!description) return "";
  if (description.error) return `课堂内容读取失败：${description.error}`;
  const pieces = description.parts
    .filter((p) => p.count > 0)
    .map((p) => `${p.label} ×${p.count}`);
  const extras = description.extras.length ? `，另含 ${description.extras.join("、")}` : "";
  if (!pieces.length && !extras) return "这节课没有生成可展示的内容";
  return `已生成内容包含：${pieces.join("、")}${extras}`;
}

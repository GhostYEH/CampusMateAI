/**
 * 「进入课堂」直达入口的决策模型。
 *
 * 这条入口**推翻**了原来的三步流程：选角色 → 选模式 → 生成预览 → 确认 → 工作台。
 * 现在用户只表达一件事（"我要进这门课的课堂"），其余的决定由这里做，而且必须是
 * **确定性**的——同一个课程、同一个主题，在任何时刻、任何一次刷新、任何一次双击
 * 之后，都要落回同一个工作台和同一份内容。
 *
 * 三条实现约束，缺一条就会退化成旧的失败模式：
 *
 * 1. **键由内容派生，不由时间派生。** 幂等键里出现时间戳或随机量，刷新就会变成
 *    "再建一个"，而这正是幂等键要防的事。所以键是课程/主题的纯函数。
 * 2. **主题来自服务端真实上报的课程事实。** 没有知识点就如实说"课程资料尚未同步"，
 *    绝不编一条充数——伪造的知识点会让学生以为课程里真讲过。
 * 3. **"读不到"不是"没有"。** 上下文读取失败（超时、权限、依赖挂掉）必须与"这门课
 *    确实还没同步资料"分开说，因为前者重试有用、后者要先去做同步。
 *
 * 这里全部是纯函数，不碰网络也不碰 DOM，因此可以在 `node --test` 里直接钉住。
 */
import { describeWorkspaceError } from "./workspaceModel.js";

/** 直达入口路由。与 `App.jsx` 里的 `path` 必须逐字一致。 */
export const ENTER_CLASSROOM_PATH = "/courses/:courseId/classroom";

/**
 * 「进入课堂」的目标地址。
 *
 * 刻意只带课程 id：角色、模式、提示词都不再由用户提供，把它们塞进 URL 会让
 * "同一个入口"产生多个不同的地址，刷新恢复与幂等判断都会跟着变复杂。
 */
export function enterClassroomHref(courseId) {
  const id = String(courseId ?? "").trim();
  if (!id) throw new Error("打开课堂需要真实的课程");
  return `/courses/${encodeURIComponent(id)}/classroom`;
}

/**
 * 工作台创建的幂等键：**每门课恒定一个**。
 *
 * 双击「进入课堂」、刷新、从别的页面切回来，算出来的都是同一个键，因此服务端
 * 只会给出同一个工作台。键里不含时间戳/随机量是刻意的。
 */
export function classroomEntryIdempotencyKey(courseId) {
  const id = String(courseId ?? "").trim();
  if (!id) throw new Error("工作台幂等键需要真实的课程");
  return `openmaic-workspace-${id}`;
}

/**
 * 首个课堂内容生成的幂等键：按 **课程 + 主题** 派生。
 *
 * 用主题参与派生，是为了让"同一门课换一个主题重进"能生成新内容；用课程参与
 * 派生，是为了让"同一门课同一主题重进/刷新"只恢复、不重生成。
 */
export function stageGenerationIdempotencyKey(courseId, topic) {
  const id = String(courseId ?? "").trim();
  if (!id) throw new Error("生成幂等键需要真实的课程");
  const normalized = String(topic ?? "").trim().replace(/\s+/g, " ");
  return `openmaic-stage-${id}-${hashText(normalized)}`;
}

/**
 * 稳定的 32 位文本散列（FNV-1a）。
 *
 * 用它而不是 `Math.random`/`Date.now`：前者每次调用都不同，后者在刷新后必然不同，
 * 两者都会让"恢复"退化成"新建"。这里只要求**跨进程稳定**，不要求抗碰撞强度。
 */
function hashText(value) {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(36);
}

/** 知识点/资料条目可能是字符串或对象，统一取一个可读标题。 */
function titleOf(item) {
  if (typeof item === "string") return item.trim();
  if (!item || typeof item !== "object") return "";
  return String(item.name || item.title || "").trim();
}

function titlesOf(items) {
  return (Array.isArray(items) ? items : []).map(titleOf).filter(Boolean);
}

/**
 * 课程简介进入默认 prompt 的长度上限（字符数）。
 *
 * 限长是必要的：简介由服务端上报，可能是一整段很长的介绍；不加限制会让默认主题
 * 被简介淹没，反而丢掉"围绕知识点组织讲解"这个必须保留的指令。180 字足够表达
 * 一门课的定位，且不会挤掉后面的章节/资料。
 */
export const DESCRIPTION_LIMIT = 180;

/**
 * 取一段用于提示词的简介：先归一化空白，再在**词/字边界**上截断。
 *
 * 只保留原文措辞，不改写、不补充。超长时以省略号结尾，让"这里被截断了"是可见的，
 * 而不是悄悄丢掉后半句造成语义失真。
 */
function excerpt(value, limit) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).trimEnd()}…`;
}

/**
 * 这门课现在到底能拿什么去生成。
 *
 * `synced` 为 false 时界面必须显示"课程资料尚未同步"，而不是照常生成一份听起来
 * 很合理的空壳课堂。`degraded` 区分"读不到"：它需要重试，而不是去做同步。
 */
export function describeCourseReadiness(course = {}) {
  const name = String(course.name || course.title || "").trim();
  const code = String(course.code || "").trim();
  const semester = String(course.semester || "").trim();
  // 课程简介同样属于"已授权的真实课程事实"。限长是因为它会进入默认 prompt，
  // 而服务端上报的简介可能很长；截断到一句话的量级既保留课程定位，又不让提示词
  // 被简介淹没。截断只在**保留上限内的字符**这个意义上发生，不改变原文措辞。
  const description = excerpt(course.description, DESCRIPTION_LIMIT);
  const knowledgePoints = titlesOf(course.knowledgePoints);
  const materials = titlesOf(course.materials);
  const chapters = titlesOf(course.chapters);
  const warnings = (Array.isArray(course.warnings) ? course.warnings : []).filter(Boolean);
  const hasTopic = Boolean(name);
  // 章节也算"已同步"：后端把 chapters 与知识点/资料并列上报，三者任一存在都
  // 表示这门课确实有内容可用。只看知识点会把"仅有章节"的课程误报成未同步，
  // 界面就会给出错误的下一步（让用户去做多余的同步）。
  // 简介**不算**已同步内容：它是课程元信息，不是可讲解的课程资料。
  const synced = knowledgePoints.length > 0 || materials.length > 0 || chapters.length > 0;

  if (synced) {
    const parts = [];
    if (chapters.length) parts.push(`${chapters.length} 个章节`);
    if (knowledgePoints.length) parts.push(`${knowledgePoints.length} 个知识点`);
    if (materials.length) parts.push(`${materials.length} 份课程资料`);
    return {
      name, code, semester, description,
      synced: true,
      degraded: false,
      knowledgePoints, materials, chapters,
      notice: `已同步 ${parts.join("、")}。`,
    };
  }
  if (warnings.length) {
    return {
      name, code, semester, description,
      synced: false,
      degraded: true,
      knowledgePoints, materials, chapters,
      // 读取失败与"确实没有"是两回事：前者重试有用。
      notice: `课程知识点与资料本次未能读取，生成内容可能不完整；可稍后重试。`,
    };
  }
  return {
    name, code, semester, description,
    synced: false,
    degraded: false,
    knowledgePoints, materials, chapters,
    notice: hasTopic
      ? "课程资料尚未同步，本次将依据课程基本信息生成入门课堂。"
      : "课程资料尚未同步。",
  };
}

/**
 * 默认生成主题。
 *
 * 把**已授权的真实课程信息**（课程名、课程代码、学期、简介）与**已同步的章节/资料
 * 标题**都纳入上下文，让生成主题贴着这门课的真实内容走。简介是限长后的真实原文，
 * 让模型知道这门课在讲什么，而不是只看到一个课名。
 *
 * 仍然不发明任何知识点：没有同步内容时只说"课程资料尚未同步"，退回课程基本
 * 信息的通用说法。凭据（token、内部地址等）从不进入这里——facts 只由课程事实
 * 字段构成。
 */
export function buildClassroomPrompt(course = {}) {
  const readiness = describeCourseReadiness(course);
  const name = readiness.name || "本课程";
  const basics = [
    readiness.code ? `课程代码 ${readiness.code}` : "",
    readiness.semester ? `学期 ${readiness.semester}` : "",
  ].filter(Boolean);

  const sections = [];
  const points = readiness.knowledgePoints.slice(0, 8);
  const chapters = readiness.chapters.slice(0, 8);
  const materials = readiness.materials.slice(0, 6);
  if (points.length) sections.push(`真实课程知识点（${points.join("、")}）`);
  if (chapters.length) sections.push(`已同步章节（${chapters.join("、")}）`);
  if (materials.length) sections.push(`可用课程资料（${materials.join("、")}）`);

  const basicsText = basics.length ? `（${basics.join("，")}）` : "";
  // 简介作为课程定位单独成句，位置在课名之后、组织方式之前。
  const descriptionText = readiness.description
    ? `课程简介：${readiness.description}。`
    : "";
  const lead = `请根据《${name}》${basicsText}的课程资料生成一节入门学习课堂`;
  if (sections.length) {
    return `${lead}，${descriptionText}围绕${sections.join("、")}组织讲解、示例、测验和练习。`;
  }
  return `${lead}，${descriptionText}围绕真实课程知识点组织讲解、示例、测验和练习。`;
}

/**
 * 生成阶段。文案与原项目 `generation.*` / `ALL_STEPS` 逐字一致，顺序也一致：
 * 这是用户看得见的"生成课程大纲 / 构建学习路径"过程本身，不是装饰。
 */
export const CLASSROOM_GENERATION_STEPS = [
  { key: "outline", title: "生成课程大纲", description: "正在构建学习路径…" },
  { key: "agent", title: "生成课堂角色", description: "正在根据课程内容生成角色…" },
  { key: "content", title: "生成页面内容", description: "正在创建幻灯片、测验和互动内容…" },
  { key: "actions", title: "生成教学动作", description: "正在编排讲解、聚焦和互动流程…" },
];

/**
 * 服务端 `step` → 可见阶段的下标。
 *
 * 服务端用的是自己的步骤名（`generating_outlines` 等），界面用的是四段式；这张表
 * 是两者之间**唯一**的映射点，缺了它进度条只会在 0 和 100 之间跳。
 */
const STEP_TO_PHASE = {
  queued: 0,
  initializing: 0,
  researching: 0,
  generating_outlines: 0,
  generating_scenes: 2,
  generating_media: 2,
  generating_tts: 3,
  persisting: 3,
  completed: CLASSROOM_GENERATION_STEPS.length,
};

function clampPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(100, Math.round(number)));
}

/**
 * 把一次 job 快照翻译成界面状态。
 *
 * 终止态只有 `completed` 算成功；`failed` / `cancelled` 都不算，且 `failed` 必须
 * 把服务端的真实原因带出来——"生成失败"四个字对用户没有任何用。
 */
export function resolveGenerationPhase(job) {
  const status = String(job?.status || "queued");
  const step = String(job?.step || "");
  const total = CLASSROOM_GENERATION_STEPS.length;

  if (status === "completed") {
    return {
      status, key: "complete", index: total, total, percent: 100,
      title: "生成完成！", description: "课堂内容已写入工作台。",
      done: true, failed: false, cancelled: false,
      reason: "",
    };
  }
  if (status === "failed" || status === "cancelled") {
    const phaseIndex = STEP_TO_PHASE[step];
    const index = Number.isInteger(phaseIndex) ? Math.min(phaseIndex, total - 1) : 0;
    return {
      status,
      key: CLASSROOM_GENERATION_STEPS[index].key,
      index, total,
      percent: clampPercent(job?.progress),
      title: status === "cancelled" ? "已中断" : "生成失败",
      description: "",
      done: false,
      failed: status === "failed",
      cancelled: status === "cancelled",
      reason: String(job?.error || job?.error_code || "").trim(),
    };
  }

  // queued / running：能用服务端 step 就用它，否则退回进度百分比。
  const hasPhase = Object.prototype.hasOwnProperty.call(STEP_TO_PHASE, step);
  const byPercent = Math.min(total - 1, Math.floor((clampPercent(job?.progress) / 100) * total));
  const index = hasPhase ? Math.min(STEP_TO_PHASE[step], total - 1) : byPercent;
  const safeIndex = Number.isInteger(index) && index >= 0 ? index : 0;
  const current = CLASSROOM_GENERATION_STEPS[safeIndex];
  return {
    status, key: current.key, index: safeIndex, total,
    percent: clampPercent(job?.progress),
    title: current.title, description: current.description,
    done: false, failed: false, cancelled: false, reason: "",
  };
}

/**
 * 一次失败/异常 → 局部可操作的中文说明。
 *
 * 复用工作台那套 reason 分类（503 的稳定 reason 决定能不能重试），额外补上
 * "job 本身失败"这一种：它不是 HTTP 错误，但同样要带真实原因、重试和手动创建。
 */
export function describeEntryFailure(error) {
  // job 失败：HTTP 是 200，失败信息在 body 里。
  const jobStatus = error?.response?.data?.status;
  if (jobStatus === "failed" || jobStatus === "cancelled") {
    const raw = String(error.response.data.error || error.response.data.error_code || "").trim();
    const cancelled = jobStatus === "cancelled";
    return {
      kind: cancelled ? "cancelled" : "job-failed",
      reason: String(error.response.data.error_code || "").trim() || "job_failed",
      retryable: !cancelled,
      canRetry: !cancelled,
      canCreateManually: true,
      completed: false,
      message: cancelled
        ? "生成已中断，可重新开始或手动创建工作台。"
        : `生成失败：${raw || "受管服务未给出具体原因"}。可重试，或手动创建工作台。`,
    };
  }

  const described = describeWorkspaceError(error);
  const manual = described.kind !== "notFound";
  return {
    kind: described.kind,
    reason: described.reason || "",
    retryable: described.retryable,
    canRetry: described.retryable,
    // 服务不可用或内容不合法时，手动创建往往是唯一还走得通的路。
    canCreateManually: manual,
    completed: false,
    message: described.message,
  };
}

/**
 * 这次结果能不能对用户说"已完成"。
 *
 * 单独抽出来是因为它是本任务里最容易被写错、后果也最严重的一条：伪造一次成功
 * 会让用户以为内容已经在了。只有显式 `completed === true` 才算。
 */
export function shouldCountAsCompleted(view) {
  return view?.completed === true;
}

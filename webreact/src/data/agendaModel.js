/**
 * 统一"今日待办"的展示模型。
 *
 * 后端 /agenda/today 是唯一事实源：首页、学习陪伴、任务总览"今天"分组、
 * 全局角标都消费同一份数据，这里只做展示映射（文案、图标、可操作性），
 * 绝不再按页面各自过滤一遍。
 *
 * 关键约束：
 * - 学习通作业/考试只读（completable=false），不允许在 CampusMate 勾选完成。
 * - "今天"由后端按 Asia/Shanghai 判定，前端不做日期比较。
 */

export const AGENDA_KIND_LABELS = {
  assignment: "课程作业",
  exam: "考试",
  personal_task: "个人待办",
  class: "课程",
};

export const AGENDA_SOURCE_LABELS = {
  chaoxing: "学习通",
  personal: "个人安排",
  academic: "课表",
};

export const AGENDA_STATUS_LABELS = {
  pending: "待完成",
  completed: "已完成",
  overdue: "已逾期",
  submitted: "已提交",
  graded: "已批阅",
};

const KIND_ICONS = {
  assignment: "PhFileText",
  exam: "PhExam",
  personal_task: "PhCheckSquare",
  class: "PhBookOpen",
};

const KIND_TONES = {
  assignment: "red",
  exam: "violet",
  personal_task: "amber",
  class: "blue",
};

/** 已终态的状态：不再计入 pending。 */
export const TERMINAL_AGENDA_STATUSES = new Set(["completed", "submitted", "graded"]);

/**
 * 只有学习通自己的 https 域名才允许作为"原始页面"外跳。
 * 这是安全校验，不是可选的展示优化：来源 URL 来自外部平台，必须 fail-closed。
 */
export function isTrustedChaoxingUrl(raw) {
  if (!raw) return false;
  try {
    const url = new URL(String(raw));
    if (url.protocol !== "https:") return false;
    const host = url.hostname.toLowerCase();
    return host === "chaoxing.com" || host.endsWith(".chaoxing.com");
  } catch {
    return false;
  }
}

export function agendaItemIsDone(item = {}) {
  return TERMINAL_AGENDA_STATUSES.has(String(item?.status || ""));
}

/**
 * 把一个后端 agenda item 映射成前端展示用的稳定结构。
 * 未知字段一律回落成安全默认值，避免后端加字段就把页面搞崩。
 */
export function normalizeTodayAgendaItem(raw = {}) {
  const status = String(raw.status || "pending");
  const kind = String(raw.kind || "personal_task");
  return {
    id: String(raw.id || `${raw.source || "agenda"}:${raw.source_id || raw.sourceId || ""}`),
    source: String(raw.source || "personal"),
    kind,
    sourceId: String(raw.source_id ?? raw.sourceId ?? ""),
    courseId: raw.course_id ?? raw.courseId ?? null,
    courseName: raw.course_name ?? raw.courseName ?? null,
    title: String(raw.title || "未命名事项"),
    description: raw.description ?? null,
    startsAt: raw.starts_at ?? raw.startsAt ?? null,
    deadline: raw.deadline ?? null,
    status,
    priority: String(raw.priority || "medium"),
    // 学习通条目由后端判定只读；前端只如实呈现，不提供勾选入口。
    editable: Boolean(raw.editable),
    completable: Boolean(raw.completable),
    readOnly: !raw.completable,
    route: raw.route || null,
    sourceUrl: isTrustedChaoxingUrl(raw.source_url ?? raw.sourceUrl)
      ? String(raw.source_url ?? raw.sourceUrl)
      : null,
    lastSyncedAt: raw.last_synced_at ?? raw.lastSyncedAt ?? null,
    kindLabel: AGENDA_KIND_LABELS[kind] || "事项",
    sourceLabel: AGENDA_SOURCE_LABELS[raw.source] || "待办",
    statusLabel: AGENDA_STATUS_LABELS[status] || "待完成",
    icon: KIND_ICONS[kind] || "PhCheckSquare",
    tone: KIND_TONES[kind] || "amber",
    done: TERMINAL_AGENDA_STATUSES.has(status),
    overdue: status === "overdue",
  };
}

function numberOrZero(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
}

export function normalizeAgendaSummary(summary = {}) {
  const total = numberOrZero(summary.total);
  const completed = numberOrZero(summary.completed);
  return {
    total,
    pending: summary.pending === undefined ? Math.max(0, total - completed) : numberOrZero(summary.pending),
    completed,
    overdue: numberOrZero(summary.overdue),
  };
}

export function normalizeAgendaSource(source = {}) {
  return {
    state: String(source.state || "ok"),
    message: source.message || null,
    itemCount: numberOrZero(source.item_count ?? source.itemCount),
    lastSyncedAt: source.last_synced_at ?? source.lastSyncedAt ?? null,
    // 学习通登录态来自 /chaoxing/status 的进程内缓存；读不到就是 unknown，不猜成 online。
    authState: String(source.auth_state ?? source.authState ?? "unknown"),
  };
}

/** 把 /agenda/today 的响应归一化成页面直接可用的结构。 */
export function normalizeTodayAgenda(payload) {
  if (!payload || typeof payload !== "object") return null;
  const items = Array.isArray(payload.items)
    ? payload.items.map(normalizeTodayAgendaItem)
    : [];
  const sources = payload.sources || {};
  return {
    date: payload.date || "",
    timezone: payload.timezone || "Asia/Shanghai",
    generatedAt: payload.generated_at ?? payload.generatedAt ?? "",
    lastChaoxingSyncedAt: payload.last_chaoxing_synced_at ?? payload.lastChaoxingSyncedAt ?? null,
    stale: Boolean(payload.stale),
    summary: normalizeAgendaSummary(payload.summary),
    sources: {
      chaoxing: normalizeAgendaSource(sources.chaoxing),
      personal: normalizeAgendaSource(sources.personal),
      schedule: normalizeAgendaSource(sources.schedule),
    },
    items,
  };
}

export function agendaPendingItems(agenda) {
  return (agenda?.items || []).filter((item) => !item.done);
}

export function agendaCompletedItems(agenda) {
  return (agenda?.items || []).filter((item) => item.done);
}

/**
 * 空列表的成因。必须区分"真的没有"与"取不到/还没同步"，否则用户看到空列表
 * 会以为数据丢了。
 */
export function resolveAgendaEmptyState(agenda, { error = "" } = {}) {
  if (error) return { kind: "error", message: error };
  if (!agenda) return { kind: "loading", message: "正在读取今日待办…" };
  if (agenda.items.length) return null;
  const chaoxing = agenda.sources?.chaoxing || {};
  if (chaoxing.state === "not_bound") {
    return { kind: "not-bound", message: "还没有绑定学习通，绑定后课程作业与考试会自动进入今日待办。" };
  }
  if (chaoxing.state === "never_synced") {
    return { kind: "never-synced", message: "还没有同步过学习通数据，同步后这里会显示今天要处理的事。" };
  }
  return { kind: "empty", message: "今天没有待办。" };
}

/**
 * 缓存过期/部分失败/登录态失效时的提示，用于"展示旧数据但标注可能不是最新"。
 *
 * `authState` 由调用方传入（来自 /chaoxing/status 的探测结果），因为今日待办接口
 * 本身不触网，只能读到进程内缓存的登录态。
 */
export function resolveAgendaFreshnessNotice(agenda, { authState = "" } = {}) {
  if (!agenda) return "";
  const chaoxing = agenda.sources?.chaoxing || {};
  const resolvedAuth = authState || chaoxing.authState || "unknown";
  if (resolvedAuth === "expired") {
    return "学习通登录态已过期，当前显示的是上一次同步的数据，请重新登录学习通。";
  }
  if (agenda.stale) {
    return "学习通数据可能不是最新，建议重新同步后再确认。";
  }
  if (chaoxing.state === "partial") {
    return "部分课程同步失败，已展示上一次成功获取的数据。";
  }
  return "";
}

/**
 * 把 agenda item 映射成首页"优先事项"卡片使用的形态。
 * 只取未完成项，保持后端给的排序（逾期 → 今天考试 → 今天截止作业 → 个人待办）。
 */
export function buildAgendaDueItems(agenda) {
  return agendaPendingItems(agenda).map((item) => ({
    id: item.sourceId || item.id,
    agendaId: item.id,
    kind: item.kindLabel,
    title: item.title,
    due: item.deadline || item.startsAt || null,
    icon: item.icon,
    tone: item.tone,
    sourceType: item.kind,
    route: item.route,
  }));
}

/** 学习陪伴右侧"今日待办"：只展示前 limit 条，但总数/完成数必须取 summary。 */
export function selectAgendaForSidebar(agenda, limit = 8) {
  const pending = agendaPendingItems(agenda);
  return {
    items: pending.slice(0, limit),
    visibleCount: Math.min(pending.length, limit),
    summary: normalizeAgendaSummary(agenda?.summary),
  };
}

/**
 * 任务总览的分组。
 *
 * "今天"分组必须来自统一今日待办（未完成项），其余分组继续用本地清单，
 * 但要按 sourceId 去重，避免同一条在"今天"和"即将截止"里各出现一次 ——
 * 那正是改造前三个页面口径不一致的表现。
 */
export function groupTasksWithAgenda({ tasks = [], agenda = null, stateOf }) {
  const resolveState = stateOf || defaultGroupState;
  const groups = { today: [], upcoming: [], later: [], completed: [] };
  const agendaPending = agendaPendingItems(agenda);
  const agendaKeys = new Set(agendaPending.map((item) => String(item.sourceId)));
  groups.today = agendaPending;
  (tasks || []).forEach((task) => {
    if (agendaKeys.has(String(task.sourceId))) return;
    const state = resolveState(task);
    if (state === "completed") groups.completed.push(task);
    else if (state === "overdue" || state === "today") groups.today.push(task);
    else if (state === "upcoming") groups.upcoming.push(task);
    else groups.later.push(task);
  });
  return groups;
}

function defaultGroupState(task) {
  if (task?.done) return "completed";
  return "later";
}

/**
 * 并发去重：同一时刻只允许一个在途请求。
 *
 * 首页、学习陪伴、任务总览都会触发今日待办刷新，如果没有这层保护，
 * 多个组件挂载就会并发重复拉取同一份数据。
 */
export function createInFlightDeduper() {
  let inFlight = null;
  return function runOnce(task) {
    if (inFlight) return inFlight;
    inFlight = Promise.resolve()
      .then(task)
      .finally(() => { inFlight = null; });
    return inFlight;
  };
}

/**
 * 自适应干预闭环的展示投影。
 *
 * 前端**只读后端持久化的决策**：后台 Worker 把结论落进
 * `adaptive_replan_decisions`，再通过 `GET /adaptive-interventions/{id}/outcome`
 * 暴露出来。页面不允许根据 delta、观测结果或干预状态去"猜"系统决定 ——
 * 猜出来的决定会和真实血缘脱节，学生看到的就不再是系统实际做了什么。
 *
 * 因此这里把"读不到 / 还没决定 / 已经决定"三种状态显式区分开，
 * 而不是把缺失一律渲染成"证据不足"。
 */

export const DECISION_STATE = {
  /** 请求进行中 */
  LOADING: "LOADING",
  /** 请求失败，或响应缺失 */
  UNAVAILABLE: "UNAVAILABLE",
  /** 闭环仍在观测窗口内，后端还没有落库决定 */
  PENDING: "PENDING",
  /** 后端已落库决定 */
  DECIDED: "DECIDED",
};

/** 唯一允许声称"学习计划已经换掉了"的文案。 */
export const PLAN_SWITCHED_LABEL = "已调整学习计划";

export const DECISION_LABEL = {
  CONTINUE: "继续当前计划",
  WAIT_FOR_EVIDENCE: "等待更多证据",
  // 注意：这只是 REPLAN 的**终态**文案，实际展示还要看 `decision_status`。
  REPLAN: PLAN_SWITCHED_LABEL,
  SUSPEND: "暂停后续规划",
};

/**
 * `adaptive_replan_decisions.status` 的取值（与数据库 CHECK 约束一致）。
 *
 * 这个字段回答的是"这次调整走到哪一步了"，而不是"决定了什么"：
 * 只有 `APPLIED` 代表学习计划**真的已经切换完成**。
 */
export const DECISION_STATUS = {
  /** 已决定，还没开始执行 */
  PENDING: "PENDING",
  /** 正在执行（生成并绑定新计划） */
  APPLYING: "APPLYING",
  /** 执行完成：计划已切换 */
  APPLIED: "APPLIED",
  /** 执行失败：计划没有切换 */
  FAILED: "FAILED",
};

const REPLAN_PENDING_LABEL = "准备调整学习计划（尚未开始）";

/**
 * REPLAN 的展示文案必须按 `decision_status` 分档。
 *
 * 把四档合并成一句"已调整学习计划"是错的：`PENDING`/`APPLYING` 时新计划可能
 * 还没生成，`FAILED` 时旧计划仍然是正式版本。学生看到"已调整"而计划其实没变，
 * 页面描述的就只是意图而不是系统实际做了什么。
 */
const REPLAN_VIEW_BY_STATUS = {
  PENDING: { label: REPLAN_PENDING_LABEL, tone: "neutral" },
  APPLYING: { label: "正在调整学习计划", tone: "neutral" },
  APPLIED: { label: PLAN_SWITCHED_LABEL, tone: "accent" },
  FAILED: { label: "调整学习计划失败", tone: "warn" },
};

const REPLAN_DETAIL_BY_STATUS = {
  PENDING: "系统已决定调整，但尚未开始执行，学习计划暂时保持原计划。",
  APPLYING: "正在生成并切换学习计划，完成前学习计划保持为原计划。",
  FAILED: "调整没有成功，学习计划保留为原计划；系统会按安全策略重试或保守等待。",
};

export const DECISION_TONE = {
  CONTINUE: "ok",
  WAIT_FOR_EVIDENCE: "neutral",
  REPLAN: "accent",
  SUSPEND: "warn",
};

export const OBSERVED_OUTCOME_LABEL = {
  IMPROVED: "观测到改善",
  STABLE: "状态基本稳定",
  DECLINED: "观测到下降",
  INSUFFICIENT_EVIDENCE: "证据不足",
};

export const ADOPTION_LABEL = {
  COMPLETED: "计划已完成",
  IN_PROGRESS: "计划执行中",
  NOT_STARTED: "尚未开始",
  UNAVAILABLE: "暂时取不到执行数据",
};

/**
 * 把一次 `/outcome` 请求的结果投影成页面可直接渲染的展示模型。
 *
 * @param {{outcome?: object|null, loading?: boolean, error?: Error|null}} input
 */
export function describeInterventionDecision({ outcome = null, loading = false, error = null } = {}) {
  if (loading) {
    return {
      state: DECISION_STATE.LOADING,
      label: "读取中",
      tone: "neutral",
      detail: null,
      decision: null,
      decisionStatus: null,
      applied: false,
      reasonCodes: [],
      adjustments: [],
      observedOutcome: null,
      observedOutcomeLabel: null,
    };
  }
  if (error) {
    return {
      state: DECISION_STATE.UNAVAILABLE,
      label: "暂时读不到系统决定",
      tone: "warn",
      detail: error.message || "请稍后重试",
      decision: null,
      decisionStatus: null,
      applied: false,
      reasonCodes: [],
      adjustments: [],
      observedOutcome: null,
      observedOutcomeLabel: null,
    };
  }
  if (!outcome) {
    return {
      state: DECISION_STATE.UNAVAILABLE,
      label: "暂时读不到系统决定",
      tone: "warn",
      detail: null,
      decision: null,
      decisionStatus: null,
      applied: false,
      reasonCodes: [],
      adjustments: [],
      observedOutcome: null,
      observedOutcomeLabel: null,
    };
  }

  const observedOutcome = outcome.observed_outcome || null;
  const observedOutcomeLabel = observedOutcome
    ? OBSERVED_OUTCOME_LABEL[observedOutcome] || "证据不足"
    : null;

  if (!outcome.decision) {
    return {
      state: DECISION_STATE.PENDING,
      label: "尚无系统决定",
      tone: "neutral",
      detail: "闭环仍在观测窗口内，系统还没有落库决定。",
      decision: null,
      decisionStatus: null,
      applied: false,
      reasonCodes: [],
      adjustments: [],
      observedOutcome,
      observedOutcomeLabel,
    };
  }

  const reasonCodes = Array.isArray(outcome.decision_reason_codes) ? outcome.decision_reason_codes : [];
  const adjustments = Array.isArray(outcome.suggested_adjustments) ? outcome.suggested_adjustments : [];

  if (outcome.decision === "REPLAN") {
    // 只有后端明确写成 APPLIED 才代表计划真的切换完成；其余一切取值
    // （含缺失与未来新增的未知状态）都按"尚未切换"保守展示。
    const status = Object.values(DECISION_STATUS).includes(outcome.decision_status)
      ? outcome.decision_status
      : null;
    const view = REPLAN_VIEW_BY_STATUS[status] ?? {
      label: REPLAN_PENDING_LABEL, tone: "neutral",
    };
    return {
      state: DECISION_STATE.DECIDED,
      label: view.label,
      tone: view.tone,
      detail: status === DECISION_STATUS.APPLIED ? null : REPLAN_DETAIL_BY_STATUS[status] ?? null,
      decision: outcome.decision,
      decisionStatus: status,
      applied: status === DECISION_STATUS.APPLIED,
      reasonCodes,
      adjustments,
      observedOutcome,
      observedOutcomeLabel,
    };
  }

  return {
    state: DECISION_STATE.DECIDED,
    label: DECISION_LABEL[outcome.decision] || outcome.decision,
    tone: DECISION_TONE[outcome.decision] || "neutral",
    detail: null,
    decision: outcome.decision,
    decisionStatus: outcome.decision_status ?? null,
    // 只有重规划才谈得上"切换学习计划"。
    applied: false,
    reasonCodes,
    adjustments,
    observedOutcome,
    observedOutcomeLabel,
  };
}

/**
 * 执行采纳的展示文案。`null` 表示后端还没给出采纳信号，
 * 与"尚未开始"是两件事，不能混为一谈。
 */
export function describeAdoption(adoption) {
  if (!adoption) return "尚未开始";
  return ADOPTION_LABEL[adoption] || String(adoption);
}

/** 观测结果的展示文案；缺失时显式说明"还没观测"，不冒充"证据不足"。 */
export function describeObservedOutcome(observedOutcome) {
  if (!observedOutcome) return "尚未产生观测结论";
  return OBSERVED_OUTCOME_LABEL[observedOutcome] || "证据不足";
}

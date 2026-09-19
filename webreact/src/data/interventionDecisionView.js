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

export const DECISION_LABEL = {
  CONTINUE: "继续当前计划",
  WAIT_FOR_EVIDENCE: "等待更多证据",
  REPLAN: "已调整学习计划",
  SUSPEND: "暂停后续规划",
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
      reasonCodes: [],
      adjustments: [],
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
    reasonCodes: Array.isArray(outcome.decision_reason_codes) ? outcome.decision_reason_codes : [],
    adjustments: Array.isArray(outcome.suggested_adjustments) ? outcome.suggested_adjustments : [],
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

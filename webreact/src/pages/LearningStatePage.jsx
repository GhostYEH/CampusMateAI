/**
 * 我的学习状态页面 — Phase 6B
 *
 * 展示学生世界模型的完整闭环：
 * 学习事实 → 状态快照 → 知识点估计 → 误区假设 → 可解释计划 →
 * 用户确认 → 原子执行 → 学习反馈 → 后续效果观察 → 状态更新 → 再规划
 *
 * 中性产品语言，避免心理画像/能力判定等负面表述。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../data/learnerStateApi.js";

const DATA_QUALITY_LABEL = {
  FRESH: "数据较新",
  PARTIAL: "部分数据可用",
  STALE: "数据可能已过期",
  UNAVAILABLE: "暂时没有足够数据",
};

const CONFIDENCE_LABEL = (c) => {
  if (c >= 0.7) return "证据较充分";
  if (c >= 0.35) return "证据一般";
  return "证据有限";
};

const CHANGE_LABEL = {
  ADDED: "新增",
  UPDATED: "更新",
  REMOVED: "移除",
  UNCHANGED: "未变",
};

const HYPOTHESIS_STATUS_LABEL = {
  OPEN: "待验证",
  CONFIRMED: "已确认",
  REJECTED: "已否定",
  RESOLVED: "已解决",
  EXPIRED: "已过期",
};

const PLAN_STATUS_LABEL = {
  PROPOSED: "待确认",
  ACCEPTED: "已接受",
  REJECTED: "已拒绝",
  EXECUTED: "已执行",
  PARTIALLY_EXECUTED: "部分执行",
  UNDONE: "已撤销",
  EXPIRED: "已过期",
};

const FEEDBACK_OPTIONS = [
  { value: "HELPFUL", label: "有帮助" },
  { value: "NOT_HELPFUL", label: "没有帮助" },
  { value: "TOO_LONG", label: "太长" },
  { value: "TOO_SHORT", label: "太短" },
  { value: "WRONG_PRIORITY", label: "优先级不合适" },
  { value: "ALREADY_DONE", label: "我已经完成" },
  { value: "MISSING_CONTEXT", label: "缺少必要信息" },
];

const DELETE_SCOPES = [
  { value: "STATE_ONLY", label: "仅状态投影", desc: "删除投影 run、snapshot 和 evidence" },
  { value: "EVENTS_AND_STATE", label: "事件与状态", desc: "删除 Learner Event 及其派生状态" },
  { value: "KNOWLEDGE_ONLY", label: "仅知识投影", desc: "删除知识投影和误区假设" },
  { value: "PLANS_ONLY", label: "仅学习计划", desc: "删除计划、计划项、反馈和评估" },
  { value: "MODEL_SHADOW_ONLY", label: "仅模型影子", desc: "删除在线影子记录" },
  { value: "ALL_LEARNER_MODEL_DATA", label: "全部学生模型数据", desc: "删除上述所有派生数据" },
];

function useAsync(fn, deps) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const mounted = useRef(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const run = useCallback(() => {
    setState((s) => ({ ...s, loading: true, error: null }));
    Promise.resolve(fnRef.current())
      .then((data) => mounted.current && setState({ loading: false, data, error: null }))
      .catch((error) => mounted.current && setState({ loading: false, data: null, error }));
  }, []);
  useEffect(() => {
    mounted.current = true;
    run();
    return () => { mounted.current = false; };
  }, deps);
  return { ...state, reload: run };
}

function Spinner({ label = "加载中" }) {
  return <div className="ls-loading" aria-busy="true" aria-live="polite">{label}…</div>;
}

function ErrorBar({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="ls-error" role="alert">
      <span>{error.message || "操作失败，请稍后重试"}</span>
      {onRetry && <button onClick={onRetry} className="ls-retry-btn">重试</button>}
    </div>
  );
}

function EmptyState({ text = "暂时没有数据" }) {
  return <div className="ls-empty">{text}</div>;
}

function QualityBadge({ quality }) {
  return <span className={`ls-quality ls-quality--${(quality || "UNAVAILABLE").toLowerCase()}`}>{DATA_QUALITY_LABEL[quality] || "未知"}</span>;
}

function ConfidenceBadge({ confidence }) {
  return <span className="ls-confidence">{CONFIDENCE_LABEL(confidence)}</span>;
}

// ===== A. 当前状态总览 =====
function StateOverview({ snapshots, onViewEvidence }) {
  const cards = useMemo(() => {
    if (!snapshots?.items) return [];
    return snapshots.items.filter((s) => s.scope_type === "USER").slice(0, 5);
  }, [snapshots]);

  if (cards.length === 0) return <EmptyState text="暂时没有足够的学习状态数据" />;

  return (
    <section className="ls-section ls-overview" aria-label="当前状态总览">
      <div className="ls-card-grid">
        {cards.map((snap) => (
          <article key={snap.snapshot_id} className="ls-state-card">
            <h3 className="ls-state-card__title">{STATE_TYPE_LABEL[snap.state_type] || snap.state_type}</h3>
            <p className="ls-state-card__value">{formatStateValue(snap)}</p>
            <div className="ls-state-card__meta">
              <QualityBadge quality={snap.data_quality} />
              <ConfidenceBadge confidence={snap.confidence} />
            </div>
            <p className="ls-state-card__time">更新于 {formatTime(snap.computed_at)}</p>
            <div className="ls-state-card__actions">
              <button className="ls-link-btn" onClick={() => onViewEvidence(snap)}>查看依据</button>
              <button className="ls-link-btn ls-link-btn--warn" onClick={() => onMarkInaccurate(snap)}>这不准确</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

const STATE_TYPE_LABEL = {
  observed_learning_activity: "最近学习活动",
  task_workload: "任务负荷",
  deadline_exposure: "截止压力",
  course_participation: "课程参与",
  data_source_health: "数据源健康度",
  knowledge_mastery_estimate: "知识点估计",
};

function formatStateValue(snap) {
  const v = snap.value;
  if (!v) return "—";
  if (snap.state_type === "task_workload") {
    return `待办 ${v.pending || 0} · 逾期 ${v.overdue || 0}`;
  }
  if (snap.state_type === "observed_learning_activity") {
    return `7天 ${v.sessions_7d || 0} 次学习`;
  }
  if (snap.state_type === "deadline_exposure") {
    return v.category || "—";
  }
  if (snap.state_type === "course_participation") {
    return `章节 ${v.chapters_completed || 0}/${v.chapters_total || 0}`;
  }
  if (snap.state_type === "data_source_health") {
    return DATA_QUALITY_LABEL[v.quality] || v.quality || "—";
  }
  return "—";
}

function formatTime(iso) {
  if (!iso) return "未知";
  try {
    const d = new Date(iso);
    const now = Date.now();
    const diff = now - d.getTime();
    if (diff < 60000) return "刚刚";
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
    return d.toLocaleDateString("zh-CN");
  } catch { return "未知"; }
}

// ===== B. 状态变化时间线 =====
function StateTimeline({ changes }) {
  if (!changes?.items?.length) return <EmptyState text="暂时没有状态变化记录" />;
  return (
    <section className="ls-section ls-timeline" aria-label="状态变化时间线">
      <ol className="ls-timeline__list">
        {changes.items.map((ch) => (
          <li key={`${ch.scope_type}-${ch.scope_id}-${ch.state_type}`} className="ls-timeline__item">
            <span className={`ls-timeline__change ls-timeline__change--${(ch.change_kind || "UPDATED").toLowerCase()}`}>
              {CHANGE_LABEL[ch.change_kind] || ch.change_kind}
            </span>
            <span className="ls-timeline__label">{STATE_TYPE_LABEL[ch.state_type] || ch.state_type}</span>
            {ch.estimator_changed && <span className="ls-timeline__tag">估计版本变化</span>}
            {ch.trigger === "correction" && <span className="ls-timeline__tag">你提交的纠正已参与重新计算</span>}
          </li>
        ))}
      </ol>
    </section>
  );
}

// ===== C. C 语言知识地图 =====
function KnowledgeMap({ knowledge, taxonomy, onViewEvidence }) {
  const groups = useMemo(() => {
    if (!knowledge?.items) return {};
    const byCategory = {};
    for (const item of knowledge.items) {
      const cat = item.category || "other";
      if (!byCategory[cat]) byCategory[cat] = [];
      byCategory[cat].push(item);
    }
    return byCategory;
  }, [knowledge]);

  const cats = Object.keys(groups);
  if (cats.length === 0) return <EmptyState text="暂时没有知识点数据" />;

  return (
    <section className="ls-section ls-knowledge" aria-label="C 语言知识地图">
      {cats.map((cat) => (
        <div key={cat} className="ls-knowledge__group">
          <h3 className="ls-knowledge__category">{CATEGORY_LABEL[cat] || cat}</h3>
          <div className="ls-knowledge__cards">
            {groups[cat].map((kc) => (
              <article key={kc.kc_code} className={`ls-kc-card ls-kc-card--${(kc.band || "INSUFFICIENT_EVIDENCE").toLowerCase()}`}>
                <h4 className="ls-kc-card__name">{kc.kc_name || kc.kc_code}</h4>
                <div className="ls-kc-card__meta">
                  <QualityBadge quality={kc.data_quality} />
                  <span className="ls-kc-card__evidence">{kc.evidence_count || 0} 条证据</span>
                </div>
                <p className="ls-kc-card__band">{BAND_LABEL[kc.band] || "证据不足"}</p>
                {kc.valid_until && <p className="ls-kc-card__valid">有效期至 {formatTime(kc.valid_until)}</p>}
              </article>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

const CATEGORY_LABEL = {
  foundations: "基础", types: "类型", expressions: "表达式", control: "控制流",
  functions: "函数", arrays: "数组", pointers: "指针", memory: "内存",
  composite: "复合类型", io: "输入输出", practice: "实践",
};

const BAND_LABEL = {
  INSUFFICIENT_EVIDENCE: "证据不足",
  EMERGING: "初步了解",
  DEVELOPING: "发展中",
  PROFICIENT: "较为熟练",
};

// ===== D. 证据抽屉 =====
function EvidenceDrawer({ snapshot, onClose, onCorrection }) {
  const [page, setPage] = useState(1);
  const [correctionType, setCorrectionType] = useState(null);
  const [correctionBusy, setCorrectionBusy] = useState(false);
  const [correctionMsg, setCorrectionMsg] = useState(null);
  const { loading, data, error } = useAsync(
    () => api.getSnapshotEvidence(snapshot.snapshot_id, page),
    [snapshot.snapshot_id, page]
  );

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const handleSubmitCorrection = useCallback(async () => {
    if (!correctionType) return;
    setCorrectionBusy(true);
    try {
      await api.createCorrection({
        projection_kind: snapshot.projection_kind || "CORE",
        projection_scope: snapshot.projection_scope || "__user__",
        target_snapshot_id: snapshot.snapshot_id,
        scope_type: snapshot.scope_type,
        scope_id: snapshot.scope_id,
        state_type: snapshot.state_type,
        correction_type: correctionType,
        reason_code: "OTHER_CONTROLLED_REASON",
        idempotency_key: `corr-${snapshot.snapshot_id}-${Date.now()}`,
      });
      setCorrectionMsg("已提交纠正，投影将在下次读取时更新");
      if (onCorrection) onCorrection(snapshot);
    } catch (e) {
      setCorrectionMsg(e.message);
    } finally {
      setCorrectionBusy(false);
    }
  }, [correctionType, snapshot, onCorrection]);

  return (
    <div className="ls-drawer-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label="证据详情">
      <div className="ls-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="ls-drawer__header">
          <h2>证据详情</h2>
          <button className="ls-drawer__close" onClick={onClose} aria-label="关闭">×</button>
        </div>
        <div className="ls-drawer__body">
          {loading && <Spinner />}
          <ErrorBar error={error} />
          {!loading && !error && data?.items?.length === 0 && <EmptyState text="暂时没有证据" />}
          {!loading && !error && data?.items?.map((ev) => (
            <div key={`${ev.evidence_kind}-${ev.event_id || ev.source_category}`} className="ls-evidence-item">
              <p className="ls-evidence-item__kind">{EVIDENCE_KIND_LABEL[ev.evidence_kind] || ev.evidence_kind}</p>
              <p className="ls-evidence-item__source">{ev.source_category}</p>
              {ev.event_type && <p className="ls-evidence-item__type">{ev.event_type}</p>}
              <p className="ls-evidence-item__time">{formatTime(ev.occurred_at)}</p>
              <p className="ls-evidence-item__role">{ev.role === "SUPPORTS" ? "支持" : ev.role === "INVALIDATES" ? "否定" : "限制"}</p>
            </div>
          ))}
          {data?.has_more && (
            <button className="ls-more-btn" onClick={() => setPage((p) => p + 1)}>加载更多</button>
          )}
        </div>
        <div className="ls-drawer__correction">
          <h3>标记此状态</h3>
          {correctionMsg && <p className="ls-correction-msg">{correctionMsg}</p>}
          <div className="ls-correction-options">
            <button className="ls-btn ls-btn--sm" onClick={() => setCorrectionType("MARK_INACCURATE")} disabled={correctionBusy}>标记不准确</button>
            <button className="ls-btn ls-btn--sm" onClick={() => setCorrectionType("SOURCE_OUTDATED")} disabled={correctionBusy}>数据源已过时</button>
            <button className="ls-btn ls-btn--sm" onClick={() => setCorrectionType("NOT_APPLICABLE")} disabled={correctionBusy}>不适用</button>
          </div>
          {correctionType && (
            <button className="ls-btn ls-btn--primary" onClick={handleSubmitCorrection} disabled={correctionBusy}>
              {correctionBusy ? "提交中…" : `确认提交（${correctionType}）`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const EVIDENCE_KIND_LABEL = {
  EVENT: "学习事件",
  SOURCE_ROW: "业务记录",
  SYNC_STATUS: "同步状态",
};

// ===== E. 学习困难假设 =====
function MisconceptionHypotheses({ hypotheses, onDecide, busy }) {
  if (!hypotheses?.items?.length) return <EmptyState text="暂时没有学习困难假设" />;
  return (
    <section className="ls-section ls-hypotheses" aria-label="学习困难假设">
      <p className="ls-hypotheses__disclaimer">这是一条待验证的学习假设，不是对能力或心理状态的定论。</p>
      {hypotheses.items.map((h) => (
        <article key={h.hypothesis_id} className="ls-hypothesis-card">
          <h3 className="ls-hypothesis-card__title">{MISCONCEPTION_LABEL[h.misconception_code] || h.misconception_code}</h3>
          <p className="ls-hypothesis-card__status">{HYPOTHESIS_STATUS_LABEL[h.status] || h.status}</p>
          <div className="ls-hypothesis-card__meta">
            <ConfidenceBadge confidence={h.confidence} />
            <span>{h.supporting_evidence_count || 0} 条支持证据</span>
          </div>
          {h.status === "OPEN" && (
            <div className="ls-hypothesis-card__actions">
              <button className="ls-btn" onClick={() => onDecide(h.hypothesis_id, "CONFIRM")} disabled={busy}>确认这个问题</button>
              <button className="ls-btn" onClick={() => onDecide(h.hypothesis_id, "REJECT")} disabled={busy}>这不符合我的情况</button>
              <button className="ls-btn ls-btn--ghost" disabled>稍后再判断</button>
            </div>
          )}
        </article>
      ))}
    </section>
  );
}

const MISCONCEPTION_LABEL = {
  pointer_value_address_confusion: "指针值与地址混淆",
  array_boundary_confusion: "数组边界混淆",
  dynamic_memory_lifecycle_error: "动态内存生命周期错误",
  function_parameter_mismatch: "函数参数不匹配",
  loop_termination_error: "循环终止条件错误",
  repeated_pointer_indirection_error: "重复指针解引用错误",
};

// ===== F. 学习计划中心 =====
function LearningPlanCenter({ plans, onAction, busy }) {
  const current = plans?.items?.find((p) => p.status === "PROPOSED" || p.status === "ACCEPTED" || p.status === "EXECUTED");
  if (!current) return <EmptyState text="暂时没有学习计划" />;
  return (
    <section className="ls-section ls-plan" aria-label="学习计划中心">
      <div className="ls-plan__header">
        <h3>当前学习计划</h3>
        <span className={`ls-plan__status ls-plan__status--${(current.status || "").toLowerCase()}`}>{PLAN_STATUS_LABEL[current.status] || current.status}</span>
      </div>
      {current.warning_codes?.length > 0 && (
        <div className="ls-plan__warnings">
          {current.warning_codes.map((w) => <p key={w} className="ls-warning">{WARNING_LABEL[w] || w}</p>)}
        </div>
      )}
      {current.items?.map((item) => (
        <div key={item.item_id} className="ls-plan-item">
          <p className="ls-plan-item__type">{ITEM_TYPE_LABEL[item.item_type] || item.item_type}</p>
          <p className="ls-plan-item__time">预计 {item.estimated_minutes || 0} 分钟</p>
          {item.explanation_codes?.map((e) => <span key={e} className="ls-plan-item__reason">{e}</span>)}
        </div>
      ))}
      <div className="ls-plan__actions">
        {current.status === "PROPOSED" && (
          <>
            <button className="ls-btn ls-btn--primary" onClick={() => onAction("accept", current.plan_id)} disabled={busy}>接受计划</button>
            <button className="ls-btn" onClick={() => onAction("reject", current.plan_id)} disabled={busy}>拒绝</button>
          </>
        )}
        {current.status === "ACCEPTED" && (
          <button className="ls-btn ls-btn--primary" onClick={() => onAction("execute", current.plan_id)} disabled={busy}>创建个人学习任务</button>
        )}
        {current.status === "EXECUTED" && (
          <>
            <button className="ls-btn" onClick={() => onAction("undo", current.plan_id)} disabled={busy}>撤销</button>
            <button className="ls-btn" onClick={() => onAction("replan", current.plan_id)} disabled={busy}>重新规划</button>
          </>
        )}
        {current.status === "EXPIRED" && (
          <p className="ls-warning">计划已过有效期</p>
        )}
      </div>
    </section>
  );
}

const ITEM_TYPE_LABEL = {
  TASK_FOCUS: "专注任务",
  KNOWLEDGE_REVIEW: "知识复习",
  CREATE_PERSONAL_TASK: "创建学习任务",
};

const WARNING_LABEL = {
  INPUT_TRUNCATED: "部分输入数据被截断",
  CORE_QUALITY_DEGRADED: "核心状态数据质量降级",
  STALE_CORE_STATE: "核心状态已过期",
  PLAN_STALE: "依据已变化，请重新规划",
};

// ===== G. 计划效果观察 =====
function PlanEvaluation({ evaluation }) {
  if (!evaluation) return null;
  return (
    <section className="ls-section ls-evaluation" aria-label="计划效果观察">
      <p className="ls-evaluation__disclaimer">这里展示计划之后观察到的学习记录，不代表计划与结果之间存在因果关系。</p>
      <div className="ls-evaluation__grid">
        <div className="ls-eval-stat"><span className="ls-eval-stat__num">{evaluation.planned_item_count || 0}</span><span>计划项</span></div>
        <div className="ls-eval-stat"><span className="ls-eval-stat__num">{evaluation.executed_item_count || 0}</span><span>已执行</span></div>
        <div className="ls-eval-stat"><span className="ls-eval-stat__num">{evaluation.completed_plan_task_count || 0}</span><span>完成任务</span></div>
        <div className="ls-eval-stat"><span className="ls-eval-stat__num">{evaluation.followup_practice_count || 0}</span><span>后续练习</span></div>
      </div>
      {evaluation.warning_codes?.length > 0 && evaluation.warning_codes.map((w) => (
        <p key={w} className="ls-warning">{WARNING_LABEL[w] || w}</p>
      ))}
    </section>
  );
}

function PlanEvaluationSection({ plans }) {
  const executedPlan = useMemo(() => {
    const items = plans?.items || [];
    return items.find((p) => p.status === "EXECUTED" || p.status === "PARTIALLY_EXECUTED") || null;
  }, [plans]);
  const evaluation = useAsync(
    () => (executedPlan ? api.getPlanEvaluation(executedPlan.plan_id) : Promise.resolve(null)),
    [executedPlan?.plan_id],
  );
  if (!executedPlan) return null;
  if (evaluation.loading) return <Spinner label="加载效果观察" />;
  if (evaluation.error) return <ErrorBar error={evaluation.error} />;
  return <PlanEvaluation evaluation={evaluation.data} />;
}

// ===== H. 数据与隐私控制 =====
function DataPrivacyControl({ controls, summary, onToggleSource, onDelete, corrections, onRevokeCorrection, busy }) {
  const [deleteScope, setDeleteScope] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <section className="ls-section ls-privacy" aria-label="数据与隐私控制">
      <h3>数据源控制</h3>
      {controls?.items?.map((src) => (
        <div key={src.source_key} className="ls-source-row">
          <span className="ls-source-row__name">{SOURCE_LABEL[src.source_key] || src.source_key}</span>
          <span className={`ls-source-row__status ls-source-row__status--${(src.status || "").toLowerCase()}`}>{SOURCE_STATUS_LABEL[src.status] || src.status}</span>
          {src.can_pause && <button className="ls-btn ls-btn--sm" onClick={() => onToggleSource(src.source_key, "PAUSED")} disabled={busy}>暂停</button>}
          {src.can_resume && <button className="ls-btn ls-btn--sm" onClick={() => onToggleSource(src.source_key, "ENABLED")} disabled={busy}>恢复</button>}
        </div>
      ))}

      <h3>数据摘要</h3>
      {summary && (
        <div className="ls-summary-grid">
          <div className="ls-summary-item"><span>事件</span><strong>{summary.event_count || 0}</strong></div>
          <div className="ls-summary-item"><span>快照</span><strong>{summary.snapshot_count || 0}</strong></div>
          <div className="ls-summary-item"><span>知识</span><strong>{summary.knowledge_snapshot_count || 0}</strong></div>
          <div className="ls-summary-item"><span>误区</span><strong>{summary.misconception_count || 0}</strong></div>
          <div className="ls-summary-item"><span>计划</span><strong>{summary.learning_plan_count || 0}</strong></div>
          <div className="ls-summary-item"><span>影子</span><strong>{summary.shadow_run_count || 0}</strong></div>
        </div>
      )}

      <h3>删除学生模型数据</h3>
      <div className="ls-delete-zone">
        {DELETE_SCOPES.map((s) => (
          <label key={s.value} className="ls-delete-option">
            <input type="radio" name="delete-scope" value={s.value} onChange={() => setDeleteScope(s.value)} />
            <span className="ls-delete-option__label">{s.label}</span>
            <span className="ls-delete-option__desc">{s.desc}</span>
          </label>
        ))}
        {deleteScope && (
          <div className="ls-delete-confirm">
            <p>确认删除「{DELETE_SCOPES.find((s) => s.value === deleteScope)?.label}」？此操作不可撤销。</p>
            <button className="ls-btn ls-btn--danger" onClick={() => { onDelete(deleteScope); setConfirmDelete(false); }} disabled={confirmDelete || busy}>确认删除</button>
          </div>
        )}
      </div>

      {corrections?.items?.length > 0 && (
        <>
          <h3>状态纠正记录</h3>
          {corrections.items.map((c) => (
            <div key={c.correction_id} className="ls-correction-row">
              <span>{c.correction_type}</span>
              <span>{c.reason_code}</span>
              <span>{c.status === "ACTIVE" ? "活跃" : "已撤销"}</span>
              {c.status === "ACTIVE" && <button className="ls-btn ls-btn--sm" onClick={() => onRevokeCorrection(c.correction_id)} disabled={busy}>撤销</button>}
            </div>
          ))}
        </>
      )}
    </section>
  );
}

const SOURCE_LABEL = {
  CORE_STUDY: "核心学习记录", PERSONAL_TASK: "个人待办", CHAOXING: "学习通",
  EDU: "教务系统", PRACTICE: "受控练习", MODEL_SHADOW: "模型影子评测", PROACTIVE_SUGGESTIONS: "主动建议",
};
const SOURCE_STATUS_LABEL = { ENABLED: "已启用", PAUSED: "已暂停", DISCONNECTED: "已断开", DELETE_REQUESTED: "删除请求中" };

// ===== I. 模型透明度 =====
function ModelTransparency({ transparency }) {
  if (!transparency?.capabilities) return <EmptyState text="暂时没有模型透明度数据" />;
  return (
    <section className="ls-section ls-transparency" aria-label="模型透明度">
      <p className="ls-transparency__note">CampusMate-LM 当前不影响你的正式学习状态。影子评测结果不会自动修改计划。</p>
      {transparency.capabilities.map((cap) => (
        <article key={cap.capability_name} className="ls-cap-card">
          <h4>{CAPABILITY_LABEL[cap.capability_name] || cap.capability_name}</h4>
          <p className="ls-cap-card__method">生产方式：{cap.production_method}</p>
          <p className={`ls-cap-card__status ls-cap-card__status--${(cap.campusmate_lm_status || "").toLowerCase()}`}>
            {PROMOTION_LABEL[cap.campusmate_lm_status] || cap.campusmate_lm_status}
          </p>
          <p>质量门控：{cap.quality_gate_passed ? "通过" : "未通过"}</p>
          <p>性能门控：{cap.performance_measured ? (cap.performance_gate_passed ? "通过" : "未通过") : "真实设备性能尚未评测"}</p>
          <p>真实模型推理：{cap.uses_real_model_inference ? "是" : "否"}</p>
        </article>
      ))}
    </section>
  );
}

const CAPABILITY_LABEL = {
  c_kc_classification_v1: "C 知识点分类",
  c_error_classification_v1: "C 错误分类",
  learning_summary_v1: "学习摘要",
  read_only_tool_routing_v1: "只读工具路由",
};
const PROMOTION_LABEL = {
  SHADOW_ONLY: "仅影子评测", BLOCKED: "已阻断", ELIGIBLE_FOR_CANARY: "可进入金丝雀", REVOKED: "已撤销",
};

// ===== 主页面 =====
export default function LearningStatePage() {
  const [evidenceSnapshot, setEvidenceSnapshot] = useState(null);
  const [toast, setToast] = useState(null);
  const [busy, setBusy] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const snapshots = useAsync(() => api.getLearnerStateSnapshots({ pageSize: 50 }), [refreshKey]);
  const changes = useAsync(() => api.getLearnerStateChanges({ pageSize: 20 }), [refreshKey]);
  const knowledge = useAsync(() => api.getKnowledgeState(""), [refreshKey]);
  const taxonomy = useAsync(() => api.getTaxonomy(), [refreshKey]);
  const hypotheses = useAsync(() => api.getMisconceptionHypotheses(""), [refreshKey]);
  const plans = useAsync(() => api.getLearningPlans(1, 10), [refreshKey]);
  const controls = useAsync(() => api.getDataControls(), [refreshKey]);
  const summary = useAsync(() => api.getDataSummary(), [refreshKey]);
  const corrections = useAsync(() => api.getCorrections(1, 20), [refreshKey]);
  const transparency = useAsync(() => api.getModelTransparency(), [refreshKey]);

  const showToast = useCallback((msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  }, []);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  const handleDecideHypothesis = useCallback(async (hid, decision) => {
    setBusy(true);
    try {
      await api.decideHypothesis(hid, decision);
      showToast(decision === "CONFIRM" ? "已确认假设" : "已否定假设");
      refresh();
    } catch (e) { showToast(e.message); }
    finally { setBusy(false); }
  }, [showToast, refresh]);

  const handlePlanAction = useCallback(async (action, planId) => {
    setBusy(true);
    try {
      if (action === "accept") await api.decideLearningPlan(planId, "ACCEPT");
      else if (action === "reject") await api.decideLearningPlan(planId, "REJECT");
      else if (action === "execute") await api.executeLearningPlan(planId);
      else if (action === "undo") await api.undoLearningPlan(planId);
      else if (action === "replan") await api.replanLearningPlan(planId, { idempotency_key: `replan-${Date.now()}` });
      showToast(`操作成功：${action}`);
      refresh();
    } catch (e) { showToast(e.message); }
    finally { setBusy(false); }
  }, [showToast, refresh]);

  const handleToggleSource = useCallback(async (sourceKey, status) => {
    setBusy(true);
    try {
      await api.updateDataControl(sourceKey, status, `toggle-${Date.now()}`);
      showToast(status === "PAUSED" ? "已暂停" : "已恢复");
      refresh();
    } catch (e) { showToast(e.message); }
    finally { setBusy(false); }
  }, [showToast, refresh]);

  const handleDelete = useCallback(async (scope) => {
    setBusy(true);
    try {
      await api.requestDeletion(scope, `delete-${Date.now()}`);
      showToast("删除完成");
      refresh();
    } catch (e) { showToast(e.message); }
    finally { setBusy(false); }
  }, [showToast, refresh]);

  const handleRevokeCorrection = useCallback(async (cid) => {
    setBusy(true);
    try {
      await api.revokeCorrection(cid, `revoke-${Date.now()}`);
      showToast("已撤销纠正");
      refresh();
    } catch (e) { showToast(e.message); }
    finally { setBusy(false); }
  }, [showToast, refresh]);

  const handleMarkInaccurate = useCallback((snap) => {
    setEvidenceSnapshot(snap);
  }, []);

  return (
    <div className="learning-state-page" aria-busy={snapshots.loading || busy}>
      <header className="ls-header">
        <div className="ls-header__title-row">
          <h1 className="ls-title">我的学习状态</h1>
          <Link className="ls-prediction-link" to="/prediction">查看预测与反事实模拟</Link>
        </div>
        <p className="ls-subtitle">根据你授权的学习记录生成，可查看依据并随时纠正</p>
        {snapshots.data?.items?.[0] && (
          <p className="ls-update-time">
            <QualityBadge quality={snapshots.data.items[0].data_quality} />
            <span> · 更新于 {formatTime(snapshots.data.items[0].computed_at)}</span>
          </p>
        )}
      </header>

      {toast && <div className="ls-toast" aria-live="assertive" role="status">{toast}</div>}

      <ErrorBar error={snapshots.error} />

      <div className="ls-layout">
        <div className="ls-layout__main">
          <StateOverview snapshots={snapshots.data} onViewEvidence={setEvidenceSnapshot} onMarkInaccurate={handleMarkInaccurate} />
          <StateTimeline changes={changes.data} />
          <KnowledgeMap knowledge={knowledge.data} taxonomy={taxonomy.data} onViewEvidence={setEvidenceSnapshot} />
        </div>
        <div className="ls-layout__side">
          <LearningPlanCenter plans={plans.data} onAction={handlePlanAction} busy={busy} />
          <MisconceptionHypotheses hypotheses={hypotheses.data} onDecide={handleDecideHypothesis} busy={busy} />
        </div>
      </div>

      <div className="ls-layout ls-layout--bottom">
        <div className="ls-layout__main">
          <PlanEvaluationSection plans={plans.data} />
        </div>
        <div className="ls-layout__side">
          <DataPrivacyControl
            controls={controls.data}
            summary={summary.data}
            corrections={corrections.data}
            onToggleSource={handleToggleSource}
            onDelete={handleDelete}
            onRevokeCorrection={handleRevokeCorrection}
            busy={busy}
          />
        </div>
      </div>

      <ModelTransparency transparency={transparency.data} />

      {evidenceSnapshot && <EvidenceDrawer snapshot={evidenceSnapshot} onClose={() => setEvidenceSnapshot(null)} onCorrection={handleMarkInaccurate} />}
    </div>
  );
}

/**
 * 趋势与方案比较页面 — 校园陪伴世界模型
 *
 * 展示预测型校园生活世界模型：
 * 未来负载 → 截止风险 → 日程冲突 → 目标进展 → 方案 A/B 对比 →
 * confidence、data quality、evidence 和 limitations
 *
 * 中性产品语言，避免心理画像/能力判定等负面表述。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../data/learnerStateApi.js";

const FORECAST_TYPE_LABEL = {
  DEADLINE_COMPLETION_RISK: "截止完成风险",
  UPCOMING_WORKLOAD: "未来负载",
  SCHEDULE_CONFLICT_RISK: "日程冲突风险",
  GOAL_PROGRESS_OUTLOOK: "目标进展展望",
  ROUTINE_CONTINUITY: "专注节律连续性",
};

const RISK_BAND_LABEL = {
  LOW: "较低",
  MODERATE: "中等",
  HIGH: "较高",
  VERY_HIGH: "很高",
};

const PRESSURE_BAND_LABEL = {
  LOW: "较轻",
  MODERATE: "中等",
  HIGH: "较重",
  VERY_HIGH: "很重",
};

const OUTLOOK_BAND_LABEL = {
  rising: "上升",
  steady: "平稳",
  declining: "下降",
  insufficient_data: "证据不足",
};

const CONTINUITY_BAND_LABEL = {
  stable: "稳定",
  variable: "波动",
  unknown: "未知",
};

const DATA_QUALITY_LABEL = {
  verified: "数据已核实",
  partial: "部分数据可用",
  stale: "数据可能已过期",
  unavailable: "暂时没有足够数据",
};

const INTERVENTION_TYPES = [
  { value: "ALLOCATE_FOCUS_MINUTES", label: "分配专注时间" },
  { value: "ACCEPT_PLAN", label: "接受行动计划" },
  { value: "REDUCE_DAILY_LOAD", label: "降低每日负载" },
  { value: "RESCHEDULE_TASK", label: "调整任务截止" },
  { value: "PAUSE_DATA_SOURCE", label: "暂停数据源" },
  { value: "ADJUST_GOAL_DEADLINE", label: "调整目标日期" },
];

const DATA_SOURCE_CATEGORIES = [
  { value: "academic", label: "教务系统" },
  { value: "chaoxing", label: "学习通" },
  { value: "notice", label: "通知" },
  { value: "study_session", label: "学习会话" },
  { value: "manual", label: "手动记录" },
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
  }, deps);
  useEffect(() => {
    mounted.current = true;
    run();
    return () => { mounted.current = false; };
  }, [run]);
  return { ...state, reload: run };
}

function Spinner() {
  return <div className="pred-spinner" aria-busy="true" aria-live="polite">加载中…</div>;
}

function ErrorBar({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="pred-error" role="alert">
      <span>{error.message || "加载失败"}</span>
      {onRetry && <button onClick={onRetry} className="pred-error__retry">重试</button>}
    </div>
  );
}

function EmptyState({ children }) {
  return <div className="pred-empty">{children}</div>;
}

function QualityBadge({ quality }) {
  return <span className={`pred-quality pred-quality--${(quality || "unavailable").toLowerCase()}`}>{DATA_QUALITY_LABEL[quality] || "未知"}</span>;
}

function pct(v) {
  if (v == null) return "—";
  return `${Math.round(v * 100)}%`;
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

function formatForecastValue(f) {
  const v = f.value;
  if (!v) return "—";
  if (f.forecast_type === "DEADLINE_COMPLETION_RISK") {
    return `待办 ${v.pending_task_count || 0} · 逾期 ${v.overdue_task_count || 0} · 风险 ${RISK_BAND_LABEL[v.risk_band] || v.risk_band || "—"}`;
  }
  if (f.forecast_type === "UPCOMING_WORKLOAD") {
    return `任务 ${v.task_count || 0} · 考试 ${v.exam_count || 0} · 压力 ${PRESSURE_BAND_LABEL[v.pressure_band] || v.pressure_band || "—"}`;
  }
  if (f.forecast_type === "SCHEDULE_CONFLICT_RISK") {
    return `冲突 ${v.conflict_count || 0} · 可用窗口 ${v.available_window_count || 0} · 风险 ${RISK_BAND_LABEL[v.risk_band] || v.risk_band || "—"}`;
  }
  if (f.forecast_type === "GOAL_PROGRESS_OUTLOOK") {
    return `活跃目标 ${v.active_goal_count || 0} · 平均进度 ${Math.round(v.average_progress_percent || 0)}% · 趋势 ${OUTLOOK_BAND_LABEL[v.outlook_band] || v.outlook_band || "—"}`;
  }
  if (f.forecast_type === "ROUTINE_CONTINUITY") {
    return `学习次数 ${v.observed_session_count || 0} · 中位间隔 ${v.median_interval_hours || 0}h · 节律 ${CONTINUITY_BAND_LABEL[v.continuity_band] || v.continuity_band || "—"}`;
  }
  return "—";
}

function ForecastCard({ forecast }) {
  return (
    <article className="pred-card">
      <div className="pred-card__header">
        <span className="pred-card__type">{FORECAST_TYPE_LABEL[forecast.forecast_type] || forecast.forecast_type}</span>
        <QualityBadge quality={forecast.data_quality} />
      </div>
      <div className="pred-card__body">
        <div className="pred-metric">
          <span className="pred-metric__label">范围</span>
          <span className="pred-metric__value">{formatTime(forecast.horizon_start)} 至 {formatTime(forecast.horizon_end)}</span>
        </div>
        <div className="pred-metric">
          <span className="pred-metric__label">估计</span>
          <span className="pred-metric__value">{formatForecastValue(forecast)}</span>
        </div>
        {forecast.probability != null && (
          <div className="pred-metric">
            <span className="pred-metric__label">概率</span>
            <span className="pred-metric__value">{pct(forecast.probability)}</span>
          </div>
        )}
        <div className="pred-metric">
          <span className="pred-metric__label">置信度</span>
          <span className="pred-metric__value">{pct(forecast.confidence)}</span>
        </div>
      </div>
      {forecast.explanation_codes?.length > 0 && (
        <p className="pred-card__reasons">依据：{forecast.explanation_codes.join("、")}</p>
      )}
      {forecast.limitations?.length > 0 && (
        <p className="pred-card__limits">局限：{forecast.limitations.join("、")}</p>
      )}
      <p className="pred-card__version">估计器版本 {forecast.estimator_version}</p>
    </article>
  );
}

export default function PredictionPage() {
  const [horizonDays, setHorizonDays] = useState(7);
  const [simForm, setSimForm] = useState({
    intervention_type: "ALLOCATE_FOCUS_MINUTES",
    focus_minutes: 60,
    reduce_minutes_per_day: 30,
    source_category: "academic",
    plan_id: "",
    task_id: "",
    new_deadline: "",
    goal_id: "",
    new_target_date: "",
  });
  const [simResult, setSimResult] = useState(null);
  const [simLoading, setSimLoading] = useState(false);
  const [simError, setSimError] = useState(null);

  const forecasts = useAsync(
    () => api.getForecasts({ horizonDays, pageSize: 50 }),
    [horizonDays],
  );

  const groupedForecasts = useMemo(() => {
    const items = forecasts.data?.items || [];
    const byType = {};
    for (const f of items) {
      const t = f.forecast_type;
      if (!byType[t]) byType[t] = [];
      byType[t].push(f);
    }
    return byType;
  }, [forecasts.data]);

  const handleSimulate = useCallback(async () => {
    setSimLoading(true);
    setSimError(null);
    try {
      const intervention = buildIntervention(simForm);
      const result = await api.createSimulation({
        intervention,
        horizon_days: horizonDays,
        idempotency_key: `sim-${Date.now()}`,
      });
      setSimResult(result);
    } catch (err) {
      setSimError(err);
    } finally {
      setSimLoading(false);
    }
  }, [simForm, horizonDays]);

  return (
    <div className="pred-page">
      <header className="pred-page__header">
        <div className="pred-page__title-row">
          <div>
            <h1>趋势与方案比较</h1>
            <p className="pred-page__subtitle">基于校园记录的确定性预测与方案模拟，诚实表达不确定性</p>
          </div>
          <Link className="pred-back-link" to="/learning-state">返回我的状态</Link>
        </div>
        <div className="pred-horizon-select">
          <label>
            <span>预测范围（天）</span>
            <input type="number" min="1" max="30" value={horizonDays}
              onChange={(e) => setHorizonDays(Math.max(1, Math.min(30, parseInt(e.target.value) || 7)))} />
          </label>
        </div>
      </header>

      {forecasts.loading ? (
        <Spinner />
      ) : forecasts.error ? (
        <ErrorBar error={forecasts.error} onRetry={forecasts.reload} />
      ) : Object.keys(groupedForecasts).length === 0 ? (
        <EmptyState>暂无预测数据，请先授权校园记录</EmptyState>
      ) : (
        <>
          <section className="pred-section">
            <h2 className="pred-section__title">未来负载</h2>
            {(groupedForecasts.UPCOMING_WORKLOAD || []).length > 0 ? (
              <div className="pred-cards">
                {groupedForecasts.UPCOMING_WORKLOAD.map((f) => <ForecastCard key={f.forecast_id} forecast={f} />)}
              </div>
            ) : (
              <EmptyState>暂无未来负载数据</EmptyState>
            )}
          </section>

          <section className="pred-section">
            <h2 className="pred-section__title">截止风险</h2>
            {(groupedForecasts.DEADLINE_COMPLETION_RISK || []).length > 0 ? (
              <div className="pred-cards">
                {groupedForecasts.DEADLINE_COMPLETION_RISK.map((f) => <ForecastCard key={f.forecast_id} forecast={f} />)}
              </div>
            ) : (
              <EmptyState>暂无截止风险数据</EmptyState>
            )}
          </section>

          <section className="pred-section">
            <h2 className="pred-section__title">日程冲突</h2>
            {(groupedForecasts.SCHEDULE_CONFLICT_RISK || []).length > 0 ? (
              <div className="pred-cards">
                {groupedForecasts.SCHEDULE_CONFLICT_RISK.map((f) => <ForecastCard key={f.forecast_id} forecast={f} />)}
              </div>
            ) : (
              <EmptyState>暂无日程冲突数据</EmptyState>
            )}
          </section>

          <section className="pred-section">
            <h2 className="pred-section__title">目标进展</h2>
            {(groupedForecasts.GOAL_PROGRESS_OUTLOOK || []).length > 0 ? (
              <div className="pred-cards">
                {groupedForecasts.GOAL_PROGRESS_OUTLOOK.map((f) => <ForecastCard key={f.forecast_id} forecast={f} />)}
              </div>
            ) : (
              <EmptyState>暂无目标进展数据</EmptyState>
            )}
          </section>

          <section className="pred-section pred-section--sim">
            <h2 className="pred-section__title">方案 A/B 对比</h2>
            <p className="pred-section__desc">假设采取干预措施后的预测变化，不会修改实际状态或执行任何操作</p>
            <div className="pred-sim-form">
              <label>
                <span>干预类型</span>
                <select value={simForm.intervention_type}
                  onChange={(e) => setSimForm({ ...simForm, intervention_type: e.target.value })}>
                  {INTERVENTION_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </label>
              {simForm.intervention_type === "ALLOCATE_FOCUS_MINUTES" && (
                <label>
                  <span>专注分钟数</span>
                  <input type="number" min="0" max="480" value={simForm.focus_minutes}
                    onChange={(e) => setSimForm({ ...simForm, focus_minutes: parseInt(e.target.value) || 0 })} />
                </label>
              )}
              {simForm.intervention_type === "ACCEPT_PLAN" && (
                <label><span>计划 ID</span><input value={simForm.plan_id} onChange={(e) => setSimForm({ ...simForm, plan_id: e.target.value })} placeholder="粘贴计划 ID" /></label>
              )}
              {simForm.intervention_type === "REDUCE_DAILY_LOAD" && (
                <label>
                  <span>每日减少分钟数</span>
                  <input type="number" min="0" max="480" value={simForm.reduce_minutes_per_day}
                    onChange={(e) => setSimForm({ ...simForm, reduce_minutes_per_day: parseInt(e.target.value) || 0 })} />
                </label>
              )}
              {simForm.intervention_type === "RESCHEDULE_TASK" && (
                <>
                  <label><span>任务 ID</span><input value={simForm.task_id} onChange={(e) => setSimForm({ ...simForm, task_id: e.target.value })} /></label>
                  <label><span>新的截止时间</span><input type="datetime-local" value={simForm.new_deadline} onChange={(e) => setSimForm({ ...simForm, new_deadline: e.target.value })} /></label>
                </>
              )}
              {simForm.intervention_type === "PAUSE_DATA_SOURCE" && (
                <label>
                  <span>数据源</span>
                  <select value={simForm.source_category}
                    onChange={(e) => setSimForm({ ...simForm, source_category: e.target.value })}>
                    {DATA_SOURCE_CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </label>
              )}
              {simForm.intervention_type === "ADJUST_GOAL_DEADLINE" && (
                <>
                  <label><span>目标 ID</span><input value={simForm.goal_id} onChange={(e) => setSimForm({ ...simForm, goal_id: e.target.value })} /></label>
                  <label><span>新的目标日期</span><input type="datetime-local" value={simForm.new_target_date} onChange={(e) => setSimForm({ ...simForm, new_target_date: e.target.value })} /></label>
                </>
              )}
              <button onClick={handleSimulate} disabled={simLoading} className="pred-btn pred-btn--primary">
                {simLoading ? "模拟中…" : "运行模拟"}
              </button>
            </div>
            {simError && <ErrorBar error={simError} />}
            {simResult && <SimulationResult result={simResult} />}
          </section>
        </>
      )}
    </div>
  );
}

function buildIntervention(form) {
  if (form.intervention_type === "ALLOCATE_FOCUS_MINUTES") {
    return {
      intervention_type: "ALLOCATE_FOCUS_MINUTES",
      focus_minutes: form.focus_minutes,
    };
  }
  if (form.intervention_type === "REDUCE_DAILY_LOAD") {
    return {
      intervention_type: "REDUCE_DAILY_LOAD",
      reduce_minutes_per_day: form.reduce_minutes_per_day,
    };
  }
  if (form.intervention_type === "ACCEPT_PLAN") return { intervention_type: "ACCEPT_PLAN", plan_id: form.plan_id };
  if (form.intervention_type === "RESCHEDULE_TASK") return { intervention_type: "RESCHEDULE_TASK", task_id: form.task_id, new_deadline: new Date(form.new_deadline).toISOString() };
  if (form.intervention_type === "ADJUST_GOAL_DEADLINE") return { intervention_type: "ADJUST_GOAL_DEADLINE", goal_id: form.goal_id, new_target_date: new Date(form.new_target_date).toISOString() };
  if (form.intervention_type === "PAUSE_DATA_SOURCE") {
    return {
      intervention_type: "PAUSE_DATA_SOURCE",
      source_category: form.source_category,
    };
  }
  return { intervention_type: form.intervention_type };
}

function SimulationResult({ result }) {
  const changedForecasts = result.changed_forecasts || [];
  const changedStates = result.changed_state_estimates || [];
  const unchangedStates = result.unchanged_states || [];

  if (changedForecasts.length === 0 && changedStates.length === 0) {
    return <EmptyState>模拟未产生变化</EmptyState>;
  }

  return (
    <div className="pred-sim-result">
      <div className="pred-sim-summary">
        <div className="pred-metric">
          <span className="pred-metric__label">置信度</span>
          <span className="pred-metric__value">{pct(result.confidence)}</span>
        </div>
        <div className="pred-metric">
          <span className="pred-metric__label">数据质量</span>
          <span className="pred-metric__value"><QualityBadge quality={result.data_quality} /></span>
        </div>
        <div className="pred-metric">
          <span className="pred-metric__label">估计器版本</span>
          <span className="pred-metric__value">{result.estimator_version}</span>
        </div>
      </div>

      {changedForecasts.length > 0 && (
        <>
          <h3 className="pred-sim-subtitle">变化的预测</h3>
          <div className="pred-sim-table-wrap">
            <table className="pred-sim-table">
              <thead>
                <tr>
                  <th>预测类型</th>
                  <th>范围</th>
                  <th>基线概率</th>
                  <th>模拟后概率</th>
                  <th>方向</th>
                  <th>幅度</th>
                </tr>
              </thead>
              <tbody>
                {changedForecasts.map((d, i) => (
                  <>
                  <tr key={`${d.forecast_type}-${d.scope_type}-${d.scope_id}-${i}`}>
                    <td>{FORECAST_TYPE_LABEL[d.forecast_type] || d.forecast_type}</td>
                    <td>{d.scope_type}/{d.scope_id}</td>
                    <td>{d.baseline_probability != null ? pct(d.baseline_probability) : "—"}</td>
                    <td>{d.intervention_probability != null ? pct(d.intervention_probability) : "—"}</td>
                    <td>{DIRECTION_LABEL[d.direction] || d.direction}</td>
                    <td className={d.magnitude > 0 ? "pos" : d.magnitude < 0 ? "neg" : ""}>
                      {d.magnitude > 0 ? "+" : ""}{pct(d.magnitude)}
                    </td>
                  </tr>
                  <tr key={`${d.forecast_type}-${d.scope_id}-${i}-detail`} className="pred-sim-table__detail"><td colSpan="6">基线：{JSON.stringify(d.baseline_value || {})} · 模拟：{JSON.stringify(d.intervention_value || {})} · 差值：{JSON.stringify(d.delta || {})}</td></tr>
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {changedStates.length > 0 && (
        <>
          <h3 className="pred-sim-subtitle">变化的状态估计</h3>
          <div className="pred-sim-table-wrap">
            <table className="pred-sim-table">
              <thead>
                <tr>
                  <th>状态类型</th>
                  <th>范围</th>
                  <th>变化类型</th>
                  <th>基线质量</th>
                  <th>模拟后质量</th>
                </tr>
              </thead>
              <tbody>
                {changedStates.map((d, i) => (
                  <tr key={`${d.state_type}-${d.scope_type}-${d.scope_id}-${i}`}>
                    <td>{d.state_type}</td>
                    <td>{d.scope_type}/{d.scope_id}</td>
                    <td>{CHANGE_TYPE_LABEL[d.change_type] || d.change_type}</td>
                    <td>{d.baseline_data_quality || "—"}</td>
                    <td>{d.intervention_data_quality || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {result.assumptions?.length > 0 && (
        <p className="pred-sim-assumptions">假设：{result.assumptions.join("、")}</p>
      )}
      {result.limitations?.length > 0 && (
        <p className="pred-sim-limits">局限：{result.limitations.join("、")}</p>
      )}
      {unchangedStates.length > 0 && (
        <p className="pred-sim-unchanged">未变化状态数：{unchangedStates.length}</p>
      )}
    </div>
  );
}

const DIRECTION_LABEL = {
  increased: "增加",
  decreased: "减少",
  unchanged: "未变",
  unknown: "未知",
};

const CHANGE_TYPE_LABEL = {
  updated: "更新",
  added: "新增",
  removed: "移除",
  degraded: "降级",
};

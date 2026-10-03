import { FORECAST_TYPE_LABEL, RISK_BAND_LABEL, PRESSURE_BAND_LABEL, OUTLOOK_BAND_LABEL, CONTINUITY_BAND_LABEL } from "../../features/learnerState/forecastLabels.js";
import { useMemo } from 'react';
import { EmptyState, QualityBadge, ConfidenceBadge, formatTime, DATA_QUALITY_LABEL } from './shared.jsx';

const CHANGE_LABEL = {
  ADDED: "新增",
  UPDATED: "更新",
  REMOVED: "移除",
  UNCHANGED: "未变",
};

const STATE_TYPE_LABEL = {
  observed_learning_activity: "最近学习活动",
  task_workload: "任务负荷",
  deadline_exposure: "截止压力",
  course_participation: "课程参与",
  data_source_health: "数据源健康度",
  workload_pressure: "未来负载压力",
  schedule_conflict: "日程冲突",
  academic_progress: "学业进展",
  focus_rhythm: "专注节律",
  goal_progress: "目标进展",
  execution_consistency: "执行连续性",
  growth_momentum: "成长动量",
  preference_profile: "偏好画像",
};

function StateOverview({ snapshots, onViewEvidence, onMarkInaccurate }) {
  const cards = useMemo(() => {
    if (!snapshots?.items) return [];
    return snapshots.items.filter((s) => s.scope_type === "USER").slice(0, 5);
  }, [snapshots]);

  if (cards.length === 0) return <EmptyState text="暂时没有足够的状态数据" />;

  return (
    <section className="ls-section ls-overview" aria-label="今日状态总览">
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

function WorldSnapshotSection({ snapshots, onViewEvidence }) {
  const items = snapshots?.items || [];
  if (items.length === 0) return <EmptyState text="暂时没有世界状态数据" />;
  return (
    <section className="ls-section ls-overview" aria-label="校园生活世界状态">
      <div className="ls-section__heading"><h2>校园生活世界状态</h2><span className="ls-section__hint">基于已授权记录的可解释估计</span></div>
      <div className="ls-card-grid">
        {items.filter((s) => s.scope_type === "USER").map((snap) => (
          <article key={snap.snapshot_id} className="ls-state-card">
            <h3 className="ls-state-card__title">{STATE_TYPE_LABEL[snap.state_type] || snap.state_type}</h3>
            <p className="ls-state-card__value">{formatWorldValue(snap)}</p>
            <div className="ls-state-card__meta"><QualityBadge quality={snap.data_quality} /><ConfidenceBadge confidence={snap.confidence} /><span>{snap.evidence_count || 0} 条依据</span></div>
            <p className="ls-state-card__time">更新于 {formatTime(snap.as_of || snap.computed_at)}</p>
            <button className="ls-link-btn" onClick={() => onViewEvidence(snap)}>查看依据</button>
          </article>
        ))}
      </div>
    </section>
  );
}

function formatWorldValue(snap) {
  const value = snap.value || {};
  const entries = Object.entries(value).filter(([key]) => !["computed_at", "valid_until"].includes(key));
  if (!entries.length) return "—";
  return entries.slice(0, 2).map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`).join(" · ");
}

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

function ForecastSection({ forecasts }) {
  const items = forecasts?.items || [];

  const grouped = useMemo(() => {
    const byType = {};
    for (const f of items) {
      const t = f.forecast_type;
      if (!byType[t]) byType[t] = [];
      byType[t].push(f);
    }
    return byType;
  }, [items]);

  if (items.length === 0) return <EmptyState text="暂时没有未来预测数据" />;

  return (
    <section className="ls-section ls-forecasts" aria-label="未来压力与冲突">
      {Object.entries(grouped).map(([type, list]) => (
        <div key={type} className="ls-forecast__group">
          <h3 className="ls-forecast__type">{FORECAST_TYPE_LABEL[type] || type}</h3>
          <div className="ls-forecast__cards">
            {list.map((f) => (
              <article key={f.forecast_id} className="ls-forecast-card">
                <p className="ls-forecast-card__horizon">
                  {formatTime(f.horizon_start)} 至 {formatTime(f.horizon_end)}
                </p>
                <p className="ls-forecast-card__value">{formatForecastValue(f)}</p>
                <div className="ls-forecast-card__meta">
                  <QualityBadge quality={f.data_quality} />
                  <ConfidenceBadge confidence={f.confidence} />
                </div>
                {f.explanation_codes?.length > 0 && (
                  <p className="ls-forecast-card__reasons">{f.explanation_codes.join("、")}</p>
                )}
                {f.limitations?.length > 0 && (
                  <p className="ls-forecast-card__limits">局限：{f.limitations.join("、")}</p>
                )}
              </article>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
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

export { StateOverview, WorldSnapshotSection, StateTimeline, ForecastSection, formatForecastValue };

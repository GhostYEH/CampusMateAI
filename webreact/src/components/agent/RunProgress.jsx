import { useMemo } from "react";
import {
  runStatusLabel,
  runPhaseLabel,
  riskLevelLabel,
  isTerminalRunStatus,
  isCancellable,
} from "../../data/agentContracts.js";

/**
 * RunProgress — 显示 run 状态、阶段、进度条与事件摘要时间线。
 *
 * 可访问性：
 * - progress 条用 role="progressbar" + aria-valuenow/min/max。
 * - 状态用 aria-live="polite" 实时通告。
 * - 风险等级用文字 + 图标表达，不只靠颜色。
 *
 * 状态覆盖：loading / empty / offline / reconnecting / partial / approval / terminal。
 * 不展示 prompt、chain-of-thought、完整上下文或敏感 trace。
 */
export default function RunProgress({ run, events = [], streamStatus, streamStatusLabel, loading, error, onCancel, canCancel = true }) {
  const status = run?.status;
  const phase = run?.phase;
  const progress = run?.progress || {};
  const percent = typeof progress.percent === "number" ? progress.percent : null;
  const terminal = isTerminalRunStatus(status);
  const cancellable = canCancel && isCancellable(status);

  const recentEvents = useMemo(() => {
    const list = [...events].sort((a, b) => b.sequence - a.sequence);
    return list.slice(0, 6);
  }, [events]);

  const streamTone = useMemo(() => {
    if (streamStatus === "open") return "live";
    if (streamStatus === "reconnecting" || streamStatus === "connecting") return "reconnecting";
    if (streamStatus === "error" || streamStatus === "unauthorized") return "offline";
    return "idle";
  }, [streamStatus]);

  if (loading && !run) {
    return (
      <section className="agent-run-progress state-card loading-state" aria-busy="true">
        <span className="loading-orb" aria-hidden="true" />
        <p>正在加载任务状态…</p>
      </section>
    );
  }

  if (error && !run) {
    return (
      <section className="agent-run-progress state-card error-state" role="alert">
        <h3>任务状态加载失败</h3>
        <p>{error.message || error}</p>
      </section>
    );
  }

  if (!run) {
    return (
      <section className="agent-run-progress state-card empty-state">
        <p>暂无任务信息</p>
      </section>
    );
  }

  return (
    <section className="agent-run-progress" aria-labelledby="run-progress-title">
      <h3 id="run-progress-title">任务进度</h3>

      <div className="run-status-line" aria-live="polite">
        <span className={`run-status-badge tone-${status || "unknown"}`}>
          {runStatusLabel(status)}
        </span>
        {phase && <span className="run-phase-badge">{runPhaseLabel(phase)}</span>}
        {run?.risk_level && (
          <span className={`run-risk-badge risk-${run.risk_level}`}>
            风险：{riskLevelLabel(run.risk_level)}
          </span>
        )}
        <span className={`run-stream-badge stream-${streamTone}`}>{streamStatusLabel || "状态待确认"}</span>
      </div>

      {percent !== null && (
        <div
          className="run-progress-bar"
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="任务完成进度"
        >
          <div className="run-progress-fill" style={{ width: `${percent}%` }} />
          <span className="run-progress-text">{percent}%</span>
        </div>
      )}

      {error && (
        <p className="run-error-text" role="alert">
          {error.message || error}
        </p>
      )}

      {recentEvents.length > 0 && (
        <ol className="run-event-timeline" aria-label="近期事件">
          {recentEvents.map((evt) => (
            <li key={evt.id || evt.sequence} className={`run-event-item type-${evt.type || "unknown"}`}>
              <span className="run-event-seq">#{evt.sequence}</span>
              <span className="run-event-summary">{evt.summary || runStatusLabel(evt.status)}</span>
            </li>
          ))}
        </ol>
      )}

      {cancellable && !terminal && (
        <button className="button button-secondary run-cancel-btn" type="button" onClick={onCancel}>
          取消任务
        </button>
      )}
      {terminal && <p className="run-terminal-note">任务已结束</p>}
    </section>
  );
}
import { useMemo } from "react";
import { Icon } from "../../components/Icon.jsx";

function formatFocusMinutes(seconds) {
  const total = Math.max(0, Math.round(Number(seconds || 0) / 60));
  if (total < 60) return `${total} 分钟`;
  const hours = Math.floor(total / 60);
  const minutes = total % 60;
  return minutes ? `${hours} 小时 ${minutes} 分` : `${hours} 小时`;
}

function deadlineLabel(value, now) {
  if (!value) return "未设置截止";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "截止时间待确认";
  const current = new Date(now);
  const sameDay = date.toDateString() === current.toDateString();
  if (sameDay) return `今日截止 ${date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
  return date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

/**
 * First-viewport CampusMate composition over the fixed Sylva scene.
 *
 * Receives the shared home state plus the existing navigation callbacks and
 * renders only the business layer: the learning command (left), the today
 * rhythm + next-thing cards (right) and floating scene stats. All cards are
 * real entries that route through onNavigate / onOpenDue.
 */
export default function SylvaCampusOverview({ state, onNavigate, onOpenDue }) {
  const command = state.learningCommand;
  const pulse = command?.pulse || [];
  const nextItems = useMemo(() => state.filteredDueItems.slice(0, 2), [state.filteredDueItems]);
  const sceneStats = useMemo(() => [
    { key: "course", label: "今日课程", value: `${state.todayCourses.length} 门`, icon: "PhBookOpen" },
    { key: "todo", label: "待办事项", value: `${state.overviewMetrics.pendingCount} 项`, icon: "PhCheckSquare" },
    { key: "focus", label: "专注时长", value: formatFocusMinutes(state.todayFocusSeconds), icon: "PhTimer" },
  ], [state.todayCourses, state.overviewMetrics.pendingCount, state.todayFocusSeconds]);

  return (
    <section className="sylva-campus-overview" aria-label="CampusMate 今日学习概览" aria-busy={state.loading}>
      <div className="sylva-overview-layout">
        <div className="sylva-overview-copy">
          <span className="sylva-overview-eyebrow"><i />CampusMate · 今日行动</span>
          <h1 className="sylva-overview-title">{command?.headline || "给今天安排一段完整的学习时间"}</h1>
          <p className="sylva-overview-detail">{command?.detail || "当前没有紧迫的校园事项，选一个明确目标开始今天的学习。"}</p>
          <div className="sylva-overview-actions">
            <button className="sylva-overview-primary" onClick={() => onNavigate?.(command?.primaryAction?.path)}>
              {command?.primaryAction?.label || "开始专注"}
              <Icon name={command?.primaryAction?.icon || "PhPlay"} size={17} weight="bold" />
            </button>
            <button className="sylva-overview-secondary" onClick={() => onNavigate?.(command?.secondaryAction?.path)}>
              <Icon name={command?.secondaryAction?.icon || "PhSparkle"} size={16} />
              {command?.secondaryAction?.label || "整理本周计划"}
            </button>
          </div>
          <small className="sylva-overview-trust"><Icon name="PhShieldCheck" size={14} />建议来自你已同步的校园数据，执行仍由你决定</small>
        </div>

        <div className="sylva-overview-rail">
          <div className="sylva-scene-stats" aria-hidden="true">
            {sceneStats.map((stat) => (
              <span key={stat.key} className="sylva-scene-stat">
                <small>{stat.label}</small><strong>{stat.value}</strong>
              </span>
            ))}
          </div>

          <article className="sylva-rhythm-card" aria-labelledby="sylva-rhythm-title">
            <header className="sylva-card-head">
              <div><span>今日数据</span><h2 id="sylva-rhythm-title">今日学习节奏</h2></div>
              <small>课程、任务、考试与学习记录实时汇合</small>
            </header>
            <div className="sylva-rhythm-grid">
              {pulse.map((item) => (
                <button key={item.key} onClick={() => onNavigate?.(item.path)}>
                  <span className="sylva-rhythm-icon"><Icon name={item.icon} size={19} /></span>
                  <span className="sylva-rhythm-copy"><small>{item.label}</small><strong>{item.value}</strong></span>
                  <Icon name="PhArrowUpRight" className="sylva-rhythm-arrow" size={14} />
                </button>
              ))}
            </div>
          </article>

          <article className="sylva-next-card" aria-labelledby="sylva-next-title">
            <header className="sylva-card-head">
              <div><span>优先处理</span><h2 id="sylva-next-title">下一件事</h2></div>
              <button className="sylva-card-more" onClick={() => onNavigate?.("/tasks")}>全部待办<Icon name="PhArrowRight" size={14} /></button>
            </header>
            {nextItems.length ? (
              <div className="sylva-next-list">
                {nextItems.map((item) => (
                  <button key={`${item.kind}-${item.id}`} onClick={() => onOpenDue?.(item)}>
                    <span className={`sylva-next-kind ${item.tone || ""}`}>{item.kind}</span>
                    <span className="sylva-next-copy"><strong>{item.title}</strong><time>{deadlineLabel(item.due, state.now)}</time></span>
                    <Icon name="PhCaretRight" size={14} />
                  </button>
                ))}
              </div>
            ) : (
              <div className="sylva-next-empty">
                <Icon name="PhCheckCircle" size={24} />
                <span>没有临近截止事项</span>
                <button onClick={() => onNavigate?.("/tasks")}>进入待办与作业</button>
              </div>
            )}
          </article>
        </div>
      </div>
    </section>
  );
}

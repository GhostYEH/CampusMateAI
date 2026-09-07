import { useMemo } from "react";
import { Icon } from "../../components/Icon.jsx";
import SylvaPriorityCard from "./SylvaPriorityCard.jsx";
import SylvaScheduleCard from "./SylvaScheduleCard.jsx";

function formatFocusMinutes(seconds) {
  const total = Math.max(0, Math.round(Number(seconds || 0) / 60));
  if (total < 60) return `${total} 分钟`;
  const hours = Math.floor(total / 60);
  const minutes = total % 60;
  return minutes ? `${hours} 小时 ${minutes} 分` : `${hours} 小时`;
}

/**
 * First-viewport CampusMate workbench over the fixed Sylva scene.
 *
 * Three columns: priorities (left), the today action narrative plus real
 * metrics (center), and the compact today schedule (right). Everything is
 * wired to existing state and callbacks — no fake data.
 */
export default function SylvaCampusOverview({ state, onNavigate, onOpenDue }) {
  const command = state.learningCommand;
  const sceneStats = useMemo(() => [
    { key: "course", label: "今日课程", value: `${state.todayCourses.length} 门`, icon: "PhBookOpen" },
    { key: "todo", label: "待办事项", value: `${state.overviewMetrics.pendingCount} 项`, icon: "PhCheckSquare" },
    { key: "focus", label: "专注时长", value: formatFocusMinutes(state.todayFocusSeconds), icon: "PhTimer" },
  ], [state.todayCourses, state.overviewMetrics.pendingCount, state.todayFocusSeconds]);

  return (
    <section className="sylva-campus-overview" aria-label="CampusMate 今日学习工作台" aria-busy={state.loading}>
      <div className="sylva-overview-layout">
        <SylvaPriorityCard state={state} onNavigate={onNavigate} onOpenDue={onOpenDue} />

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
          <div className="sylva-scene-stats" aria-label="今日学习指标">
            {sceneStats.map((stat) => (
              <span key={stat.key} className="sylva-scene-stat">
                <small>{stat.label}</small><strong>{stat.value}</strong>
              </span>
            ))}
          </div>
          <small className="sylva-overview-trust"><Icon name="PhShieldCheck" size={14} />建议来自你已同步的校园数据，执行仍由你决定</small>
        </div>

        <SylvaScheduleCard state={state} onNavigate={onNavigate} />
      </div>
    </section>
  );
}

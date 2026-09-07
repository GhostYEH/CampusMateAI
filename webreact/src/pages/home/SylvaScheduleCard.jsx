import { useMemo } from "react";
import { Icon } from "../../components/Icon.jsx";
import { scheduleWeekOf, sectionLabel } from "./homeTime.js";

/**
 * Compact today-schedule card for the right side of the first viewport.
 * Shows the current week strip with today highlighted and today's
 * courses; the full schedule lives on the academic page.
 */
export default function SylvaScheduleCard({ state, onNavigate }) {
  const week = useMemo(() => scheduleWeekOf(state.now), [state.now]);
  const todayItems = state.todayCourses;

  return (
    <article className="sylva-schedule-card" aria-labelledby="sylva-schedule-title">
      <header className="sylva-card-head">
        <div><span>今日课程表</span><h2 id="sylva-schedule-title">今天有 {todayItems.length} 门课</h2></div>
        <button className="sylva-card-link" onClick={() => onNavigate?.("/profile/academic")}>查看课表<Icon name="PhArrowRight" size={14} /></button>
      </header>

      <div className="sylva-schedule-week" aria-hidden="true">
        <small>{week.label}</small>
        <div className="sylva-schedule-days">
          {week.days.map((day) => (
            <span key={day.name} className={day.isToday ? "today" : ""}><b>{day.name}</b>{day.date}</span>
          ))}
        </div>
      </div>

      {state.scheduleLoading ? (
        <div className="sylva-schedule-loading" aria-label="正在加载课程表"><i /><i /><i /></div>
      ) : todayItems.length ? (
        <div className="sylva-schedule-today" aria-label="今日课程">
          {todayItems.map((item) => (
            <button key={item.id || `${item.course_name}-${item.start_section}-${item.location}`} onClick={() => onNavigate?.("/profile/academic")}>
              <span className="sylva-schedule-dot" aria-hidden="true" />
              <span className="sylva-schedule-copy">
                <strong>{item.course_name || "未命名课程"}</strong>
                <small>{sectionLabel(item)}{item.location ? ` · ${item.location}` : ""}</small>
              </span>
              <Icon name="PhCaretRight" size={14} />
            </button>
          ))}
        </div>
      ) : (
        <div className="sylva-schedule-empty">
          <Icon name="PhCalendarBlank" size={22} />
          <span>今天没有排课</span>
          <button onClick={() => onNavigate?.("/profile/academic")}>管理我的课表</button>
        </div>
      )}
    </article>
  );
}

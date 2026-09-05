import { useMemo } from "react";
import { Icon } from "../../components/Icon.jsx";
import { groupScheduleByWeekday } from "../../data/scheduleModel.js";

const weekdayNames = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

function sectionText(item) {
  const start = item.start_section;
  const end = item.end_section ?? start;
  if (!start) return "时间待定";
  return start === end ? `第 ${start} 节` : `第 ${start}-${end} 节`;
}

export default function HomeSchedulePanel({ items, loading, onOpenAcademic }) {
  const todayWeekday = new Date().getDay() || 7;
  const weeklySchedule = useMemo(() => groupScheduleByWeekday(items), [items]);
  const hasSchedule = weeklySchedule.some((dayItems) => dayItems.length);
  const referenceScheduleWeek = useMemo(() => {
    const current = new Date();
    const mondayOffset = (current.getDay() + 6) % 7;
    const start = new Date(current);
    start.setDate(current.getDate() - mondayOffset);
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    const dateText = (value) => `${value.getMonth() + 1}月${value.getDate()}日`;
    return {
      label: `${dateText(start)} – ${dateText(end)}`,
      days: Array.from({ length: 7 }, (_, index) => {
        const date = new Date(start);
        date.setDate(start.getDate() + index);
        return { name: weekdayNames[index].replace("周", ""), date: date.getDate(), isToday: index + 1 === todayWeekday };
      }),
    };
  }, [todayWeekday]);

  return (
    <article className="student-home-panel course-panel">
      <div className="home-panel-head">
        <h2><Icon name="PhCalendarBlank" size={19} />课程表</h2>
        <button onClick={() => onOpenAcademic?.()}>查看课表<Icon name="PhArrowRight" size={15} /></button>
      </div>
      {loading ? (
        <div className="home-schedule-loading" aria-label="正在加载课程表"><i /><i /><i /></div>
      ) : hasSchedule ? (
        <div className="home-schedule-grid" aria-label="课程表">
          {weeklySchedule.map((dayItems, index) => (
            <section key={weekdayNames[index]} className={index + 1 === todayWeekday ? "today" : ""}>
              <header><strong>{weekdayNames[index]}</strong>{index + 1 === todayWeekday && <small>今日</small>}</header>
              {dayItems.map((item) => (
                <button key={item.id || `${item.course_name}-${item.start_section}-${item.location}`} onClick={() => onOpenAcademic?.()}>
                  <strong>{item.course_name || "未命名课程"}</strong>
                  <small>{sectionText(item)}{item.location ? ` · ${item.location}` : ""}</small>
                </button>
              ))}
              {!dayItems.length && <span className="home-schedule-empty">—</span>}
            </section>
          ))}
        </div>
      ) : (
        <div className="compact-empty home-reference-schedule-empty" role="status">
          <div className="reference-schedule-week">
            <strong>{referenceScheduleWeek.label}</strong><small>本周</small>
            <span>{referenceScheduleWeek.days.map((day) => (
              <i key={day.name} className={day.isToday ? "today" : ""}><b>{day.name}</b>{day.date}</i>
            ))}</span>
          </div>
          <div className="schedule-empty-art" aria-hidden="true">
            <svg viewBox="0 0 220 150" role="presentation">
              <defs>
                <linearGradient id="schedule-paper" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0" stopColor="#ffffff" />
                  <stop offset="1" stopColor="#dce7ff" />
                </linearGradient>
                <linearGradient id="schedule-cover" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0" stopColor="#7e9eff" />
                  <stop offset="1" stopColor="#4d6cf0" />
                </linearGradient>
                <filter id="schedule-soft-shadow" x="-20%" y="-20%" width="140%" height="150%">
                  <feDropShadow dx="0" dy="8" stdDeviation="7" floodColor="#718ad5" floodOpacity=".18" />
                </filter>
              </defs>
              <ellipse cx="110" cy="133" rx="70" ry="10" fill="#e9efff" />
              <circle cx="42" cy="46" r="18" fill="#edf2ff" />
              <circle cx="181" cy="31" r="10" fill="#f0f4ff" />
              <g filter="url(#schedule-soft-shadow)" transform="rotate(-4 110 78)">
                <rect x="57" y="38" width="108" height="86" rx="12" fill="url(#schedule-paper)" stroke="#c9d7ff" strokeWidth="2" />
                <rect x="57" y="38" width="108" height="25" rx="12" fill="url(#schedule-cover)" />
                <path d="M57 51h108" stroke="#6f8bf3" strokeWidth="2" />
                <path d="M76 29v18M146 29v18" stroke="#4e6cf0" strokeWidth="7" strokeLinecap="round" />
                <path d="M78 76h27M78 91h48M78 106h33" stroke="#bdd0ff" strokeWidth="6" strokeLinecap="round" />
                <rect x="130" y="74" width="20" height="20" rx="6" fill="#e4ebff" />
                <path d="m136 84 5 5 9-11" fill="none" stroke="#5676ee" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
              </g>
            </svg>
          </div>
          <strong>暂无课程安排</strong><span>暂无课程安排，假期或未选课？</span>
          <button className="reference-empty-action" onClick={() => onOpenAcademic?.()}>管理我的课表</button>
        </div>
      )}
      {hasSchedule && (
        <button className="panel-footer blue" onClick={() => onOpenAcademic?.()}>管理教务课表<Icon name="PhArrowRight" size={15} /></button>
      )}
    </article>
  );
}
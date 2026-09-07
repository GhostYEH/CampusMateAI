import { useMemo } from "react";

// 移植自 Summer Checkin 的 calendar/heatmap.tsx：
// 年度热力图（周列 × 星期行），已打卡格子用主题色混合透明度显示
function checkedColor(checked, level) {
  if (!checked) return { cls: "hm-cell--off" };
  const opacity = level === 1 ? 0.22 : level === 2 ? 0.45 : level === 3 ? 0.7 : 1;
  return {
    cls: "",
    style: {
      backgroundColor: `color-mix(in oklab, var(--theme-primary) ${Math.round(opacity * 100)}%, transparent)`,
    },
  };
}

export function Heatmap({ data, year, compact = false }) {
  const weeks = useMemo(() => {
    const result = [];
    let currentWeek = [];
    for (const day of data) {
      const d = new Date(`${day.date}T00:00:00`);
      const dayOfWeek = d.getDay();
      currentWeek.push({ ...day, dayOfWeek });
      if (dayOfWeek === 6 || day.date === data[data.length - 1].date) {
        result.push(currentWeek);
        currentWeek = [];
      }
    }
    return result;
  }, [data]);

  const cellSize = compact ? 12 : 13;
  const gap = 3;

  const months = useMemo(() => {
    const m = [];
    weeks.forEach((week, i) => {
      if (week.length > 0) {
        const d = new Date(`${week[0].date}T00:00:00`);
        const month = d.toLocaleDateString("zh-CN", { month: "short" });
        const last = m[m.length - 1];
        if (!last || last.label !== month) m.push({ label: month, index: i });
      }
    });
    return m;
  }, [weeks]);

  const step = cellSize + gap;

  return (
    <div className="hm">
      {!compact && (
        <div className="hm-months" style={{ marginLeft: 28 }}>
          {months.map((m, i) => (
            <div key={`${m.label}-${i}`} className="hm-label" style={{ marginLeft: i === 0 ? m.index * step : (m.index - months[i - 1].index) * step }}>{m.label}</div>
          ))}
        </div>
      )}

      <div className="hm-body" style={{ gap }}>
        {!compact && (
          <div className="hm-days" style={{ gap, paddingTop: 2 }}>
            {["日", "", "二", "", "四", "", "六"].map((label, i) => (
              <div key={i} className="hm-label" style={{ width: cellSize, height: cellSize, lineHeight: `${cellSize}px` }}>{label}</div>
            ))}
          </div>
        )}

        <div className="hm-groups" style={{ gap }}>
          {weeks.map((week, wi) => (
            <div key={wi} className="hm-week" style={{ gap }}>
              {Array.from({ length: 7 }).map((_, di) => {
                const day = week.find((d) => d.dayOfWeek === di);
                if (!day || !day.date) {
                  return <div key={`${wi}-${di}`} className="hm-cell hm-cell--off" style={{ width: cellSize, height: cellSize }} />;
                }
                const { cls, style } = checkedColor(day.checked);
                return (
                  <div
                    key={`${wi}-${di}`}
                    title={`${day.date}${day.checked ? " · 已来访" : ""}`}
                    className={`hm-cell ${cls}`}
                    style={{ width: cellSize, height: cellSize, ...style }}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {!compact && (
        <div className="hm-legend">
          <span>少</span>
          <div className="hm-cell hm-cell--off" />
          <div className="hm-cell" style={checkedColor(true, 1).style} />
          <div className="hm-cell" style={checkedColor(true, 2).style} />
          <div className="hm-cell" style={checkedColor(true, 3).style} />
          <span>多</span>
        </div>
      )}
    </div>
  );
}
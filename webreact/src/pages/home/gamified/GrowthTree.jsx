import { useMemo } from "react";
import { Icon } from "../../../components/Icon.jsx";

const weekLabels = ["一", "二", "三", "四", "五", "六", "日"];

export default function GrowthTree({ summary }) {
  const branches = useMemo(() => [
    { label: "专注能力", value: summary.weekFocusMinutes, unit: "min", icon: "PhTimer", progress: Math.min(100, summary.weekFocusMinutes / 3), tone: "cyan" },
    { label: "任务执行", value: summary.weekCompletedTasks, unit: "项", icon: "PhCheckCircle", progress: Math.min(100, summary.weekCompletedTasks * 10), tone: "violet" },
    { label: "持续成长", value: summary.streak, unit: "天", icon: "PhFire", progress: Math.min(100, summary.streak / 7 * 100), tone: "gold" },
  ], [summary.weekFocusMinutes, summary.weekCompletedTasks, summary.streak]);
  const chartMax = Math.max(20, ...summary.weekXpSeries);
  const chartPoints = summary.weekXpSeries
    .map((value, index) => `${index * 16.6667},${44 - (value / chartMax) * 38}`)
    .join(" ");

  return (
    <section className="rpg-growth-tree rpg-hud-panel" aria-labelledby="growth-tree-title">
      <header className="rpg-panel-header">
        <div><span className="rpg-kicker">GROWTH TRACK · THIS WEEK</span><h2 id="growth-tree-title">成长轨迹</h2></div>
        <span className="rpg-week-xp">本周 <strong>+{summary.weekXp} XP</strong></span>
      </header>
      <div className="rpg-growth-trunk">
        <div className="rpg-growth-level"><span>LV</span><strong>{summary.level}</strong><small>{summary.title}</small></div>
        <div className="rpg-growth-branches">
          {branches.map((branch) => (
            <article key={branch.label} className={branch.tone}>
              <span><Icon name={branch.icon} size={20} weight="duotone" /></span>
              <div><small>{branch.label}</small><strong>{branch.value} <em>{branch.unit}</em></strong></div>
              <i role="progressbar" aria-label={`${branch.label}本周记录`} aria-valuenow={branch.value}><b style={{ width: `${branch.progress}%` }} /></i>
            </article>
          ))}
        </div>
      </div>
      <div className="rpg-growth-chart" aria-label="本周每日真实经验成长曲线">
        <svg viewBox="0 0 100 48" preserveAspectRatio="none" aria-hidden="true">
          <defs><linearGradient id="rpg-growth-line" x1="0" x2="1"><stop stopColor="#43d9ff" /><stop offset="1" stopColor="#9c6cff" /></linearGradient></defs>
          <polyline points={chartPoints} fill="none" stroke="url(#rpg-growth-line)" strokeWidth="1.35" vectorEffect="non-scaling-stroke" />
        </svg>
        <div>{weekLabels.map((label, index) => (
          <span key={label}><i style={{ height: `${Math.max(5, summary.weekXpSeries[index] / chartMax * 100)}%` }} /><small>周{label}</small></span>
        ))}</div>
      </div>
    </section>
  );
}
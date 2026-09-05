import { useMemo } from "react";
import { Icon } from "../../../components/Icon.jsx";

export default function DailySignIn({ summary, onNavigate }) {
  const currentIndex = Math.min(6, Math.max(0, summary.streak));
  const days = useMemo(() => Array.from({ length: 7 }, (_, index) => ({
    day: index + 1,
    signed: index < Math.min(summary.streak, 7),
    current: index === currentIndex && summary.streak < 7,
    reward: index === 6 ? "宝箱" : index === 3 ? "+20 XP" : "+10 XP",
  })), [summary.streak, currentIndex]);

  const actionLabel = summary.dailyAdventure.completed < summary.dailyAdventure.total ? "继续今日成长" : "查看成长记录";
  const actionRoute = summary.dailyAdventure.completed < summary.dailyAdventure.total ? "/study" : "/profile";

  return (
    <section className="rpg-daily-signin rpg-hud-panel" aria-labelledby="daily-signin-title">
      <header className="rpg-panel-header">
        <div><span className="rpg-kicker">DAILY SIGN-IN · STREAK</span><h2 id="daily-signin-title">每日签到</h2><p>学习与任务记录会自动点亮签到</p></div>
        <span className="rpg-signin-streak"><Icon name="PhFire" size={15} weight="fill" />{summary.streak} 天</span>
      </header>
      <div className="rpg-signin-route">
        {days.map((day) => (
          <div key={day.day} className={`${day.signed ? "signed" : ""} ${day.current ? "current" : ""} ${day.day === 7 ? "jackpot" : ""}`}>
            <span><Icon name={day.day === 7 ? "PhTreasureChest" : day.signed ? "PhCheck" : "PhStar"} size={18} weight="fill" /></span>
            <strong>第 {day.day} 天</strong>
            <small>{day.reward}</small>
          </div>
        ))}
      </div>
      <button className="rpg-signin-action" onClick={() => onNavigate?.(actionRoute)}>
        {actionLabel}<Icon name="PhArrowRight" size={15} />
      </button>
    </section>
  );
}
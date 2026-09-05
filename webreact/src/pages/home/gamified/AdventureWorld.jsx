import { useMemo } from "react";
import { Icon } from "../../../components/Icon.jsx";
import WorldMapNavigation from "./WorldMapNavigation.jsx";

export default function AdventureWorld({ summary, nextExam, now, onNavigate }) {
  const examDays = useMemo(() => {
    if (!nextExam?.exam_date) return null;
    const target = new Date(`${nextExam.exam_date}T${nextExam.start_time || "23:59"}`).getTime();
    const current = new Date(now);
    current.setHours(0, 0, 0, 0);
    return Number.isFinite(target) ? Math.ceil((target - current.getTime()) / 86400000) : null;
  }, [nextExam, now]);
  const isBossChallenge = examDays !== null && examDays >= 0 && examDays <= 7;
  const progressPercent = Math.round((summary.dailyAdventure.completed / summary.dailyAdventure.total) * 100);
  const nextRoute = summary.dailyAdventure.completedTasks === 0 ? "/tasks" : "/study";
  const missionTitle = isBossChallenge
    ? `${nextExam.course_name || "考试"} · 期末挑战`
    : summary.dailyAdventure.completedTasks === 0 ? "完成今日首个任务" : "完成 60 分钟专注训练";
  const missionMeta = isBossChallenge
    ? `距离挑战 ${examDays === 0 ? "不到 1" : examDays} 天`
    : `${summary.dailyAdventure.completed} / ${summary.dailyAdventure.total} 个成长节点已点亮`;
  const rewardText = summary.dailyAdventure.nextReward
    ? `+${summary.dailyAdventure.nextReward.xp} XP`
    : "今日路线完成";

  return (
    <section className="rpg-adventure-world" aria-labelledby="adventure-title">
      <div className="rpg-adventure-sky" aria-hidden="true"><i /><i /><i /><i /><i /></div>
      <div className="rpg-world-copy">
        <span className="rpg-world-status"><i />CAMPUS WORLD · ONLINE</span>
        {isBossChallenge && <span className="rpg-boss-label">BOSS CHALLENGE</span>}
        <h2 id="adventure-title">今日校园冒险</h2>
        <p>完成当前任务，解锁新的校园区域，获得真实成长经验。</p>
        <button className="rpg-current-mission" onClick={() => onNavigate?.(nextRoute)}>
          <span><Icon name={isBossChallenge ? "PhExam" : "PhFlagCheckered"} size={25} weight="fill" /></span>
          <span><small>当前任务 · CURRENT QUEST</small><strong>{missionTitle}</strong><em>{missionMeta}</em></span>
          <b>{rewardText}</b>
          <Icon name="PhArrowUpRight" size={17} />
        </button>
        <div className="rpg-world-actions">
          <button onClick={() => onNavigate?.(nextRoute)}>开始冒险<Icon name="PhPlay" size={17} weight="fill" /></button>
          <span><small>今日已获得</small><strong>+{summary.dailyAdventure.todayXp} XP</strong></span>
        </div>
      </div>
      <aside className="rpg-world-route" aria-label="今日冒险路线">
        <header><span>今日路线</span><strong>{summary.dailyAdventure.completed} / {summary.dailyAdventure.total}</strong></header>
        <div className="rpg-route-line"><i style={{ height: `${progressPercent}%` }} /></div>
        <div className={`rpg-route-node ${summary.dailyAdventure.completedTasks > 0 ? "complete" : ""}`}>
          <span><Icon name={summary.dailyAdventure.completedTasks > 0 ? "PhCheck" : "PhListChecks"} size={18} weight="bold" /></span>
          <div><small>QUEST NODE 01</small><strong>任务推进</strong><em>{summary.dailyAdventure.completedTasks} 项完成</em></div>
        </div>
        <div className={`rpg-route-node ${summary.dailyAdventure.focusMinutes >= 60 ? "complete" : ""}`}>
          <span><Icon name={summary.dailyAdventure.focusMinutes >= 60 ? "PhCheck" : "PhTimer"} size={18} weight="bold" /></span>
          <div><small>QUEST NODE 02</small><strong>专注训练</strong><em>{Math.min(summary.dailyAdventure.focusMinutes, 60)} / 60 min</em></div>
        </div>
        <div className={`rpg-route-reward ${!summary.dailyAdventure.nextReward ? "complete" : ""}`}>
          <Icon name="PhSparkle" size={18} weight="fill" />
          <span><small>NEXT REWARD</small><strong>{rewardText}</strong></span>
        </div>
      </aside>
      <section className="rpg-digital-human-stage" aria-label="CampusMate AI 数字人伙伴">
        <div className="rpg-human-halo" aria-hidden="true" />
        <img className="rpg-human-fallback" src="/digital-human/fallback-avatar.png" alt="CampusMate CPM 数字人伙伴" />
        <div className="rpg-human-dialogue">
          <span>AI COMPANION · ONLINE</span>
          <strong>嗨，今天也一起探索校园吧。</strong>
          <button onClick={() => onNavigate?.("/counselor")}>与我对话<Icon name="PhChatCircleText" size={15} /></button>
        </div>
      </section>
      <WorldMapNavigation onNavigate={onNavigate} />
    </section>
  );
}
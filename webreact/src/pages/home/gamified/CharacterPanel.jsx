import { useMemo } from "react";
import { Icon } from "../../../components/Icon.jsx";

export default function CharacterPanel({ user, summary }) {
  const progressPercent = useMemo(() => Math.round(summary.progress * 100), [summary.progress]);
  const identityDetail = user?.detail
    || [user?.college, user?.major].filter(Boolean).join(" · ")
    || "CampusMateAI 冒险者档案";

  return (
    <section className="rpg-character-panel" aria-labelledby="character-name">
      <div className="rpg-character-avatar">
        <img src={user?.avatar_url || "/assets/generated/home-reference-student-avatar.png"} alt="" />
        <span>LV.{summary.level}</span>
      </div>
      <div className="rpg-character-identity">
        <span className="rpg-kicker"><Icon name="PhIdentificationCard" size={13} />角色档案 · CHARACTER</span>
        <div className="rpg-character-name-row">
          <h1 id="character-name">{user?.name || user?.username || "同学"}</h1>
          <span>{summary.title}</span>
        </div>
        <p>{identityDetail}</p>
      </div>
      <div className="rpg-character-xp">
        <div><span>成长经验</span><strong>{summary.currentLevelXp} <small>/ {summary.nextLevelXp} XP</small></strong></div>
        <div className="rpg-xp-track" role="progressbar" aria-label="成长经验" aria-valuenow={summary.currentLevelXp} aria-valuemin="0" aria-valuemax={summary.nextLevelXp}>
          <i style={{ width: `${progressPercent}%` }} />
          <b style={{ left: `${progressPercent}%` }} />
        </div>
        <small>距离 LV.{summary.level + 1} 还需 {summary.nextLevelXp - summary.currentLevelXp} XP</small>
      </div>
      <dl className="rpg-character-vitals">
        <div><dt><Icon name="PhFire" size={15} weight="fill" />连续学习</dt><dd>{summary.streak}<small> 天</small></dd></div>
        <div><dt><Icon name="PhSparkle" size={15} weight="fill" />累计经验</dt><dd>{summary.totalXp}<small> XP</small></dd></div>
      </dl>
    </section>
  );
}
import { useMemo, useState, useRef, useEffect } from "react";
import { Icon } from "../../../components/Icon.jsx";

function progress(achievement) {
  return Math.min(100, Math.round((achievement.current / achievement.target) * 100));
}

function unlockedDate(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "" : date.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
}

export default function AchievementHall({ summary }) {
  const [selected, setSelected] = useState(null);
  const closeButtonRef = useRef(null);
  const achievements = useMemo(() => summary.achievementCollection.slice(0, 5), [summary.achievementCollection]);
  const unlockedCount = achievements.filter((item) => item.unlocked).length;

  useEffect(() => {
    if (selected && closeButtonRef.current) closeButtonRef.current.focus();
  }, [selected]);

  useEffect(() => {
    if (!selected) return;
    function onEsc(e) { if (e.key === "Escape") setSelected(null); }
    document.addEventListener("keydown", onEsc);
    return () => document.removeEventListener("keydown", onEsc);
  }, [selected]);

  return (
    <>
      <section className="rpg-achievement-hall rpg-hud-panel" aria-labelledby="achievement-hall-title">
        <header className="rpg-panel-header">
          <div><span className="rpg-kicker">ACHIEVEMENT HALL · COLLECTION</span><h2 id="achievement-hall-title">荣誉大厅</h2><p>最近获得与下一里程碑</p></div>
          <span className="rpg-hall-count"><strong>{unlockedCount}</strong> / {achievements.length} 已点亮</span>
        </header>
        <div className="rpg-trophy-case">
          {achievements.map((achievement) => (
            <button key={achievement.id} className={!achievement.unlocked ? "locked" : ""} onClick={() => setSelected(achievement)}>
              <span className="rpg-trophy-medal"><Icon name={achievement.unlocked ? achievement.icon : "PhLock"} size={25} weight="duotone" /></span>
              <strong>{achievement.title}</strong>
              {achievement.unlocked ? (
                <small>{unlockedDate(achievement.unlockedAt)} 获得</small>
              ) : (
                <small>{achievement.current} / {achievement.target} {achievement.unit}</small>
              )}
              {!achievement.unlocked && <i><b style={{ width: `${progress(achievement)}%` }} /></i>}
              <em>{achievement.unlocked ? "UNLOCKED" : "LOCKED"}</em>
            </button>
          ))}
        </div>
      </section>
      {selected && (
        <div className="rpg-dialog-backdrop" onClick={(e) => e.target === e.currentTarget && setSelected(null)}>
          <section className="rpg-achievement-dialog" role="dialog" aria-modal="true" aria-labelledby="achievement-dialog-title">
            <button ref={closeButtonRef} className="rpg-dialog-close" aria-label="关闭成就详情" onClick={() => setSelected(null)}><Icon name="PhX" size={18} /></button>
            <span className={`rpg-dialog-medal ${!selected.unlocked ? "locked" : ""}`}><Icon name={selected.unlocked ? selected.icon : "PhLock"} size={36} weight="duotone" /></span>
            <span className="rpg-kicker">{selected.unlocked ? "ACHIEVEMENT UNLOCKED" : "NEXT MILESTONE"}</span>
            <h2 id="achievement-dialog-title">{selected.title}</h2>
            <p>{selected.description}</p>
            {selected.unlocked ? (
              <small>获得于 {unlockedDate(selected.unlockedAt)}</small>
            ) : (
              <div className="rpg-dialog-progress"><span><i style={{ width: `${progress(selected)}%` }} /></span><strong>{selected.current} / {selected.target} {selected.unit}</strong></div>
            )}
          </section>
        </div>
      )}
    </>
  );
}
import { useMemo } from "react";
import { Icon } from "../../../components/Icon.jsx";

const sourceLabels = { course: "COURSE QUEST", assignment: "DEADLINE QUEST", "personal-task": "SIDE OBJECTIVE", exam: "BOSS CHALLENGE" };

function metaText(quest) {
  if (!["assignment", "personal-task"].includes(quest.sourceType)) return quest.meta;
  const date = new Date(quest.meta);
  return Number.isNaN(date.valueOf()) ? quest.meta : date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function questReward(quest) {
  if (quest.sourceType === "personal-task") return "+20 XP";
  return ({ course: "课程节点", assignment: "截止提醒", exam: "挑战日程" }[quest.sourceType] || "校园事项");
}

export default function QuestLog({ quests, onNavigate }) {
  const primaryQuest = quests[0] || null;
  const supportingQuests = useMemo(() => quests.slice(1, 5), [quests]);

  return (
    <section className="rpg-quest-log rpg-hud-panel" aria-labelledby="quest-log-title">
      <header className="rpg-panel-header">
        <div><span className="rpg-kicker">QUEST LOG · ACTIVE</span><h2 id="quest-log-title">任务日志</h2></div>
        <button onClick={() => onNavigate?.("/tasks")}>全部任务<Icon name="PhArrowRight" size={15} /></button>
      </header>
      {primaryQuest && (
        <button className="rpg-main-quest" onClick={() => onNavigate?.(primaryQuest.route)}>
          <span className="rpg-quest-rank">MAIN</span>
          <span className="rpg-main-quest-icon"><Icon name={primaryQuest.icon} size={29} weight="duotone" /></span>
          <span className="rpg-main-quest-copy">
            <small>{sourceLabels[primaryQuest.sourceType] || "CAMPUS QUEST"}</small>
            <strong>{primaryQuest.title}</strong>
            <em>{metaText(primaryQuest)}</em>
          </span>
          <span className="rpg-quest-state"><i />进行中</span>
          <span className="rpg-quest-reward"><small>QUEST SIGNAL</small><strong>{questReward(primaryQuest)}</strong></span>
          <span className="rpg-main-quest-action">进入任务<Icon name="PhArrowUpRight" size={15} /></span>
        </button>
      )}
      {supportingQuests.length ? (
        <div className="rpg-supporting-quests" aria-label="支线任务">
          <header><span>SIDE QUESTS</span><small>{supportingQuests.length} 个可推进节点</small></header>
          {supportingQuests.map((quest) => (
            <button key={quest.id} onClick={() => onNavigate?.(quest.route)}>
              <span className={quest.sourceType}><Icon name={quest.icon} size={18} /></span>
              <span><small>{sourceLabels[quest.sourceType] || "CAMPUS QUEST"}</small><strong>{quest.title}</strong><em>{metaText(quest)}</em></span>
              <b>{questReward(quest)}</b>
              <Icon name="PhCaretRight" size={15} />
            </button>
          ))}
        </div>
      ) : (
        <div className="rpg-empty-state" role="status">
          <Icon name="PhFlagCheckered" size={32} />
          <strong>任务日志已清空</strong>
          <p>课程、截止事项和考试同步后会继续生成真实任务节点。</p>
          <button onClick={() => onNavigate?.("/tasks")}>查看待办</button>
        </div>
      )}
    </section>
  );
}
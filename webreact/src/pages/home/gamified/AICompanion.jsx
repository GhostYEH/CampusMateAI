import { useMemo } from "react";
import { Icon } from "../../../components/Icon.jsx";

export default function AICompanion({ summary, onNavigate }) {
  const suggestion = useMemo(() => {
    const reward = summary.dailyAdventure.nextReward;
    if (!reward) return "今天的成长路线已经完成，可以回顾成果或为明天整理计划。";
    if (reward.type === "focus-goal") return `再完成 ${reward.remainingMinutes} 分钟专注训练，即可点亮今日第二个成长节点。`;
    return "先完成一项真实待办，开启今天的校园成长路线。";
  }, [summary.dailyAdventure.nextReward]);

  const quickActions = [
    { label: "专注训练", detail: `${Math.min(summary.dailyAdventure.focusMinutes, 60)} / 60 min`, icon: "PhTimer", route: "/study" },
    { label: "今日任务", detail: `${summary.dailyAdventure.completedTasks} 项完成`, icon: "PhListChecks", route: "/tasks" },
  ];

  return (
    <section className="rpg-ai-companion" aria-labelledby="ai-companion-title">
      <div className="rpg-ai-portrait"><img src="/digital-human/fallback-avatar.png" alt="CampusMate CPM 数字人伙伴" /><i /></div>
      <div className="rpg-ai-copy">
        <span className="rpg-kicker">AI COMPANION · ONLINE</span>
        <h2 id="ai-companion-title">AI 伙伴</h2>
        <p>{suggestion}</p>
        <div className="rpg-ai-actions">
          {quickActions.map((action) => (
            <button key={action.route} onClick={() => onNavigate?.(action.route)}>
              <Icon name={action.icon} size={15} /><span><strong>{action.label}</strong><small>{action.detail}</small></span>
            </button>
          ))}
        </div>
      </div>
      <button className="rpg-ai-chat" onClick={() => onNavigate?.("/counselor")}>与伙伴对话<Icon name="PhChatCircleText" size={15} /></button>
    </section>
  );
}
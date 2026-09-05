import { Icon } from "../../../components/Icon.jsx";

const nodes = [
  { label: "冒险首页", code: "ADVENTURE HOME", icon: "PhHouse", route: "/home", x: "8%", y: "55%", tone: "cyan" },
  { label: "课程表", code: "SCHEDULE", icon: "PhCalendarBlank", route: "/courses", x: "18%", y: "78%", tone: "gold" },
  { label: "任务日志", code: "QUEST LOG", icon: "PhListChecks", route: "/tasks", x: "30%", y: "46%", tone: "violet", badge: "!" },
  { label: "考试试炼", code: "EXAM BOSS", icon: "PhExam", route: "/exams", x: "40%", y: "73%", tone: "ember" },
  { label: "专注训练", code: "FOCUS TRAINING", icon: "PhTimer", route: "/study", x: "51%", y: "40%", tone: "cyan" },
  { label: "AI 导师", code: "AI MENTOR", icon: "PhSparkle", route: "/counselor", x: "63%", y: "69%", tone: "violet" },
  { label: "校园探索", code: "CAMPUS MAP", icon: "PhMapTrifold", route: "/community", x: "74%", y: "38%", tone: "cyan" },
  { label: "校园社区", code: "CAMPUS WORLD", icon: "PhChatsCircle", route: "/community", x: "86%", y: "68%", tone: "emerald" },
  { label: "成长记录", code: "GROWTH", icon: "PhChartLineUp", route: "/profile", x: "91%", y: "31%", tone: "violet" },
  { label: "设置中心", code: "SETTINGS", icon: "PhGear", route: "/profile/settings", x: "95%", y: "83%", tone: "cyan" },
];

const utilityNodes = [];

export default function WorldMapNavigation({ onNavigate }) {
  return (
    <nav className="rpg-world-map" aria-label="校园世界地图导航">
      <div className="rpg-energy-road" aria-hidden="true"><i /><i /><i /></div>
      {nodes.map((node) => (
        <button
          key={node.route}
          className={`rpg-world-node ${node.tone}`}
          style={{ "--node-x": node.x, "--node-y": node.y }}
          aria-label={`${node.label} ${node.code}`}
          onClick={() => onNavigate?.(node.route)}
        >
          <span><Icon name={node.icon} size={20} weight="duotone" />{node.badge && <b>{node.badge}</b>}</span>
          <strong>{node.label}</strong>
          <small>{node.code}</small>
        </button>
      ))}
      <div className="rpg-world-utilities">
        {utilityNodes.map((node) => (
          <button key={node.route} onClick={() => onNavigate?.(node.route)}>
            <Icon name={node.icon} size={17} /><span>{node.label}</span><Icon name="PhArrowUpRight" size={13} />
          </button>
        ))}
      </div>
    </nav>
  );
}

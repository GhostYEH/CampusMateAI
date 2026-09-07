import { Link, useLocation } from "react-router-dom";
import { Icon } from "../Icon.jsx";

// 移植自 Summer Checkin 顶部导航（top-nav）的主导航入口，固定到学习陪伴页底部
const DOCK_LINKS = Object.freeze([
  { to: "/study", label: "小岛" },
  { to: "/tasks", label: "计划" },
  { to: "/courses", label: "阅读" },
  { to: "/home", label: "主页" },
]);

export default function SummerNavDock({ sceneAudio }) {
  const { pathname } = useLocation();

  return (
    <nav className="study-summer-dock" aria-label="学习陪伴导航">
      <div className="study-summer-dock__inner">
        <Link to="/study" className="study-summer-dock__brand">
          <span className="study-summer-dock__logo">
            <Icon name="PhTree" size={13} weight="fill" />
          </span>
          <span>学习陪伴</span>
        </Link>

        <div className="study-summer-dock__links">
          {DOCK_LINKS.map((item) => (
            <Link key={item.to} to={item.to} className={pathname === item.to ? "is-active" : ""}>
              {item.label}
            </Link>
          ))}
        </div>

        <div className="study-summer-dock__tools">
          <button
            type="button"
            className={sceneAudio.enabled ? "is-active" : ""}
            aria-pressed={sceneAudio.enabled}
            onClick={sceneAudio.toggle}
          >
            <Icon name="PhWaveform" size={15} />
            <span>场景音</span>
          </button>
        </div>
      </div>
    </nav>
  );
}
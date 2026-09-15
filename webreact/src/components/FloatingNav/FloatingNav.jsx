import { memo, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Icon } from "../Icon.jsx";
import LiquidMetalNav from "./LiquidMetalNav.jsx";
import { navItems } from "./navItems.js";

const STUDY_ROUTE_PREFIXES = Object.freeze(["study", "island", "plans", "docs", "statistics"]);
const WORLD_MODEL_ROUTE_PREFIXES = Object.freeze(["learning-state", "prediction"]);

const FloatingNav = memo(function FloatingNav({ pendingCount = 0, unreadCount = 0, reduceMotion = false, onIntent }) {
  const preloadedRouteKeys = useRef(new Set());
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (key) => {
    const prefixes = key === "study"
      ? STUDY_ROUTE_PREFIXES
      : key === "learning-state" ? WORLD_MODEL_ROUTE_PREFIXES : [key];
    return prefixes.some((prefix) => location.pathname === `/${prefix}` || location.pathname.startsWith(`/${prefix}/`));
  };
  const countFor = (key) => key === "tasks" ? pendingCount : key === "notifications" ? unreadCount : 0;
  const activeIndex = navItems.findIndex(({ key }) => isActive(key));

  const preloadFromEvent = (event) => {
    const button = event.target.closest?.(".floating-nav-button");
    const item = navItems.find((candidate) => candidate.label === button?.getAttribute("aria-label"));
    if (!item || preloadedRouteKeys.current.has(item.key)) return;
    preloadedRouteKeys.current.add(item.key);
    void onIntent?.(`/${item.key}`);
  };

  return <div className="floating-nav floating-nav--primary" onPointerOver={preloadFromEvent} onFocusCapture={preloadFromEvent}>
    <LiquidMetalNav
      items={navItems}
      activeIndex={activeIndex}
      reduceMotion={reduceMotion}
      staticControls
      className="floating-nav-inner"
      onSelect={({ key }) => navigate(`/${key}`)}
      renderItem={({ key, label, icon }) => {
        const active = isActive(key);
        const count = countFor(key);
        return <>
          <span className="floating-nav-icon" aria-hidden="true">
            <Icon name={icon} size={20} weight={active ? "duotone" : "regular"} />
          </span>
          <span className="floating-nav-label" aria-hidden="true">{label}</span>
          {count > 0 && <i className="floating-nav-dot" aria-label={`${count} 条待处理`} />}
        </>;
      }}
    />
  </div>;
});

export default FloatingNav;

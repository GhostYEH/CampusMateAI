import { memo, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import GlassSurface from "../GlassSurface.jsx";
import { Icon } from "../Icon.jsx";
import { navItems } from "./navItems.js";
import "./FloatingNav.css";

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
  const preloadFromEvent = (event) => {
    const button = event.target.closest?.(".floating-nav-button");
    const item = navItems.find((candidate) => candidate.label === button?.getAttribute("aria-label"));
    if (!item || preloadedRouteKeys.current.has(item.key)) return;
    preloadedRouteKeys.current.add(item.key);
    void onIntent?.(`/${item.key}`);
  };

  return <div className="floating-nav floating-nav--primary" data-reduce-motion={reduceMotion ? "true" : undefined} onPointerOver={preloadFromEvent} onFocusCapture={preloadFromEvent}>
    <GlassSurface
      className="floating-nav-glass"
      width="100%"
      height="100%"
      borderRadius={32}
      borderWidth={0.075}
      brightness={72}
      opacity={0.9}
      blur={9}
      displace={10}
      backgroundOpacity={0.18}
      saturation={1.35}
      distortionScale={-125}
      redOffset={4}
      greenOffset={12}
      blueOffset={20}
      mixBlendMode="screen"
    >
      <nav className="floating-nav-inner" aria-label="主导航">
        <ul className="floating-nav-list">
          {navItems.map(({ key, label, icon }) => {
            const active = isActive(key);
            const count = countFor(key);
            return <li key={key} className={active ? "active" : undefined}>
              <button
                type="button"
                className="floating-nav-button"
                aria-label={label}
                aria-current={active ? "page" : undefined}
                onClick={() => {
                  if (!active) navigate(`/${key}`);
                }}
              >
                <span className="floating-nav-icon" aria-hidden="true">
                  <Icon name={icon} size={20} weight={active ? "duotone" : "regular"} />
                </span>
                <span className="floating-nav-label" aria-hidden="true">{label}</span>
                {count > 0 && <span className="floating-nav-dot" aria-label={`${count} 条待处理`} />}
              </button>
            </li>;
          })}
        </ul>
      </nav>
    </GlassSurface>
  </div>;
});

export default FloatingNav;

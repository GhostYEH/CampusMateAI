import { memo } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Icon } from "../Icon.jsx";
import LiquidGlassSurface from "../LiquidGlassSurface.jsx";
import GooeyNav from "./GooeyNav.jsx";
import { navItems } from "./navItems.js";

const FloatingNav = memo(function FloatingNav({ tone = "dark", pendingCount = 0, unreadCount = 0, reduceMotion = false }) {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (key) => location.pathname === `/${key}` || location.pathname.startsWith(`/${key}/`);
  const countFor = (key) => key === "tasks" ? pendingCount : key === "notifications" ? unreadCount : 0;
  const activeIndex = Math.max(0, navItems.findIndex(({ key }) => isActive(key)));

  return <LiquidGlassSurface className={`floating-nav floating-nav--${tone}`}>
    <GooeyNav
      items={navItems}
      activeIndex={activeIndex}
      reduceMotion={reduceMotion}
      dockDistance={185}
      dockMagnification={54}
      dockBaseItemSize={36}
      className="floating-nav-inner"
      onSelect={({ key }) => navigate(`/${key}`)}
      renderItem={({ key, label, icon }) => {
        const active = isActive(key);
        const count = countFor(key);
        return <>
          <span className="floating-nav-icon" aria-hidden="true">
            <Icon name={icon} size={20} weight={active ? "duotone" : "regular"} />
          </span>
          <span className="floating-nav-label">{label}</span>
          {count > 0 && <i className="floating-nav-dot" aria-label={`${count} 条待处理`} />}
        </>;
      }}
    />
  </LiquidGlassSurface>;
});

export default FloatingNav;

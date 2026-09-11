import { memo, useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Glass } from "open-glass-ui";
import { Icon } from "../Icon.jsx";
import LiquidMetalNav from "./LiquidMetalNav.jsx";
import { navItems } from "./navItems.js";

const FloatingNav = memo(function FloatingNav({ tone = "dark", pendingCount = 0, unreadCount = 0, reduceMotion = false, onIntent }) {
  const dockRef = useRef(null);
  const preloadedRouteKeys = useRef(new Set());
  const location = useLocation();
  const navigate = useNavigate();
  const isHomeScene = location.pathname === "/home";

  // The living home scene can vary continuously. A stable opaque dark glass
  // treatment keeps the nav readable without synchronously reading GPU pixels.
  useEffect(() => {
    const dock = dockRef.current;
    if (!dock) return undefined;
    if (isHomeScene) dock.setAttribute("data-contrast", "dark");
    else dock.removeAttribute("data-contrast");
    return undefined;
  }, [isHomeScene]);

  const isActive = (key) => location.pathname === `/${key}` || location.pathname.startsWith(`/${key}/`);
  const countFor = (key) => key === "tasks" ? pendingCount : key === "notifications" ? unreadCount : 0;
  const activeIndex = Math.max(0, navItems.findIndex(({ key }) => isActive(key)));

  const preloadFromEvent = (event) => {
    const button = event.target.closest?.(".floating-nav-button");
    const item = navItems.find((candidate) => candidate.label === button?.getAttribute("aria-label"));
    if (!item || preloadedRouteKeys.current.has(item.key)) return;
    preloadedRouteKeys.current.add(item.key);
    void onIntent?.(`/${item.key}`);
  };

  return <Glass ref={dockRef} className={`floating-nav floating-nav--${tone}`} material="clear" tone={tone} interactive onPointerOver={preloadFromEvent} onFocusCapture={preloadFromEvent}>
    <LiquidMetalNav
      items={navItems}
      activeIndex={activeIndex}
      reduceMotion={reduceMotion}
      stableLayout
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
  </Glass>;
});

export default FloatingNav;

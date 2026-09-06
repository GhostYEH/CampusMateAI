import { memo, useLayoutEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { gsap } from "gsap";
import { Icon } from "../Icon.jsx";
import GlassSurface from "./GlassSurface.jsx";
import GooeyNav from "./GooeyNav.jsx";
import { navItems } from "./navItems.js";
import { getFloatingNavWidth } from "./layout.js";

const FloatingNav = memo(function FloatingNav({ tone = "dark", pendingCount = 0, unreadCount = 0, reduceMotion = false }) {
  const dockRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();

  useLayoutEffect(() => {
    const dock = dockRef.current;
    if (!dock) return undefined;

    const reduced = reduceMotion || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const buttons = [...dock.querySelectorAll(".floating-nav-button")];
    const labels = [...dock.querySelectorAll(".floating-nav-label")];
    const list = dock.querySelector(".floating-nav-list");
    const collapsedWidth = getComputedStyle(dock).getPropertyValue("--floating-nav-collapsed-width").trim();
    const styles = getComputedStyle(dock);
    const itemGap = Number.parseFloat(styles.getPropertyValue("--floating-nav-item-gap")) || 8;
    const expandedItemGap = Number.parseFloat(styles.getPropertyValue("--floating-nav-expanded-item-gap")) || 26;
    const expandedButtonOffset = Number.parseFloat(styles.getPropertyValue("--floating-nav-expanded-button-offset")) || 68;
    const navGutter = Number.parseFloat(styles.getPropertyValue("--floating-nav-gutter")) || 12;
    const listPaddingStart = Number.parseFloat(styles.getPropertyValue("--floating-nav-list-start-padding")) || 8;
    const listPaddingEnd = Number.parseFloat(styles.getPropertyValue("--floating-nav-list-end-padding")) || 8;
    const measureExpandedWidth = () => {
      const labelWidths = labels.map((label) => Math.ceil(label.scrollWidth || label.getBoundingClientRect().width));
      const itemWidths = labelWidths.map((width) => expandedButtonOffset + width);
      const contentWidth = itemWidths.reduce((total, width) => total + width, 0) + Math.max(0, itemWidths.length - 1) * expandedItemGap + listPaddingStart + listPaddingEnd + 2;
      return getFloatingNavWidth({ contentWidth, viewportWidth: window.innerWidth, gutter: navGutter });
    };
    const setExpandedWidth = () => {
      const expandedWidth = `${measureExpandedWidth()}px`;
      dock.style.setProperty("--floating-nav-expanded-width", expandedWidth);
      return expandedWidth;
    };
    setExpandedWidth();
    const collapsedButtonWidth = Number.parseFloat(getComputedStyle(buttons[0]).width) || 44;
    let removeListeners = () => {};
    const ctx = gsap.context(() => {
      const timeline = gsap.timeline({ paused: true, defaults: { duration: reduced ? 0 : 0.34, ease: "power3.out" } });
      gsap.set(dock, { width: collapsedWidth });
      gsap.set(buttons, { width: collapsedButtonWidth });
      gsap.set(list, { gap: itemGap });
      gsap.set(labels, { autoAlpha: 0, maxWidth: 0, x: -6 });
      timeline
        .to(dock, { width: () => measureExpandedWidth() }, 0)
        .to(list, { gap: expandedItemGap }, 0)
        .to(buttons, { width: (index) => expandedButtonOffset + Math.ceil(labels[index].scrollWidth || labels[index].getBoundingClientRect().width), stagger: 0.012 }, 0)
        .to(labels, { autoAlpha: 1, maxWidth: (index) => Math.ceil(labels[index].scrollWidth || labels[index].getBoundingClientRect().width), x: 0, stagger: 0.018 }, 0.035);

      const expand = () => timeline.play();
      const collapse = () => timeline.reverse();
      const collapseOnFocusOut = (event) => { if (!dock.contains(event.relatedTarget)) collapse(); };
      const resize = () => {
        setExpandedWidth();
        if (timeline.progress() > 0) timeline.invalidate().progress(1);
      };
      dock.addEventListener("mouseenter", expand);
      dock.addEventListener("mouseleave", collapse);
      dock.addEventListener("focusin", expand);
      dock.addEventListener("focusout", collapseOnFocusOut);
      window.addEventListener("resize", resize);
      removeListeners = () => {
        dock.removeEventListener("mouseenter", expand);
        dock.removeEventListener("mouseleave", collapse);
        dock.removeEventListener("focusin", expand);
        dock.removeEventListener("focusout", collapseOnFocusOut);
        window.removeEventListener("resize", resize);
      };
    }, dock);

    return () => { removeListeners(); ctx.revert(); };
  }, [reduceMotion]);

  const isActive = (key) => location.pathname === `/${key}` || location.pathname.startsWith(`/${key}/`);
  const countFor = (key) => key === "tasks" ? pendingCount : key === "notifications" ? unreadCount : 0;
  const activeIndex = Math.max(0, navItems.findIndex(({ key }) => isActive(key)));

  return <GlassSurface ref={dockRef} className={`floating-nav floating-nav--${tone}`} borderRadius={999} backgroundOpacity={0.035} saturation={1.18} distortionScale={0} redOffset={0} greenOffset={0} blueOffset={0}>
    <GooeyNav
      items={navItems}
      activeIndex={activeIndex}
      reduceMotion={reduceMotion}
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
  </GlassSurface>;
});

export default FloatingNav;

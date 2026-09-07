import { memo, useLayoutEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { gsap } from "gsap";
import { Icon } from "../Icon.jsx";
import LiquidGlassSurface from "../LiquidGlassSurface.jsx";
import GooeyNav from "./GooeyNav.jsx";
import { navItems } from "./navItems.js";
import { getFloatingNavWidth } from "./layout.js";

const CONTRAST_SAMPLE_MS = 180;

/**
 * Samples the Sylva scene behind the nav (home page only) and returns a
 * contrast keyword for the nav text: "light" means the sampled background
 * is bright so the nav should use dark text; "dark" means light text.
 * Returns null when the scene cannot be sampled yet.
 */
function sampleSceneContrast(dock) {
  const iframe = document.querySelector(".sylva-home-hero.sylva-scene-background iframe");
  const frameDocument = iframe?.contentDocument;
  const canvas = frameDocument?.querySelector("#scene");
  if (!canvas || !canvas.width || !canvas.height) return null;
  const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
  if (!gl) return null;

  const rect = dock.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  const centerX = Math.round(((rect.left + rect.width / 2) / window.innerWidth) * canvas.width);
  const centerY = Math.round(((rect.top + rect.height / 2) / window.innerHeight) * canvas.height);

  const size = 16;
  const x0 = Math.max(0, Math.min(canvas.width - size, centerX - size / 2));
  const y0 = Math.max(0, Math.min(canvas.height - size, centerY - size / 2));
  const pixels = new Uint8Array(size * size * 4);
  try {
    gl.readPixels(x0, canvas.height - y0 - size, size, size, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  } catch {
    return null;
  }

  let luminance = 0;
  for (let index = 0; index < pixels.length; index += 4) {
    luminance += 0.2126 * pixels[index] + 0.7152 * pixels[index + 1] + 0.0722 * pixels[index + 2];
  }
  luminance /= size * size * 255;
  if (!Number.isFinite(luminance) || luminance <= 0) return null;
  return luminance > 0.48 ? "light" : "dark";
}

const FloatingNav = memo(function FloatingNav({ tone = "dark", pendingCount = 0, unreadCount = 0, reduceMotion = false }) {
  const dockRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const isHomeScene = location.pathname === "/home";

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

  // Adaptive contrast: on the home page the nav samples the Sylva scene
  // behind it and toggles between light/dark text via data-contrast.
  useLayoutEffect(() => {
    const dock = dockRef.current;
    if (!dock) return undefined;

    if (!isHomeScene) {
      dock.removeAttribute("data-contrast");
      return undefined;
    }

    // Safe default before the scene can be sampled: the Sylva scene is dark.
    dock.setAttribute("data-contrast", "dark");

    const timer = window.setInterval(() => {
      const contrast = sampleSceneContrast(dock);
      if (contrast) dock.setAttribute("data-contrast", contrast);
    }, CONTRAST_SAMPLE_MS);

    return () => window.clearInterval(timer);
  }, [isHomeScene]);

  const isActive = (key) => location.pathname === `/${key}` || location.pathname.startsWith(`/${key}/`);
  const countFor = (key) => key === "tasks" ? pendingCount : key === "notifications" ? unreadCount : 0;
  const activeIndex = Math.max(0, navItems.findIndex(({ key }) => isActive(key)));

  return <LiquidGlassSurface ref={dockRef} className={`floating-nav floating-nav--${tone} floating-nav-surface`}>
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
  </LiquidGlassSurface>;
});

export default FloatingNav;

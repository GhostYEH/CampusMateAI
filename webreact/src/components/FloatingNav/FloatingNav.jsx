import { memo, useLayoutEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Glass } from "open-glass-ui";
import { Icon } from "../Icon.jsx";
import LiquidMetalNav from "./LiquidMetalNav.jsx";
import { navItems } from "./navItems.js";

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

  return <Glass ref={dockRef} className={`floating-nav floating-nav--${tone}`} material="clear" tone={tone} interactive>
    <LiquidMetalNav
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
          <span className="floating-nav-label" aria-hidden="true">{label}</span>
          {count > 0 && <i className="floating-nav-dot" aria-label={`${count} 条待处理`} />}
        </>;
      }}
    />
  </Glass>;
});

export default FloatingNav;

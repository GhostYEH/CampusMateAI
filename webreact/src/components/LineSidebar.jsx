import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "./Icon.jsx";
import "./LineSidebar.css";

const FALLOFF_CURVES = {
  linear: (progress) => progress,
  smooth: (progress) => progress * progress * (3 - 2 * progress),
  sharp: (progress) => progress * progress * progress,
};

function normalizeItem(item) {
  return typeof item === "string" ? { label: item } : item;
}

export default function LineSidebar({
  items = [],
  accentColor = "#5966ea",
  textColor = "#7887a4",
  markerColor = "#cbd4e5",
  showIndex = true,
  showMarker = true,
  proximityRadius = 94,
  maxShift = 13,
  falloff = "smooth",
  markerLength = 25,
  markerGap = 11,
  tickScale = 0.52,
  scaleTick = true,
  itemGap = 10,
  fontSize = 0.78,
  smoothing = 90,
  defaultActive = 0,
  onItemClick,
  className = "",
}) {
  const listRef = useRef(null);
  const itemRefs = useRef([]);
  const targetsRef = useRef([]);
  const currentRef = useRef([]);
  const rafRef = useRef(null);
  const lastRef = useRef(0);
  const activeRef = useRef(defaultActive);
  const [activeIndex, setActiveIndex] = useState(defaultActive);

  activeRef.current = activeIndex;

  const runFrame = useCallback((now) => {
    const delta = Math.min((now - lastRef.current) / 1000, 0.05);
    lastRef.current = now;
    const smoothingTime = Math.max(smoothing, 1) / 1000;
    const easing = 1 - Math.exp(-delta / smoothingTime);
    let moving = false;

    itemRefs.current.forEach((element, index) => {
      if (!element) return;
      const target = Math.max(targetsRef.current[index] || 0, activeRef.current === index ? 1 : 0);
      const current = currentRef.current[index] || 0;
      const next = current + (target - current) * easing;
      const settled = Math.abs(target - next) < 0.0015;
      const value = settled ? target : next;
      currentRef.current[index] = value;
      element.style.setProperty("--effect", value.toFixed(4));
      if (!settled) moving = true;
    });

    rafRef.current = moving ? requestAnimationFrame(runFrame) : null;
  }, [smoothing]);

  const startLoop = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    lastRef.current = performance.now();
    rafRef.current = requestAnimationFrame(runFrame);
  }, [runFrame]);

  const handlePointerMove = useCallback((event) => {
    const list = listRef.current;
    if (!list) return;
    const rect = list.getBoundingClientRect();
    const pointerY = event.clientY - rect.top;
    const ease = FALLOFF_CURVES[falloff] || FALLOFF_CURVES.linear;

    itemRefs.current.forEach((element, index) => {
      if (!element) return;
      const center = element.offsetTop + element.offsetHeight / 2;
      const distance = Math.abs(pointerY - center);
      targetsRef.current[index] = ease(Math.max(0, 1 - distance / proximityRadius));
    });
    startLoop();
  }, [falloff, proximityRadius, startLoop]);

  const handlePointerLeave = useCallback(() => {
    targetsRef.current = targetsRef.current.map(() => 0);
    startLoop();
  }, [startLoop]);

  function handleClick(index, item) {
    setActiveIndex(index);
    onItemClick?.(index, item.label, item);
  }

  useEffect(() => {
    startLoop();
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [activeIndex, startLoop]);

  return (
    <nav
      className={`line-sidebar${showMarker ? " line-sidebar--markers" : ""}${scaleTick ? " line-sidebar--scale-tick" : ""}${className ? ` ${className}` : ""}`}
      aria-label="帖子分类"
      style={{
        "--accent-color": accentColor,
        "--text-color": textColor,
        "--marker-color": markerColor,
        "--marker-length": `${markerLength}px`,
        "--marker-gap": `${markerGap}px`,
        "--tick-scale": tickScale,
        "--max-shift": `${maxShift}px`,
        "--item-gap": `${itemGap}px`,
        "--font-size": `${fontSize}rem`,
      }}
    >
      <ul
        ref={listRef}
        className="line-sidebar__list"
        role="list"
        onPointerMove={handlePointerMove}
        onPointerLeave={handlePointerLeave}
      >
        {items.map((rawItem, index) => {
          const item = normalizeItem(rawItem);
          return (
            <li
              key={`${item.key || item.label}-${index}`}
              ref={(element) => { itemRefs.current[index] = element; }}
              className="line-sidebar__item"
              aria-current={activeIndex === index ? "true" : undefined}
            >
              <button type="button" onClick={() => handleClick(index, item)}>
                {showMarker && <span className="line-sidebar__marker" aria-hidden="true" />}
                <span className="line-sidebar__label">
                  {showIndex && <span className="line-sidebar__index">{String(index + 1).padStart(2, "0")}</span>}
                  {item.icon && <Icon name={item.icon} size={14} />}
                  <span className="line-sidebar__text">{item.label}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

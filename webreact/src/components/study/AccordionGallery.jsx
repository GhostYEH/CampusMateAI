import { useCallback, useEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import "./AccordionGallery.css";

const DEFAULT_ITEMS = Object.freeze([
  { image: "https://picsum.photos/id/1015/900/1200", label: "Canyon" },
  { image: "https://picsum.photos/id/1018/900/1200", label: "Ridgeline" },
  { image: "https://picsum.photos/id/1039/900/1200", label: "Falls" },
  { image: "https://picsum.photos/id/1043/900/1200", label: "Harbour" },
  { image: "https://picsum.photos/id/1044/900/1200", label: "Skyline" },
]);

function clampIndex(value, count) {
  if (!count) return 0;
  return Math.min(Math.max(Number(value) || 0, 0), count - 1);
}

export default function AccordionGallery({
  items = DEFAULT_ITEMS,
  activeIndex,
  defaultIndex = 2,
  accentColor = "#ffffff",
  overlayColor = "#060010",
  textColor = "#ffffff",
  height = 460,
  gap = 10,
  radius = 16,
  expandRatio = 0.52,
  orientation = "horizontal",
  duration = 0.6,
  ease = "power3.out",
  parallax = 0.5,
  tilt = 8,
  stagger = 0.06,
  trigger = "hover",
  showLabels = true,
  grayscale = true,
  onChange,
  className = "",
}) {
  const rootRef = useRef(null);
  const panelRefs = useRef([]);
  const mediaRefs = useRef([]);
  const barRefs = useRef([]);
  const textRefs = useRef([]);
  const timelineRef = useRef(null);
  const firstRunRef = useRef(true);
  const mediaSizeRef = useRef(320);
  const count = items.length;
  const controlled = Number.isInteger(activeIndex);
  const [uncontrolledActive, setUncontrolledActive] = useState(() => clampIndex(defaultIndex, count));
  const active = controlled ? clampIndex(activeIndex, count) : clampIndex(uncontrolledActive, count);
  const vertical = orientation === "vertical";
  const prefersReduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;

  const selectIndex = useCallback((nextIndex) => {
    const next = clampIndex(nextIndex, count);
    if (!controlled) setUncontrolledActive(next);
    const item = items[next];
    if (item) onChange?.(item.key ?? item.value ?? next, item, next);
  }, [controlled, count, items, onChange]);

  const applyLayout = useCallback((animate) => {
    const panels = panelRefs.current;
    if (!panels.length) return;

    const ratio = Math.min(Math.max(expandRatio, 0.2), 0.9);
    const grow = count > 1 ? (ratio * (count - 1)) / (1 - ratio) : 1;
    const mediaSize = mediaSizeRef.current;
    timelineRef.current?.kill();
    const stepDuration = animate && !prefersReduced ? duration : 0;
    const timeline = gsap.timeline();

    panels.forEach((panel, index) => {
      if (!panel) return;
      const isActive = index === active;
      const media = mediaRefs.current[index];
      const bar = barRefs.current[index];
      const text = textRefs.current[index];
      const rotation = isActive ? 0 : index < active ? tilt : -tilt;
      const rotationProps = vertical ? { rotateX: -rotation } : { rotateY: rotation };

      timeline.to(panel, { flexGrow: isActive ? grow : 1, ...rotationProps, duration: stepDuration, ease }, 0);
      if (media) {
        const drift = Math.max(-1.5, Math.min(1.5, active - index));
        const shift = drift * parallax * mediaSize * 0.06;
        timeline.to(media, {
          xPercent: -50,
          yPercent: -50,
          x: vertical ? 0 : isActive ? 0 : shift,
          y: vertical ? isActive ? 0 : shift : 0,
          "--ag-gray": grayscale && !isActive ? 1 : 0,
          "--ag-dim": isActive ? 0 : 0.35,
          duration: stepDuration,
          ease,
        }, 0);
      }
      if (showLabels && bar && text) {
        timeline.to([bar, text], {
          opacity: isActive ? 1 : 0,
          x: isActive ? 0 : -14,
          duration: isActive ? stepDuration : stepDuration * 0.6,
          ease,
          stagger: prefersReduced ? 0 : stagger,
        }, 0);
      }
    });
    timelineRef.current = timeline;
  }, [active, count, duration, ease, expandRatio, grayscale, parallax, prefersReduced, showLabels, stagger, tilt, vertical]);

  useEffect(() => {
    const element = rootRef.current;
    if (!element) return undefined;
    const measure = () => {
      const rect = element.getBoundingClientRect();
      const total = vertical ? rect.height : rect.width;
      const usable = Math.max(total - gap * Math.max(count - 1, 0), 120);
      const size = Math.max(140, usable * Math.min(Math.max(expandRatio, 0.2), 0.9) * 1.22);
      mediaSizeRef.current = size;
      element.style.setProperty("--ag-media-size", `${size}px`);
      applyLayout(!firstRunRef.current);
    };
    measure();
    if (typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [applyLayout, count, expandRatio, gap, vertical]);

  useEffect(() => {
    applyLayout(!firstRunRef.current);
    firstRunRef.current = false;
  }, [applyLayout]);

  useEffect(() => () => timelineRef.current?.kill(), []);

  const handleKeyDown = (index, event) => {
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      selectIndex((index + 1) % count);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      selectIndex((index - 1 + count) % count);
    } else if (event.key === "Home") {
      event.preventDefault();
      selectIndex(0);
    } else if (event.key === "End") {
      event.preventDefault();
      selectIndex(count - 1);
    }
  };

  if (!count) return null;

  return (
    <div
      ref={rootRef}
      className={`accordion-gallery${vertical ? " accordion-gallery--vertical" : ""}${className ? ` ${className}` : ""}`}
      style={{
        "--ag-accent": accentColor,
        "--ag-overlay": overlayColor,
        "--ag-text": textColor,
        "--ag-gap": `${gap}px`,
        "--ag-radius": `${radius}px`,
        height: vertical ? `${Math.round(height * 1.6)}px` : `${height}px`,
      }}
      role="group"
      aria-label="选择学习场景"
    >
      {items.map((item, index) => {
        const isActive = index === active;
        return (
          <button
            key={item.key ?? item.value ?? index}
            ref={(element) => { panelRefs.current[index] = element; }}
            type="button"
            className={`ag-panel${isActive ? " ag-panel--active" : ""}`}
            style={{ borderRadius: `${radius}px` }}
            onClick={() => selectIndex(index)}
            onMouseEnter={() => trigger === "hover" && selectIndex(index)}
            onFocus={() => selectIndex(index)}
            onKeyDown={(event) => handleKeyDown(index, event)}
            aria-current={isActive ? "true" : undefined}
            aria-label={item.ariaLabel || `${item.label || "场景"}${item.caption ? `，${item.caption}` : ""}`}
          >
            <span className="ag-panel__frame">
              <span className="ag-panel__media" ref={(element) => { mediaRefs.current[index] = element; }}>
                <img src={item.image || item.asset} alt={item.alt || item.label || ""} draggable="false" />
              </span>
              <span className="ag-panel__overlay" aria-hidden="true" />
            </span>
            {showLabels && (
              <span className="ag-panel__label" aria-hidden="true">
                <span className="ag-panel__bar" ref={(element) => { barRefs.current[index] = element; }} />
                <span className="ag-panel__text" ref={(element) => { textRefs.current[index] = element; }}>
                  <strong>{item.label}</strong>
                  {item.caption && <small>{item.caption}</small>}
                </span>
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

import { motion, useMotionValue, useSpring, useTransform } from "motion/react";
import { useEffect, useLayoutEffect, useRef } from "react";
import LiquidMetalButton from "../LiquidMetalButton.jsx";
import { getDockScale } from "./layout.js";
import "./LiquidMetalNav.css";

const dockSpring = { mass: 0.25, stiffness: 260, damping: 22 };

function DockItem({
  item,
  index,
  active,
  mouseX,
  distance,
  magnification,
  baseItemSize,
  reduceMotion,
  onClick,
  renderItem,
}) {
  const itemRef = useRef(null);
  const centerX = useMotionValue(Number.NaN);
  useLayoutEffect(() => {
    const element = itemRef.current;
    if (!element) return undefined;

    let measureFrame = 0;
    const measure = () => {
      if (measureFrame) return;
      measureFrame = requestAnimationFrame(() => {
        measureFrame = 0;
        const rect = element.getBoundingClientRect();
        centerX.set(rect.left + rect.width / 2);
      });
    };

    measure();
    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(measure) : null;
    observer?.observe(element);
    window.addEventListener("resize", measure, { passive: true });

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
      if (measureFrame) cancelAnimationFrame(measureFrame);
    };
  }, [centerX]);

  const pointerDistance = useTransform([mouseX, centerX], ([value, center]) => {
    if (!Number.isFinite(value) || !Number.isFinite(center)) return Number.POSITIVE_INFINITY;
    return value - center;
  });
  const targetScale = useTransform(pointerDistance, (value) => getDockScale(value, distance, baseItemSize, magnification));
  const scale = useSpring(targetScale, dockSpring);

  return (
    <motion.li
      ref={itemRef}
      className={active ? "active" : ""}
      style={{ scale: reduceMotion ? 1 : scale }}
    >
      <LiquidMetalButton
        variant="nav"
        active={active}
        defer
        disableEffects={reduceMotion}
        maxFps={20}
        dprCap={1}
        className="floating-nav-button"
        aria-label={item.label}
        aria-current={active ? "page" : undefined}
        onClick={(event) => onClick(event, index)}
      >
        {renderItem(item, index)}
      </LiquidMetalButton>
    </motion.li>
  );
}

export default function LiquidMetalNav({
  items = [],
  activeIndex: controlledActiveIndex = 0,
  onSelect,
  renderItem = (item) => item.label,
  ariaLabel = "主导航",
  className = "",
  reduceMotion = false,
  dockDistance = 120,
  dockMagnification = 60,
  dockBaseItemSize = 44,
}) {
  const mouseX = useMotionValue(Number.POSITIVE_INFINITY);
  const pointerFrameRef = useRef(0);
  const pendingPointerXRef = useRef(Number.POSITIVE_INFINITY);
  const activeIndex = Number.isInteger(controlledActiveIndex) ? controlledActiveIndex : 0;

  useEffect(() => () => {
    if (pointerFrameRef.current) cancelAnimationFrame(pointerFrameRef.current);
  }, []);

  const handleMouseMove = (event) => {
    if (reduceMotion) return;
    pendingPointerXRef.current = event.clientX;
    if (pointerFrameRef.current) return;
    pointerFrameRef.current = requestAnimationFrame(() => {
      pointerFrameRef.current = 0;
      mouseX.set(pendingPointerXRef.current);
    });
  };

  const handleMouseLeave = () => {
    pendingPointerXRef.current = Number.POSITIVE_INFINITY;
    if (pointerFrameRef.current) {
      cancelAnimationFrame(pointerFrameRef.current);
      pointerFrameRef.current = 0;
    }
    mouseX.set(Number.POSITIVE_INFINITY);
  };

  const handleClick = (event, index) => {
    const item = items[index];
    if (!item || activeIndex === index) return;
    onSelect?.(item, index);
  };

  return (
    <div
      className={`liquid-metal-nav-container ${className}`}
      data-reduce-motion={reduceMotion ? "true" : undefined}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      <nav aria-label={ariaLabel}>
        <ul className="floating-nav-list">
          {items.map((item, index) => (
            <DockItem
              key={item.key || item.href || index}
              item={item}
              index={index}
              active={activeIndex === index}
              mouseX={mouseX}
              distance={dockDistance}
              magnification={dockMagnification}
              baseItemSize={dockBaseItemSize}
              reduceMotion={reduceMotion}
              onClick={handleClick}
              renderItem={renderItem}
            />
          ))}
        </ul>
      </nav>
    </div>
  );
}

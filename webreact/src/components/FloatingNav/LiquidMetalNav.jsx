import { motion, useMotionValue, useSpring, useTransform } from "motion/react";
import { useRef } from "react";
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
  const pointerDistance = useTransform(mouseX, (value) => {
    const rect = itemRef.current?.getBoundingClientRect();
    if (!rect) return Number.POSITIVE_INFINITY;
    return value - (rect.left + rect.width / 2);
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
  const activeIndex = Number.isInteger(controlledActiveIndex) ? controlledActiveIndex : 0;

  const handleClick = (event, index) => {
    const item = items[index];
    if (!item || activeIndex === index) return;
    onSelect?.(item, index);
  };

  return (
    <div
      className={`liquid-metal-nav-container ${className}`}
      data-reduce-motion={reduceMotion ? "true" : undefined}
      onMouseMove={(event) => mouseX.set(event.clientX)}
      onMouseLeave={() => mouseX.set(Number.POSITIVE_INFINITY)}
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

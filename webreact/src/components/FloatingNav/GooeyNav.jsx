import { motion, useMotionValue, useSpring, useTransform } from "motion/react";
import { useEffect, useRef, useState } from "react";
import "./GooeyNav.css";
import { getDockScale } from "./layout.js";

const noise = (amount = 1) => amount / 2 - Math.random() * amount;
const dockSpring = { mass: 0.25, stiffness: 260, damping: 22 };

function getXY(distance, pointIndex, totalPoints) {
  const angle = ((360 + noise(8)) / totalPoints) * pointIndex * (Math.PI / 180);
  return [distance * Math.cos(angle), distance * Math.sin(angle)];
}

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
  const buttonRef = useRef(null);
  const pointerDistance = useTransform(mouseX, (value) => {
    const rect = buttonRef.current?.getBoundingClientRect();
    if (!rect) return Number.POSITIVE_INFINITY;
    return value - (rect.left + rect.width / 2);
  });
  const targetScale = useTransform(pointerDistance, (value) => getDockScale(value, distance, baseItemSize, magnification));
  const scale = useSpring(targetScale, dockSpring);

  return (
    <li className={active ? "active" : ""}>
      <motion.button
        ref={buttonRef}
        type="button"
        className="floating-nav-button"
        aria-label={item.label}
        aria-current={active ? "page" : undefined}
        style={{ scale: reduceMotion ? 1 : scale }}
        onClick={(event) => onClick(event, index)}
      >
        {renderItem(item, index)}
      </motion.button>
    </li>
  );
}

export default function GooeyNav({
  items = [],
  activeIndex: controlledActiveIndex = 0,
  animationTime = 600,
  particleCount = 15,
  particleDistances = [42, 8],
  particleR = 100,
  timeVariance = 300,
  colors = [1, 2, 3, 1, 2, 3, 1, 4],
  onSelect,
  renderItem = (item) => item.label,
  ariaLabel = "主导航",
  className = "",
  reduceMotion = false,
  dockDistance = 120,
  dockMagnification = 60,
  dockBaseItemSize = 44,
}) {
  const containerRef = useRef(null);
  const navRef = useRef(null);
  const filterRef = useRef(null);
  const textRef = useRef(null);
  const timersRef = useRef([]);
  const mouseX = useMotionValue(Number.POSITIVE_INFINITY);
  const [internalActiveIndex, setInternalActiveIndex] = useState(controlledActiveIndex);
  const activeIndex = Number.isInteger(controlledActiveIndex) ? controlledActiveIndex : internalActiveIndex;

  useEffect(() => {
    setInternalActiveIndex(controlledActiveIndex);
  }, [controlledActiveIndex]);

  const updateEffectPosition = (element) => {
    if (!containerRef.current || !filterRef.current || !textRef.current || !element) return;
    const containerRect = containerRef.current.getBoundingClientRect();
    const position = element.getBoundingClientRect();
    const styles = {
      left: `${position.x - containerRect.x}px`,
      top: `${position.y - containerRect.y}px`,
      width: `${position.width}px`,
      height: `${position.height}px`,
    };
    Object.assign(filterRef.current.style, styles);
    Object.assign(textRef.current.style, styles);
  };

  const makeParticles = (element) => {
    if (reduceMotion) return;
    const bubbleTime = animationTime * 2 + timeVariance;
    element.style.setProperty("--time", `${bubbleTime}ms`);
    const particleTimers = [];

    for (let index = 0; index < particleCount; index += 1) {
      const start = getXY(particleDistances[0], particleCount - index, particleCount);
      const end = getXY(particleDistances[1] + noise(7), particleCount - index, particleCount);
      const duration = animationTime * 2 + noise(timeVariance * 2);
      const particle = document.createElement("span");
      const point = document.createElement("span");
      particle.className = "gooey-nav-particle";
      particle.style.setProperty("--start-x", `${start[0]}px`);
      particle.style.setProperty("--start-y", `${start[1]}px`);
      particle.style.setProperty("--end-x", `${end[0]}px`);
      particle.style.setProperty("--end-y", `${end[1]}px`);
      particle.style.setProperty("--time", `${duration}ms`);
      particle.style.setProperty("--scale", `${1 + noise(0.2)}`);
      particle.style.setProperty("--color", `var(--color-${colors[Math.floor(Math.random() * colors.length)]}, var(--blue))`);
      particle.style.setProperty("--rotate", `${noise(particleR / 10) * 10}deg`);
      point.className = "gooey-nav-point";
      particle.appendChild(point);
      element.appendChild(particle);
      requestAnimationFrame(() => element.classList.add("active"));

      const removeTimer = window.setTimeout(() => particle.remove(), Math.max(0, duration));
      particleTimers.push(removeTimer);
    }

    timersRef.current.push(...particleTimers);
  };

  const handleClick = (event, index) => {
    event.preventDefault();
    const item = items[index];
    if (!item || activeIndex === index) return;
    const itemElement = event.currentTarget.closest("li");
    setInternalActiveIndex(index);
    updateEffectPosition(itemElement);
    if (filterRef.current) {
      filterRef.current.querySelectorAll(".gooey-nav-particle").forEach((particle) => particle.remove());
      makeParticles(filterRef.current);
    }
    textRef.current?.classList.remove("active");
    void textRef.current?.offsetWidth;
    textRef.current?.classList.add("active");
    onSelect?.(item, index);
  };

  useEffect(() => {
    if (!navRef.current || !containerRef.current) return undefined;
    const activeItem = navRef.current.querySelectorAll("li")[activeIndex];
    if (activeItem) {
      updateEffectPosition(activeItem);
      textRef.current?.classList.add("active");
    }
    const resizeObserver = new ResizeObserver(() => {
      const currentActiveItem = navRef.current?.querySelectorAll("li")[activeIndex];
      if (currentActiveItem) updateEffectPosition(currentActiveItem);
    });
    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, [activeIndex]);

  useEffect(() => () => {
    timersRef.current.forEach((timer) => window.clearTimeout(timer));
  }, []);

  return (
    <div
      ref={containerRef}
      className={`gooey-nav-container ${className}`}
      data-reduce-motion={reduceMotion ? "true" : undefined}
      onMouseMove={(event) => mouseX.set(event.clientX)}
      onMouseLeave={() => mouseX.set(Number.POSITIVE_INFINITY)}
    >
      <nav aria-label={ariaLabel}>
        <ul ref={navRef} className="floating-nav-list">
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
      <span className="gooey-nav-effect filter" ref={filterRef} aria-hidden="true" />
      <span className="gooey-nav-effect text" ref={textRef} aria-hidden="true" />
    </div>
  );
}

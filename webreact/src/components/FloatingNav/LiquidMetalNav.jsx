import { motion, useMotionValue, useSpring, useTransform } from "motion/react";
import { useCallback, useEffect, useLayoutEffect, useRef } from "react";
import LiquidMetalButton from "../LiquidMetalButton.jsx";
import { getSharedNavigationLiquidRenderer } from "../liquidMetalScene";
import { getDockScale } from "./layout.js";
import "./LiquidMetalNav.css";

const dockSpring = { mass: 0.25, stiffness: 260, damping: 22 };

export function createStableHoverGate() {
  let pointerVersion = 0;
  let claimedIndex = null;
  let claimedVersion = -1;

  return {
    notePointerMove() {
      pointerVersion += 1;
    },
    claim(index) {
      if (claimedIndex === index) return true;
      if (claimedIndex !== null && claimedVersion === pointerVersion) return false;
      claimedIndex = index;
      claimedVersion = pointerVersion;
      return true;
    },
    release(index, { force = false } = {}) {
      if (claimedIndex !== index || (!force && claimedVersion === pointerVersion)) return false;
      claimedIndex = null;
      claimedVersion = pointerVersion;
      return true;
    },
    current() {
      return claimedIndex;
    },
  };
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
  useSharedNavigationRenderer,
  onCenterValue,
  onLiquidStageReady,
  onLiquidTargetEnter,
  onLiquidTargetLeave,
  onLiquidTargetDown,
  onLiquidTargetFocus,
  onLiquidTargetBlur,
  onLiquidTargetKeyDown,
  onLiquidTargetKeyUp,
}) {
  const itemRef = useRef(null);
  const centerX = useMotionValue(Number.NaN);
  useLayoutEffect(() => {
    onCenterValue(index, centerX);
    return () => onCenterValue(index, null);
  }, [centerX, index, onCenterValue]);

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
        useSharedNavigationRenderer={useSharedNavigationRenderer}
        maxFps={20}
        dprCap={1}
        className="floating-nav-button"
        aria-label={item.label}
        aria-current={active ? "page" : undefined}
        onClick={(event) => onClick(event, index)}
        onLiquidStageReady={(stage) => onLiquidStageReady(index, stage)}
        onLiquidTargetEnter={(stage, event) => onLiquidTargetEnter(index, stage, event)}
        onLiquidTargetLeave={(stage, event) => onLiquidTargetLeave(index, stage, event)}
        onLiquidTargetDown={(stage, event) => onLiquidTargetDown(index, stage, event)}
        onLiquidTargetFocus={(stage) => onLiquidTargetFocus(index, stage)}
        onLiquidTargetBlur={(stage, event) => onLiquidTargetBlur(index, stage, event)}
        onLiquidTargetKeyDown={(stage, event) => onLiquidTargetKeyDown(index, stage, event)}
        onLiquidTargetKeyUp={(stage, event) => onLiquidTargetKeyUp(index, stage, event)}
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
  reuseRenderer = false,
  effectGeometrySelector,
}) {
  const mouseX = useMotionValue(Number.POSITIVE_INFINITY);
  const listRef = useRef(null);
  const pointerFrameRef = useRef(0);
  const geometryFrameRef = useRef(0);
  const pendingPointerXRef = useRef(Number.POSITIVE_INFINITY);
  const centerValuesRef = useRef(new Map());
  const stageRefs = useRef(new Map());
  const hoverGateRef = useRef(createStableHoverGate());
  const hoveredIndexRef = useRef(null);
  const focusedIndexRef = useRef(null);
  const activeIndexRef = useRef(0);
  const navTransitionRef = useRef(false);
  const sharedRendererRef = useRef(null);
  if (!sharedRendererRef.current) sharedRendererRef.current = getSharedNavigationLiquidRenderer();
  const activeIndex = Number.isInteger(controlledActiveIndex) ? controlledActiveIndex : 0;
  activeIndexRef.current = activeIndex;

  const measureDockItems = useCallback(() => {
    geometryFrameRef.current = 0;
    const list = listRef.current;
    if (!list) return;
    Array.from(list.children).forEach((element, index) => {
      const centerX = centerValuesRef.current.get(index);
      if (!centerX) return;
      const rect = element.getBoundingClientRect();
      centerX.set(rect.left + rect.width / 2);
    });
  }, []);
  const scheduleDockMeasure = useCallback(() => {
    if (geometryFrameRef.current) return;
    geometryFrameRef.current = requestAnimationFrame(measureDockItems);
  }, [measureDockItems]);
  const registerCenterValue = useCallback((index, centerX) => {
    if (centerX) centerValuesRef.current.set(index, centerX);
    else centerValuesRef.current.delete(index);
    scheduleDockMeasure();
  }, [scheduleDockMeasure]);
  const attachIndex = useCallback((index) => {
    if (!reuseRenderer || reduceMotion) return false;
    const stage = stageRefs.current.get(index);
    if (!stage) return false;
    return sharedRendererRef.current.attach(stage, {
      getActive: () => activeIndexRef.current === index,
      getEngaged: () => activeIndexRef.current === index
        || hoveredIndexRef.current === index
        || focusedIndexRef.current === index,
      geometrySelector: effectGeometrySelector,
      maxFps: 20,
      dprCap: 1,
    });
  }, [effectGeometrySelector, reduceMotion, reuseRenderer]);
  const registerStage = useCallback((index, stage) => {
    const previousStage = stageRefs.current.get(index);
    if (stage) stageRefs.current.set(index, stage);
    else stageRefs.current.delete(index);
    if (!stage && previousStage) sharedRendererRef.current.detach(previousStage);
    const preferredIndex = focusedIndexRef.current ?? hoveredIndexRef.current ?? activeIndexRef.current;
    if (stage && preferredIndex === index) attachIndex(index);
  }, [attachIndex]);

  useLayoutEffect(() => {
    const list = listRef.current;
    if (!list) return undefined;
    const nav = list.closest(".floating-nav");
    const observer = typeof ResizeObserver === "function"
      ? new ResizeObserver(() => {
        if (!navTransitionRef.current) scheduleDockMeasure();
      })
      : null;
    const handleTransitionRun = (event) => {
      if (event.target !== nav || event.propertyName !== "width") return;
      navTransitionRef.current = true;
      scheduleDockMeasure();
    };
    const handleTransitionEnd = (event) => {
      if (event.target !== nav || event.propertyName !== "width") return;
      navTransitionRef.current = false;
      nav.classList.remove("floating-nav--collapsing");
      scheduleDockMeasure();
    };

    observer?.observe(list);
    window.addEventListener("resize", scheduleDockMeasure, { passive: true });
    nav?.addEventListener("transitionrun", handleTransitionRun);
    nav?.addEventListener("transitionend", handleTransitionEnd);
    nav?.addEventListener("transitioncancel", handleTransitionEnd);
    scheduleDockMeasure();
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", scheduleDockMeasure);
      nav?.removeEventListener("transitionrun", handleTransitionRun);
      nav?.removeEventListener("transitionend", handleTransitionEnd);
      nav?.removeEventListener("transitioncancel", handleTransitionEnd);
      nav?.classList.remove("floating-nav--collapsing");
      if (geometryFrameRef.current) cancelAnimationFrame(geometryFrameRef.current);
    };
  }, [scheduleDockMeasure]);

  useLayoutEffect(() => {
    if (!reuseRenderer || reduceMotion) return undefined;
    attachIndex(focusedIndexRef.current ?? hoveredIndexRef.current ?? activeIndex);
    return undefined;
  }, [activeIndex, attachIndex, reduceMotion, reuseRenderer]);

  useEffect(() => () => {
    if (pointerFrameRef.current) cancelAnimationFrame(pointerFrameRef.current);
  }, []);

  const handleMouseMove = (event) => {
    if (reduceMotion) return;
    listRef.current?.closest(".floating-nav")?.classList.remove("floating-nav--collapsing");
    if (reuseRenderer) {
      hoverGateRef.current.notePointerMove();
      sharedRendererRef.current.move(event.nativeEvent || event);
    }
    pendingPointerXRef.current = event.clientX;
    if (pointerFrameRef.current) return;
    pointerFrameRef.current = requestAnimationFrame(() => {
      pointerFrameRef.current = 0;
      mouseX.set(pendingPointerXRef.current);
    });
  };

  const handleMouseLeave = () => {
    if (!reduceMotion) listRef.current?.closest(".floating-nav")?.classList.add("floating-nav--collapsing");
    if (reuseRenderer) {
      const hoveredIndex = hoverGateRef.current.current();
      if (hoveredIndex !== null) {
        hoverGateRef.current.release(hoveredIndex, { force: true });
        hoveredIndexRef.current = null;
        const stage = stageRefs.current.get(hoveredIndex);
        if (stage) sharedRendererRef.current.leave(stage, { pointerType: "mouse" });
      }
      attachIndex(focusedIndexRef.current ?? activeIndexRef.current);
    }
    pendingPointerXRef.current = Number.POSITIVE_INFINITY;
    if (pointerFrameRef.current) {
      cancelAnimationFrame(pointerFrameRef.current);
      pointerFrameRef.current = 0;
    }
    mouseX.set(Number.POSITIVE_INFINITY);
  };

  const handleLiquidTargetEnter = (index, stage, event) => {
    if (!reuseRenderer || reduceMotion || (event?.pointerType && event.pointerType !== "mouse")) return;
    if (!hoverGateRef.current.claim(index)) return;
    hoveredIndexRef.current = index;
    if (!attachIndex(index)) return;
    sharedRendererRef.current.enter(stage, event);
  };
  const handleLiquidTargetLeave = (index, stage, event) => {
    if (!reuseRenderer || !hoverGateRef.current.release(index)) return;
    hoveredIndexRef.current = null;
    sharedRendererRef.current.leave(stage, event);
    attachIndex(focusedIndexRef.current ?? activeIndexRef.current);
  };
  const handleLiquidTargetDown = (index, stage, event) => {
    if (!reuseRenderer || reduceMotion) return;
    if (hoverGateRef.current.claim(index)) hoveredIndexRef.current = index;
    if (attachIndex(index)) sharedRendererRef.current.down(stage, event);
  };
  const handleLiquidTargetFocus = (index, stage) => {
    if (!reuseRenderer || reduceMotion) return;
    focusedIndexRef.current = index;
    if (attachIndex(index)) sharedRendererRef.current.focus(stage);
  };
  const handleLiquidTargetBlur = (index, stage, event) => {
    if (!reuseRenderer || focusedIndexRef.current !== index) return;
    focusedIndexRef.current = null;
    sharedRendererRef.current.blur(stage, event);
    attachIndex(hoveredIndexRef.current ?? activeIndexRef.current);
  };
  const handleLiquidTargetKeyDown = (index, stage, event) => {
    if (!reuseRenderer || reduceMotion) return;
    if (attachIndex(index)) sharedRendererRef.current.keyDown(stage, event);
  };
  const handleLiquidTargetKeyUp = (index, stage, event) => {
    if (!reuseRenderer || reduceMotion) return;
    if (attachIndex(index)) sharedRendererRef.current.keyUp(stage, event);
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
        <ul ref={listRef} className="floating-nav-list">
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
              useSharedNavigationRenderer={reuseRenderer}
              onCenterValue={registerCenterValue}
              onLiquidStageReady={registerStage}
              onLiquidTargetEnter={handleLiquidTargetEnter}
              onLiquidTargetLeave={handleLiquidTargetLeave}
              onLiquidTargetDown={handleLiquidTargetDown}
              onLiquidTargetFocus={handleLiquidTargetFocus}
              onLiquidTargetBlur={handleLiquidTargetBlur}
              onLiquidTargetKeyDown={handleLiquidTargetKeyDown}
              onLiquidTargetKeyUp={handleLiquidTargetKeyUp}
            />
          ))}
        </ul>
      </nav>
    </div>
  );
}

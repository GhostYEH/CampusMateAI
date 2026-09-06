import { useCallback, useEffect, useRef, useState } from "react";
import { motion, useInView } from "motion/react";

function AnimatedItem({ index, delay = 0.1, layoutMode = "list", animateLayout = false, reducedMotion = false, onMouseEnter, onClick, children }) {
  const ref = useRef(null);
  const inView = useInView(ref, { amount: 0.4, once: false });
  const wrapperStyle = layoutMode === "grid" ? { cursor: "pointer" } : { marginBottom: "1rem", cursor: "pointer" };
  const motionContent = (
    <motion.div
      ref={ref}
      data-index={index}
      layout={animateLayout ? "position" : false}
      initial={reducedMotion ? false : { scale: 0.7, opacity: 0 }}
      animate={reducedMotion ? { scale: 1, opacity: 1 } : inView ? { scale: 1, opacity: 1 } : { scale: 0.7, opacity: 0 }}
      transition={reducedMotion ? { duration: 0 } : {
        layout: { type: "spring", stiffness: 520, damping: 42, mass: 0.28 },
        opacity: { duration: 0.22, delay, ease: "easeOut" },
        scale: { duration: 0.22, delay, ease: "easeOut" },
      }}
      style={{ transformOrigin: "center top" }}
    >
      {children}
    </motion.div>
  );
  return (
    <div className="animated-list-flip-wrapper" onMouseEnter={onMouseEnter} onClick={onClick} style={wrapperStyle}>
      {motionContent}
    </div>
  );
}

export default function AnimatedList({
  items = [],
  renderItem,
  onItemSelect,
  showGradients = true,
  enableArrowNavigation = true,
  className = "",
  itemClassName = "",
  displayScrollbar = true,
  initialSelectedIndex = -1,
  maxHeight = "72vh",
  layout = "list",
  animateLayout = false,
  reducedMotion = false,
  topFadeOnScroll = false,
}) {
  const listRef = useRef(null);
  const [selectedIndex, setSelectedIndex] = useState(initialSelectedIndex);
  const selectedIndexRef = useRef(initialSelectedIndex);
  const keyboardNavRef = useRef(false);
  const [topGradientOpacity, setTopGradientOpacity] = useState(0);
  const [bottomGradientOpacity, setBottomGradientOpacity] = useState(1);

  const commitSelected = useCallback((next) => {
    const value = typeof next === "function" ? next(selectedIndexRef.current) : next;
    selectedIndexRef.current = value;
    setSelectedIndex(value);
  }, []);

  const handleScroll = useCallback((event) => {
    const { scrollTop, scrollHeight, clientHeight } = event.currentTarget;
    if (topFadeOnScroll) {
      const progress = Math.min(Math.max(scrollTop / 112, 0), 1);
      event.currentTarget.style.setProperty("--animated-list-top-alpha", String(Number((1 - progress).toFixed(3))));
      event.currentTarget.style.setProperty("--animated-list-mid-alpha", String(Number((1 - progress * 0.72).toFixed(3))));
    }
    if (showGradients) {
      setTopGradientOpacity(Math.min(scrollTop / 50, 1));
      const bottomDistance = scrollHeight - (scrollTop + clientHeight);
      setBottomGradientOpacity(scrollHeight <= clientHeight ? 0 : Math.min(bottomDistance / 50, 1));
    }
  }, [showGradients, topFadeOnScroll]);

  const handleItemMouseEnter = useCallback((index) => commitSelected(index), [commitSelected]);
  const handleItemClick = useCallback((item, index) => {
    commitSelected(index);
    if (onItemSelect) onItemSelect(item, index);
  }, [commitSelected, onItemSelect]);

  useEffect(() => {
    if (!enableArrowNavigation) return undefined;
    const handleKeyDown = (event) => {
      const total = items.length;
      if (event.key === "ArrowDown" || (event.key === "Tab" && !event.shiftKey)) {
        event.preventDefault();
        keyboardNavRef.current = true;
        commitSelected((prev) => Math.min(prev + 1, total - 1));
      } else if (event.key === "ArrowUp" || (event.key === "Tab" && event.shiftKey)) {
        event.preventDefault();
        keyboardNavRef.current = true;
        commitSelected((prev) => Math.max(prev - 1, 0));
      } else if (event.key === "Enter") {
        const current = selectedIndexRef.current;
        if (current >= 0 && current < total) {
          event.preventDefault();
          if (onItemSelect) onItemSelect(items[current], current);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enableArrowNavigation, items, onItemSelect, commitSelected]);

  useEffect(() => {
    if (!keyboardNavRef.current || selectedIndex < 0 || !listRef.current) return;
    const container = listRef.current;
    const selectedItem = container.querySelector(`[data-index="${selectedIndex}"]`);
    if (selectedItem) {
      const extraMargin = 50;
      const containerScrollTop = container.scrollTop;
      const containerHeight = container.clientHeight;
      const itemTop = selectedItem.offsetTop;
      const itemBottom = itemTop + selectedItem.offsetHeight;
      if (itemTop < containerScrollTop + extraMargin) {
        container.scrollTo({ top: itemTop - extraMargin, behavior: "smooth" });
      } else if (itemBottom > containerScrollTop + containerHeight - extraMargin) {
        container.scrollTo({ top: itemBottom - containerHeight + extraMargin, behavior: "smooth" });
      }
    }
    keyboardNavRef.current = false;
  }, [selectedIndex]);

  const scrollClassName = `animated-list-scroll ${displayScrollbar ? "" : "animated-list-scroll--hidden"} ${layout === "grid" ? "animated-list-scroll--grid" : ""} ${topFadeOnScroll ? "animated-list-scroll--top-fade" : ""}`.trim();
  const topFadeStyle = topFadeOnScroll ? { "--animated-list-top-alpha": 1, "--animated-list-mid-alpha": 1 } : {};
  const scrollContent = (
    <div ref={listRef} onScroll={handleScroll} className={scrollClassName} style={{ maxHeight, ...topFadeStyle }}>
      {items.map((item, index) => (
        <AnimatedItem
          key={item?.id ?? index}
          index={index}
          delay={0.1}
          layoutMode={layout}
          animateLayout={animateLayout}
          reducedMotion={reducedMotion}
          onMouseEnter={() => handleItemMouseEnter(index)}
          onClick={() => handleItemClick(item, index)}
        >
          <div className={`animated-list-item ${selectedIndex === index ? "is-selected" : ""} ${itemClassName}`.trim()}>
            {renderItem ? renderItem(item, { index, selected: selectedIndex === index }) : item}
          </div>
        </AnimatedItem>
      ))}
    </div>
  );

  return (
    <div className={`scroll-list-container ${className}`.trim()} style={{ position: "relative", width: "100%" }}>
      {scrollContent}
      {showGradients && (
        <>
          <div className="animated-list-gradient animated-list-gradient--top" style={{ opacity: topGradientOpacity }} />
          <div className="animated-list-gradient animated-list-gradient--bottom" style={{ opacity: bottomGradientOpacity }} />
        </>
      )}
    </div>
  );
}

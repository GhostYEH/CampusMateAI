import { useCallback, useEffect, useLayoutEffect, useRef } from "react";

/**
 * 右栏面板头里的课程标签条。
 *
 * 面板头的"名字那一半"**就是**这条标签条，所以开多少门课都不占新的 chrome 行。
 * 没有上限也没有淘汰，因此它必须能无限退化：标签缩到地板宽度后改为横向滚动。
 *
 * 三处细节是刻意的，缺一个就会重演参考项目里踩过的坑：
 *
 * 1. **"还有更多"需要两个信号。** 只有边缘渐隐会让用户以为内容被裁坏了；只有
 *    滚动条则在没有滚动前完全不可见。所以两者都要：渐隐表示"这里断开了但还有"，
 *    手绘的滚动条表示"可以拖"。原生 overlay 滚动条在未滚动时不占位也不绘制，
 *    等于一个必须先猜到才存在的提示，因此被隐藏并重画。
 * 2. **只在活动标签或标签数量变化时把它滚进视野。** 每次渲染都 `scrollIntoView`
 *    比不做还糟：用户手动滚开去看别的标签，一次无关的渲染就会把它拽回来。
 * 3. **要瞄两次。** 面板宽度有过渡，第一次算出来的滚动视口可能还是它正在离开的
 *    宽度，于是活动标签停在半出屏的位置。
 */

/** 长于面板宽度过渡，保证第二次瞄准落在稳定后的视口上。 */
const SETTLE_MS = 340;
/** 标签极多时手绘滑块仍然抓得住。 */
const THUMB_MIN_PX = 28;

export default function WorkspaceCourseTabs({ tabs = [], activeCourseId, onActivate, onClose }) {
  const stripRef = useRef(null);
  const revealTimer = useRef(null);

  /** 哪一侧还有更多、以及手绘滚动条的位置。只算尺寸与偏移，样式留在 CSS。 */
  const paintEdges = useCallback(() => {
    const strip = stripRef.current;
    if (!strip) return;
    const overflow = strip.scrollWidth - strip.clientWidth;
    if (overflow <= 1) {
      strip.dataset.more = "none";
      strip.style.backgroundSize = "";
      strip.style.backgroundPosition = "";
      return;
    }
    const left = strip.scrollLeft > 1;
    const right = strip.scrollLeft < overflow - 1;
    strip.dataset.more = left && right ? "both" : left ? "left" : "right";
    const width = Math.max(THUMB_MIN_PX, Math.round(strip.clientWidth * (strip.clientWidth / strip.scrollWidth)));
    const x = Math.round((strip.clientWidth - width) * (strip.scrollLeft / overflow));
    strip.style.backgroundSize = `${width}px 3px, 100% 3px`;
    strip.style.backgroundPosition = `${x}px bottom, 0 bottom`;
  }, []);

  const activeFullyVisible = useCallback(() => {
    const strip = stripRef.current;
    const element = strip?.querySelector('[aria-selected="true"]');
    if (!strip || !element) return true;
    const stripBox = strip.getBoundingClientRect();
    const tabBox = element.getBoundingClientRect();
    return tabBox.left >= stripBox.left - 0.5 && tabBox.right <= stripBox.right + 0.5;
  }, []);

  const revealActive = useCallback(() => {
    const aim = () => {
      const element = stripRef.current?.querySelector('[aria-selected="true"]');
      element?.scrollIntoView({ block: "nearest", inline: "nearest" });
    };
    aim();
    if (revealTimer.current) window.clearTimeout(revealTimer.current);
    revealTimer.current = window.setTimeout(aim, SETTLE_MS);
  }, []);

  // 首帧之前就画好，渐隐不会晚一帧。
  useLayoutEffect(() => { paintEdges(); }, [paintEdges, tabs]);

  // 只有"换了活动标签"或"标签数变了"才重新瞄准。
  useEffect(() => {
    revealActive();
    return () => { if (revealTimer.current) window.clearTimeout(revealTimer.current); };
  }, [activeCourseId, tabs.length, revealActive]);

  // rail 可拖宽，所以标签条可能在**状态完全没变**的情况下被挤窄。
  useEffect(() => {
    const strip = stripRef.current;
    if (!strip || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      paintEdges();
      // 只有真的把活动标签挤出视野才重新瞄准，手滚过的位置保持不动。
      if (!activeFullyVisible()) revealActive();
    });
    observer.observe(strip);
    return () => observer.disconnect();
  }, [activeFullyVisible, paintEdges, revealActive]);

  const onKeyDown = (event) => {
    const strip = stripRef.current;
    if (!strip) return;
    const items = [...strip.querySelectorAll(".ow-ctab")];
    const current = event.target instanceof Element ? event.target.closest(".ow-ctab") : null;
    const index = current ? items.indexOf(current) : -1;
    if (index < 0) return;

    // Delete/Backspace 关闭当前标签——这是那个"刻意不作为 tab stop"的 × 的键盘路径。
    if (event.key === "Delete" || event.key === "Backspace") {
      event.preventDefault();
      const id = current?.dataset.courseId;
      if (!id) return;
      onClose?.(id);
      window.requestAnimationFrame(() => {
        const rest = [...(stripRef.current?.querySelectorAll(".ow-ctab") ?? [])];
        rest[Math.min(index, rest.length - 1)]?.focus();
      });
      return;
    }

    let next = null;
    if (event.key === "ArrowRight") next = (index + 1) % items.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + items.length) % items.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = items.length - 1;
    else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      const id = current?.dataset.courseId;
      if (id) onActivate?.(id);
      return;
    }
    if (next === null) return;
    event.preventDefault();
    const target = items[next];
    const id = target?.dataset.courseId;
    if (!id) return;
    target.focus();
    onActivate?.(id);
  };

  if (!tabs.length) return null;

  return <div
    ref={stripRef}
    className="ow-ctabs"
    role="tablist"
    aria-label="已打开的课堂"
    aria-orientation="horizontal"
    data-more="none"
    onScroll={paintEdges}
    onKeyDown={onKeyDown}
  >
    {tabs.map((tab) => {
      const selected = tab.id === activeCourseId;
      const name = tab.name || "未命名课堂";
      // 用 div 而不是 button：它内部有一个真实的关闭 button，交互元素不能嵌套。
      return <div
        key={tab.id}
        role="tab"
        data-course-id={tab.id}
        aria-selected={selected}
        tabIndex={selected ? 0 : -1}
        title={name}
        className={`ow-ctab${selected ? " ow-ctab-on" : ""}`}
        onClick={(event) => {
          if (event.target instanceof Element && event.target.closest(".ow-ctab-x")) return;
          onActivate?.(tab.id);
        }}
      >
        <span className="ow-ctab-name">{name}</span>
        <button
          type="button"
          tabIndex={-1}
          className="ow-ctab-x"
          aria-label={`关闭标签页《${name}》`}
          onClick={(event) => { event.stopPropagation(); onClose?.(tab.id); }}
        >
          <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" aria-hidden="true">
            <path d="m4.8 4.8 6.4 6.4M11.2 4.8l-6.4 6.4" />
          </svg>
        </button>
      </div>;
    })}
  </div>;
}

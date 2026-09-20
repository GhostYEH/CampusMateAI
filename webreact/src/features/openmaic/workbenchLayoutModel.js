/**
 * 工作台舞台的几何计算与「编辑 / 播放」模式的推导。
 *
 * 这两件事都在参考项目里被证明过一次，而且都是**踩过坑之后**的写法，所以原样
 * 搬过来、不重新发明：
 *
 * 1. **16:9 不是 CSS。** 用 `aspect-ratio` 或 padding-bottom 撑出来的框，在
 *    画布首次挂载时会因为宿主还在 settle（pane 列宽变化、字体回流、rail 异步
 *    出现）而读到过期的尺寸，表现为"第一次打开舞台是歪的，拖一下分隔条才对"。
 *    参考项目的解法是 ResizeObserver + 像素盒，见 `ContainBox`。
 * 2. **模式是推导出来的，不是状态。** 面板里的课堂是"编辑锁定"的：进播放的唯一
 *    门是用户按「开始学习」。任何"编辑还没准备好"的中间态都必须落在 `loading`
 *    上，绝不能落到播放——否则会先闪一屏播放 chrome 再跳回编辑。
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

/** 16:9。舞台与卡片都用它。 */
export const CLASSROOM_ASPECT_RATIO = 16 / 9;

/**
 * 容器内能放下的最大 16:9 盒子（letterbox）。
 * 任何非有限/非正数输入都返回 0，调用方据此回退到 100%，而不是渲染一个 NaN 尺寸。
 */
export function containBox(containerWidth, containerHeight, ratio) {
  if (
    !Number.isFinite(containerWidth) ||
    !Number.isFinite(containerHeight) ||
    !Number.isFinite(ratio) ||
    containerWidth <= 0 ||
    containerHeight <= 0 ||
    ratio <= 0
  ) {
    return { width: 0, height: 0 };
  }
  if (containerWidth / containerHeight > ratio) {
    return { width: containerHeight * ratio, height: containerHeight };
  }
  return { width: containerWidth, height: containerWidth / ratio };
}

/** 与宿主等宽、高度按 16:9 推出（超出部分由调用方裁掉）。 */
export function fillWidthBox(containerWidth, ratio) {
  if (!Number.isFinite(containerWidth) || !Number.isFinite(ratio) || containerWidth <= 0 || ratio <= 0) {
    return { width: 0, height: 0 };
  }
  return { width: containerWidth, height: containerWidth / ratio };
}

/** 会影响布局的 CSS 属性。只有这些的 transitionend 才意味着宿主可能换了尺寸。 */
const LAYOUT_PROPERTIES = new Set([
  "width", "height", "min-width", "max-width", "min-height", "max-height",
  "flex", "flex-basis", "flex-grow", "flex-shrink", "gap", "row-gap", "column-gap",
  "grid-template-columns", "grid-template-rows",
  "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
  "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
  "border-width", "border-top-width", "border-right-width", "border-bottom-width", "border-left-width",
  "inset", "top", "right", "bottom", "left",
]);

/**
 * 舞台的 16:9 像素盒。
 *
 * 参考实现里有**四层**测量，缺一层就会出现"首次打开尺寸不对"：
 * 首次同步测量、ResizeObserver（同时观察父元素）、400ms 兜底轮询、以及
 * 1500ms 的 rAF settle 循环 + 布局类 transition/animation 结束后重新 settle。
 * 只有尺寸真的变了才 setState，所以稳定布局下这些重复测量几乎不花钱。
 */
export function useContainBox({ ratio = CLASSROOM_ASPECT_RATIO, fit = "contain" } = {}) {
  const hostRef = useRef(null);
  const [box, setBox] = useState({ width: 0, height: 0 });

  useLayoutEffect(() => {
    const element = hostRef.current;
    if (!element) return;

    const apply = (next) => {
      setBox((current) =>
        current.width === next.width && current.height === next.height ? current : next,
      );
    };

    const measure = () => {
      apply(
        fit === "fill-width"
          ? fillWidthBox(element.clientWidth, ratio)
          : containBox(element.clientWidth, element.clientHeight, ratio),
      );
    };

    measure();

    let observer = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(measure);
      observer.observe(element);
      // 父元素往往先一步拿到新宽度（rail 换宽、grid 轨道重分配），也观察它。
      if (element.parentElement) observer.observe(element.parentElement);
    }

    const backstop = window.setInterval(measure, 400);

    let settleRaf = 0;
    let settleUntil = 0;
    const loop = () => {
      measure();
      settleRaf = performance.now() < settleUntil ? window.requestAnimationFrame(loop) : 0;
    };
    const kick = (ms) => {
      settleUntil = performance.now() + ms;
      if (!settleRaf) settleRaf = window.requestAnimationFrame(loop);
    };
    kick(1500);

    // 宿主的尺寸也可能通过 CSS 过渡/动画变化，而 RO 是逐帧跟的；过渡**结束**才是
    // "已经稳定"的权威信号。挂在 document 的捕获阶段，因为发生变化的多半是宿主的
    // 祖先或兄弟（rail、pane 列），挂在宿主子树里永远看不到。
    const onSettled = (event) => {
      if (event.type === "transitionend") {
        const property = event.propertyName;
        if (property && !LAYOUT_PROPERTIES.has(property)) return;
      }
      kick(400);
    };
    document.addEventListener("transitionend", onSettled, true);
    document.addEventListener("animationend", onSettled, true);

    return () => {
      window.clearInterval(backstop);
      if (settleRaf) window.cancelAnimationFrame(settleRaf);
      document.removeEventListener("transitionend", onSettled, true);
      document.removeEventListener("animationend", onSettled, true);
      observer?.disconnect();
    };
  }, [fit, ratio]);

  return { hostRef, box };
}

/**
 * 面板内课堂的 chrome 模式。
 *
 * `playback` 只有一个来源：用户按了「开始学习」。其余任何"还不够编辑"的情况都
 * 返回 `loading`，这是一个中性的等待壳，不是播放壳。
 */
export function resolveStageChromeMode({
  hosted = true,
  storedMode = "edit",
  workbenchShowingClassroom = true,
  workbenchLearning = false,
  isEditable = false,
  hasCurrentScene = false,
  stageMatchesHost = true,
  editorReady = true,
  editorLoadFailed = false,
} = {}) {
  if (!hosted) return storedMode;
  if (workbenchLearning) return "playback";
  if (!stageMatchesHost) return "loading";
  if (!workbenchShowingClassroom) return "loading";
  if (!isEditable || !hasCurrentScene) return "loading";
  if (editorLoadFailed) return "loading";
  return editorReady ? "edit" : "loading";
}

/** 参考实现的中断常量：窄缝折叠、以及判定"窄屏互斥"。 */
export const NARROW_QUERY = "(max-width: 1023px)";

/**
 * 窄屏下可以被选中的面板。
 *
 * 这个列表是**唯一**的合法取值来源：模型、渲染和测试都从它派生，所以"新增一个
 * 面板却忘了在切换器里给出入口"或者"切换器给出一个渲染不出来的面板"都不可能
 * 悄悄发生。
 */
export const NARROW_PANES = Object.freeze(["rail", "classroom", "tools"]);

/** 未知面板名的回退目标：课堂是窄屏的默认视图。 */
export const NARROW_PANE_FALLBACK = "classroom";

/**
 * 是否是"窄屏"（<1024）。
 *
 * 参考项目在窄屏下只是隐藏 rail，没有互斥；本项目的需求明确要求 768–1023 走
 * **互斥单面板**，所以这里提供一个显式的判断，由 `resolveWorkbenchLayout` 消费。
 */
export function useNarrowViewport(query = NARROW_QUERY) {
  const [narrow, setNarrow] = useState(() =>
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia(query).matches
      : false,
  );
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(query);
    const apply = () => setNarrow(media.matches);
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [query]);
  return narrow;
}

/**
 * 三栏该显示哪些。
 *
 * 两条规则来自参考项目的实战结论，照搬：
 *
 * - **收起 rail 时不能再收起最后一个可见面板。** 折叠一个没人接手的列会把用户
 *   留在空工作台上。
 * - **窄屏互斥。** <1024 时三栏并排会把 16:9 舞台压到无法使用；此时**恰好一个**
 *   面板占据整个可用工作区，其余两个都完全不渲染。
 *
 * 窄屏这一支此前是错的，而且错得很隐蔽：它让 rail（mini，60px）**和**当前内容
 * 面板同时在 `flex` 行里，于是一个 60px 的目录栏永远挤着 320/390/768 上的舞台；
 * 而 `classroom` 又被无条件置为 `true`，所以切到「工具」时课堂仍然在渲染。
 * 现在三者的不变式是显式的：
 *
 *     `rail` / `classroom` / `tools` 中**恰好一个**为 true。
 *
 * 未激活的面板不是"被视觉隐藏"，而是根本不进 DOM——一个 `display: none` 的面板
 * 仍然会保留可聚焦元素、仍然要跑它的数据加载，那正是这条需求要杜绝的。
 */
export function resolveWorkbenchLayout({
  narrow = false,
  railCollapsed = false,
  activePane = NARROW_PANE_FALLBACK,
  classroomOpen = true,
  toolsCollapsed = false,
} = {}) {
  if (narrow) {
    // 未知取值退到课堂，而不是什么都不显示——空工作台比默认面板更难理解。
    const pane = NARROW_PANES.includes(activePane) ? activePane : NARROW_PANE_FALLBACK;
    return {
      narrow: true,
      pane,
      // 互斥：只有被选中的那一个为 true，其余两个连宽度都不占。
      rail: pane === "rail",
      railMini: false,
      classroom: pane === "classroom",
      tools: pane === "tools",
      // 窄屏没有"缝上的重开标签"这回事，切换器本身就是那个入口。
      classroomTab: false,
    };
  }
  // 宽屏：rail 可折叠；工具区独立成一栏，可单独收起。
  return {
    narrow: false,
    pane: "wide",
    rail: !railCollapsed,
    railMini: railCollapsed,
    classroom: classroomOpen,
    tools: !toolsCollapsed,
    classroomTab: !classroomOpen,
  };
}

/** 拖拽调宽。返回经过 clamp 的宽度，并在拖动期间锁住光标与选中。 */
export function useResizableWidth({ initial, min, max, storageKey = "" }) {
  const [width, setWidth] = useState(() => {
    if (typeof window === "undefined" || !storageKey) return initial;
    try {
      const raw = window.localStorage.getItem(storageKey);
      const parsed = Number(raw);
      return Number.isFinite(parsed) && parsed >= min && parsed <= max ? parsed : initial;
    } catch { return initial; }
  });
  const clamp = useCallback((value) => Math.round(Math.max(min, Math.min(max, value))), [min, max]);

  const commit = useCallback((value) => {
    const next = clamp(value);
    setWidth(next);
    if (storageKey && typeof window !== "undefined") {
      try { window.localStorage.setItem(storageKey, String(next)); } catch { /* 隐私模式 */ }
    }
  }, [clamp, storageKey]);

  return { width, clamp, commit, reset: useCallback(() => commit(initial), [commit, initial]) };
}

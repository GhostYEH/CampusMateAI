import * as React from "react";
import { useCallback, useState } from "react";
import {
  PanelLeftClose,
  PieChart,
  Cpu,
  MousePointer2,
  BookOpen,
  Globe,
  Trophy,
} from "lucide-react";

import { cn } from "../utils/cn.js";
import { SceneThumbnailContent } from "./scene-thumbnail.jsx";

/**
 * 逐字移植自参考项目 `components/stage/scene-sidebar.tsx` 的**左侧场景栏视觉外壳**。
 *
 * 机械改写清单：
 *  - 擦除 TypeScript 类型；`@/lib/utils` -> `../utils/cn.js`；去掉 `'use client'`。
 *  - `useRouter()` -> 丢弃（logo 按钮改成 `<a href="/">`，与参考的 `router.push('/')`
 *    同一语义）。
 *  - `useI18n()` / `t('key')` -> 参考 `lib/i18n/locales/zh-CN.json` 里的简体中文原值
 *    （见文件底部 `ZH` 常量，逐条注明来源 key）。
 *  - zustand（`useStageStore` / `useCanvasStore`）-> props。`scenes` / `currentSceneId`
 *    由调用方注入；`viewportSize` / `viewportRatio` 变成可选 props 并有参考默认值。
 *  - `SlideThumbnail` / `ThumbnailInteractive`（本仓库无此模块）-> 占位实现，
 *    可由 `renderSlideThumbnail` / `renderInteractiveThumbnail` 回调接回真组件。
 *
 * 结构、类名、内联 style 均与参考逐字一致（含拖拽调宽手柄、行高亮、
 * 缩略图外框、hover 遮罩）。参考里只读的 local state 改用 `useState`。
 *
 * 与参考的差异（均为**有意**的、为了在无 store 环境里可用）：
 *  1. `generatingOutlines` / `failedOutlines` / `generationStatus` / `onRetryOutline`
 *     驱动的「下一个生成中占位行（skeleton + shimmer + 失败重试）」被移除
 *     —— 它 100% 依赖 stage store 与生成轮询，用户已显式授权删除。
 *     「课程完成」占位行**保留**：它只依赖 `isCourseComplete` 与 `currentSceneId`，
 *     条件里原有的 `generatingOutlines.length === 0` 退化为恒真。
 *  2. `useNearViewport` 视口门控 -> 走 `SceneThumbnailContent` 的 `visible` prop
 *     （默认 true）。视口门控只是性能优化，不改变布局。
 */

const ZH = {
  // zh-CN.json > generation.backToHome
  backToHome: "返回首页",
  // zh-CN.json > stage.courseComplete
  courseComplete: "课程完成",
};

const DEFAULT_WIDTH = 220;
const MIN_WIDTH = 170;
const MAX_WIDTH = 400;

/** 参考项目 `lib/store/stage.ts` 的 PENDING_SCENE_ID，用于判断「课程完成」占位行是否选中。 */
export const PENDING_SCENE_ID = "__pending__";

/**
 * @param {object} props
 * @param {boolean} props.collapsed 是否收起（收起时宽度 0 且内容 `hidden`）
 * @param {(collapsed: boolean) => void} props.onCollapseChange 收起状态变更回调
 * @param {Array<{id: string, title: string, type: string, order?: number, content?: any}>} [props.scenes] 场景列表
 * @param {string} [props.currentSceneId] 当前场景 id（可能不在 scenes 中，此时无行高亮）
 * @param {(sceneId: string) => void} [props.onSceneSelect] 点击某个场景
 * @param {boolean} [props.isCourseComplete] 是否展示「课程完成」占位行
 * @param {number} [props.viewportSize] 幻灯片视口宽度（参考项目来自 canvas store）
 * @param {number} [props.viewportRatio] 幻灯片视口宽高比
 * @param {() => void} [props.onLogoClick] logo 点击；不传则用 `<a href="/">`
 * @param {string} [props.logoSrc] logo 图片地址，默认沿用参考项目的 `/logo-horizontal.png`
 * @param {React.ReactNode} [props.headerSlot] 替换 logo 行的自定义内容
 * @param {(args: object) => React.ReactNode} [props.renderSlideThumbnail] 接入真实幻灯片缩略图
 * @param {(args: object) => React.ReactNode} [props.renderInteractiveThumbnail] 接入真实 iframe 缩略图
 */
export function MaicSceneSidebar({
  collapsed,
  onCollapseChange,
  scenes,
  currentSceneId,
  onSceneSelect,
  isCourseComplete = false,
  viewportSize = 1080,
  viewportRatio = 16 / 9,
  onLogoClick,
  logoSrc = "/logo-horizontal.png",
  headerSlot,
  renderSlideThumbnail,
  renderInteractiveThumbnail,
}) {
  const list = Array.isArray(scenes) ? scenes : [];

  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_WIDTH);
  // 拖动中用 ref 会绕过 React 的渲染时机（参考实现改 ref 不触发重渲染，
  // 靠 setSidebarWidth 的渲染顺带读取，行为等价但依赖时序）。这里用 state：
  // 目的只是「拖动期间关掉 width 过渡」，与参考的可见效果一致。
  const [isDragging, setIsDragging] = useState(false);

  const handleDragStart = useCallback(
    (e) => {
      e.preventDefault();
      setIsDragging(true);
      const startX = e.clientX;
      const startWidth = sidebarWidth;

      const handleMouseMove = (me) => {
        const delta = me.clientX - startX;
        const newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidth + delta));
        setSidebarWidth(newWidth);
      };

      const handleMouseUp = () => {
        setIsDragging(false);
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      };

      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    },
    [sidebarWidth],
  );

  const getSceneTypeIcon = (type) => {
    const icons = {
      slide: BookOpen,
      quiz: PieChart,
      interactive: MousePointer2,
      pbl: Cpu,
    };
    return icons[type] || BookOpen;
  };

  const displayWidth = collapsed ? 0 : sidebarWidth;

  return (
    <div
      style={{
        width: displayWidth,
        transition: isDragging ? "none" : "width 0.3s ease",
      }}
      className="bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border-r border-gray-100 dark:border-gray-800 shadow-[2px_0_24px_rgba(0,0,0,0.02)] flex flex-col shrink-0 z-20 relative overflow-visible"
    >
      {/* Drag handle */}
      {!collapsed && (
        <div
          onMouseDown={handleDragStart}
          className="absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize z-50 group hover:bg-purple-400/30 dark:hover:bg-purple-600/30 active:bg-purple-500/40 dark:active:bg-purple-500/40 transition-colors"
        >
          <div className="absolute right-0.5 top-1/2 -translate-y-1/2 w-0.5 h-8 rounded-full bg-gray-300 dark:bg-gray-600 group-hover:bg-purple-400 dark:group-hover:bg-purple-500 transition-colors" />
        </div>
      )}

      <div className={cn("flex flex-col w-full h-full overflow-hidden", collapsed && "hidden")}>
        {/* Logo Header */}
        <div className="h-10 flex items-center justify-between shrink-0 relative mt-3 mb-1 px-3">
          {headerSlot ?? (
            <a
              href="/"
              onClick={
                onLogoClick
                  ? (event) => {
                      event.preventDefault();
                      onLogoClick();
                    }
                  : undefined
              }
              className="flex items-center gap-2 cursor-pointer rounded-lg px-1.5 -mx-1.5 py-1 -my-1 hover:bg-gray-100/80 dark:hover:bg-gray-800/60 active:scale-[0.97] transition-all duration-150"
              title={ZH.backToHome}
            >
              <img src={logoSrc} alt="magic class" className="h-6" />
            </a>
          )}
          <button
            onClick={() => onCollapseChange(true)}
            className="w-7 h-7 shrink-0 rounded-lg flex items-center justify-center bg-gray-100/80 dark:bg-gray-800/80 text-gray-500 dark:text-gray-400 ring-1 ring-black/[0.04] dark:ring-white/[0.06] hover:bg-gray-200/90 dark:hover:bg-gray-700/90 hover:text-gray-700 dark:hover:text-gray-200 active:scale-90 transition-all duration-200"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        </div>

        {/* Scenes List */}
        <div
          data-testid="scene-list"
          className="flex-1 overflow-y-auto overflow-x-hidden p-2 space-y-2 scrollbar-hide pt-1"
        >
          {list.map((scene, index) => {
            const isActive = currentSceneId === scene.id;
            const Icon = getSceneTypeIcon(scene.type);
            const isSlide = scene.type === "slide";
            const isInteractive = scene.type === "interactive";

            return (
              <div
                key={scene.id}
                data-testid="scene-item"
                onClick={() => {
                  if (onSceneSelect) {
                    onSceneSelect(scene.id);
                  }
                }}
                className={cn(
                  "group relative rounded-lg transition-all duration-200 cursor-pointer flex flex-col gap-1 p-1.5",
                  isActive
                    ? "bg-purple-50 dark:bg-purple-900/20 ring-1 ring-purple-200 dark:ring-purple-700"
                    : "hover:bg-gray-50/80 dark:hover:bg-gray-800/50",
                )}
              >
                {/* Scene Header */}
                <div className="flex justify-between items-center px-2 pt-0.5">
                  <div className="flex items-center gap-2 max-w-full">
                    <span
                      className={cn(
                        "text-[10px] font-black w-4 h-4 rounded-full flex items-center justify-center shrink-0",
                        isActive
                          ? "bg-purple-600 dark:bg-purple-500 text-white shadow-sm shadow-purple-500/30"
                          : "bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400",
                      )}
                    >
                      {index + 1}
                    </span>
                    <span
                      data-testid="scene-title"
                      className={cn(
                        "text-xs font-bold truncate transition-colors",
                        isActive
                          ? "text-purple-700 dark:text-purple-300"
                          : "text-gray-600 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-gray-100",
                      )}
                    >
                      {scene.title}
                    </span>
                  </div>
                </div>

                {/* Thumbnail */}
                <div className="relative aspect-video w-full rounded overflow-hidden bg-gray-100 dark:bg-gray-800 ring-1 ring-black/5 dark:ring-white/5">
                  <div className="absolute inset-0 flex items-center justify-center">
                    {ListThumbnail({
                      scene,
                      Icon,
                      sidebarWidth,
                      viewportSize,
                      viewportRatio,
                      renderSlideThumbnail,
                      renderInteractiveThumbnail,
                    })}

                    {isSlide && (
                      <div
                        className={cn(
                          "absolute inset-0 bg-purple-500/0 transition-colors",
                          isActive
                            ? "bg-purple-500/0"
                            : "group-hover:bg-black/5 dark:group-hover:bg-white/5",
                        )}
                      />
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {/* 课程完成占位行：参考实现里 `isCourseComplete && generatingOutlines.length === 0`。
              生成队列被丢弃后条件退化为 `isCourseComplete`；PENDING_SCENE_ID 仍沿用参考常量。 */}
          {isCourseComplete &&
            (() => {
              const isActive = currentSceneId === PENDING_SCENE_ID;
              return (
                <div
                  key="course-complete-slot"
                  onClick={() => {
                    if (onSceneSelect) {
                      onSceneSelect(PENDING_SCENE_ID);
                    }
                  }}
                  className={cn(
                    "group relative rounded-lg flex flex-col gap-1 p-1.5 transition-all duration-200 cursor-pointer hover:bg-amber-50/60 dark:hover:bg-amber-900/10",
                    !isActive && "opacity-80",
                    isActive &&
                      "bg-amber-50 dark:bg-amber-900/20 ring-1 ring-amber-200 dark:ring-amber-700 opacity-100",
                  )}
                >
                  <div className="flex justify-between items-center px-2 pt-0.5">
                    <div className="flex items-center gap-2 max-w-full">
                      <span
                        className={cn(
                          "text-[10px] font-black w-4 h-4 rounded-full flex items-center justify-center shrink-0",
                          isActive
                            ? "bg-amber-500 dark:bg-amber-400 text-white shadow-sm shadow-amber-500/30"
                            : "bg-amber-100 dark:bg-amber-900/40 text-amber-600 dark:text-amber-400",
                        )}
                      >
                        {list.length + 1}
                      </span>
                      <span
                        className={cn(
                          "text-xs font-bold truncate transition-colors",
                          isActive
                            ? "text-amber-700 dark:text-amber-300"
                            : "text-amber-600 dark:text-amber-400",
                        )}
                      >
                        {ZH.courseComplete}
                      </span>
                    </div>
                  </div>
                  <div
                    className={cn(
                      "relative aspect-video w-full rounded overflow-hidden ring-1 flex items-center justify-center transition-all",
                      "bg-amber-50/80 dark:bg-amber-950/20",
                      isActive
                        ? "ring-amber-300 dark:ring-amber-700"
                        : "ring-amber-100 dark:ring-amber-900/40",
                    )}
                  >
                    {/* soft radial glow */}
                    <div
                      className="absolute inset-0"
                      style={{
                        background:
                          "radial-gradient(circle at 50% 55%, rgba(251, 191, 36, 0.14), transparent 65%)",
                      }}
                    />
                    {/* sparkles (subtle) */}
                    <svg
                      viewBox="0 0 20 20"
                      className="absolute top-1 right-1.5 w-1.5 h-1.5 text-amber-300/70 dark:text-amber-400/60"
                      aria-hidden
                    >
                      <path
                        d="M10 1 L12 8 L19 10 L12 12 L10 19 L8 12 L1 10 L8 8 Z"
                        fill="currentColor"
                      />
                    </svg>
                    <svg
                      viewBox="0 0 20 20"
                      className="absolute bottom-1 left-1.5 w-1 h-1 text-amber-300/60 dark:text-amber-400/50"
                      aria-hidden
                    >
                      <path
                        d="M10 1 L12 8 L19 10 L12 12 L10 19 L8 12 L1 10 L8 8 Z"
                        fill="currentColor"
                      />
                    </svg>
                    <Trophy
                      className="relative w-8 h-8 text-amber-500 dark:text-amber-400"
                      strokeWidth={1.6}
                    />
                  </div>
                </div>
              );
            })()}
        </div>

        {/* Spacer to push toggle button area */}
        <div className="mt-auto" />
      </div>
    </div>
  );
}

/**
 * 单行缩略图分支选择。参考实现把这段 JSX 直接内联在 `scenes.map` 里；
 * 这里抽成函数只是为了避免过深的缩进，**分支顺序与各分支的类名逐字不变**。
 */
function ListThumbnail({
  scene,
  Icon,
  sidebarWidth,
  viewportSize,
  viewportRatio,
  renderSlideThumbnail,
  renderInteractiveThumbnail,
}) {
  // 参考实现把这段分支内联在 `scenes.map` 的回调里，`isInteractive` 是那个回调的
  // 局部常量。抽成独立函数时必须把同一判断一起带过来，否则 interactive 分支会在
  // 求值时抛 `isInteractive is not defined`，整个侧栏随之白屏。
  const isInteractive = scene.type === "interactive";

  if (scene.type === "slide") {
    const slideContent = scene.content;
    if (slideContent) {
      return (
        <SceneThumbnailContent
          scene={scene}
          size={Math.max(100, sidebarWidth - 28)}
          viewportSize={viewportSize}
          viewportRatio={viewportRatio}
          visible
          renderSlideThumbnail={renderSlideThumbnail}
          renderInteractiveThumbnail={renderInteractiveThumbnail}
        />
      );
    }
    return <FallbackMockup Icon={Icon} type={scene.type} />;
  }

  if (scene.type === "quiz") {
    return <SceneThumbnailContent scene={scene} />;
  }

  if (isInteractive && scene.content && scene.content.html) {
    return (
      <SceneThumbnailContent
        scene={scene}
        size={Math.max(100, sidebarWidth - 28)}
        renderInteractiveThumbnail={renderInteractiveThumbnail}
      />
    );
  }

  if (scene.type === "interactive") {
    return <InteractiveMockup />;
  }

  if (scene.type === "pbl") {
    return <SceneThumbnailContent scene={scene} />;
  }

  return <FallbackMockup Icon={Icon} type={scene.type} />;
}

/** 参考 scene-sidebar 的 interactive 无 html 分支（浏览器窗口 mockup）。 */
function InteractiveMockup() {
  return (
    <div className="w-full h-full bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-950/30 dark:to-teal-950/20 p-1.5 flex flex-col">
      <div className="flex items-center gap-1 mb-1 pb-1 border-b border-emerald-200/40 dark:border-emerald-700/20">
        <div className="flex gap-0.5">
          <div className="w-1 h-1 rounded-full bg-red-300 dark:bg-red-500/60" />
          <div className="w-1 h-1 rounded-full bg-amber-300 dark:bg-amber-500/60" />
          <div className="w-1 h-1 rounded-full bg-green-300 dark:bg-green-500/60" />
        </div>
        <div className="h-1.5 flex-1 bg-emerald-200/40 dark:bg-emerald-700/30 rounded-full ml-0.5" />
      </div>
      <div className="flex-1 flex gap-1">
        <div className="w-1/4 space-y-1 pt-0.5">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-0.5 w-full bg-emerald-200/60 dark:bg-emerald-700/30 rounded-full"
            />
          ))}
        </div>
        <div className="flex-1 bg-emerald-100/40 dark:bg-emerald-800/20 rounded flex items-center justify-center border border-emerald-200/40 dark:border-emerald-700/20">
          <Globe className="w-4 h-4 text-emerald-300/80 dark:text-emerald-600/50" />
        </div>
      </div>
    </div>
  );
}

/** 参考 scene-sidebar 的兜底分支。 */
function FallbackMockup({ Icon, type }) {
  return (
    <div className="w-full h-full flex flex-col items-center justify-center gap-1 bg-gray-50 dark:bg-gray-800 text-gray-300 dark:text-gray-500">
      <Icon className="w-4 h-4" />
      <span className="text-[9px] font-bold uppercase tracking-wider opacity-80">{type}</span>
    </div>
  );
}

import { BookOpen, Globe } from "lucide-react";

import { cn } from "../utils/cn.js";

/**
 * 逐字移植自参考项目 `components/stage/scene-thumbnail-content.tsx`。
 *
 * 机械改写清单：
 *  - 擦除 TypeScript 类型（`Scene` / `SlideContent` / `InteractiveContent` / props 接口）。
 *  - `@/lib/utils` -> `../utils/cn.js`。
 *  - 去掉 `'use client'`。
 *
 * 一处**有意**的替换（报告里已说明）：参考实现里 `slide` 走
 * `components/slide-renderer/SlideThumbnail`（一个会真正渲染幻灯片画布的
 * 组件）。本仓库不提供该组件，因此把这一分支抽成 `renderSlideThumbnail`
 * 回调；调用方（父级集成层）可以传入 `src/maic/slide` 导出的缩略图组件把它
 * 接回去。没有传回调时回落到 SlidePlaceholder —— 保持同样的 aspect-video 盒
 * 尺寸，不会让侧栏行高发生位移。
 *
 * 除 slide 分支外，quiz / interactive / pbl / 未知类型四条分支的类名、
 * 内联结构与参考完全一致。
 */

const INTERACTIVE_FALLBACK_SIZE = 200;

/**
 * @param {object} props
 * @param {object} props.scene 场景对象 `{ id, title, type, order, content? }`
 * @param {number} [props.size] ThumbnailInteractive 的内层像素宽度
 * @param {number} [props.viewportSize] 幻灯片视口宽度（参考项目来自 canvas store）
 * @param {number} [props.viewportRatio] 幻灯片视口宽高比
 * @param {boolean} [props.visible] 是否在视口附近（参考项目用 useNearViewport 判定）
 * @param {(args: { slide: any, sceneId: string, viewportSize: number, viewportRatio: number, visible: boolean }) => React.ReactNode} [props.renderSlideThumbnail]
 * @param {(args: { content: any, size: number }) => React.ReactNode} [props.renderInteractiveThumbnail]
 */
export function SceneThumbnailContent({
  scene,
  size,
  viewportSize,
  viewportRatio,
  visible = true,
  renderSlideThumbnail,
  renderInteractiveThumbnail,
}) {
  if (scene.type === "slide") {
    const slideContent = scene.content;
    if (renderSlideThumbnail) {
      return renderSlideThumbnail({
        slide: slideContent ? slideContent.canvas : undefined,
        sceneId: scene.id,
        viewportSize,
        viewportRatio,
        visible,
      });
    }
    return <SlideThumbnailPlaceholder />;
  }

  if (scene.type === "quiz") {
    return (
      <div className="flex h-full w-full flex-col bg-gradient-to-br from-orange-50 to-amber-50 dark:from-orange-950/30 dark:to-amber-950/20 p-2">
        <div className="mb-1.5 h-1.5 w-4/5 rounded-full bg-orange-200/70 dark:bg-orange-700/30" />
        <div className="grid flex-1 grid-cols-2 gap-1">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className={cn(
                "flex items-center gap-1 rounded px-1",
                i === 1
                  ? "border border-orange-300/50 bg-orange-400/20 dark:border-orange-600/30 dark:bg-orange-500/20"
                  : "border border-orange-100/60 bg-white/60 dark:border-orange-800/20 dark:bg-white/5",
              )}
            >
              <div
                className={cn(
                  "h-1.5 w-1.5 shrink-0 rounded-full",
                  i === 1
                    ? "bg-orange-400 dark:bg-orange-500"
                    : "bg-orange-200 dark:bg-orange-700/50",
                )}
              />
              <div
                className={cn(
                  "h-1 flex-1 rounded-full",
                  i === 1
                    ? "bg-orange-300/60 dark:bg-orange-600/40"
                    : "bg-orange-100/80 dark:bg-orange-800/30",
                )}
              />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (scene.type === "interactive") {
    const interactiveContent = scene.content;
    if (interactiveContent && interactiveContent.html && visible) {
      if (renderInteractiveThumbnail) {
        return renderInteractiveThumbnail({
          content: interactiveContent,
          size: size ?? INTERACTIVE_FALLBACK_SIZE,
        });
      }
      return <InteractiveThumbnailPlaceholder size={size ?? INTERACTIVE_FALLBACK_SIZE} />;
    }
    return (
      <div className="flex h-full w-full flex-col bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-950/30 dark:to-teal-950/20 p-1.5">
        <div className="mb-1 flex items-center gap-1 border-b border-emerald-200/40 pb-1 dark:border-emerald-700/20">
          <div className="flex gap-0.5">
            <div className="h-1 w-1 rounded-full bg-red-300 dark:bg-red-500/60" />
            <div className="h-1 w-1 rounded-full bg-amber-300 dark:bg-amber-500/60" />
            <div className="h-1 w-1 rounded-full bg-green-300 dark:bg-green-500/60" />
          </div>
          <div className="ml-0.5 h-1.5 flex-1 rounded-full bg-emerald-200/40 dark:bg-emerald-700/30" />
        </div>
        <div className="flex flex-1 gap-1">
          <div className="w-1/4 space-y-1 pt-0.5">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-0.5 w-full rounded-full bg-emerald-200/60 dark:bg-emerald-700/30"
              />
            ))}
          </div>
          <div className="flex flex-1 items-center justify-center rounded border border-emerald-200/40 bg-emerald-100/40 dark:border-emerald-700/20 dark:bg-emerald-800/20">
            <Globe className="h-4 w-4 text-emerald-300/80 dark:text-emerald-600/50" />
          </div>
        </div>
      </div>
    );
  }

  if (scene.type === "pbl") {
    return (
      <div className="flex h-full w-full flex-col bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/20 p-1.5">
        <div className="mb-1.5 flex items-center gap-1">
          <div className="h-1.5 w-1.5 rounded bg-blue-300 dark:bg-blue-600" />
          <div className="h-1 w-8 rounded-full bg-blue-200/60 dark:bg-blue-700/30" />
        </div>
        <div className="flex flex-1 gap-1 overflow-hidden">
          {[0, 1, 2].map((col) => (
            <div
              key={col}
              className="flex flex-1 flex-col gap-0.5 rounded bg-white/50 p-0.5 dark:bg-white/5"
            >
              <div
                className={cn(
                  "mb-0.5 h-0.5 w-3 rounded-full",
                  col === 0 ? "bg-blue-300/70" : col === 1 ? "bg-amber-300/70" : "bg-green-300/70",
                )}
              />
              {Array.from({ length: col === 0 ? 3 : col === 1 ? 2 : 1 }).map((_, i) => (
                <div
                  key={i}
                  className="h-2 w-full rounded border border-blue-200/30 bg-blue-100/60 dark:border-blue-700/20 dark:bg-blue-800/20"
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // 兜底分支：参考实现标注为「新场景类型被旧客户端加载」的前向兼容路径。
  const unknownType = scene.type;
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-1 bg-gray-50 text-gray-300 dark:bg-gray-800 dark:text-gray-500">
      <BookOpen className="h-4 w-4" />
      <span className="text-[9px] font-bold uppercase tracking-wider opacity-80">
        {unknownType}
      </span>
    </div>
  );
}

/** slide 分支的占位实现（参考实现走 SlideThumbnail，本仓库未提供）。 */
function SlideThumbnailPlaceholder() {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-1 bg-gray-50 text-gray-300 dark:bg-gray-800 dark:text-gray-500">
      <BookOpen className="h-4 w-4" />
      <span className="text-[9px] font-bold uppercase tracking-wider opacity-80">slide</span>
    </div>
  );
}

/** interactive 分支在缺少 iframe 缩略图组件时的占位实现，尺寸与 ThumbnailInteractive 契约一致。 */
function InteractiveThumbnailPlaceholder({ size }) {
  return (
    <div
      className="flex h-full w-full flex-col items-center justify-center gap-1 bg-emerald-50 text-emerald-300/80 dark:bg-emerald-950/30 dark:text-emerald-600/50"
      style={{ width: size }}
    >
      <Globe className="h-4 w-4" />
    </div>
  );
}

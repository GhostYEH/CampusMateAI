import * as React from "react";
import { ArrowLeft, LayoutList, Maximize2, Minimize2 } from "lucide-react";

import { cn } from "../utils/cn.js";

/**
 * 逐字移植自参考项目 `components/header.tsx`（`Header` 组件）的**布局外壳**。
 *
 * 参考结构：
 *   <header className="h-20 px-8 flex items-center justify-between z-10 bg-transparent gap-4">
 *     <div className="flex items-center gap-3 min-w-0 flex-1">   // 左：返回控件 + 标题块
 *     <HeaderControls … />                                        // 右：控制簇
 *   </header>
 * 三者（左槽 / 中间标题 / 右控制簇）与类名全部保留。
 *
 * 机械改写清单：
 *  - 擦除 TypeScript 类型；去掉 `'use client'`；`@/lib/utils` -> `../utils/cn.js`。
 *  - `useRouter()` / `useSearchParams()` / `exitClassroom()` -> 丢弃。默认返回按钮改成
 *    由 `onBack` 驱动；没有 `onBack` 时按钮 `disabled`（不再跳首页，避免破坏宿主路由）。
 *  - `useI18n()` / `t('key')` -> zh-CN 原值（见 `ZH`），每条注明来源 key。
 *  - `HeaderControls`（参考 `components/stage/header-controls.tsx`）依赖 4 个 store、
 *    3 个导出 hook、Switch / DropdownMenu / 设置弹窗等本仓库没有的模块。按任务要求
 *    「保留视觉槽位」：右侧控制簇保留为一个固定 `gap-4` 的容器，里面的语言/主题/
 *    设置胶囊、Pro 开关、导出菜单**全部丢弃**，改由 `headerActions` 提供。
 *
 * 关于两个始终在场的切换按钮（`stage.fullscreen` 侧栏/演示开关）：
 * 参考项目里它们不在 `Header` 里，而在 `components/canvas/canvas-toolbar.tsx`
 * （侧栏开关用 `LayoutList`，演示开关用 `Maximize2` / `Minimize2`）。按任务要求
 * 「始终在场的 presentation/sidebar toggles」，这里把它们放在右控制簇左侧，
 * 并**复用 canvas-toolbar 的 `ctrlBtn` 类名与 `CtrlDivider` 结构**，尺寸 28px 控制
 * 在 h-20 头栏内不改变头栏高度与左右比例。
 */

const ZH = {
  // zh-CN.json > stage.currentScene
  currentScene: "当前场景",
  // zh-CN.json > generation.backToHome（classroomExitLabelKey 在非 workbench 场景返回的 key）
  backToHome: "返回首页",
  // zh-CN.json > stage.fullscreen
  fullscreen: "全屏",
  // zh-CN.json > stage.exitFullscreen
  exitFullscreen: "退出全屏",
};

/** 参考 `components/canvas/canvas-toolbar.tsx` 的 `ctrlBtn`，逐字保留。 */
export const ctrlBtn = cn(
  "relative w-7 h-7 rounded-md flex items-center justify-center",
  "transition-all duration-150 outline-none cursor-pointer",
  "hover:bg-gray-500/[0.08] dark:hover:bg-gray-400/[0.08] active:scale-90",
);

/** 参考 `canvas-toolbar.tsx` 的 `CtrlDivider`，逐字保留。 */
export function CtrlDivider() {
  return <div className="w-px h-3 bg-gray-200/80 dark:bg-gray-700/60 mx-0.5 shrink-0" />;
}

/**
 * @param {object} props
 * @param {string} [props.title] 中间的一级标题（参考的 `currentSceneTitle`），可为空
 * @param {React.ReactNode} [props.backControl] 左槽自定义返回控件；不传则用内置 ArrowLeft 按钮
 * @param {boolean} [props.hideBackControl] 整个左槽返回控件都不渲染
 * @param {() => void} [props.onBack] 内置返回按钮的回调
 * @param {React.ReactNode} [props.headerActions] 右控制簇（语言/主题/设置/导出等）由调用方注入
 * @param {boolean} [props.sidebarCollapsed] 右侧侧栏切换按钮的当前状态
 * @param {() => void} [props.onToggleSidebar] 侧栏切换；不传则不渲染该按钮
 * @param {boolean} [props.isPresenting] 右侧演示切换按钮的当前状态
 * @param {() => void} [props.onTogglePresentation] 演示切换；不传则不渲染该按钮
 * @param {string} [props.className] 追加到头栏容器上的类名
 */
export function MaicClassroomHeader({
  title = "",
  backControl,
  hideBackControl = false,
  onBack,
  headerActions,
  sidebarCollapsed = false,
  onToggleSidebar,
  isPresenting = false,
  onTogglePresentation,
  className,
}) {
  const presentationLabel = isPresenting ? ZH.exitFullscreen : ZH.fullscreen;

  return (
    <header
      className={cn(
        // 参考是固定 `px-8 gap-4`。窄屏（<640px）必须收窄：320px 下左右各 32px 的
        // padding 加上左右两个控制簇会把标题块挤成 0 宽，子元素溢出后右侧控制簇
        // 会盖在返回按钮上并吃掉点击（真实复现：320px 下点不到「返回编辑」）。
        // 640px 及以上逐字保持参考值，桌面端像素不变。
        "h-20 px-4 sm:px-8 flex items-center justify-between z-10 bg-transparent gap-2 sm:gap-4",
        className,
      )}
    >
      <div className="flex items-center gap-3 min-w-0 flex-1">
        {hideBackControl
          ? null
          : (backControl ?? (
              <button
                onClick={onBack}
                disabled={!onBack}
                className="shrink-0 p-2 rounded-lg text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-gray-300 transition-colors disabled:cursor-default disabled:hover:bg-transparent disabled:hover:text-gray-400 dark:disabled:hover:text-gray-500"
                title={ZH.backToHome}
                aria-label={ZH.backToHome}
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
            ))}
        {/* Title block —— 参考实现在 `mode === 'edit'` 时隐藏标题块；本组件没有
            mode 概念（playback chrome 专用），因此该分支恒为渲染。
            参考的 `currentSceneTitle || t('common.loading')` 在移植里退化为
            `title || ''`：按集成契约 `title` 可以为空，且这里没有加载态可言。 */}
        <div className="flex flex-col min-w-0 overflow-hidden">
          <span className="text-[10px] uppercase tracking-widest font-bold text-gray-400 dark:text-gray-500 mb-0.5">
            {ZH.currentScene}
          </span>
          <h1
            className="text-xl font-bold text-gray-800 dark:text-gray-200 tracking-tight truncate"
            suppressHydrationWarning
          >
            {title || ""}
          </h1>
        </div>
      </div>

      {/* 右控制簇：参考是 <HeaderControls/>（自带宽 gap-4 的胶囊 + Pro 开关 + 导出）。
          这里保留同样的 `flex items-center gap-4` 外层，槽位交给 headerActions。 */}
      <div className="flex items-center gap-2 sm:gap-4 shrink-0">
        <div className="flex items-center gap-1 shrink-0">
          {onToggleSidebar && (
            <button
              onClick={onToggleSidebar}
              className={cn(
                ctrlBtn,
                sidebarCollapsed
                  ? "text-gray-400 dark:text-gray-500"
                  : "text-gray-600 dark:text-gray-300",
              )}
              aria-label="Toggle sidebar"
              aria-pressed={!sidebarCollapsed}
            >
              <LayoutList className="w-3.5 h-3.5" />
            </button>
          )}
          {onTogglePresentation && (
            <button
              onClick={onTogglePresentation}
              className={cn(
                ctrlBtn,
                isPresenting ? "text-violet-600 dark:text-violet-400" : "text-gray-500 dark:text-gray-400",
              )}
              aria-label={presentationLabel}
              title={presentationLabel}
            >
              {isPresenting ? (
                <Minimize2 className="w-3.5 h-3.5" />
              ) : (
                <Maximize2 className="w-3.5 h-3.5" />
              )}
            </button>
          )}
          {headerActions ? <CtrlDivider /> : null}
        </div>
        {headerActions}
      </div>
    </header>
  );
}

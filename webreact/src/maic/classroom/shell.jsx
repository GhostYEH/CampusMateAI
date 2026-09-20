import * as React from "react";

import { cn } from "../utils/cn.js";
import { MaicSceneSidebar } from "./scene-sidebar.jsx";
import { MaicClassroomHeader } from "./classroom-header.jsx";

/**
 * 移植自参考项目 `components/edit/PlaybackChromeRoot.tsx` 第 1589-1688 行的
 * **播放态外壳**（结构、类名、内联 style 逐字保留）。
 *
 * 只移植视觉外壳与布局：键盘快捷键、全屏状态机、自动播放、TTS、生成轮询、
 * zustand stores、圆桌（Roundtable）流式对话全部不在范围内，因此这里没有
 * 任何行为引擎，只依赖 props。
 *
 * 与参考的结构对应关系：
 *   <div className="flex-1 flex overflow-hidden bg-gray-50 dark:bg-gray-900">
 *     <SceneSidebar …/>                         -> <MaicSceneSidebar …/>
 *     <div className="flex-1 flex flex-col overflow-hidden min-w-0 relative">
 *       {!isPresenting && !hideHeader && <Header …/>}  -> <MaicClassroomHeader …/>
 *       <div className="overflow-hidden relative flex-1 min-h-0 isolate"
 *            style={{ height: sceneViewerHeight }}>  // 画布区
 *         <CanvasArea …/>                        -> {children}
 *       </div>
 *       {mode === 'playback' && <Roundtable …/>}  -> 丢弃（行为引擎 + 依赖 chat store）
 *     </div>
 *   </div>
 *
 * 保留的动态部分只有画布区高度：参考的 `sceneViewerHeight` 是
 * `calc(100% - ${headerHeight + roundtableHeight}px)`，其中
 * `headerHeight = isPresenting || hideHeader ? 0 : 80`（头栏 h-20 = 80px），
 * `roundtableHeight = mode === 'playback' && !isPresenting ? 192 : 0`。
 * Roundtable 被丢弃后第二项恒为 0，于是这里保留
 * `headerVisible ? 'calc(100% - 80px)' : '100%'` 这一支，`className` 一字不改。
 *
 * 用法注意：`maic.css` 的令牌与 `@utility scrollbar-hide` 都只在 `.maic-root`
 * 作用域内生效。按集成契约本组件根节点的 className 必须逐字是
 * `flex-1 flex overflow-hidden bg-gray-50 dark:bg-gray-900`，所以**不**在这里
 * 追加 `.maic-root`；请由承载它的外层容器（页面/应用外壳）提供 `.maic-root`。
 *
 * `onPrevScene` / `onNextScene` 属于集成契约的一部分（参考里由 CanvasArea /
 * canvas-toolbar 消费）。播放控制条不在本次移植范围内，所以这两个回调在本组件里
 * **不渲染任何东西**，只是接住签名，便于之后补底栏时不必改契约；当前请由
 * `children`（画布层）自行接管上一页/下一页。
 *
 * 为什么这个组件在 `.jsx` 而不是 `index.js`：Vite 的模块分析只对 `.jsx`/`.tsx`
 * 开启 JSX，含 JSX 的 `.js` 会在 SSR 模块加载期直接报
 * "Failed to parse source for import analysis ... name the file with the .jsx"。
 * `index.js` 保持为纯再导出，导入路径因此不变。
 */
export function MaicClassroomShell({
  title = "",
  scenes,
  currentSceneId,
  onSelectScene,
  onPrevScene, // 契约占位：见文件头说明（当前不渲染播放控制条）
  onNextScene, // 契约占位：见文件头说明（当前不渲染播放控制条）
  sidebarCollapsed = false,
  onToggleSidebar,
  backControl,
  headerActions,
  children,
  className,
  // 以下是可选扩展（都有默认值，只传上面那批必需 props 也能完整渲染）：
  hideHeader = false,
  isPresenting = false,
  onTogglePresentation,
  headerClassName,
  sidebarProps,
}) {
  const safeScenes = Array.isArray(scenes) ? scenes : [];
  const headerVisible = !hideHeader && !isPresenting;

  // 参考：const headerHeight = isPresenting || hideHeader ? 0 : 80;
  //       const roundtableHeight = mode === 'playback' && !isPresenting ? 192 : 0;
  //       return `calc(100% - ${headerHeight + roundtableHeight}px)`;
  // Roundtable 不在移植范围内，因此 roundtableHeight 恒为 0。
  const sceneViewerHeight = headerVisible ? "calc(100% - 80px)" : "100%";

  return (
    <div
      className={cn(
        "flex-1 flex overflow-hidden bg-gray-50 dark:bg-gray-900",
        isPresenting && "cursor-none",
        className,
      )}
    >
      <MaicSceneSidebar
        collapsed={sidebarCollapsed}
        onCollapseChange={(next) => {
          // 参考：onCollapseChange={setSidebarCollapsed}，侧栏只上报目标值。
          if (onToggleSidebar && next !== sidebarCollapsed) onToggleSidebar();
        }}
        scenes={safeScenes}
        currentSceneId={currentSceneId}
        onSceneSelect={onSelectScene}
        {...sidebarProps}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0 relative">
        {headerVisible && (
          <MaicClassroomHeader
            title={title || ""}
            backControl={backControl}
            headerActions={headerActions}
            sidebarCollapsed={sidebarCollapsed}
            onToggleSidebar={onToggleSidebar}
            isPresenting={isPresenting}
            onTogglePresentation={onTogglePresentation}
            className={headerClassName}
          />
        )}

        {/* Canvas Area */}
        <div
          className="overflow-hidden relative flex-1 min-h-0 isolate"
          style={{
            height: sceneViewerHeight,
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}

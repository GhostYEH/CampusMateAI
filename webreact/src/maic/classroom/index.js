/**
 * 课堂播放外壳的公开入口。
 *
 * 本文件**只做再导出**，不含 JSX：Vite 的模块分析只对 `.jsx`/`.tsx` 开启 JSX，
 * 含 JSX 的 `.js` 会在 SSR 模块加载期直接报
 * `Failed to parse source for import analysis ... name the file with the .jsx`。
 * 把实现放进 `shell.jsx` 后，外部导入路径 `src/maic/classroom/index.js` 保持不变。
 *
 * 参考来源：`components/edit/PlaybackChromeRoot.tsx`（外壳）、
 * `components/stage/scene-sidebar.tsx`（场景栏）、
 * `components/stage/header-controls.tsx`（头栏）、
 * `components/stage/scene-thumbnail-content.tsx`（缩略图框）。
 */
export { MaicClassroomShell } from "./shell.jsx";
export { MaicSceneSidebar, PENDING_SCENE_ID } from "./scene-sidebar.jsx";
export { MaicClassroomHeader } from "./classroom-header.jsx";
export { SceneThumbnailContent } from "./scene-thumbnail.jsx";

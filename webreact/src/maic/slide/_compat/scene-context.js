/**
 * 移植补充：`useSceneData` / `useSceneSelector` 的等价层。
 *
 * 参考项目的 `@/lib/contexts/scene-context` 把 classroom 正在播放的场景挂在
 * React context 上：
 *   - `useSceneSelector((content) => content.canvas.theme)` 读主题色；
 *   - `useSceneData()` 提供 `sceneId` / `sceneData`（元素重试上报要用）。
 *
 * CampusMate 的 `MaicSlideSurface` 直接接收一张 canvas，没有场景容器，因此这里
 * 提供同形状的 context。`MaicSlideSurface` 写入的 value 形状是：
 *
 *   { sceneId, sceneData, type: 'slide', canvas: { theme, background, elements } }
 *
 * 于是两个 hook 的返回语义与参考一致：
 *   - `useSceneSelector((content) => content.canvas.theme)` → 主题；
 *   - `useSceneData()` → `{ sceneId, sceneData }`。
 *
 * 不在 Provider 下时（例如单独渲染某个 base 元素做单测），selector 收到的是
 * 一张空 canvas 的缺省场景，`useSceneData()` 返回空 sceneId —— 与参考项目
 * 首页缩略图没有 stageId 时的行为一致。
 */
import { createContext, useContext } from 'react';

const EMPTY_CANVAS = { elements: [] };

const SceneContext = createContext(null);

export const SceneProvider = SceneContext.Provider;

export function useSceneData() {
  const scene = useContext(SceneContext);
  if (!scene) {
    return { sceneId: '', sceneData: null };
  }
  return { sceneId: scene.sceneId ?? '', sceneData: scene.sceneData ?? null };
}

export function useSceneSelector(selector) {
  const scene = useContext(SceneContext);
  if (!scene) {
    return selector({ type: 'slide', canvas: EMPTY_CANVAS });
  }
  return selector(scene);
}

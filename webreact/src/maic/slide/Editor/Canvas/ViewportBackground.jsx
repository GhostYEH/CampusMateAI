/**
 * 逐字移植自参考
 * `components/slide-renderer/Editor/Canvas/ViewportBackground.tsx`。
 *
 * 机械改写：去掉 `'use client'`、TypeScript 类型与 `@openmaic/dsl` 类型导入；
 * `@/lib/contexts/scene-context` 的 `useSceneSelector` → `_compat/scene-context.js`；
 * `@/lib/hooks/use-slide-background-style` → `_compat/use-slide-background-style.js`。
 *
 * 额外新增可选 prop `background`：参考实现从场景 context 里取
 * `content.canvas.background`；`MaicSlideSurface` 直接把 canvas 交给画布，
 * 没有场景容器，因此允许显式传入。不传时行为与参考一致（走 context）。
 */
import { useSceneSelector } from '../../_compat/scene-context.js';
import { useSlideBackgroundStyle } from '../../_compat/use-slide-background-style.js';

/**
 * Viewport background component using Scene Context
 * Renders the slide background from current scene data
 */
export function ViewportBackground({ background: backgroundProp }) {
  // Subscribe only to background for performance
  const contextBackground = useSceneSelector((content) => content.canvas?.background);
  const background = backgroundProp ?? contextBackground;

  const { backgroundStyle: bgStyle } = useSlideBackgroundStyle(background);

  const backgroundStyle = {
    ...bgStyle,
    width: '100%',
    height: '100%',
    backgroundPosition: 'center',
    position: 'absolute',
    pointerEvents: 'none', // Don't block mouse events
  };

  return <div className="viewport-background" style={backgroundStyle} />;
}

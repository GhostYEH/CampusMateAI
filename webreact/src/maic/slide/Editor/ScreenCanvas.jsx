/**
 * 逐字移植自参考 `components/slide-renderer/Editor/ScreenCanvas.tsx` 与
 * `RendererScreenCanvas.tsx`（`PlaybackScreenCanvas` 那个入口）。
 *
 * 机械改写：
 *   - 去掉 `'use client'`、TypeScript 类型与 `@openmaic/dsl` / `@/lib/types/*`
 *     的类型导入；
 *   - `@/lib/hooks/use-slide-background-style` →
 *     `_compat/use-slide-background-style.js`；
 *   - `@/lib/store` 的 `useCanvasStore` → `_compat/canvas-store.js`；
 *   - `@/lib/contexts/scene-context` 的 `useSceneSelector` →
 *     `_compat/scene-context.js`（`MaicSlideSurface` 会直接传 `canvas`）；
 *   - `@/lib/utils/geometry` 的 `findElementGeometry` → `_compat/geometry.js`；
 *   - `./Canvas/hooks/useViewportSize` → `_compat/useViewportSize.js`（参考项目里
 *     编辑器版本会写回 store；渲染器包里的版本是纯计算，这里用纯计算那份，
 *     并把 `viewportSize` / `viewportRatio` 从 canvas 取，而不是写死 1000×0.5625）；
 *   - `@/lib/config/feature-flags` 的 `isPlaybackRendererEnabled()` 决定
 *     `PlaybackScreenCanvas` 走 Renderer 还是 Editor 画布。目标项目是 read-only
 *     移植，`MaicSlideSurface` 只在**没有**传 `renderImage` / `renderVideo` 回调时
 *     用 `RendererScreenCanvas`（与参考的 chrome 路径一致），这里不引入 feature flag。
 *
 * 两个 props（不改变 DOM）：
 *   - `canvas`：`SlideContent.canvas`（`{ width, height, elements, background?, theme? }`）。
 *     参考实现从场景 context 与 store 里取这些值，目标项目直接接收。
 *   - `className`：透传到 `RendererScreenCanvas`（`ScreenCanvas` 保持了参考里
 *     不带 className 的根节点）。
 *
 * 未移植的调用：`useSyncCanvasViewportFromSlide()`（参考项目在 store 与 canvas
 * 数据之间做双向同步）与 `RendererScreenCanvas` 里对 store 的 `setCanvasScale`
 * 写回。目标项目没有那个 store 契约：`canvasScale` 由 `MaicSlideSurface` 的
 * `canvasScale` prop 决定，`onScaleChange` 是唯一的回调出口。
 */
import { ScreenElement } from './ScreenElement.jsx';
import { HighlightOverlay } from './HighlightOverlay.jsx';
import { SpotlightOverlay } from './SpotlightOverlay.jsx';
import { LaserOverlay } from './LaserOverlay.jsx';
import { RendererScreenCanvas } from './RendererScreenCanvas.jsx';
import { useSlideBackgroundStyle } from '../_compat/use-slide-background-style.js';
import { useCanvasStore } from '../_compat/canvas-store.js';
import { findElementGeometry } from '../_compat/geometry.js';
import { useViewportSize } from '../_compat/useViewportSize.js';
import { useRef, useMemo } from 'react';
import { AnimatePresence } from 'motion/react';

const DEFAULT_VIEWPORT_SIZE = 1000;
const DEFAULT_VIEWPORT_RATIO = 0.5625;
const EMPTY_ELEMENTS = [];
const EMPTY_HIGHLIGHTS = [];

function useCanvasGeometry(canvas) {
  const viewportSize = canvas?.width ?? DEFAULT_VIEWPORT_SIZE;
  const viewportRatio =
    canvas?.width && canvas?.height ? canvas.height / canvas.width : DEFAULT_VIEWPORT_RATIO;
  return { viewportSize, viewportRatio };
}

export function ScreenCanvas({ canvas, effectsEnabled = true }) {
  const canvasScale = useCanvasStore.use.canvasScale();
  const highlightedElementIds = useCanvasStore.use.highlightedElementIds();
  const highlightOptions = useCanvasStore.use.highlightOptions();
  const spotlightElementId = useCanvasStore.use.spotlightElementId();
  const spotlightOptions = useCanvasStore.use.spotlightOptions();
  const laserElementId = useCanvasStore.use.laserElementId();
  const laserOptions = useCanvasStore.use.laserOptions();
  const zoomTarget = useCanvasStore.use.zoomTarget();

  const elements = canvas?.elements ?? EMPTY_ELEMENTS;
  const canvasRef = useRef(null);

  const { viewportSize, viewportRatio } = useCanvasGeometry(canvas);

  // Viewport size and positioning
  const { viewportStyles, fitScale } = useViewportSize(canvasRef, {
    viewportSize,
    viewportRatio,
    canvasPercentage: 100,
  });
  const resolvedCanvasScale = canvasScale ?? fitScale;

  // Get background style
  const background = canvas?.background;
  const { backgroundStyle } = useSlideBackgroundStyle(background);

  // Compute laser pointer geometry
  const laserGeometry = useMemo(() => {
    if (!laserElementId) return null;
    const element = elements.find((el) => el.id === laserElementId);
    if (!element) return null;
    return findElementGeometry(elements, laserElementId, viewportSize, viewportRatio);
  }, [laserElementId, elements, viewportSize, viewportRatio]);

  // Compute zoom target geometry
  const zoomGeometry = useMemo(() => {
    if (!zoomTarget) return null;
    const element = elements.find((el) => el.id === zoomTarget.elementId);
    if (!element) return null;
    return findElementGeometry(elements, zoomTarget.elementId, viewportSize, viewportRatio);
  }, [zoomTarget, elements, viewportSize, viewportRatio]);

  const highlights = useMemo(() => {
    if (!highlightOptions || !highlightedElementIds.length) return EMPTY_HIGHLIGHTS;
    return highlightedElementIds.map((elementId) => ({
      elementId,
      ...highlightOptions,
    }));
  }, [highlightOptions, highlightedElementIds]);

  return (
    <div className="relative h-full w-full overflow-hidden select-none" ref={canvasRef}>
      <div
        className="absolute shadow-[0_0_0_1px_rgba(0,0,0,0.01),0_0_12px_0_rgba(0,0,0,0.1)] rounded-lg overflow-hidden transition-transform duration-700"
        style={{
          width: `${viewportStyles.width * resolvedCanvasScale}px`,
          height: `${viewportStyles.height * resolvedCanvasScale}px`,
          left: `${viewportStyles.left}px`,
          top: `${viewportStyles.top}px`,
          ...(zoomTarget && zoomGeometry
            ? {
                transform: `scale(${zoomTarget.scale})`,
                transformOrigin: `${zoomGeometry.centerX}% ${zoomGeometry.centerY}%`,
              }
            : {}),
        }}
      >
        {/* Background layer */}
        <div
          className="w-full h-full bg-position-center rounded-lg"
          style={{ ...backgroundStyle }}
        ></div>

        {/* Content layer - scaled */}
        <div
          className="absolute top-0 left-0 origin-top-left"
          style={{
            width: `${viewportStyles.width}px`,
            height: `${viewportStyles.height}px`,
            transform: `scale(${resolvedCanvasScale})`,
          }}
        >
          {elements.map((element, index) => (
            <ScreenElement key={element.id} elementInfo={element} elementIndex={index + 1} />
          ))}

          {/* Highlight overlay - stacked above elements */}
          {highlights.map((highlight) => {
            const element = elements.find((el) => el.id === highlight.elementId);
            return element ? (
              <HighlightOverlay key={highlight.elementId} element={element} options={highlight} />
            ) : null;
          })}
        </div>

        {/* Spotlight overlay - covers the entire slide, positioned via DOM measurement */}
        <SpotlightOverlay
          elementIdPrefix="screen-element-"
          options={{
            elementId: effectsEnabled ? spotlightElementId : '',
            ...spotlightOptions,
          }}
        />

        {/* Visual effects layer - outside the scale layer, using percentage coordinates */}
        <div className="absolute inset-0 pointer-events-none" style={{ padding: '5%' }}>
          <div className="relative w-full h-full">
            {/* Laser pointer overlay */}
            <AnimatePresence>
              {effectsEnabled && laserElementId && laserGeometry && (
                <LaserOverlay
                  key={`laser-${laserElementId}`}
                  geometry={laserGeometry}
                  color={laserOptions?.color}
                  duration={laserOptions?.duration}
                />
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * 参考的 `PlaybackScreenCanvas` 入口。目标项目没有 feature flag，因此默认走
 * `RendererScreenCanvas`（它内部会按需要回退到 `ScreenCanvas`）。
 */
export function PlaybackScreenCanvas({ canvas, className, assetResolver, children, effectsEnabled = true }) {
  return (
    <RendererScreenCanvas canvas={canvas} className={className} assetResolver={assetResolver} effectsEnabled={effectsEnabled}>
      {children}
    </RendererScreenCanvas>
  );
}

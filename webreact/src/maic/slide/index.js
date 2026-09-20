/**
 * `src/maic/slide/` 的公开出口。
 *
 * 移植自参考项目 `components/slide-renderer/` 的播放渲染层
 * （`Editor/` 下的画布与 `components/element/` 下的只读元素渲染件）。
 * 编辑器专用文件（`Editor/Canvas/**`、`ProsemirrorEditor.tsx`、`Editor/EditShell`）
 * 不在移植范围内。
 *
 * 两层入口：
 *   1. `MaicSlideSurface` —— 给一张 `SlideContent.canvas`，渲染整块画布；
 *   2. 逐个 `Base*Element` —— 需要在别处单独渲染某个元素时使用。
 *
 * 命名与参考文件保持一一对应（`BaseTextElement`、`BaseShapeElement`、……），
 * 便于与上游逐文件对照。
 */

// ==================== 集成入口 ====================
export { MaicSlideSurface } from './MaicSlideSurface.jsx';

// ==================== 播放画布 ====================
export { ScreenCanvas, PlaybackScreenCanvas } from './Editor/ScreenCanvas.jsx';
export {
  RendererScreenCanvas,
  PlaybackImageContent,
  PlaybackVideoContent,
  getPlaybackImageState,
} from './Editor/RendererScreenCanvas.jsx';
export { ScreenElement } from './Editor/ScreenElement.jsx';
export { ZoomWrapper } from './Editor/ZoomWrapper.jsx';
export { ViewportBackground } from './Editor/Canvas/ViewportBackground.jsx';
export { HighlightOverlay } from './Editor/HighlightOverlay.jsx';
export { SpotlightOverlay } from './Editor/SpotlightOverlay.jsx';
export { LaserOverlay } from './Editor/LaserOverlay.jsx';

// ==================== 只读元素渲染件 ====================
export { BaseTextElement } from './components/element/TextElement/BaseTextElement.jsx';
export { BaseShapeElement } from './components/element/ShapeElement/BaseShapeElement.jsx';
export { BaseImageElement } from './components/element/ImageElement/BaseImageElement.jsx';
export { BaseLineElement } from './components/element/LineElement/BaseLineElement.jsx';
export { BaseChartElement } from './components/element/ChartElement/BaseChartElement.jsx';
export { BaseLatexElement } from './components/element/LatexElement/BaseLatexElement.jsx';
export { BaseTableElement } from './components/element/TableElement/BaseTableElement.jsx';
export { BaseVideoElement } from './components/element/VideoElement/BaseVideoElement.jsx';
export { BaseCodeElement, setCodeHighlighterFactory } from './components/element/CodeElement/BaseCodeElement.jsx';
export { ElementOutline } from './components/element/ElementOutline.jsx';

// ==================== 元素子部件（参考项目里的同级文件） ====================
export { GradientDefs } from './components/element/ShapeElement/GradientDefs.jsx';
export { PatternDefs } from './components/element/ShapeElement/PatternDefs.jsx';
export { LinePointMarker } from './components/element/LineElement/LinePointMarker.jsx';
export { StaticTable } from './components/element/TableElement/StaticTable.jsx';
export { getTextStyle, formatText, getHiddenCells } from './components/element/TableElement/tableUtils.js';
export { Chart } from './components/element/ChartElement/Chart.jsx';
export { getChartOption } from './components/element/ChartElement/chartOption.js';
export { useResolvedImageSrc, resolveImageSrc } from './components/element/ImageElement/useResolvedImageSrc.js';
export { useFilter, imageFiltersToCss } from './components/element/ImageElement/useFilter.js';
export { useClipImage } from './components/element/ImageElement/useClipImage.js';
export { useResolvedVideoMedia, useResolvedVideoMediaFromContext } from './components/element/VideoElement/useResolvedVideoMedia.js';
export { ChartElement } from './components/element/ChartElement/index.jsx';
export { LineElement } from './components/element/LineElement/index.jsx';
export { TableElement } from './components/element/TableElement/index.jsx';

// ==================== hooks ====================
export { useElementFill } from './components/element/hooks/useElementFill.js';
export { useElementFlip } from './components/element/hooks/useElementFlip.js';
export { useElementOutline } from './components/element/hooks/useElementOutline.js';
export { useElementShadow } from './components/element/hooks/useElementShadow.js';
export { useSlideBackgroundStyle } from './_compat/use-slide-background-style.js';
export { useViewportSize } from './_compat/useViewportSize.js';
export { useResolvedSlide, useResolvedSlideMedia, resolveSlideMedia, resolveSlideMediaState } from './_compat/use-resolved-slide.js';
export { useAssetResolver } from './_compat/asset-resolver.js';

// ==================== 播放期状态（课堂动作层用） ====================
/**
 * 参考项目由 Zustand 的 `@/lib/store/canvas` hold 住播放焦点（视频）与播放期
 * 特效（聚光灯 / 激光笔 / 缩放 / 高亮）。CampusMate 没有那个 store，这里导出
 * 移植层内的等价物，供课堂动作层驱动：
 *
 *   useCanvasStore.getState().playVideo(elementId)   // 播放某个视频元素
 *   useCanvasStore.getState().pauseVideo()
 *   useCanvasStore.getState().setSpotlight(id, { dimness })
 *   useCanvasStore.getState().setLaser(id, { color, duration })
 *   useCanvasStore.getState().setZoomTarget({ elementId, scale })
 *   useCanvasStore.getState().setHighlightedElementIds([...])
 *   useCanvasStore.getState().setHighlightOptions({ color, opacity, borderWidth, animated })
 *   useCanvasStore.getState().resetEffects()
 */
export { useCanvasStore } from './_compat/canvas-store.js';

// ==================== 工具 ====================
export { useSceneData, useSceneSelector, SceneProvider } from './_compat/scene-context.js';
export { AssetResolverProvider, resolveAssetWith } from './_compat/asset-resolver.js';
export { createTranslator, DEFAULT_MEDIA_STRINGS } from './_compat/i18n.js';
export { SLIDE_RENDERER_STYLES, createTextProseStyles } from './_compat/styles.js';
export {
  SCREEN_ELEMENT_ID_PREFIX,
  EDITABLE_ELEMENT_ID_PREFIX,
  MAIC_ELEMENT_ID_ATTRIBUTE,
  screenElementDomId,
  editableElementDomId,
  maicElementIdAttributes,
} from './_compat/element-dom.js';
export {
  findElementGeometry,
  getElementPercentageGeometry,
  findNearestCorner,
} from './_compat/geometry.js';
export { ElementTypes } from './_compat/dsl.js';
export { CLIPPATHS, ClipPathTypes, ClipPaths } from './_compat/image-clip.js';
export {
  getLineElementPath,
  getTableSubThemeColor,
  getElementRange,
  getElementListRange,
  getRectRotatedRange,
  getRectRotatedOffset,
  getLineElementLength,
  uniqAlignLines,
  isElementInViewport,
} from './_compat/element.js';
export { analogous, withAlpha, toRgbString } from './_compat/color.js';

import "../../styles/magicclass.css";
/**
 * MagicClassSlideSurface —— 移植层的集成入口。
 *
 * 接收一张 magic class 幻灯片画布（`SlideContent.canvas`：
 * `{ width, height, elements, background?, theme? }`），渲染成一块自适应的
 * 播放画布。渲染管线与参考项目一致：
 *
 *   MagicClassSlideSurface
 *     └── AssetResolverProvider   （无 DOM，把 assetResolver 往下传）
 *     └── MediaStringsProvider    （无 DOM，覆盖媒体文案）
 *     └── SceneProvider           （无 DOM，提供 theme / sceneId 给元素）
 *           └── RendererScreenCanvas
 *                 └── ScreenCanvas（背景层 + 缩放层 + 特效层）
 *                       └── ScreenElement × N（同一个 .base-element-* 只读渲染件）
 *
 * 与参考的差异都在 `_compat/` 里注明；本文件只负责把「一张 canvas」翻译成
 * 参考项目由场景 context + store 提供的那几个输入。
 *
 * 尺寸约定（与参考 `SlideCanvas` 相同）：画布自身是 `width/height: 100%`，
 * 高度由父容器决定（`useViewportSize` 依据容器实测尺寸自动适配缩放并居中）。
 * 因此外层 div 用 `h-full w-full`，`className` / `style` 直接作用在它上面，
 * 方便宿主覆盖。
 *
 * `assetResolver` 是目标项目特有的注入点：所有图片 / 视频 / 封面 / 背景图 /
 * SVG pattern 位图的 src 都会经过它。不传时原样使用 canvas 里的 src。
 * 它同时写进 context，因此叶子组件（`BaseImageElement` 等）无论从哪条路径拿到
 * 元素，解析结果都一致。
 */
import { useMemo } from 'react';
import { AssetResolverProvider, resolveAssetWith } from './_compat/asset-resolver.js';
import { MediaStringsProvider } from './_compat/i18n.js';
import { SceneProvider } from './_compat/scene-context.js';
import { SLIDE_RENDERER_STYLES } from './_compat/styles.js';
import { RendererScreenCanvas } from './Editor/RendererScreenCanvas.jsx';

import { campusBackground, campusElements, campusTheme } from '../../features/magicclass/slideTheme.js';

function identity(src) {
  return src;
}

export function MagicClassSlideSurface({
  canvas,
  className,
  assetResolver,
  mediaStrings,
  sceneId = '',
  sceneData = null,
  style,
  effectsEnabled = true,
  // 同一页会在主舞台与侧栏缩略图各渲染一次；缩略图必须使用独立 DOM id 前缀，
  // 否则聚光灯会按缩略图坐标挖洞，主画布整页变暗。
  elementIdPrefix,
}) {
  const elements = canvas && Array.isArray(canvas.elements) ? canvas.elements : null;
  const background = useMemo(() => campusBackground(canvas?.background), [canvas?.background]);
  const theme = useMemo(() => campusTheme(canvas?.theme, background), [canvas?.theme, background]);
  const themedElements = useMemo(() => campusElements(elements, theme.fontColor), [elements, theme.fontColor]);

  const sceneValue = useMemo(
    () => ({
      sceneId,
      sceneData,
      type: 'slide',
      canvas: {
        theme,
        background,
        elements: themedElements ?? [],
      },
    }),
    [sceneId, sceneData, theme, background, themedElements],
  );

  // 背景图也走 assetResolver。元素上的 src 交给 `useResolvedSlideMedia` 处理
  // （与参考一致：解析发生在媒体解析层，不在 surface 里）。
  const resolvedCanvas = useMemo(() => {
    if (!canvas || !elements) return canvas;
    let nextBackground = background;
    if (typeof assetResolver === 'function' && background?.type === 'image') {
      const backgroundImage = background.image;
      if (backgroundImage?.src) {
        const resolvedBackgroundSrc = resolveAssetWith(assetResolver, backgroundImage.src);
        if (resolvedBackgroundSrc !== backgroundImage.src) {
          nextBackground = {
            ...background,
            image: { ...backgroundImage, src: resolvedBackgroundSrc },
          };
        }
      }
    }
    return { ...canvas, background: nextBackground, theme, elements: themedElements };
  }, [canvas, elements, assetResolver, background, theme, themedElements]);

  if (!canvas || !elements) {
    return null;
  }

  return (
    <AssetResolverProvider value={typeof assetResolver === 'function' ? assetResolver : identity}>
      <MediaStringsProvider value={mediaStrings ?? null}>
        <SceneProvider value={sceneValue}>
          <div className={`h-full w-full ${className || ''}`} style={style}>
            <style dangerouslySetInnerHTML={{ __html: SLIDE_RENDERER_STYLES }} />
            <RendererScreenCanvas
              canvas={resolvedCanvas}
              assetResolver={assetResolver}
              effectsEnabled={effectsEnabled}
              elementIdPrefix={elementIdPrefix}
            />
          </div>
        </SceneProvider>
      </MediaStringsProvider>
    </AssetResolverProvider>
  );
}

/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/ImageElement/BaseImageElement.tsx`。
 *
 * 机械改写：
 *   - 去掉 `'use client'`、TypeScript 类型与 `@magicclass/dsl` 类型导入；
 *   - `@/lib/media/media-orchestrator` 的 `mediaRetryTarget` / `retryMediaTask`
 *     → `_compat/media-ref.js`（目标项目没有生成任务可重试，`retryMediaTask`
 *     为 no-op，并且 `mediaResolutionCanRetry` 恒为 false，所以重试按钮不会渲染）；
 *   - `@/lib/hooks/use-i18n` → `_compat/i18n.js`；
 *   - `@/lib/contexts/scene-context` 的 `useSceneData` → `_compat/scene-context.js`；
 *   - `@/lib/media/media-failure` 的 `mediaFailureNoticeKey` 与
 *     `@/lib/media/resolve-media-ref` 的 `mediaResolutionCanRetry`
 *     → `_compat/media-ref.js`。
 *
 * 新增的可选 props（都不改变 DOM）：
 *   - `renderImage` —— 与参考渲染器包 `BaseImageElement` 的插槽同签名
 *     `(element, resolvedSrc, defaultContent)`。参考项目的
 *     `RendererScreenCanvas` 就是通过 `SlideCanvas` 的 `renderImage` 注入
 *     `PlaybackImageContent` 的；目标项目保留这个插槽，`RendererScreenCanvas`
 *     才能原样把骨架屏/重试 UI 接回来。
 *   - `sceneId` / `sceneData` —— 让宿主在没有 SceneProvider 时也能给出场景信息；
 *     不传时从 scene context 读默认值（`sceneId: ''`）。
 *
 * 骨架屏 / 禁用 / 失败三条分支、类名、内联样式与 DOM 层级逐字保留。
 */
import { useElementShadow } from '../hooks/useElementShadow.js';
import { useElementFlip } from '../hooks/useElementFlip.js';
import { useClipImage } from './useClipImage.js';
import { useFilter } from './useFilter.js';
import { ImageOutline } from './ImageOutline/index.jsx';
import { useResolvedImageSrc } from './useResolvedImageSrc.js';
import {
  mediaRetryTarget,
  retryMediaTask,
  mediaResolutionCanRetry,
} from '../../../_compat/media-ref.js';
import { RotateCcw, Paintbrush, ShieldAlert, ImageOff } from 'lucide-react';
import { useI18n } from '../../../_compat/i18n.js';
import { useSceneData } from '../../../_compat/scene-context.js';

/**
 * Base image element component for read-only display
 */
export function BaseImageElement({
  elementInfo,
  renderImage,
  sceneId: sceneIdProp,
  sceneData: sceneDataProp,
}) {
  const scene = useSceneData();
  const sceneId = sceneIdProp ?? scene.sceneId;
  const sceneData = sceneDataProp ?? scene.sceneData;
  const { resolvedSrc } = useResolvedImageSrc(elementInfo);

  const defaultContent = (
    <DefaultImageContent elementInfo={elementInfo} sceneId={sceneId} sceneData={sceneData} />
  );

  if (renderImage) {
    return renderImage(elementInfo, resolvedSrc, defaultContent);
  }

  return defaultContent;
}

function DefaultImageContent({ elementInfo, sceneId, sceneData }) {
  const { t } = useI18n();
  const { shadowStyle } = useElementShadow(elementInfo.shadow);
  const { flipStyle } = useElementFlip(elementInfo.flipH, elementInfo.flipV);
  const { clipShape, imgPosition } = useClipImage(elementInfo);
  const { filter } = useFilter(elementInfo.filters);

  // Shared with the editor canvas's interactive ImageElement so both variants
  // resolve gen_img_* placeholders identically (Pro mode previously rendered
  // the raw placeholder string and showed a broken-image icon).
  const { resolvedSrc, task, resolution } = useResolvedImageSrc(elementInfo);
  const showSkeleton = resolution.kind === 'pending' || resolution.kind === 'placeholder';
  const showDisabled = resolution.kind === 'disabled';
  const showError = resolution.kind === 'failed';
  const canRetry = mediaResolutionCanRetry(resolution);
  // 参考项目里的生成被拒原因码；目标项目没有生成编排，恒为 undefined。
  const failureNotice = undefined;
  void task;

  return (
    <div
      className="element-content absolute"
      style={{
        top: `${elementInfo.top}px`,
        left: `${elementInfo.left}px`,
        width: `${elementInfo.width}px`,
        height: `${elementInfo.height}px`,
      }}
    >
      <div className="w-full h-full" style={{ transform: `rotate(${elementInfo.rotate}deg)` }}>
        <div
          className="w-full h-full relative"
          style={{
            filter: shadowStyle ? `drop-shadow(${shadowStyle})` : '',
            transform: flipStyle,
          }}
        >
          <ImageOutline elementInfo={elementInfo} />

          <div
            className="w-full h-full overflow-hidden relative"
            style={{ clipPath: clipShape.style }}
          >
            {showSkeleton ? (
              <div className="w-full h-full bg-gradient-to-br from-amber-50 via-orange-50/60 to-yellow-50 dark:from-amber-950/40 dark:via-orange-950/30 dark:to-yellow-950/20 flex items-center justify-center">
                <style>{`
                  @keyframes img-pulse-ring { 0%, 100% { opacity: 0.15; transform: scale(0.85); } 50% { opacity: 0.35; transform: scale(1.1); } }
                `}</style>
                <div className="relative w-12 h-12">
                  <div
                    className="absolute inset-0 rounded-full border-2 border-amber-300/40 dark:border-amber-500/30"
                    style={{
                      animation: 'img-pulse-ring 2.4s ease-in-out infinite',
                    }}
                  />
                  <Paintbrush
                    className="absolute inset-0 m-auto w-5 h-5 text-amber-400/80 dark:text-amber-500/70"
                    strokeWidth={1.5}
                  />
                </div>
              </div>
            ) : showDisabled ? (
              <div
                className="w-full h-full bg-gray-50 dark:bg-gray-900/20 flex items-center justify-center"
                data-media-state="disabled"
              >
                <div className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-gray-500 dark:text-gray-400">
                  <ImageOff className="w-3 h-3 shrink-0" />
                  <span>{t('settings.mediaGenerationDisabled')}</span>
                </div>
              </div>
            ) : showError ? (
              <div className="w-full h-full bg-red-50 dark:bg-red-900/20 flex flex-col items-center justify-center gap-1.5">
                {failureNotice ? (
                  <div className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-amber-600 dark:text-amber-400">
                    <ShieldAlert className="w-3 h-3 shrink-0" />
                    <span>{t(failureNotice)}</span>
                  </div>
                ) : null}
                {canRetry ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      retryMediaTask(
                        elementInfo.src,
                        mediaRetryTarget(elementInfo.id, sceneId, sceneData),
                      );
                    }}
                    onPointerDown={(e) => e.stopPropagation()}
                    className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/40 rounded hover:bg-red-200 dark:hover:bg-red-900/60 transition-colors"
                  >
                    <RotateCcw className="w-3 h-3" />
                    {t('settings.mediaRetry')}
                  </button>
                ) : null}
              </div>
            ) : resolvedSrc ? (
              <>
                <img
                  src={resolvedSrc}
                  draggable={false}
                  style={{
                    position: 'absolute',
                    top: imgPosition.top,
                    left: imgPosition.left,
                    width: imgPosition.width,
                    height: imgPosition.height,
                    filter,
                  }}
                  alt=""
                  onDragStart={(e) => e.preventDefault()}
                />
                {elementInfo.colorMask && (
                  <div
                    className="absolute inset-0"
                    style={{ backgroundColor: elementInfo.colorMask }}
                  />
                )}
              </>
            ) : null}
            {canRetry && resolution.kind !== 'failed' ? (
              <button
                onClick={(event) => {
                  event.stopPropagation();
                  retryMediaTask(
                    elementInfo.src,
                    mediaRetryTarget(elementInfo.id, sceneId, sceneData),
                  );
                }}
                onPointerDown={(event) => event.stopPropagation()}
                className="absolute right-1 top-1 flex items-center gap-1 rounded bg-red-100/95 px-2 py-1 text-[10px] font-medium text-red-600 shadow-sm dark:bg-red-900/80 dark:text-red-300"
              >
                <RotateCcw className="h-3 w-3" />
                {t('settings.mediaRetry')}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

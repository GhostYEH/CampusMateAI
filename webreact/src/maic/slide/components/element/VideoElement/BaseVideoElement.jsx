/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/VideoElement/BaseVideoElement.tsx`。
 *
 * 机械改写：
 *   - 去掉 `'use client'`、TypeScript 类型与 `@openmaic/dsl` 类型导入；
 *   - `@/lib/store/canvas` 的 `useCanvasStore` → `_compat/canvas-store.js`
 *     （API 子集同形状：`use.playingVideoElementId()` / `getState().pauseVideo()`）；
 *   - `@/lib/media/media-orchestrator` → `_compat/media-ref.js`；
 *   - `@/lib/media/media-failure` / `@/lib/media/resolve-media-ref`
 *     → `_compat/media-ref.js`；
 *   - `@/lib/hooks/use-i18n` → `_compat/i18n.js`；
 *   - `@/lib/logger` → `_compat/i18n.js` 的 `createLogger`；
 *   - `@/lib/store/settings` 的「视频生成开关」→ 恒为开启（目标项目没有该开关）；
 *   - `@/lib/contexts/scene-context` → `_compat/scene-context.js`。
 *
 * 新增可选 props（不改变 DOM）：`sceneId` / `sceneData`，以及
 * `renderVideo`——与参考渲染器包 `BaseVideoElement` 的插槽同签名
 * `(element) => ReactNode`。参考项目的 `RendererScreenCanvas` 通过
 * `SlideCanvas` 的 `renderVideo` 注入 `PlaybackVideoContent`；目标项目保留这个
 * 插槽，`RendererScreenCanvas` 才能原样把骨架屏/重试 UI 接回来。
 * `playingVideoElementId` / `tasks` / `stageId` 原先来自全局 store，现在
 * `playingVideoElementId` 仍从 `_compat/canvas-store.js` 读，播放流程
 * （课堂动作 → playVideo → 缩放动画 + play()）与参考完全一致。
 *
 * 「轻按」缩放动画、错误/骨架/禁用分支、类名与内联样式逐字保留。
 */
import { useRef, useEffect } from 'react';
import { useAnimate } from 'motion/react';
import { useCanvasStore } from '../../../_compat/canvas-store.js';
import { mediaRetryTarget, retryMediaTask, mediaResolutionCanRetry } from '../../../_compat/media-ref.js';
import { RotateCcw, Film, ShieldAlert, VideoOff } from 'lucide-react';
import { useI18n, createLogger } from '../../../_compat/i18n.js';
import { useSceneData } from '../../../_compat/scene-context.js';
import { useResolvedVideoMediaFromContext } from './useResolvedVideoMedia.js';

const log = createLogger('BaseVideoElement');

/**
 * Base video element component for read-only/presentation display.
 * Controlled exclusively by the canvas store via the play_video action.
 * Videos never autoplay — they wait for an explicit play_video action.
 */
export function BaseVideoElement({
  elementInfo,
  renderVideo,
  sceneId: sceneIdProp,
  sceneData: sceneDataProp,
}) {
  if (renderVideo) {
    return renderVideo(elementInfo);
  }
  return (
    <DefaultVideoContent
      elementInfo={elementInfo}
      sceneId={sceneIdProp}
      sceneData={sceneDataProp}
    />
  );
}

function DefaultVideoContent({ elementInfo, sceneId: sceneIdProp, sceneData: sceneDataProp }) {
  const { t } = useI18n();
  const scene = useSceneData();
  const sceneId = sceneIdProp ?? scene.sceneId;
  const sceneData = sceneDataProp ?? scene.sceneData;
  const videoRef = useRef(null);
  const playingVideoElementId = useCanvasStore.use.playingVideoElementId();
  const prevPlayingRef = useRef('');
  const [scope, animate] = useAnimate();

  const { mediaRef, task, resolution, resolvedSrc, resolvedPoster } =
    useResolvedVideoMediaFromContext(elementInfo);
  const showSkeleton = resolution.kind === 'pending' || resolution.kind === 'placeholder';
  const showDisabled = resolution.kind === 'disabled';
  const showError = resolution.kind === 'failed';
  const canRetry = mediaResolutionCanRetry(resolution);
  // 参考项目里的生成被拒原因码；目标项目没有生成编排，恒为 undefined。
  const failureNotice = undefined;
  const isReady = !!resolvedSrc;
  // 参考项目这里会把 task 交给 mediaFailureNoticeKey；目标项目没有 task。
  void task;

  // Ensure video is paused on mount — prevents browser autoplay from user gesture context
  useEffect(() => {
    const video = videoRef.current;
    if (video) {
      video.pause();
    }
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const isMe = playingVideoElementId === elementInfo.id;
    const wasMe = prevPlayingRef.current === elementInfo.id;
    prevPlayingRef.current = playingVideoElementId;

    if (isMe && !wasMe) {
      // "Tap" press animation — a deliberate, teacher-paced click feel
      animate(
        scope.current,
        { scale: [1, 1.035, 1] },
        {
          duration: 0.6,
          ease: [0.25, 0.1, 0.25, 1],
          times: [0, 0.35, 1],
        },
      );
      video.play().catch((err) => {
        log.warn('[BaseVideoElement] play() failed:', err);
      });
    } else if (!isMe && wasMe) {
      video.pause();
    }
  }, [playingVideoElementId, elementInfo.id, animate, scope]);

  // 参考项目由全局 store 持有播放焦点；组件卸载时释放，避免指向已消失的元素。
  useEffect(() => {
    return () => {
      useCanvasStore.clearPlayingIfMatches(elementInfo.id);
    };
  }, [elementInfo.id]);

  const handleEnded = () => {
    if (useCanvasStore.getState().playingVideoElementId === elementInfo.id) {
      useCanvasStore.getState().pauseVideo();
    }
  };

  return (
    <div
      className="element-content absolute"
      data-video-element
      style={{
        top: `${elementInfo.top}px`,
        left: `${elementInfo.left}px`,
        width: `${elementInfo.width}px`,
        height: `${elementInfo.height}px`,
      }}
      onClick={(e) => e.stopPropagation()}
      onPointerDown={(e) => e.stopPropagation()}
    >
      <div
        ref={scope}
        className="relative w-full h-full"
        style={{ transform: `rotate(${elementInfo.rotate}deg)` }}
      >
        {showSkeleton ? (
          <div className="w-full h-full bg-gradient-to-br from-indigo-50 via-violet-50/60 to-blue-50 dark:from-indigo-950/40 dark:via-violet-950/30 dark:to-blue-950/20 flex items-center justify-center rounded">
            <style>{`
              @keyframes vid-pulse-ring { 0%, 100% { opacity: 0.15; transform: scale(0.85); } 50% { opacity: 0.35; transform: scale(1.1); } }
            `}</style>
            <div className="relative w-14 h-14">
              <div
                className="absolute inset-0 rounded-full border-2 border-indigo-300/40 dark:border-indigo-500/30"
                style={{
                  animation: 'vid-pulse-ring 2.4s ease-in-out infinite',
                }}
              />
              <Film
                className="absolute inset-0 m-auto w-5 h-5 text-indigo-400/80 dark:text-indigo-500/70"
                strokeWidth={1.5}
              />
            </div>
          </div>
        ) : showDisabled ? (
          <div
            className="w-full h-full bg-gray-50 dark:bg-gray-900/20 flex items-center justify-center rounded"
            data-media-state="disabled"
          >
            <div className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-gray-500 dark:text-gray-400">
              <VideoOff className="w-3 h-3 shrink-0" />
              <span>{t('settings.mediaGenerationDisabled')}</span>
            </div>
          </div>
        ) : showError ? (
          <div className="w-full h-full bg-red-50 dark:bg-red-900/20 flex flex-col items-center justify-center gap-1.5 rounded">
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
                  if (mediaRef) {
                    retryMediaTask(mediaRef, mediaRetryTarget(elementInfo.id, sceneId, sceneData));
                  }
                }}
                onPointerDown={(e) => e.stopPropagation()}
                className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/40 rounded hover:bg-red-200 dark:hover:bg-red-900/60 transition-colors"
              >
                <RotateCcw className="w-3 h-3" />
                {t('settings.mediaRetry')}
              </button>
            ) : null}
          </div>
        ) : isReady && resolvedSrc ? (
          <video
            ref={videoRef}
            className="w-full h-full"
            style={{ objectFit: 'contain' }}
            src={resolvedSrc}
            poster={resolvedPoster ?? undefined}
            preload="metadata"
            controls
            playsInline
            onEnded={handleEnded}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-black/10 rounded">
            <svg
              className="w-12 h-12 text-gray-400"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          </div>
        )}
        {canRetry && resolution.kind !== 'failed' ? (
          <button
            onClick={(event) => {
              event.stopPropagation();
              if (mediaRef) {
                retryMediaTask(mediaRef, mediaRetryTarget(elementInfo.id, sceneId, sceneData));
              }
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
  );
}

/**
 * 逐字移植自参考 `components/slide-renderer/Editor/RendererScreenCanvas.tsx`。
 *
 * 机械改写：
 *   - 去掉 `'use client'`、TypeScript 类型与 `@openmaic/dsl` / `@/lib/types/*`
 *     的类型导入；
 *   - `@openmaic/renderer` 的 `SlideCanvas` → 本目录 `ScreenCanvas.jsx`。两条
 *     canvas 实现最终渲染的是同一批 base 元素（同一套 `.base-element-*` 标记、
 *     同一套 DOM id 契约），因此视觉结果等价；
 *   - `../use-resolved-slide` → `_compat/use-resolved-slide.js`；
 *   - `@/lib/store` / `@/lib/store/canvas` → `_compat/canvas-store.js`；
 *   - `@/lib/contexts/scene-context` → `_compat/scene-context.js`；
 *   - `@/lib/media/*` → `_compat/media-ref.js`；
 *   - `@/lib/hooks/use-i18n` → `_compat/i18n.js`；
 *   - `@/lib/logger` → `_compat/i18n.js` 的 `createLogger`。
 *
 * 保留全部四条媒体状态分支（骨架 / 禁用 / 失败 / 正常）。在目标项目里
 * `_compat/media-ref.js` 只会产出 `url` 与 `placeholder` 两种 resolution，
 * 因此「骨架」之外的禁用/失败分支不会自行出现；一旦宿主给
 * `resolveSlideMediaState` 传了显式的 `resolution`，这些分支就会照参考原样生效。
 */
import { useEffect, useRef } from 'react';
import { useAnimate } from 'motion/react';
import { Film, ImageOff, Paintbrush, RotateCcw, ShieldAlert, VideoOff } from 'lucide-react';
import { useCanvasStore } from '../_compat/canvas-store.js';
import { useResolvedSlideMedia } from '../_compat/use-resolved-slide.js';
import {
  mediaFailureNoticeKey,
  mediaResolutionCanRetry,
  retryMediaTask,
} from '../_compat/media-ref.js';
import { useI18n, createLogger } from '../_compat/i18n.js';
import { ScreenCanvas } from './ScreenCanvas.jsx';

const log = createLogger('RendererScreenCanvas');

export function PlaybackVideoContent({ element, media, sceneId, slideId }) {
  const { t } = useI18n();
  const videoRef = useRef(null);
  const playingVideoElementId = useCanvasStore.use.playingVideoElementId();
  const prevPlayingRef = useRef('');
  const [scope, animate] = useAnimate();

  const task = media?.task;
  const mediaRef = media?.ref;
  const resolvedSrc = element.src || undefined;
  const resolvedPoster = element.poster || undefined;
  const showSkeleton =
    media?.resolution.kind === 'pending' || media?.resolution.kind === 'placeholder';
  const showDisabled = media?.resolution.kind === 'disabled';
  const showError = media?.resolution.kind === 'failed';
  const canRetry = mediaResolutionCanRetry(media?.resolution);
  // A refusal shows why instead of a Retry that would fail the same way.
  const failureNotice = mediaFailureNoticeKey(task?.errorCode);

  useEffect(() => {
    videoRef.current?.pause();
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const isMe = playingVideoElementId === element.id;
    const wasMe = prevPlayingRef.current === element.id;
    prevPlayingRef.current = playingVideoElementId;

    if (isMe && !wasMe) {
      animate(
        scope.current,
        { scale: [1, 1.035, 1] },
        { duration: 0.6, ease: [0.25, 0.1, 0.25, 1], times: [0, 0.35, 1] },
      );
      video.play().catch((err) => {
        log.warn('[PlaybackVideoContent] play() failed:', err);
      });
    } else if (!isMe && wasMe) {
      video.pause();
    }
    // sceneId / slideId 只用于重试上报，不参与播放状态机
    void sceneId;
    void slideId;
  }, [playingVideoElementId, element.id, animate, scope, sceneId, slideId]);

  const handleEnded = () => {
    if (useCanvasStore.getState().playingVideoElementId === element.id) {
      useCanvasStore.getState().pauseVideo();
    }
  };

  if (showSkeleton) {
    return (
      <div className="flex h-full w-full items-center justify-center rounded bg-gradient-to-br from-indigo-50 via-violet-50/60 to-blue-50 dark:from-indigo-950/40 dark:via-violet-950/30 dark:to-blue-950/20">
        <div className="relative h-14 w-14">
          <div className="absolute inset-0 animate-pulse rounded-full border-2 border-indigo-300/40 dark:border-indigo-500/30" />
          <Film
            className="absolute inset-0 m-auto h-5 w-5 text-indigo-400/80 dark:text-indigo-500/70"
            strokeWidth={1.5}
          />
        </div>
      </div>
    );
  }

  if (showDisabled) {
    return (
      <div
        className="flex h-full w-full items-center justify-center rounded bg-gray-50 dark:bg-gray-900/20"
        data-media-state="disabled"
      >
        <div className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-gray-500 dark:text-gray-400">
          <VideoOff className="h-3 w-3 shrink-0" />
          <span>{t('settings.mediaGenerationDisabled')}</span>
        </div>
      </div>
    );
  }

  if (showError && media?.resolution.kind === 'failed') {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-1.5 rounded bg-red-50 dark:bg-red-900/20">
        {failureNotice ? (
          <div className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-amber-600 dark:text-amber-400">
            <ShieldAlert className="h-3 w-3 shrink-0" />
            <span>{t(failureNotice)}</span>
          </div>
        ) : null}
        {canRetry ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (mediaRef) {
                retryMediaTask(mediaRef, { elementId: element.id, sceneId, slideId });
              }
            }}
            onPointerDown={(e) => e.stopPropagation()}
            className="flex items-center gap-1 rounded bg-red-100 px-2 py-1 text-[10px] font-medium text-red-600 transition-colors hover:bg-red-200 dark:bg-red-900/40 dark:text-red-400 dark:hover:bg-red-900/60"
          >
            <RotateCcw className="h-3 w-3" />
            {t('settings.mediaRetry')}
          </button>
        ) : null}
      </div>
    );
  }

  if (resolvedSrc) {
    return (
      <div ref={scope} className="relative h-full w-full">
        <video
          ref={videoRef}
          className="h-full w-full"
          style={{ objectFit: 'contain' }}
          src={resolvedSrc}
          poster={resolvedPoster ?? undefined}
          preload="metadata"
          controls
          playsInline
          onEnded={handleEnded}
        />
        {canRetry ? (
          <button
            onClick={(event) => {
              event.stopPropagation();
              if (mediaRef) {
                retryMediaTask(mediaRef, { elementId: element.id, sceneId, slideId });
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
    );
  }

  return (
    <div className="flex h-full w-full items-center justify-center rounded bg-black/10">
      <svg
        className="h-12 w-12 text-gray-400"
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
  );
}

export function getPlaybackImageState(resolution) {
  if (resolution.kind === 'failed') return 'failed';
  if (resolution.kind === 'disabled') return 'disabled';
  if (resolution.kind === 'pending' || resolution.kind === 'placeholder') return 'pending';
  return 'ready';
}

export function PlaybackImageContent({ element, defaultContent, media, sceneId, slideId }) {
  const { t } = useI18n();
  const task = media?.task;
  const state = getPlaybackImageState(media?.resolution ?? { kind: 'placeholder' });
  const canRetry = mediaResolutionCanRetry(media?.resolution);
  // A refusal shows why instead of a Retry that would fail the same way.
  const failureNotice = mediaFailureNoticeKey(task?.errorCode);

  if (state === 'pending') {
    return (
      <div
        className="flex h-full w-full items-center justify-center bg-gradient-to-br from-amber-50 via-orange-50/60 to-yellow-50 dark:from-amber-950/40 dark:via-orange-950/30 dark:to-yellow-950/20"
        data-media-state="pending"
      >
        <div className="relative h-12 w-12">
          <div className="absolute inset-0 animate-pulse rounded-full border-2 border-amber-300/40 dark:border-amber-500/30" />
          <Paintbrush
            className="absolute inset-0 m-auto h-5 w-5 text-amber-400/80 dark:text-amber-500/70"
            strokeWidth={1.5}
          />
        </div>
      </div>
    );
  }

  if (state === 'disabled') {
    return (
      <div
        className="flex h-full w-full items-center justify-center bg-gray-50 dark:bg-gray-900/20"
        data-media-state="disabled"
      >
        <div className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-gray-500 dark:text-gray-400">
          <ImageOff className="h-3 w-3 shrink-0" />
          <span>{t('settings.mediaGenerationDisabled')}</span>
        </div>
      </div>
    );
  }

  if (state === 'failed' && media?.resolution.kind === 'failed') {
    return (
      <div
        className="flex h-full w-full flex-col items-center justify-center gap-1.5 bg-red-50 dark:bg-red-900/20"
        data-media-state="failed"
      >
        {failureNotice ? (
          <div className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-amber-600 dark:text-amber-400">
            <ShieldAlert className="h-3 w-3 shrink-0" />
            <span>{t(failureNotice)}</span>
          </div>
        ) : null}
        {canRetry ? (
          <button
            onClick={(event) => {
              event.stopPropagation();
              if (media?.ref) {
                retryMediaTask(media.ref, { elementId: element.id, sceneId, slideId });
              }
            }}
            onPointerDown={(event) => event.stopPropagation()}
            className="flex items-center gap-1 rounded bg-red-100 px-2 py-1 text-[10px] font-medium text-red-600 transition-colors hover:bg-red-200 dark:bg-red-900/40 dark:text-red-400 dark:hover:bg-red-900/60"
          >
            <RotateCcw className="h-3 w-3" />
            {t('settings.mediaRetry')}
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <>
      {defaultContent}
      {canRetry ? (
        <button
          onClick={(event) => {
            event.stopPropagation();
            if (media?.ref) {
              retryMediaTask(media.ref, { elementId: element.id, sceneId, slideId });
            }
          }}
          onPointerDown={(event) => event.stopPropagation()}
          className="absolute right-1 top-1 flex items-center gap-1 rounded bg-red-100/95 px-2 py-1 text-[10px] font-medium text-red-600 shadow-sm dark:bg-red-900/80 dark:text-red-300"
        >
          <RotateCcw className="h-3 w-3" />
          {t('settings.mediaRetry')}
        </button>
      ) : null}
    </>
  );
}

/**
 * 播放画布的渲染器入口。
 *
 * 与参考的差异（同一批元素、同一套 DOM 契约，只换宿主组件）：
 * 参考把 `resolved.slide` 交给 `@openmaic/renderer` 的 `<SlideCanvas>`，并把
 * `PlaybackImageContent` / `PlaybackVideoContent` 通过它的 `renderImage` /
 * `renderVideo` 插槽注入。目标项目没有那个包，改用本目录的 `ScreenCanvas`：
 *
 *   - `ScreenCanvas` 渲染的也是同一批 `base-element-*` 组件（同一套源码移植），
 *     所以元素的像素结果等价；
 *   - 参考的媒体状态包装件仍然是本文件导出的 `PlaybackImageContent` /
 *     `PlaybackVideoContent`（同 props）。宿主需要「骨架屏 / 重试」这套 UI 时
 *     可以自己作为 `renderImage` / `renderVideo` 接进去；默认路径不注入，
 *     因为注入会给每个元素多包一层 DOM，参考的 `ScreenCanvas` 路径本来也没有。
 */
export function RendererScreenCanvas({ canvas, className, assetResolver, children, effectsEnabled = true }) {
  const resolved = useResolvedSlideMedia(canvas, { assetResolver });

  return (
    <ScreenCanvas canvas={resolved.slide} className={className} effectsEnabled={effectsEnabled}>
      {children}
    </ScreenCanvas>
  );
}

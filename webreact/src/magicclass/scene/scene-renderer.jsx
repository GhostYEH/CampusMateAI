import { useEffect, useMemo, useRef, useState } from 'react';

import { MagicClassSlideSurface } from '../slide/index.js';
import { QuizView } from './quiz-view.jsx';
import { InteractiveRenderer } from './interactive-renderer.jsx';
import { PBLRenderer } from './pbl-renderer.jsx';
import { MarkdownText } from './pbl/markdown-text.jsx';

/**
 * 移植自参考项目 `components/stage/scene-renderer.tsx` 的播放态场景分发器。
 *
 * 为什么单独放在 `.jsx` 里：目标项目的 vite 配置（`@vitejs/plugin-react` +
 * 默认 esbuild loader）只对 `.jsx` 启用 JSX 语法，`.js` 里的 JSX 会在构建时报
 * `The JSX syntax extension is not currently enabled`。因此分发器本体放在本文件，
 * `index.js` 负责再导出——`MagicClassSceneRenderer` 仍然从 `src/magicclass/scene/index.js`
 * 可用，满足入口约定。
 *
 * 参考实现的四个分支原样保留（含 "Invalid … content" / "Unknown scene type"
 * 的兜底文案），唯一的机械改写：
 *   - `SlideEditor as SlideRenderer` -> 另一路移植的 `MagicClassSlideSurface`
 *     （`../slide/index.js`，签名 `{ canvas, className, assetResolver }`）；
 *     参考实现只传 `mode`，因为它从 store 里取当前 slide —— 目标项目没有 store，
 *     所以这里按约定的入口把 `scene.content.canvas` 传进去。
 *   - 增加 `slide` 分支的**退化渲染**（见 SlideCanvasFallback 的说明）。
 */

/** 参考实现里 slide 画布的设计尺寸（`@magicclass/renderer` 的 viewport 默认值）。 */
const SLIDE_VIEWPORT_SIZE = 1000;
const SLIDE_VIEWPORT_RATIO = 0.5625; // 16:9
const SLIDE_VIEWPORT_HEIGHT = SLIDE_VIEWPORT_SIZE * SLIDE_VIEWPORT_RATIO; // 562.5

/**
 * **CampusMate 专用兜底**（不属于参考项目）。
 *
 * magic class 的 slide 场景内容是 `{ type: 'slide', canvas: { elements: [...] } }`。
 * CampusMate 生成的课堂里，一部分 slide 场景只带 `{ title, body }`，没有 `canvas`。
 * 直接交给 `MagicClassSlideSurface` 会渲染出一个空画布（课堂里就是一块空白色矩形）。
 *
 * 这个兜底把 title / body 放进**和参考实现一致的 1000 × 562.5 画布盒**里，
 * 但视觉换成 CampusMate 的讲义模板：封面深绿底米白字，内容页米白底 + 深绿字 +
 * 铜色/琥珀强调；长正文按长度降字号并在正文区滚动，不再被 16:9 裁掉。
 * 文字用 slide 尺度的排版渲染，正文走移植后的 `MarkdownText`，纯文本与 Markdown
 * 都能正常显示。
 *
 * 只有 `canvas.elements` 缺失或为空时才走这里；有真实画布时永远走
 * `MagicClassSlideSurface`，不存在"覆盖"上游渲染的问题。
 */
function SlideCanvasFallback({ title, body }) {
  const containerRef = useRef(null);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const measure = () => {
      const width = node.clientWidth;
      const height = node.clientHeight;
      if (width <= 0 || height <= 0) return;
      setScale(Math.min(width / SLIDE_VIEWPORT_SIZE, height / SLIDE_VIEWPORT_HEIGHT));
    };
    measure();
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    if (observer) observer.observe(node);
    window.addEventListener('resize', measure);
    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, []);

  const hasTitle = typeof title === 'string' && title.trim().length > 0;
  const hasBody = typeof body === 'string' && body.trim().length > 0;
  const isCover = hasTitle && !hasBody;
  // 长正文在 16:9 里最容易溢出：按长度降字号，并允许正文区自身滚动，
  // 不把最后几行裁掉。
  const bodyText = typeof body === 'string' ? body : '';
  const bodyFontSize = bodyText.length > 420 ? 16 : bodyText.length > 220 ? 18 : 20;

  const contentArea = isCover
    ? {
        backgroundColor: '#153B34',
        backgroundImage:
          'radial-gradient(circle at 88% 18%, rgba(218,178,122,0.18), transparent 42%), radial-gradient(circle at 12% 92%, rgba(173,104,69,0.16), transparent 46%)',
      }
    : {
        backgroundColor: '#F2F1E8',
        backgroundImage:
          'linear-gradient(90deg, rgba(21,59,52,0.035) 1px, transparent 1px), linear-gradient(rgba(21,59,52,0.028) 1px, transparent 1px)',
        backgroundSize: '32px 32px',
      };

  return (
    <div
      ref={containerRef}
      className="relative flex h-full w-full items-center justify-center overflow-hidden bg-[#E7E2D3]"
    >
      <div
        className="relative shrink-0 overflow-hidden"
        style={{
          width: SLIDE_VIEWPORT_SIZE,
          height: SLIDE_VIEWPORT_HEIGHT,
          ...contentArea,
          transform: `scale(${scale})`,
          transformOrigin: 'center center',
          borderRadius: 10,
          boxShadow: '0 18px 50px rgba(0,0,0,0.28)',
        }}
      >
        <style>{`
          @keyframes cm-slide-rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
          @keyframes cm-slide-underline { from { width: 0; opacity: 0; } to { width: 88px; opacity: 1; } }
          @keyframes cm-slide-focus {
            0%, 100% { box-shadow: 0 0 0 0 rgba(218,178,122,0); }
            50% { box-shadow: 0 0 0 10px rgba(218,178,122,.28); }
          }
          .cm-slide-focus { animation: cm-slide-focus 1.2s ease-in-out 2; border-radius: 8px; }
          .cm-slide-prose .prose { max-width: none; font-size: inherit; line-height: inherit; color: #2C3F37; }
          .cm-slide-prose .prose :where(p, li, blockquote, td, th) { color: #2C3F37; }
          .cm-slide-prose .prose :where(h1, h2, h3, h4) { color: #153B34; }
          .cm-slide-rise { animation: cm-slide-rise .5s cubic-bezier(.22,1,.36,1) both; }
          .cm-slide-underline {
            display: block;
            width: 0;
            height: 4px;
            margin-top: 14px;
            border-radius: 999px;
            background: #DAB27A;
            animation: cm-slide-underline .6s cubic-bezier(.22,1,.36,1) .2s forwards;
          }
          @media (prefers-reduced-motion: reduce) {
            .cm-slide-rise { animation: none; }
            .cm-slide-focus { animation: none; box-shadow: 0 0 0 8px rgba(218,178,122,.28); }
            .cm-slide-underline { animation: none; width: 88px; opacity: 1; }
          }
        `}</style>
        {isCover ? (
          <div className="flex h-full w-full flex-col justify-between px-[76px] py-[60px] text-[#F2F1E8]">
            <div className="flex items-center gap-3">
              <span className="h-[2px] w-9 bg-[#DAB27A]" />
              <span className="text-[13px] font-semibold uppercase tracking-[0.28em] text-[#DAB27A]">
                CampusMate · 本节导览
              </span>
            </div>
            <h1
              className="cm-slide-rise max-w-[860px] font-bold leading-[1.14] tracking-[-0.02em]"
              style={{
                fontSize: title.length > 24 ? 50 : 58,
                display: '-webkit-box',
                WebkitLineClamp: 3,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }}
            >
              {title}
            </h1>
            <div className="flex items-center justify-between border-t border-[#F2F1E8]/20 pt-5">
              <span className="text-[13px] text-[#F2F1E8]/70">把这一节讲成一条线</span>
              <span className="flex items-center gap-2 text-[13px] text-[#DAB27A]">
                <i className="h-1.5 w-1.5 rounded-full bg-[#DAB27A]" />
                课堂讲义
              </span>
            </div>
          </div>
        ) : (
          <div className="flex h-full w-full flex-col px-[76px] py-[52px]">
            <div className="flex shrink-0 items-center gap-3">
              <span className="h-[3px] w-10 rounded-full bg-[#AD6845]" />
              <span className="text-[12px] font-semibold uppercase tracking-[0.22em] text-[#AD6845]">
                CampusMate · 课堂讲义
              </span>
            </div>
            {hasTitle && (
              <h1
                id="campus-fallback-title"
                className="cm-slide-rise mt-5 max-w-[860px] shrink-0 font-bold leading-[1.18] tracking-[-0.015em] text-[#153B34]"
                style={{
                  fontSize: title.length > 28 ? 38 : 44,
                  display: '-webkit-box',
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                }}
              >
                {title}
              </h1>
            )}
            {hasTitle && <span className="cm-slide-underline" aria-hidden="true" />}
            {hasBody && (
              <div
                className="cm-slide-prose cm-slide-rise mt-6 min-h-0 flex-1 overflow-y-auto pr-3 text-[#2C3F37] [scrollbar-width:thin]"
                style={{ fontSize: bodyFontSize, lineHeight: 1.62 }}
              >
                <MarkdownText content={body} />
              </div>
            )}
            {!hasBody && !hasTitle && (
              <div className="flex flex-1 items-center justify-center text-[20px] text-[#6C7A72]">
                这一页没有可显示的文字。
              </div>
            )}
            <div className="mt-4 flex shrink-0 items-center justify-between border-t border-[#153B34]/12 pt-3 text-[11px] text-[#6C7A72]">
              <span>深绿 · 米白 · 琥珀</span>
              <span>跟着讲解看重点</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/** 从多种历史字段里取出兜底用的 title / body。 */
function readSlideFallbackText(scene) {
  const content = scene?.content ?? {};
  const title = content.title ?? scene?.title ?? '';
  const body = content.body ?? content.text ?? content.markdown ?? '';
  return { title, body };
}

/**
 * Playback scene dispatcher. In Pro (edit) mode, Stage renders EditShell
 * directly as a top-level takeover — SceneRenderer is only on the playback
 * path, so it does not branch on `mode === 'edit'`.
 */
export function MagicClassSceneRenderer({ scene, mode, onQuizGraded }) {
  const renderer = useMemo(() => {
    switch (scene.type) {
      case 'slide': {
        if (scene.content.type !== 'slide') return <div>Invalid slide content</div>;
        const canvas = scene.content.canvas;
        const hasCanvas = Array.isArray(canvas?.elements) && canvas.elements.length > 0;
        if (!hasCanvas) {
          // CampusMate 的 `{ title, body }` slide：用标准画布盒渲染文字兜底。
          const { title, body } = readSlideFallbackText(scene);
          return <SlideCanvasFallback title={title} body={body} />;
        }
        return <MagicClassSlideSurface canvas={canvas} />;
      }
      case 'quiz':
        if (scene.content.type !== 'quiz') return <div>Invalid quiz content</div>;
        return (
          <QuizView
            key={scene.id}
            questions={scene.content.questions}
            sceneId={scene.id}
            stageId={scene.stageId}
            onGraded={onQuizGraded}
          />
        );
      case 'interactive':
        if (scene.content.type !== 'interactive') return <div>Invalid interactive content</div>;
        return <InteractiveRenderer content={scene.content} sceneId={scene.id} />;
      case 'pbl':
        if (scene.content.type !== 'pbl') return <div>Invalid PBL content</div>;
        return <PBLRenderer content={scene.content} mode={mode} sceneId={scene.id} />;
      default:
        return <div>Unknown scene type</div>;
    }
  }, [scene, mode, onQuizGraded]);

  return <div className="w-full h-full">{renderer}</div>;
}

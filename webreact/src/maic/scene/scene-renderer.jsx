import { useEffect, useMemo, useRef, useState } from 'react';

import { MaicSlideSurface } from '../slide/index.js';
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
 * `index.js` 负责再导出——`MaicSceneRenderer` 仍然从 `src/maic/scene/index.js`
 * 可用，满足入口约定。
 *
 * 参考实现的四个分支原样保留（含 "Invalid … content" / "Unknown scene type"
 * 的兜底文案），唯一的机械改写：
 *   - `SlideEditor as SlideRenderer` -> 另一路移植的 `MaicSlideSurface`
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
 * 直接交给 `MaicSlideSurface` 会渲染出一个空画布（课堂里就是一块空白色矩形）。
 *
 * 这个兜底把 title / body 放进**和参考实现完全一致的画布盒**里：
 *   - 设计尺寸 1000 × 562.5（16:9），
 *   - 背景 `#fff`（`@magicclass/renderer` 的 `useSlideBackgroundStyle` 默认值），
 *   - 用 contain 方式等比缩放到容器内（与 `useViewportSize` 的 fit 语义相同）。
 * 文字用 slide 尺度的排版（标题 44px / 正文 20px）渲染，正文走移植后的
 * `MarkdownText`，这样纯文本与 Markdown 都能正常显示。
 *
 * 只有 `canvas.elements` 缺失或为空时才走这里；有真实画布时永远走
 * `MaicSlideSurface`，不存在"覆盖"上游渲染的问题。
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

  return (
    <div
      ref={containerRef}
      className="relative flex h-full w-full items-center justify-center overflow-hidden"
    >
      <div
        className="relative shrink-0 overflow-hidden"
        style={{
          width: SLIDE_VIEWPORT_SIZE,
          height: SLIDE_VIEWPORT_HEIGHT,
          backgroundColor: '#fff',
          transform: `scale(${scale})`,
          transformOrigin: 'center center',
        }}
      >
        <div className="flex h-full w-full flex-col justify-center gap-6 overflow-hidden px-[72px] py-[56px]">
          {hasTitle && (
            <h1 className="shrink-0 text-[44px] font-bold leading-[1.2] tracking-tight text-[#1f2937]">
              {title}
            </h1>
          )}
          {hasBody && (
            <div className="min-h-0 overflow-hidden text-[20px] leading-[1.6] text-[#374151]">
              <MarkdownText content={body} />
            </div>
          )}
        </div>
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
export function MaicSceneRenderer({ scene, mode }) {
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
        return <MaicSlideSurface canvas={canvas} />;
      }
      case 'quiz':
        if (scene.content.type !== 'quiz') return <div>Invalid quiz content</div>;
        return (
          <QuizView
            key={scene.id}
            questions={scene.content.questions}
            sceneId={scene.id}
            stageId={scene.stageId}
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
  }, [scene, mode]);

  return <div className="w-full h-full">{renderer}</div>;
}

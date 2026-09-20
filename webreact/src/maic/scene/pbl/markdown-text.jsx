import { useMemo } from 'react';
import { marked } from 'marked';

import { cn } from '../../utils/cn.js';

/**
 * 移植自参考项目 `components/scene-renderers/pbl/v2/markdown-text.tsx`。
 *
 * **唯一但重要的近似替换**：上游用 `streamdown` 渲染 Markdown（OpenMAIC 渲染
 * AI 元素消息用的同一个组件）。目标项目依赖里没有 `streamdown`，只有 `marked`。
 * 因此：
 *   - 外层 `<div>` 的**全部 Tailwind 类名逐字保留**（包括那一长串
 *     `[&_div[data-streamdown=...]]` 变体——它们针对的是 streamdown 的 DOM 标记，
 *     用 marked 时不会命中，但按"保留每一个类名"的要求原样留在这里，将来若接入
 *     streamdown 即自动生效）；
 *   - 渲染改为 `marked.parse()` + `dangerouslySetInnerHTML`。
 *
 * 视觉影响：正文排版（`prose` 系列）在目标项目里目前是 no-op——参考项目启用了
 * `@tailwindcss/typography` 插件，而本层的 maic.css 只引入了 Tailwind 的
 * theme + utilities 两层，没有 typography。类名仍然保留，接入插件后即可生效。
 */
export function MarkdownText({ content, className }) {
  const html = useMemo(() => (typeof content === 'string' ? marked.parse(content) : ''), [content]);

  return (
    <div
      className={cn(
        'prose prose-sm dark:prose-invert max-w-none',
        'prose-p:my-2 prose-pre:my-2 prose-headings:mt-3 prose-headings:mb-1',
        'prose-a:text-primary prose-strong:text-foreground prose-li:marker:text-muted-foreground',
        'prose-code:before:content-none prose-code:after:content-none',
        'prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:bg-white/10 prose-code:text-violet-100',
        'prose-pre:bg-zinc-950 prose-pre:text-zinc-100 prose-pre:p-3 prose-pre:rounded-md',
        'prose-pre:overflow-x-auto',
        '[&_div[data-streamdown=code-block]]:relative [&_div[data-streamdown=code-block]]:my-2 [&_div[data-streamdown=code-block]]:gap-0',
        '[&_div[data-streamdown=code-block]]:overflow-hidden [&_div[data-streamdown=code-block]]:rounded-lg [&_div[data-streamdown=code-block]]:border-border/70',
        '[&_div[data-streamdown=code-block]]:bg-zinc-950 [&_div[data-streamdown=code-block]]:p-0',
        '[&_div[data-streamdown=code-block-header]]:absolute [&_div[data-streamdown=code-block-header]]:left-3 [&_div[data-streamdown=code-block-header]]:top-2',
        '[&_div[data-streamdown=code-block-header]]:z-10 [&_div[data-streamdown=code-block-header]]:h-auto [&_div[data-streamdown=code-block-header]]:text-[11px]',
        '[&_div[data-streamdown=code-block-header]]:text-zinc-400 [&_div[data-streamdown=code-block-header]>span]:ml-0',
        '[&_*:has(>div[data-streamdown=code-block-actions])]:!static [&_*:has(>div[data-streamdown=code-block-actions])]:!m-0',
        '[&_*:has(>div[data-streamdown=code-block-actions])]:!h-0 [&_*:has(>div[data-streamdown=code-block-actions])]:!p-0',
        '[&_div[data-streamdown=code-block-actions]]:!absolute [&_div[data-streamdown=code-block-actions]]:!bottom-1.5 [&_div[data-streamdown=code-block-actions]]:!right-1.5',
        '[&_div[data-streamdown=code-block-actions]]:!rounded-md [&_div[data-streamdown=code-block-actions]]:!border-white/10 [&_div[data-streamdown=code-block-actions]]:!bg-zinc-900/85 [&_div[data-streamdown=code-block-actions]]:!text-zinc-300',
        '[&_div[data-streamdown=code-block-body]]:!min-h-[76px] [&_div[data-streamdown=code-block-body]]:!rounded-none [&_div[data-streamdown=code-block-body]]:!border-0',
        '[&_div[data-streamdown=code-block-body]]:!bg-transparent [&_div[data-streamdown=code-block-body]]:!px-3 [&_div[data-streamdown=code-block-body]]:!pb-10 [&_div[data-streamdown=code-block-body]]:!pt-8',
        '[&_div[data-streamdown=code-block-body]]:!text-[13px] [&_div[data-streamdown=code-block-body]]:!text-zinc-100',
        // streamdown ships the code body as `overflow-hidden`, so a long line is
        // clipped on the right with no way to reach it. Make the body (and its
        // <pre>) scroll horizontally instead; keep the vertical axis clipped so
        // the box height is unchanged. The absolutely-positioned header / copy
        // button anchor to the outer code-block, so they stay put while scrolling.
        '[&_div[data-streamdown=code-block-body]]:!overflow-x-auto [&_div[data-streamdown=code-block-body]]:!overflow-y-hidden',
        '[&_div[data-streamdown=code-block-body]>pre]:!m-0 [&_div[data-streamdown=code-block-body]>pre]:!overflow-x-auto [&_div[data-streamdown=code-block-body]>pre]:!bg-transparent [&_div[data-streamdown=code-block-body]>pre]:!text-zinc-100',
        '[&_div[data-streamdown=code-block-body]_code]:!text-zinc-100 [&_div[data-streamdown=code-block-body]_span]:!text-zinc-100',
        className,
      )}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

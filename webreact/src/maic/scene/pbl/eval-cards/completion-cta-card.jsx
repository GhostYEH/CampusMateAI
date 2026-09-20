import { ArrowRight, PartyPopper } from 'lucide-react';

import { cn } from '../../../utils/cn.js';

/**
 * 移植自参考项目
 * `components/scene-renderers/pbl/v2/eval-cards/completion-cta-card.tsx`。
 *
 * 机械改写：擦除接口/类型、去掉 `'use client'`、`@/lib/utils` 改相对路径；
 * `useI18n()` 的 4 个 key 换成 zh-CN 真实文案（见下方内联注释）。类名逐字保留。
 *
 * PBL v2 — Completion CTA card.
 *
 * Appears in chat ONCE the final evaluation has finished streaming.
 * It is NOT the completion report itself — the report is a separate
 * page (completion.jsx). This card is the entry-point that
 * lets the learner re-read the chat history before opening the
 * report.
 */
export function CompletionCtaCard({ onView, className }) {
  return (
    <div
      className={cn(
        'space-y-3 rounded-2xl border border-cyan-100/[0.13] bg-gradient-to-br from-emerald-300/[0.16] via-primary/[0.16] to-purple-300/[0.14] p-5 shadow-[0_18px_46px_rgba(6,16,34,0.28)]',
        className,
      )}
    >
      <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-primary">
        <PartyPopper className="w-4 h-4" />
        {/* pbl.v2.completionCard.title */}
        项目完成 · Completion
      </div>
      <div className="text-sm font-semibold leading-snug">
        {/* pbl.v2.completionCard.subtitle */}
        恭喜你！整个项目跑通了。
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">
        {/* pbl.v2.completionCard.description */}
        我们已经基于你这段时间的数据（用时、对话、错误恢复、解锁的概念……）生成了一份结业报告，包含你打造了什么、学到了什么，以及接下来可以走向哪里。
      </p>
      <button
        type="button"
        onClick={onView}
        className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-[0_0_28px_rgba(155,124,255,0.26)] transition-opacity hover:opacity-90"
      >
        {/* pbl.v2.completion.completionCta */}
        查看结业报告
        <ArrowRight className="w-4 h-4" />
      </button>
    </div>
  );
}

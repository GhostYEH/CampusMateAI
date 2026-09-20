import { ArrowRight, CheckCircle2, Flag } from 'lucide-react';

import { cn } from '../../../utils/cn.js';
import {
  sanitizeMilestoneEvaluationFeedback,
  stripEvaluationTail,
} from '../../lib/eval-tail-parser.js';
import { trimmedPBLText } from '../../lib/pbl-readers.js';
import { MarkdownText } from '../markdown-text.jsx';
import { StarRating } from './star-rating.jsx';

/**
 * 移植自参考项目
 * `components/scene-renderers/pbl/v2/eval-cards/milestone-card.tsx`。
 *
 * 机械改写：擦除接口/类型、去掉 `'use client'`，`@/lib/pbl/v2/readers` 与
 * `@/lib/pbl/v2/operations/runtime/eval-tail-parser` 改本层相对路径；
 * `useI18n()` 的 7 个 key 换成 zh-CN 真实文案。类名与 DOM 逐字保留。
 *
 * PBL v2 — Milestone reflection + handover (combined) card.
 *
 * Per PR 6 D7-B: we merge what the refactor/openmaic-pbl repo had as
 * TWO separate cards (MilestoneNarrativeCard + HandoverCard) into ONE
 * card so the learner doesn't have to scroll past evaluation prose
 * to reach the "继续到下一阶段" button.
 */
export function MilestoneCard({ evaluation, handover, onContinue, className }) {
  if (evaluation.kind !== 'milestone') return null;
  const learned = evaluation.strengths ?? [];
  const performance = (evaluation.improvements ?? [])[0] ?? '';
  const stars = typeof evaluation.stars === 'number' ? evaluation.stars : null;
  const rawNarrative = stripEvaluationTail(
    sanitizeMilestoneEvaluationFeedback(trimmedPBLText(evaluation.feedback)),
  );
  const narrative = handover ? rawNarrative : stripFinalMilestoneContinueGuidance(rawNarrative);
  const ctaState = milestoneHandoverCtaState(handover);
  const consumed = ctaState === 'consumed';

  return (
    <div
      className={cn(
        'relative space-y-4 overflow-hidden rounded-2xl border border-violet-200/85 bg-[linear-gradient(145deg,rgba(252,250,255,0.98)_0%,rgba(238,242,255,0.94)_48%,rgba(232,250,255,0.96)_100%)] p-5 text-slate-800 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_22px_58px_rgba(8,18,38,0.30),0_0_0_1px_rgba(139,92,246,0.10),0_0_42px_rgba(34,211,238,0.10)] ring-1 ring-violet-300/20',
        className,
      )}
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-violet-500 via-indigo-500 to-cyan-400" />
      <div className="pointer-events-none absolute -right-16 -top-20 h-44 w-44 rounded-full bg-cyan-200/35 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 -left-16 h-48 w-48 rounded-full bg-violet-200/30 blur-3xl" />
      {/* Header */}
      <div className="relative flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-violet-700">
          <span className="flex h-7 w-7 items-center justify-center rounded-full border border-violet-200 bg-violet-100 text-violet-700">
            <Flag className="w-4 h-4" />
          </span>
          {/* pbl.v2.milestoneCard.title */}
          阶段测评
        </div>
        {stars !== null && (
          <div className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1">
            <StarRating value={stars} size={18} />
          </div>
        )}
      </div>

      {/* Narrative paragraph */}
      {narrative && (
        <div className="relative text-sm leading-relaxed text-slate-800">
          <MarkdownText
            content={narrative}
            className="pbl-v2-light-card-markdown text-slate-700 prose-p:text-slate-700 prose-strong:text-slate-900 prose-li:marker:text-violet-500"
          />
        </div>
      )}

      {/* Learned bullets */}
      {learned.length > 0 && (
        <div className="relative">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mb-2">
            {/* pbl.v2.milestoneCard.youLearned */}
            你学到了
          </div>
          <ul className="space-y-1.5 text-[13px] text-slate-700">
            {learned.map((s, i) => (
              <li key={i} className="flex gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Performance prose */}
      {performance && (
        <div className="relative border-l-2 border-violet-300 bg-white/35 py-1.5 pl-3 pr-2 text-[13px] italic text-slate-600">
          {performance}
        </div>
      )}

      {/* Handover footer */}
      <div className="relative border-t border-violet-200/80 pt-2">
        {handover ? (
          <div className="space-y-2">
            <div className="text-xs text-slate-600">
              {/* pbl.v2.milestoneCard.nextStage */}
              下一阶段：
              <span className="font-medium text-slate-800 ml-1">{handover.nextMilestoneTitle}</span>
              {!consumed && (
                <div className="text-[11px] text-slate-500 mt-0.5">
                  {/* pbl.v2.milestoneCard.continueHint */}
                  点击 Continue 按钮后，我会再带你进入下一阶段。
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={consumed ? undefined : onContinue}
              disabled={consumed}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-semibold transition-all',
                consumed
                  ? 'cursor-default border border-slate-300 bg-slate-100 text-slate-500 shadow-none'
                  : 'bg-gradient-to-r from-violet-600 to-cyan-500 text-white shadow-[0_12px_28px_rgba(99,102,241,0.30),0_0_22px_rgba(34,211,238,0.18)] hover:from-violet-500 hover:to-cyan-400 hover:shadow-[0_16px_34px_rgba(99,102,241,0.38),0_0_28px_rgba(34,211,238,0.24)]',
              )}
            >
              {consumed ? (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  {/* pbl.v2.milestoneCard.alreadyEntered */}
                  已进入下一阶段
                </>
              ) : (
                <>
                  {/* pbl.v2.milestoneCard.continueToNext */}
                  继续到下一阶段
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        ) : (
          <div className="text-xs text-slate-500">
            {/* pbl.v2.milestoneCard.projectAlmostDone */}
            🎉 项目即将完成 —— 等待结业报告
          </div>
        )}
      </div>
    </div>
  );
}

export function milestoneHandoverCtaState(handover) {
  if (!handover) return 'hidden';
  return handover.consumed ? 'consumed' : 'ready';
}

export function stripFinalMilestoneContinueGuidance(text) {
  return text
    .replace(
      /(?:[。！？!?]\s*)?[^。！？!?]*(?:点击|按|选择)\s*(?:右侧|下方|这个)?\s*(?:Continue|继续)(?:\s*按钮)?[^。！？!?]*(?:[。！？!?]|$)/giu,
      (match) => {
        const trimmed = match.trimStart();
        return trimmed.startsWith('。') || trimmed.startsWith('！') || trimmed.startsWith('？')
          ? trimmed.charAt(0)
          : '';
      },
    )
    .replace(/\s{2,}/g, ' ')
    .trim();
}

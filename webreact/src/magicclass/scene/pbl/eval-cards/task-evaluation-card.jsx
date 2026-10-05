import { ClipboardCheck, TrendingUp, Sparkles } from 'lucide-react';

import { cn } from '../../../utils/cn.js';

/**
 * 移植自参考项目
 * `components/scene-renderers/pbl/v2/eval-cards/task-evaluation-card.tsx`。
 *
 * 机械改写：擦除接口/类型、去掉 `'use client'`、`@/lib/utils` 改相对路径；
 * `useI18n()` 的 3 个 key 换成 zh-CN 真实文案。类名、内联 style、DOM 逐字保留。
 *
 * PBL v2 — Task evaluation card.
 *
 * Rendered inside an assistant chat bubble (NOT a standalone full-
 * width card — task eval is "small judgement step" per PR 6 D1-B).
 * Appears after the learner submits something AND advance_micro_task
 * fires the task eval flow.
 *
 * Fields used: strengths[], improvements[], score? — none of
 * what_you_built / what_you_learned / stars (those belong to other
 * evaluation kinds). Score is OPTIONAL: if the LLM omitted it we
 * just render the prose lists; no fake "/100" appears.
 */
export function TaskEvaluationCard({ evaluation, className }) {
  if (evaluation.kind !== 'task') return null;
  const strengths = evaluation.strengths ?? [];
  const improvements = evaluation.improvements ?? [];
  const score = typeof evaluation.score === 'number' ? evaluation.score : undefined;
  if (strengths.length === 0 && improvements.length === 0 && score === undefined) {
    return null;
  }

  return (
    <div
      className={cn(
        'pbl-v2-task-review-card mt-2 space-y-3 rounded-2xl px-3.5 py-3 text-sm text-slate-800',
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-violet-700">
          <ClipboardCheck className="h-3 w-3" />
          {/* pbl.v2.taskEvalCard.title */}
          本次提交点评
        </span>
        {score !== undefined && (
          <span
            className="rounded-md border border-violet-200/70 bg-violet-100/90 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-violet-700 shadow-sm"
            aria-label={`Score ${score} out of 100`}
          >
            {score} / 100
          </span>
        )}
      </div>

      {strengths.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-indigo-700 mb-1.5 font-medium">
            <Sparkles className="w-3 h-3" />
            {/* pbl.v2.taskEvalCard.strengths */}
            做得好的
          </div>
          <ul className="space-y-1 text-sm leading-snug text-slate-700">
            {strengths.map((s, i) => (
              <li key={i} className="flex gap-1.5">
                <span className="shrink-0 text-indigo-600">✓</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {improvements.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-cyan-700 mb-1.5 font-medium">
            <TrendingUp className="w-3 h-3" />
            {/* pbl.v2.taskEvalCard.improvements */}
            下次可以
          </div>
          <ul className="space-y-1 text-sm leading-snug text-slate-700">
            {improvements.map((s, i) => (
              <li key={i} className="flex gap-1.5">
                <span className="shrink-0 text-cyan-700">→</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

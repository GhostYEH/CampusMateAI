import {
  ArrowLeft,
  Award,
  Check,
  Clock,
  Compass,
  Contrast,
  Hammer,
  Layers,
  Lightbulb,
  MessageCircle,
  ShieldCheck,
  Sparkles,
  Star,
  Target,
  Trophy,
  X,
} from 'lucide-react';
import { motion } from 'motion/react';

import { stripEvaluationTail } from '../lib/eval-tail-parser.js';
import { computeCompletionStats } from '../lib/completion-stats.js';

/**
 * 移植自参考项目 `components/scene-renderers/pbl/v2/completion.tsx`（729 行）。
 *
 * 机械改写（类名、内联 style、SVG/motion 参数、DOM 结构全部逐字保留）：
 *   1. TypeScript 类型 / interface / 泛型 / `as` 全部擦除。
 *   2. `useI18n()` 的 `t('key')` 全部换成参考项目 zh-CN locale 的真实文案；
 *      插值用模板字符串：
 *        durationMinutes        {{m}} 分钟        -> `${m} 分钟`
 *        durationHours          {{h}} 小时        -> `${h} 小时`
 *        durationHoursMinutes   {{h}} 小时 {{m}} 分钟 -> `${h} 小时 ${m} 分钟`
 *        summary                {{completed}}/{{total}}/{{stages}}
 *        scenario.summary       {{acts}}
 *        scenario.goalReviewHint{{achieved}}/{{total}}
 *        submissionsInStage     {{count}}
 *        coreConceptGrasp       {{concept}} / {{quality}}
 *        highlight.independence {{unlocks}}/{{total}}
 *        highlight.resilience   {{title}} / {{errors}}
 *        scenario.castLabel     {{names}}
 *      动态 key `pbl.v2.completion.synthesisQuality.<strong|ok|weak>` 用同值常量表
 *      SYNTHESIS_QUALITY（键一一对应）。
 *   3. `@/lib/pbl/v2/operations/runtime/*` 改本层相对路径。
 *   4. 注意：`Stars` 这个小标题在参考项目里本来就是硬编码英文（不是 i18n key），
 *      因此原样保留。
 */

export function buildCompletionReportViewModel(project) {
  const totalMicrotasks = project.milestones.reduce((acc, m) => acc + m.microtasks.length, 0);
  const completedMicrotasks = project.milestones.reduce(
    (acc, m) => acc + m.microtasks.filter((t) => t.status === 'completed').length,
    0,
  );
  const finalEvaluation = project.evaluations.filter((ev) => ev.kind === 'final').at(-1);
  return {
    totalMicrotasks,
    completedMicrotasks,
    stageCount: project.milestones.length,
    finalEvaluation,
    intro: cleanCompletionIntro(finalEvaluation?.feedback),
    whatYouBuilt: finalEvaluation?.whatYouBuilt ?? [],
    whatYouLearned: finalEvaluation?.whatYouLearned ?? [],
    whatsNext: finalEvaluation?.whatsNext,
    stars: finalEvaluation?.stars,
    stats: computeCompletionStats(project),
  };
}

export function cleanCompletionIntro(feedback) {
  const intro = stripEvaluationTail(typeof feedback === 'string' ? feedback : '')
    .replace(/\{\{\s*[^}]+\s*\}\}/g, '')
    .trim();
  return intro || undefined;
}

/** pbl.v2.completion.duration* 三个模板。 */
function formatDuration(totalSeconds) {
  if (totalSeconds <= 0) return '—';
  const m = Math.floor(totalSeconds / 60);
  if (m < 60) return `${m} 分钟`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return rm > 0 ? `${h} 小时 ${rm} 分钟` : `${h} 小时`;
}

/** pbl.v2.completion.synthesisQuality.*（zh-CN）——动态 key，用同值常量表。 */
const SYNTHESIS_QUALITY = {
  strong: '理解到位 ✅',
  ok: '基本掌握 👍',
  weak: '还可以再巩固 💪',
};

export function PBLV2Completion({ project, onBack }) {
  const report = buildCompletionReportViewModel(project);
  const { stats } = report;

  // Shared shell (celebration, hero, stars, what's-next) is identical for both
  // project kinds; the BODY between hero and what's-next is fully split by
  // `stats.kind` into two components that share NO fields — the discriminated
  // union makes it impossible for one to read the other's metrics.
  const heroCaption = stats.kind === 'scenario' ? stats.sceneCaption : undefined;
  const heroSummary =
    report.intro ??
    (stats.kind === 'scenario'
      ? // pbl.v2.completion.scenario.summary
        `你完成了这场情景模拟的 ${stats.acts.total} 幕。这是这次角色扮演的表现回顾。`
      : // pbl.v2.completion.summary
        `你完成了全部 ${report.completedMicrotasks} / ${report.totalMicrotasks} 个任务，跨越了 ${report.stageCount} 个阶段。`);

  return (
    <div className="relative h-full w-full overflow-y-auto bg-[radial-gradient(circle_at_20%_10%,rgba(124,92,255,0.18),transparent_32%),radial-gradient(circle_at_88%_0%,rgba(34,211,238,0.14),transparent_30%),linear-gradient(135deg,#0b1220_0%,#111c33_52%,#0a1020_100%)] text-slate-100">
      <div className="m-auto w-full max-w-6xl px-8 py-10">
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="mb-4 inline-flex items-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-xs font-medium text-slate-200 transition hover:bg-white/[0.08]"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            {/* pbl.v2.completion.backToWorkspace */}
            返回工作台
          </button>
        )}

        {/* ── Celebration ── */}
        <CelebrationHeader />

        {/* ── Hero banner ── */}
        <section className="relative overflow-hidden rounded-3xl border border-white/[0.08] bg-white/[0.045] p-7 shadow-[0_12px_40px_rgba(0,0,0,0.20)] backdrop-blur-xl">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-wider text-cyan-200/90">
            <span className="inline-flex items-center gap-2">
              <Trophy className="h-4 w-4 text-amber-300" />
              {/* pbl.v2.completion.title */}
              项目结业报告
            </span>
          </div>
          <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-white">{project.title}</h1>
              {heroCaption && (
                <p className="mt-2 text-sm font-medium text-cyan-200/80">{heroCaption}</p>
              )}
              <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-300/90">
                {heroSummary}
              </p>
            </div>
            {typeof report.stars === 'number' && (
              <div className="shrink-0 rounded-2xl border border-amber-200/15 bg-amber-300/[0.08] px-4 py-3 text-right">
                <div className="mb-1 text-[10px] uppercase tracking-wider text-amber-200/90">
                  Stars
                </div>
                <div className="flex items-center gap-1 text-amber-300">
                  <Star className="h-4 w-4 fill-current" />
                  <span className="text-2xl font-bold text-white">{report.stars}</span>
                  <span className="text-sm text-amber-100/80">/ 5</span>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* ── Body (split by project kind — no shared fields) ── */}
        {stats.kind === 'scenario' ? (
          <ScenarioCompletionBody stats={stats} report={report} />
        ) : (
          <StandardCompletionBody stats={stats} report={report} />
        )}

        {/* ── What's next ── */}
        <section className="mt-4 rounded-2xl border border-white/[0.07] bg-white/[0.035] p-5">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-100">
            <Compass className="h-4 w-4 text-cyan-300" />
            {/* pbl.v2.completion.whatsNext */}
            下一步
          </div>
          <p className="text-sm leading-relaxed text-slate-300">
            {/* pbl.v2.completion.noWhatsNext */}
            {report.whatsNext ?? '最终评测还没有写入下一步建议。'}
          </p>
        </section>
      </div>
    </div>
  );
}

/** Knowledge-project body: stat cards + built/learned + stage review +
 *  highlights. This is the ORIGINAL completion content, moved verbatim — normal
 *  projects render byte-identically to before the scenario split. */
function StandardCompletionBody({ stats, report }) {
  return (
    <>
      {/* ── Stats cards ── */}
      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard
          icon={<Lightbulb className="h-4 w-4" />}
          /* pbl.v2.completion.statConcepts */
          label="掌握概念"
          value={String(stats.conceptsUnlocked.length)}
        />
        <StatCard
          icon={<MessageCircle className="h-4 w-4" />}
          /* pbl.v2.completion.statTurns */
          label="对话轮次"
          value={String(stats.totalTurns)}
        />
        <StatCard
          icon={<Layers className="h-4 w-4" />}
          /* pbl.v2.completion.statScope */
          label="阶段 · 任务"
          value={`${report.stageCount} · ${report.totalMicrotasks}`}
        />
        <StatCard
          icon={<Clock className="h-4 w-4" />}
          /* pbl.v2.completion.statDuration */
          label="项目用时"
          value={formatDuration(stats.totalDurationSeconds)}
        />
        <StatCard
          icon={<Hammer className="h-4 w-4" />}
          /* pbl.v2.completion.statSubmissions */
          label="提交作品"
          value={String(stats.totalSubmissions)}
        />
      </div>

      {/* ── LLM global summary ── */}
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <ReportSection
          icon={<Hammer className="h-4 w-4" />}
          /* pbl.v2.completion.whatYouBuilt */
          title="你打造了什么"
          items={report.whatYouBuilt}
          /* pbl.v2.completion.noDataFallback */
          fallback="最终评测还没有写入"
        />
        <ReportSection
          icon={<Sparkles className="h-4 w-4" />}
          /* pbl.v2.completion.whatYouLearned */
          title="你学到了什么"
          items={report.whatYouLearned}
          fallback="最终评测还没有写入"
        />
      </div>

      {/* ── Stage review ── */}
      {stats.stageDetails.length > 0 && (
        <section className="mt-4 rounded-2xl border border-white/[0.07] bg-white/[0.035] p-5">
          <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-100">
            <ShieldCheck className="h-4 w-4 text-cyan-300" />
            {/* pbl.v2.completion.stageReview */}
            阶段回顾
          </div>
          <ol className="grid gap-3 md:grid-cols-2">
            {stats.stageDetails.map((sd, idx) => (
              <StageReviewItem key={`${idx}-${sd.milestoneTitle}`} detail={sd} index={idx} />
            ))}
          </ol>
        </section>
      )}

      {stats.highlights.length > 0 && (
        <section className="mt-4 rounded-2xl border border-amber-200/15 bg-amber-300/[0.05] p-5">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-100">
            <Award className="h-4 w-4 text-amber-300" />
            {/* pbl.v2.completion.highlightsTitle */}
            你的亮点
          </div>
          <ul className="space-y-2">
            {stats.highlights.map((h, idx) => (
              <li key={idx} className="text-sm leading-relaxed text-slate-200">
                {formatHighlight(h)}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

/** SCENARIO body: skill-practice stat cards + what-you-did-well / skills +
 *  per-act goal review (the externalised hidden goals, judged by the final
 *  evaluator) + cast. Shows NO knowledge metrics. */
function ScenarioCompletionBody({ stats, report }) {
  const cov = stats.goalCoverage;
  return (
    <>
      {/* ── Stat cards ── */}
      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {cov && (
          <StatCard
            icon={<Target className="h-4 w-4" />}
            /* pbl.v2.completion.scenario.statGoals */
            label="目标达成"
            value={`${cov.achieved}/${cov.total}`}
          />
        )}
        <StatCard
          icon={<Layers className="h-4 w-4" />}
          /* pbl.v2.completion.scenario.statActs */
          label="完成幕数"
          value={String(stats.acts.total)}
        />
        <StatCard
          icon={<MessageCircle className="h-4 w-4" />}
          /* pbl.v2.completion.statTurns */
          label="对话轮次"
          value={String(stats.totalTurns)}
        />
        <StatCard
          icon={<Clock className="h-4 w-4" />}
          /* pbl.v2.completion.statDuration */
          label="项目用时"
          value={formatDuration(stats.totalDurationSeconds)}
        />
      </div>

      {/* ── LLM skill summary ── */}
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <ReportSection
          icon={<Hammer className="h-4 w-4" />}
          /* pbl.v2.completion.scenario.whatYouDidWell */
          title="你做得好的地方"
          items={report.whatYouBuilt}
          fallback="最终评测还没有写入"
        />
        <ReportSection
          icon={<Sparkles className="h-4 w-4" />}
          /* pbl.v2.completion.scenario.skillsPracticed */
          title="你练到的技能"
          items={report.whatYouLearned}
          fallback="最终评测还没有写入"
        />
      </div>

      {/* ── Per-act goal review (externalised hidden goals) ── */}
      {cov && (
        <section className="mt-4 rounded-2xl border border-white/[0.07] bg-white/[0.035] p-5">
          <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-slate-100">
            <Target className="h-4 w-4 text-cyan-300" />
            {/* pbl.v2.completion.scenario.goalReviewTitle */}
            逐幕回顾
          </div>
          <p className="mb-4 text-xs leading-relaxed text-slate-400">
            {/* pbl.v2.completion.scenario.goalReviewHint */}
            这场情景模拟为每一幕都设定了几个关键目标。下面根据你和角色的真实对话，回顾你这次达成了其中的 {cov.achieved}/{cov.total} 个。
          </p>
          <ol className="grid gap-3 md:grid-cols-2">
            {cov.acts.map((act, idx) => (
              <ActGoalReviewItem key={`${idx}-${act.milestoneId}`} act={act} index={idx} />
            ))}
          </ol>
        </section>
      )}

      {/* ── Per-act goal list (FALLBACK, no verdict) ──
          Shown only when there is no scored `goalCoverage` — chiefly older
          projects finished before the act-goals evaluator shipped. Renders the
          authored "what each act asked you to do" read-only, so the structured
          review survives instead of dropping to a bare narrative. Mutually
          exclusive with the scored review above. */}
      {!cov && stats.goalScaffold && stats.goalScaffold.length > 0 && (
        <section className="mt-4 rounded-2xl border border-white/[0.07] bg-white/[0.035] p-5">
          <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-slate-100">
            <Target className="h-4 w-4 text-cyan-300" />
            {/* pbl.v2.completion.scenario.goalListTitle */}
            每一幕的目标
          </div>
          <p className="mb-4 text-xs leading-relaxed text-slate-400">
            {/* pbl.v2.completion.scenario.goalListHint */}
            这场情景模拟为每一幕都设定了几个关键目标。下面是各幕的目标回顾。
          </p>
          <ol className="grid gap-3 md:grid-cols-2">
            {stats.goalScaffold.map((act, idx) => (
              <ActGoalListItem key={`${idx}-${act.milestoneId}`} act={act} index={idx} />
            ))}
          </ol>
        </section>
      )}

      {/* ── Cast ── */}
      {stats.characterNames.length > 0 && (
        <p className="mt-3 px-1 text-xs text-slate-400">
          {/* pbl.v2.completion.scenario.castLabel：你与之互动的角色：{{names}}
              （参考实现用 join('、') 连接角色名，此处保留。） */}
          你与之互动的角色：{stats.characterNames.join('、')}
        </p>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

// Deterministic confetti layout (no Math.random at render → no hydration
// mismatch). Each piece falls + drifts + spins on an infinite loop.
const CONFETTI = [
  { left: 6, color: '#a78bfa', size: 6, delay: 0.0, duration: 3.0, drift: 14, rotate: 320 },
  { left: 14, color: '#67e8f9', size: 7, delay: 0.7, duration: 3.4, drift: -10, rotate: -260 },
  { left: 22, color: '#fcd34d', size: 5, delay: 1.3, duration: 2.8, drift: 8, rotate: 400 },
  { left: 30, color: '#6ee7b7', size: 6, delay: 0.4, duration: 3.2, drift: -16, rotate: -340 },
  { left: 38, color: '#f9a8d4', size: 7, delay: 1.0, duration: 3.6, drift: 12, rotate: 300 },
  { left: 46, color: '#7dd3fc', size: 5, delay: 0.2, duration: 2.9, drift: -8, rotate: -380 },
  { left: 54, color: '#a78bfa', size: 6, delay: 1.5, duration: 3.3, drift: 16, rotate: 360 },
  { left: 62, color: '#fcd34d', size: 7, delay: 0.6, duration: 3.0, drift: -12, rotate: -300 },
  { left: 70, color: '#6ee7b7', size: 5, delay: 1.1, duration: 3.5, drift: 10, rotate: 420 },
  { left: 78, color: '#67e8f9', size: 6, delay: 0.3, duration: 2.7, drift: -14, rotate: -340 },
  { left: 86, color: '#f9a8d4', size: 7, delay: 0.9, duration: 3.4, drift: 8, rotate: 320 },
  { left: 94, color: '#a78bfa', size: 5, delay: 1.4, duration: 3.1, drift: -10, rotate: -360 },
  { left: 18, color: '#fcd34d', size: 6, delay: 1.8, duration: 3.2, drift: 12, rotate: 380 },
  { left: 82, color: '#7dd3fc', size: 6, delay: 2.0, duration: 3.3, drift: -8, rotate: -320 },
];

function CelebrationHeader() {
  return (
    <div className="pointer-events-none relative mx-auto mb-2 flex h-24 w-full max-w-md items-center justify-center">
      {CONFETTI.map((c, i) => (
        <motion.span
          key={i}
          className="absolute top-0 block rounded-[2px]"
          style={{
            left: `${c.left}%`,
            width: c.size,
            height: c.size * 1.6,
            backgroundColor: c.color,
          }}
          initial={{ y: -12, x: 0, opacity: 0, rotate: 0 }}
          animate={{ y: [-12, 108], x: [0, c.drift], opacity: [0, 1, 1, 0], rotate: [0, c.rotate] }}
          transition={{
            duration: c.duration,
            delay: c.delay,
            repeat: Infinity,
            repeatDelay: 0.5,
            ease: 'easeIn',
          }}
        />
      ))}
      <motion.div
        className="relative z-10 select-none text-5xl drop-shadow-[0_6px_18px_rgba(0,0,0,0.35)]"
        initial={{ scale: 0.5, rotate: -12, opacity: 0 }}
        animate={{ scale: 1, rotate: 0, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 220, damping: 12, delay: 0.1 }}
      >
        <motion.span
          className="inline-block"
          animate={{ y: [0, -6, 0], rotate: [0, 6, -4, 0] }}
          transition={{ duration: 2.6, repeat: Infinity, ease: 'easeInOut' }}
        >
          🎉
        </motion.span>
      </motion.div>
    </div>
  );
}

/** pbl.v2.completion.highlight.* —— 参考实现通过 `t()` 插值，此处用模板字符串。 */
function formatHighlight(h) {
  switch (h.kind) {
    case 'independence':
      return `你自主展现了 ${h.unlocks ?? 0}/${h.total ?? 0} 个概念——不靠追问，自己就表达出来了，理解很扎实。`;
    case 'resilience':
      return h.milestoneTitle
        ? `在「${h.milestoneTitle}」阶段你克服了 ${h.errors ?? 0} 个错误，逐一攻克——韧性强。`
        : `你克服了 ${h.errors ?? 0} 个错误，逐一攻克——韧性强。`;
    case 'completion':
    default:
      return '完成了全部任务，每一步都扎实走过。';
  }
}

function StatCard({ icon, label, value }) {
  return (
    <div className="rounded-2xl border border-white/[0.06] bg-white/[0.035] px-4 py-3.5 text-center transition-colors hover:bg-white/[0.055]">
      <div className="mb-1.5 inline-flex items-center justify-center rounded-lg bg-white/[0.06] p-1.5 text-cyan-300/90">
        {icon}
      </div>
      <div className="text-xl font-bold text-white">{value}</div>
      <div className="mt-0.5 text-[11px] text-slate-400">{label}</div>
    </div>
  );
}

/** SCENARIO ONLY. One act's goal-coverage card: the act title + each
 *  externalised goal with a three-state status icon, its skill label, and the
 *  evaluator's note. The goals were hidden checkpoints during play; here they
 *  are revealed read-only as "what this act was about". */
function ActGoalReviewItem({ act, index }) {
  return (
    <li className="rounded-xl border border-white/[0.05] bg-white/[0.03] px-4 py-3.5">
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-cyan-100/[0.10] text-[11px] font-bold text-cyan-200/80">
          {index + 1}
        </span>
        <span className="text-sm font-medium text-slate-100">{act.actTitle}</span>
      </div>
      <ul className="mt-2.5 ml-1 space-y-2">
        {act.goals.map((g, gi) => (
          <li key={gi} className="flex gap-2 text-xs leading-relaxed">
            <GoalStatusIcon status={g.status} />
            <div className="min-w-0 flex-1">
              <span className="text-slate-200">{g.goal}</span>
              {g.skillFocus && (
                <span className="ml-1.5 inline-block rounded bg-violet-300/[0.10] px-1.5 py-0.5 text-[10px] text-violet-200">
                  {g.skillFocus}
                </span>
              )}
              {g.note && <p className="mt-0.5 text-[11px] text-slate-400">{g.note}</p>}
            </div>
          </li>
        ))}
      </ul>
    </li>
  );
}

/** FALLBACK list item: the authored act + its goals, READ-ONLY (no verdict).
 *  Used when there is no scored `goalCoverage` (older projects). Mirrors
 *  `ActGoalReviewItem`'s layout but drops the status icon + note. */
function ActGoalListItem({ act, index }) {
  return (
    <li className="rounded-xl border border-white/[0.05] bg-white/[0.03] px-4 py-3.5">
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-cyan-100/[0.10] text-[11px] font-bold text-cyan-200/80">
          {index + 1}
        </span>
        <span className="text-sm font-medium text-slate-100">{act.actTitle}</span>
      </div>
      <ul className="mt-2.5 ml-1 space-y-2">
        {act.goals.map((g, gi) => (
          <li key={gi} className="flex gap-2 text-xs leading-relaxed">
            <span className="mt-0.5 text-slate-500" aria-hidden>
              •
            </span>
            <div className="min-w-0 flex-1">
              <span className="text-slate-200">{g.goal}</span>
              {g.skillFocus && (
                <span className="ml-1.5 inline-block rounded bg-violet-300/[0.10] px-1.5 py-0.5 text-[10px] text-violet-200">
                  {g.skillFocus}
                </span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </li>
  );
}

/** Three-state goal status icon: achieved ✓ / partial ◐ / missed ✗. */
function GoalStatusIcon({ status }) {
  if (status === 'achieved') {
    return (
      <Check
        className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400"
        /* pbl.v2.completion.scenario.goalAchieved */
        aria-label="做到了"
      />
    );
  }
  if (status === 'partial') {
    return (
      <Contrast
        className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300"
        /* pbl.v2.completion.scenario.goalPartial */
        aria-label="部分做到"
      />
    );
  }
  return (
    <X
      className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-500"
      /* pbl.v2.completion.scenario.goalMissed */
      aria-label="没做到"
    />
  );
}

function StageReviewItem({ detail, index }) {
  const hasContent =
    detail.conceptsInStage.length > 0 || detail.submissionsInStage > 0 || detail.isCoreStage;

  return (
    <li className="rounded-xl border border-white/[0.05] bg-white/[0.03] px-4 py-3.5">
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-cyan-100/[0.10] text-[11px] font-bold text-cyan-200/80">
          {index + 1}
        </span>
        <span className="text-sm font-medium text-slate-100">
          {detail.milestoneTitle}
          {detail.isCoreStage && (
            <span className="ml-1.5 rounded-full border border-violet-300/20 bg-violet-300/[0.08] px-1.5 py-0.5 text-[10px] text-violet-200">
              {/* pbl.v2.completion.coreStageBadge */}
              核心
            </span>
          )}
        </span>
      </div>
      {hasContent ? (
        <ul className="mt-2 ml-7 space-y-1">
          {detail.conceptsInStage.length > 0 && (
            <li className="text-xs text-slate-400">
              <span className="mr-1 text-emerald-300/80">+</span>
              {/* pbl.v2.completion.conceptsInStageLabel */}
              解锁了概念：
              {detail.conceptsInStage.map((c, ci) => (
                <span key={ci}>
                  <span className="inline-block rounded bg-cyan-100/[0.08] px-1.5 py-0.5 text-[11px] text-cyan-100">
                    {c}
                  </span>
                  {ci < detail.conceptsInStage.length - 1 && (
                    <span className="text-slate-500">{'、'}</span>
                  )}
                </span>
              ))}
            </li>
          )}
          {detail.submissionsInStage > 0 && (
            <li className="text-xs text-slate-400">
              <span className="mr-1 text-cyan-300/80">+</span>
              {/* pbl.v2.completion.submissionsInStage：提交了 {{count}} 件作品 */}
              提交了 {detail.submissionsInStage} 件作品
            </li>
          )}
          {detail.isCoreStage && detail.coreConcept && detail.synthesisQuality && (
            <li className="text-xs text-slate-200">
              <span className="mr-1 text-violet-300/80">+</span>
              {/* pbl.v2.completion.coreConceptGrasp：核心概念「{{concept}}」——{{quality}} */}
              核心概念「{detail.coreConcept}」——{SYNTHESIS_QUALITY[detail.synthesisQuality]}
            </li>
          )}
        </ul>
      ) : (
        <p className="mt-1 ml-7 text-xs text-slate-500">
          {/* pbl.v2.completion.stageNoData */}
          本阶段没有记录的产出。
        </p>
      )}
    </li>
  );
}

function ReportSection({ icon, title, items, fallback }) {
  return (
    <section className="rounded-2xl border border-white/[0.07] bg-white/[0.035] p-5">
      <div className="mb-3.5 flex items-center gap-2 text-sm font-semibold text-slate-100">
        <span className="text-cyan-300">{icon}</span>
        {title}
      </div>
      {items.length ? (
        <ul className="space-y-2.5">
          {items.map((item, idx) => (
            <li
              key={`${idx}-${item}`}
              className="flex gap-2.5 text-sm leading-relaxed text-slate-300"
            >
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-300/60" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-400">{fallback}</p>
      )}
    </section>
  );
}

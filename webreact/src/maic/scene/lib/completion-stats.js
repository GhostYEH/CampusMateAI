/**
 * 移植自参考项目 `lib/pbl/v2/operations/runtime/completion-stats.ts`。
 * 仅擦除 TypeScript 类型标注（interface / type / 泛型 / 断言），计算逻辑逐字保留。
 *
 * PBL v2 — Completion report stats (deterministic, no LLM).
 *
 * All fields are derived from already-persisted project data
 * (milestones, microtask engagement caches, submissions, and
 * engagement events). The computation is pure — no side effects,
 * no network calls, no LLM invocation.
 */

import { trimmedPBLText } from './pbl-readers.js';

export function computeCompletionStats(project) {
  // One-time fork at the entry point: a scenario project and a normal project
  // share NO downstream computation. This keeps the normal-project path
  // byte-identical to before (it never touches scenario code) and the scenario
  // path free of meaningless knowledge metrics.
  return project.scenario ? computeScenarioStats(project) : computeStandardStats(project);
}

function computeStandardStats(project) {
  const concepts = collectUniqueConcepts(project);
  const { unlocks, checks } = countEvidenceEvents(project);
  const totalErrors = sumField(project, 'errorCount');
  const totalTurns = sumField(project, 'learnerTurnCount');
  const totalDurationSeconds = sumField(project, 'durationSeconds');
  const totalSubmissions = project.submissions.length;
  const toughest = findToughestMilestone(project);
  const stageDetails = buildStageDetails(project);
  const highlights = buildHighlights(
    concepts,
    unlocks,
    checks,
    totalErrors,
    toughest,
    stageDetails,
  );

  return {
    kind: 'standard',
    conceptsUnlocked: concepts,
    independenceRate: unlocks + checks > 0 ? unlocks / (unlocks + checks) : 0,
    totalErrors,
    totalTurns,
    totalDurationSeconds,
    totalSubmissions,
    toughestMilestone: toughest,
    stageDetails,
    highlights,
  };
}

/** SCENARIO ONLY. The authored act→goals scaffold: every roleplay act and its
 *  beats' `successWhen` (+ `skillFocus`), pulled straight from project data.
 *  SINGLE SOURCE OF TRUTH for BOTH the final-eval prompt (which lists these
 *  goals for the LLM to judge) AND the back-fill of the LLM's verdict
 *  (`normalizeActGoals`), so the prompt and the parse can never drift. Goal
 *  text / skill / title always originate here — never from the model. Pure. */
export function scenarioActGoalsScaffold(project) {
  const out = [];
  for (const ms of project.milestones) {
    if (ms.scenarioStage !== 'roleplay') continue;
    const goals = ms.microtasks
      .map((b) => {
        const goal = trimmedPBLText(b.successWhen) || trimmedPBLText(b.completionCriteria);
        if (!goal) return undefined;
        const skillFocus = trimmedPBLText(b.skillFocus) || undefined;
        return skillFocus ? { goal, skillFocus } : { goal };
      })
      .filter((g) => !!g);
    if (goals.length === 0) continue;
    out.push({ milestoneId: ms.id, actTitle: ms.title, goals });
  }
  return out;
}

/** SCENARIO FINAL ONLY. Overlay the final evaluator's per-goal verdict
 *  (`status` + optional `note`) onto the authored scaffold. Goal text /
 *  skillFocus / actTitle ALWAYS come from project data — the LLM only
 *  contributes status/note, so it can never rewrite or invent a goal.
 *
 *  ALIGNMENT IS STRICT AND INDEX-BASED — never by array position. Acts align by
 *  `milestoneId`; within an act, each verdict aligns to its goal by the model-
 *  supplied `goalIndex`. The model's `goals` for an act must form a perfect
 *  bijection over `[0, N)`: every index present EXACTLY once, in range, with a
 *  valid status. This defends against the model REORDERING two goals inside the
 *  same act (same count, valid statuses, but swapped) — positional alignment
 *  would silently pin each verdict onto the wrong goal; index alignment puts it
 *  back where it belongs. If ANYTHING is off — missing act, wrong goal count,
 *  out-of-range / duplicate / missing goalIndex, or an invalid status — we
 *  return `undefined` (rather than a mislabelled or fabricated scorecard) and
 *  let the completion page fall back to its narrative + read-only goal list.
 *  Pure + client-safe. */
export function normalizeActGoals(raw, project) {
  const scaffold = scenarioActGoalsScaffold(project);
  if (scaffold.length === 0) return undefined;

  const byMs = new Map();
  if (Array.isArray(raw)) {
    for (const entry of raw) {
      if (entry && typeof entry === 'object') {
        const id = entry.milestoneId;
        if (typeof id === 'string') byMs.set(id, entry);
      }
    }
  }

  const isStatus = (s) => s === 'achieved' || s === 'partial' || s === 'missed';

  const result = [];
  for (const act of scaffold) {
    const entry = byMs.get(act.milestoneId);
    const llmGoals = Array.isArray(entry?.goals) ? entry.goals : undefined;
    // STRICT GATE 1 (act presence + count): the model must have returned this
    // act, with a goals array of exactly the scaffold's length. A mismatch
    // (missing act, truncated tail, wrong count) means we cannot trust the
    // overlay — abort the whole thing so no goal is mislabelled `missed`.
    if (!llmGoals || llmGoals.length !== act.goals.length) return undefined;

    // STRICT GATE 2 (index alignment, NOT array position): align each verdict
    // to its goal by the model-supplied `goalIndex`, never by array order — so
    // a model that reorders two goals within the same act cannot silently pin a
    // verdict onto the wrong goal. Require a perfect bijection over [0, N):
    // every index present EXACTLY once, in range, with a valid status. Any
    // gap / duplicate / out-of-range / bad status → abort to undefined.
    const byIndex = new Map();
    const notes = new Map();
    for (const raw2 of llmGoals) {
      const v = raw2;
      const idx = v?.goalIndex;
      // goalIndex must be an integer in range and not already seen (no dupes).
      if (
        typeof idx !== 'number' ||
        !Number.isInteger(idx) ||
        idx < 0 ||
        idx >= act.goals.length ||
        byIndex.has(idx)
      ) {
        return undefined;
      }
      if (!isStatus(v?.status)) return undefined;
      byIndex.set(idx, v.status);
      const note = typeof v?.note === 'string' && v.note.trim() ? v.note.trim() : undefined;
      if (note) notes.set(idx, note);
    }
    // Full coverage: every authored goal index must have a verdict. (Count
    // already matches and there are no dupes, so this also implies no gaps —
    // kept explicit as a belt-and-suspenders guard.)
    for (let i = 0; i < act.goals.length; i++) {
      if (!byIndex.has(i)) return undefined;
    }

    result.push({
      milestoneId: act.milestoneId,
      actTitle: act.actTitle,
      goals: act.goals.map((g, i) => {
        const note = notes.get(i);
        return {
          goal: g.goal,
          ...(g.skillFocus ? { skillFocus: g.skillFocus } : {}),
          status: byIndex.get(i),
          ...(note ? { note } : {}),
        };
      }),
    });
  }

  return result;
}

/** SCENARIO ONLY. Roll up role-play skill metrics: act counts + turns/time from
 *  the engagement caches, the cast + caption, and the per-act goal coverage from
 *  the final evaluator. Pure; reads only persisted project data, no server-only
 *  deps. The per-act goal coverage (LLM goal-coverage verdict) is the real
 *  scenario signal — there is no choice-decision scoreboard. */
function computeScenarioStats(project) {
  // ACT MODEL: beats are background checkpoints all marked done on "finish
  // act", so per-beat counts are meaningless. Count completed ACTS (roleplay
  // milestones) and sum turns/time across them.
  let actsCompleted = 0;
  let actsTotal = 0;
  let totalTurns = 0;
  let totalDurationSeconds = 0;
  for (const ms of project.milestones) {
    if (ms.scenarioStage !== 'roleplay') continue;
    actsTotal++;
    if (ms.status === 'completed') actsCompleted++;
    for (const mt of ms.microtasks) {
      totalTurns += mt.engagement?.learnerTurnCount ?? 0;
      totalDurationSeconds += mt.engagement?.durationSeconds ?? 0;
    }
  }

  const goalCoverage = buildGoalCoverage(project);
  // FALLBACK: when there is no usable per-act verdict (older project finished
  // before the act-goals evaluator shipped, or a verdict that failed the strict
  // alignment gate), still surface the authored act→goal scaffold read-only so
  // the page keeps a structured review instead of dropping to bare narrative.
  // Mutually exclusive with goalCoverage; omitted when the scaffold is empty.
  const goalScaffold = goalCoverage ? undefined : scenarioActGoalsScaffold(project);
  return {
    kind: 'scenario',
    sceneCaption: trimmedPBLText(project.scenario?.sceneVisual?.caption) || undefined,
    characterNames: (project.scenario?.characters ?? []).map((c) => c.name).filter(Boolean),
    acts: { completed: actsCompleted, total: actsTotal },
    totalTurns,
    totalDurationSeconds,
    ...(goalCoverage ? { goalCoverage } : {}),
    ...(goalScaffold && goalScaffold.length > 0 ? { goalScaffold } : {}),
  };
}

/** SCENARIO ONLY. Aggregate the final evaluator's per-act goal verdict
 *  (`PBLEvaluation.actGoals` on the latest final eval) into a coverage summary.
 *  Returns undefined when there is no final eval or it carried no act goals →
 *  the completion page omits the per-act review. Pure. */
function buildGoalCoverage(project) {
  const finalEval = project.evaluations.filter((e) => e.kind === 'final').at(-1);
  const acts = finalEval?.actGoals;
  if (!acts || acts.length === 0) return undefined;
  let achieved = 0;
  let partial = 0;
  let missed = 0;
  for (const act of acts) {
    for (const g of act.goals) {
      if (g.status === 'achieved') achieved++;
      else if (g.status === 'partial') partial++;
      else missed++;
    }
  }
  const total = achieved + partial + missed;
  if (total === 0) return undefined;
  return { achieved, partial, missed, total, acts };
}

/**
 * Fallback display name for a concept whose machine `signature` has no
 * human-readable `label` (older projects, or an observation recorded before
 * the label field existed). Turns a snake/kebab tag into spaced words — not a
 * translation, but readable rather than a raw token. Pure, for unit testing.
 */
export function humanizeConceptSignature(signature) {
  return signature.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim();
}

function collectUniqueConcepts(project) {
  const seen = new Set();
  for (const ms of project.milestones) {
    for (const mt of ms.microtasks) {
      for (const c of mt.engagement?.conceptsUnlocked ?? []) {
        if (c) seen.add(c);
      }
    }
  }
  return [...seen];
}

/** Count concept_unlocked events vs. closing_check + stage_synthesis_check
 *  events so we can compute the independence rate. */
function countEvidenceEvents(project) {
  let unlocks = 0;
  let checks = 0;
  // Engagement caches are the single source of truth (one per microtask).
  // A `stage_synthesis_check` is already absorbed into its owning
  // microtask's `closingQuestion` by microtaskEngagement(), so it is
  // counted here via the cache. We must NOT also count it from the
  // ledger — doing so double-counts a core-stage integrative reverse-
  // question and wrongly depresses independenceRate.
  for (const ms of project.milestones) {
    for (const mt of ms.microtasks) {
      const e = mt.engagement;
      if (!e) continue;
      if ((e.conceptsUnlocked?.length ?? 0) > 0) unlocks++;
      if (e.closingQuestion) checks++;
    }
  }
  return { unlocks, checks };
}

function sumField(project, field) {
  let sum = 0;
  for (const ms of project.milestones) {
    for (const mt of ms.microtasks) {
      sum += mt.engagement?.[field] ?? 0;
    }
  }
  return sum;
}

function findToughestMilestone(project) {
  let best = null;
  for (const ms of project.milestones) {
    let errors = 0;
    for (const mt of ms.microtasks) {
      errors += mt.engagement?.errorCount ?? 0;
    }
    if (errors >= 3 && errors > (best?.errors ?? 0)) {
      best = { title: ms.title, errors };
    }
  }
  return best;
}

function buildStageDetails(project) {
  return project.milestones
    .slice()
    .sort((a, b) => a.order - b.order)
    .map((ms) => {
      // Dedupe within the stage so a concept unlocked across two
      // microtasks of the same stage isn't listed twice (the global
      // conceptsUnlocked is already deduped; this matches it per-stage).
      // Resolve each machine `signature` to its human-readable, localised
      // `label` (cached on the engagement summary); fall back to a humanised
      // signature for older data recorded without a label. This is what the
      // learner sees in the report — never the raw snake_case tag.
      const conceptsSeen = new Set();
      const labelBySignature = new Map();
      for (const mt of ms.microtasks) {
        for (const c of mt.engagement?.conceptsUnlocked ?? []) {
          if (c) conceptsSeen.add(c);
        }
        for (const [sig, label] of Object.entries(mt.engagement?.conceptUnlockLabels ?? {})) {
          const trimmed = trimmedPBLText(label);
          if (sig && trimmed && !labelBySignature.has(sig)) labelBySignature.set(sig, trimmed);
        }
      }
      const conceptsInStage = [
        ...new Set(
          [...conceptsSeen].map(
            (sig) => labelBySignature.get(sig) ?? humanizeConceptSignature(sig),
          ),
        ),
      ];
      const submissionsInStage = project.submissions.filter((s) =>
        ms.microtasks.some((mt) => mt.id === s.microtaskId),
      ).length;

      // Stage synthesis quality — look up from the ledger.
      let synthesisQuality;
      for (const ev of project.engagementEvents) {
        if (ev.kind === 'stage_synthesis_check' && ev.milestoneId === ms.id) {
          synthesisQuality = ev.payload?.quality;
          break;
        }
      }

      return {
        milestoneTitle: ms.title,
        debrief: ms.debrief,
        isCoreStage: !!ms.synthesisCheck,
        coreConcept: ms.synthesisCheck?.coreConcept,
        synthesisQuality,
        conceptsInStage,
        submissionsInStage,
      };
    });
}

function buildHighlights(concepts, unlocks, checks, totalErrors, toughest, _stageDetails) {
  const highlights = [];
  const totalEvidence = unlocks + checks;

  // Independence: the learner showed concepts proactively.
  if (totalEvidence >= 2 && unlocks / totalEvidence >= 0.6) {
    highlights.push({
      kind: 'independence',
      unlocks,
      total: totalEvidence,
    });
  }

  // Resilience: the learner overcame errors.
  if (totalErrors >= 1) {
    highlights.push({
      kind: 'resilience',
      milestoneTitle: toughest?.title,
      errors: totalErrors,
    });
  }

  // Fallback completion note.
  if (highlights.length === 0) {
    highlights.push({ kind: 'completion' });
  }

  return highlights;
}

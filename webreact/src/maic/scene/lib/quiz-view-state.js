/**
 * 移植自参考项目 `lib/quiz/view-state.ts`。
 * 仅擦除 TypeScript 类型标注，纯函数逻辑逐字保留。
 */

export function createQuizViewLifetime() {
  let generation = 0;
  return {
    capture: () => generation,
    invalidate: () => {
      generation += 1;
    },
    isCurrent: (token) => token === generation,
  };
}

export async function runQuizPersistenceTransition(persist, lifetime, onSuccess, onError) {
  const token = lifetime.capture();
  try {
    await persist();
  } catch (error) {
    if (lifetime.isCurrent(token)) onError(error);
    return;
  }
  if (lifetime.isCurrent(token)) onSuccess();
}

export function isQuizRuntimeReady(gate) {
  return gate.status === 'ready';
}

export async function persistQuizRetry(input, writer) {
  await writer.recordPhase({
    ...input,
    phase: 'draft',
    answers: {},
    startNewAttempt: true,
  });
}

export async function persistQuizSubmission(input, writer) {
  await writer.recordPhase({ ...input, phase: 'submitted' });
}

export async function persistQuizReview(input, writer) {
  await writer.recordPhase({ ...input, phase: 'reviewed' });
}

export function quizViewStateFromAttempt(state) {
  if (!state) return { phase: 'not_started', answers: {}, results: [] };
  if (state.phase === 'reviewed') {
    return {
      phase: 'reviewing',
      answers: state.answers,
      results: state.results ?? [],
    };
  }
  if (state.phase === 'draft' && Object.keys(state.answers).length === 0) {
    return { phase: 'not_started', answers: {}, results: [] };
  }
  return { phase: 'answering', answers: state.answers, results: [] };
}

const SHORT_ANSWER_TYPES = new Set(["short", "short-answer", "text", "freeform"]);

function stringValue(value) {
  return typeof value === "string" ? value.trim() : String(value ?? "").trim();
}

function uniqueStrings(values) {
  return [...new Set((Array.isArray(values) ? values : [values]).map(stringValue).filter(Boolean))];
}

function optionValue(option) {
  if (option && typeof option === "object") return stringValue(option.value ?? option.label);
  return stringValue(option);
}

export function normalizeQuizQuestions(content) {
  const questions = Array.isArray(content?.questions) ? content.questions : [];
  return questions.filter(Boolean).map((question, index) => {
    const type = SHORT_ANSWER_TYPES.has(stringValue(question.type).toLowerCase())
      ? "short"
      : stringValue(question.type).toLowerCase() === "multiple"
        ? "multiple"
        : "single";
    const options = Array.isArray(question.options)
      ? question.options.map((option, optionIndex) => ({
        label: stringValue(option?.label ?? option?.value) || `选项 ${optionIndex + 1}`,
        value: optionValue(option) || `option-${optionIndex + 1}`,
      }))
      : [];
    return {
      id: stringValue(question.id) || `question-${index + 1}`,
      type,
      question: stringValue(question.question) || "未命名题目",
      options,
      answers: uniqueStrings(question.answer ?? question.answers ?? question.correctAnswer),
      acceptedAnswers: uniqueStrings(question.acceptedAnswers ?? question.answer ?? question.answers ?? question.correctAnswer),
      analysis: stringValue(question.analysis) || "暂无解析。",
      points: Math.max(0, Number(question.points) || 1),
    };
  });
}

function sameSet(left, right) {
  const a = uniqueStrings(left).sort();
  const b = uniqueStrings(right).sort();
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

function answerForQuestion(question, answer) {
  if (question.type === "multiple") return Array.isArray(answer) ? answer : [];
  if (question.type === "short") return stringValue(answer);
  return stringValue(answer);
}

function isCorrect(question, answer) {
  if (question.type === "short") {
    const actual = stringValue(answer).toLowerCase().replaceAll(/\s+/g, "");
    return question.acceptedAnswers.some((expected) => stringValue(expected).toLowerCase().replaceAll(/\s+/g, "") === actual);
  }
  if (question.type === "multiple") return sameSet(answer, question.answers);
  return sameSet([answer], question.answers);
}

export function evaluateQuiz(questions, answers = {}) {
  const normalized = Array.isArray(questions) ? questions : normalizeQuizQuestions(questions);
  const results = normalized.map((question) => {
    const correct = isCorrect(question, answerForQuestion(question, answers[question.id]));
    return {
      questionId: question.id,
      correct,
      earned: correct ? question.points : 0,
      analysis: question.analysis,
    };
  });
  return {
    score: results.reduce((sum, item) => sum + item.earned, 0),
    total: normalized.reduce((sum, question) => sum + question.points, 0),
    results,
  };
}

function parametersOf(content) {
  const parameters = content?.widgetConfig?.parameters;
  return Array.isArray(parameters) ? parameters.filter((parameter) => parameter && parameter.id) : [];
}

function clampParameter(parameter, rawValue) {
  const min = Number.isFinite(Number(parameter.min)) ? Number(parameter.min) : 0;
  const max = Number.isFinite(Number(parameter.max)) ? Number(parameter.max) : Math.max(min, Number(parameter.value) || 0);
  const value = Number(rawValue);
  const bounded = Math.min(max, Math.max(min, Number.isFinite(value) ? value : Number(parameter.value) || min));
  const step = Number(parameter.step);
  if (!Number.isFinite(step) || step <= 0) return bounded;
  return Math.round((bounded - min) / step) * step + min;
}

function calculateSimulation(content, values) {
  const formula = stringValue(content?.widgetConfig?.formula).toLowerCase();
  if (formula === "force / mass") {
    const mass = Number(values.mass);
    return mass ? Number((Number(values.force || 0) / mass).toFixed(4)) : 0;
  }
  if (formula === "distance / time") {
    const time = Number(values.time);
    return time ? Number((Number(values.distance || 0) / time).toFixed(4)) : 0;
  }
  return null;
}

export function createSimulationState(content) {
  const parameters = parametersOf(content);
  const values = Object.fromEntries(parameters.map((parameter) => [parameter.id, clampParameter(parameter, parameter.value)]));
  return { values, result: null, hasRun: false };
}

export function stepSimulation(content, state, action) {
  const current = state || createSimulationState(content);
  if (action?.type === "reset") return createSimulationState(content);
  if (action?.type === "set") {
    const parameter = parametersOf(content).find((item) => item.id === action.id);
    if (!parameter) return current;
    return { ...current, values: { ...current.values, [parameter.id]: clampParameter(parameter, action.value) }, result: null, hasRun: false };
  }
  if (action?.type === "run") {
    const value = calculateSimulation(content, current.values);
    return { ...current, result: { label: stringValue(content?.widgetConfig?.resultLabel) || "实验结果", value }, hasRun: true };
  }
  return current;
}

export function pblProgress(content, completedTaskIds = []) {
  const tasks = (Array.isArray(content?.phases) ? content.phases : []).flatMap((phase) => Array.isArray(phase?.tasks) ? phase.tasks : []).filter((task) => task?.id);
  const completed = new Set(completedTaskIds.map(stringValue));
  const count = tasks.filter((task) => completed.has(task.id)).length;
  return { completed: count, total: tasks.length, percent: tasks.length ? Math.round((count / tasks.length) * 100) : 0 };
}

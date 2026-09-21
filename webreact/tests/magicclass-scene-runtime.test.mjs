import assert from "node:assert/strict";
import test from "node:test";

import {
  createSimulationState,
  evaluateQuiz,
  normalizeQuizQuestions,
  pblProgress,
  stepSimulation,
} from "../src/features/magicclass/sceneRuntimeModel.js";

test("normalizes quiz questions and grades a single choice with analysis", () => {
  const questions = normalizeQuizQuestions({
    type: "quiz",
    questions: [{
      id: "q1",
      type: "single",
      question: "牛顿第二定律是什么？",
      options: [{ label: "F=ma", value: "a" }, { label: "E=mc²", value: "b" }],
      answer: ["a"],
      analysis: "质量与加速度共同决定力。",
      points: 2,
    }],
  });

  assert.deepEqual(questions[0].options.map((item) => item.value), ["a", "b"]);
  assert.deepEqual(evaluateQuiz(questions, { q1: "a" }), {
    score: 2,
    total: 2,
    results: [{ questionId: "q1", correct: true, earned: 2, analysis: "质量与加速度共同决定力。" }],
  });
});

test("grades multiple choice by set equality and accepts short-answer matches", () => {
  const questions = normalizeQuizQuestions({
    type: "quiz",
    questions: [
      { id: "q1", type: "multiple", question: "选择", options: [{ value: "a" }, { value: "b" }], answer: ["a", "b"], points: 2 },
      { id: "q2", type: "short", question: "公式", answer: ["F=ma", "f = ma"], points: 1 },
    ],
  });

  const result = evaluateQuiz(questions, { q1: ["b", "a"], q2: " f = ma " });
  assert.equal(result.score, 3);
  assert.equal(result.results.every((item) => item.correct), true);
});

test("runs a bounded simulation and resets to its declared defaults", () => {
  const content = {
    type: "interactive",
    widgetType: "simulation",
    widgetConfig: {
      title: "牛顿第二定律",
      parameters: [
        { id: "force", label: "力", min: 0, max: 100, step: 1, value: 20, unit: "N" },
        { id: "mass", label: "质量", min: 1, max: 20, step: 1, value: 5, unit: "kg" },
      ],
      formula: "force / mass",
      resultLabel: "加速度",
    },
  };

  const initial = createSimulationState(content);
  assert.equal(initial.values.force, 20);
  assert.equal(initial.result, null);
  const changed = stepSimulation(content, initial, { type: "set", id: "force", value: 30 });
  assert.equal(changed.values.force, 30);
  const ran = stepSimulation(content, changed, { type: "run" });
  assert.equal(ran.result.value, 6);
  assert.equal(stepSimulation(content, ran, { type: "reset" }).values.force, 20);
});

test("reports PBL task progress without inventing missing tasks", () => {
  const content = {
    type: "pbl",
    phases: [
      { id: "p1", title: "提出问题", tasks: [{ id: "t1", title: "定义问题" }] },
      { id: "p2", title: "验证", tasks: [{ id: "t2", title: "检查证据" }, { id: "t3", title: "提交结论" }] },
    ],
  };
  assert.deepEqual(pblProgress(content, ["t1", "missing"]), { completed: 1, total: 3, percent: 33 });
});

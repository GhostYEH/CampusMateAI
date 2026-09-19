import React from "react";
import { Button } from "../Primitives.jsx";
import { evaluateQuiz, normalizeQuizQuestions } from "../../features/openmaic/sceneRuntimeModel.js";

function storageKey(sceneId) {
  return sceneId ? `campusmate:openmaic:quiz:${sceneId}` : "";
}

function readSaved(sceneId) {
  if (!storageKey(sceneId) || typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(storageKey(sceneId));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveAttempt(sceneId, payload) {
  if (!storageKey(sceneId) || typeof window === "undefined") return;
  try { window.localStorage.setItem(storageKey(sceneId), JSON.stringify(payload)); } catch { /* private mode */ }
}

function isAnswered(question, value) {
  return Array.isArray(value) ? value.length > 0 : String(value || "").trim().length > 0;
}

export default function QuizRuntimePanel({ questions: rawQuestions, sceneId }) {
  const questions = React.useMemo(() => normalizeQuizQuestions({ type: "quiz", questions: rawQuestions }), [rawQuestions]);
  const saved = React.useMemo(() => readSaved(sceneId), [sceneId]);
  const [phase, setPhase] = React.useState(saved?.phase === "review" ? "review" : "intro");
  const [answers, setAnswers] = React.useState(saved?.answers || {});
  const [review, setReview] = React.useState(saved?.review || null);

  function persist(nextPhase, nextAnswers, nextReview = review) {
    saveAttempt(sceneId, { phase: nextPhase, answers: nextAnswers, review: nextReview });
  }

  function updateAnswer(questionId, value) {
    const next = { ...answers, [questionId]: value };
    setAnswers(next);
    persist(phase, next);
  }

  function submitAnswers(event) {
    event.preventDefault();
    const result = evaluateQuiz(questions, answers);
    setReview(result);
    setPhase("review");
    persist("review", answers, result);
  }

  function retry() {
    setAnswers({});
    setReview(null);
    setPhase("answering");
    persist("answering", {}, null);
  }

  const allAnswered = questions.length > 0 && questions.every((question) => isAnswered(question, answers[question.id]));
  if (!questions.length) return <p className="openmaic-hint">这份测验还没有题目。</p>;

  if (phase === "intro") return <section className="openmaic-quiz-runtime" aria-label="测验开始">
    <div className="openmaic-runtime-cover">
      <span className="openmaic-runtime-kicker">互动测验</span>
      <strong>{questions.length} 道题 · 共 {questions.reduce((sum, question) => sum + question.points, 0)} 分</strong>
      <p>完成答题后提交，系统会立即给出得分和逐题解析。</p>
      <Button type="button" onClick={() => { setPhase("answering"); persist("answering", answers); }}>开始答题</Button>
    </div>
  </section>;

  if (phase === "review" && review) return <section className="openmaic-quiz-runtime" aria-label="测验结果">
    <div className="openmaic-runtime-result">
      <span className="openmaic-runtime-kicker">测验完成</span>
      <strong data-testid="quiz-score">得分 {review.score} / {review.total}</strong>
      <p>{review.score === review.total ? "全部答对，讲解内容掌握得很好。" : "查看下面的答案解析，再重新作答巩固。"}</p>
    </div>
    <ol className="openmaic-quiz-runtime__questions">
      {questions.map((question, index) => {
        const result = review.results[index];
        return <li key={question.id} className={result.correct ? "is-correct" : "is-incorrect"}>
          <div className="openmaic-quiz-runtime__question-head"><strong>{index + 1}. {question.question}</strong><span>{result.correct ? "回答正确" : "需要复习"}</span></div>
          <p className="openmaic-quiz-runtime__analysis"><b>答案解析：</b>{result.analysis}</p>
        </li>;
      })}
    </ol>
    <Button type="button" variant="secondary" onClick={retry}>重新作答</Button>
  </section>;

  return <section className="openmaic-quiz-runtime" aria-label="测验答题">
    <div className="openmaic-runtime-progress"><strong>答题中</strong><span>{Object.values(answers).filter((value) => isAnswered({ type: "single" }, value)).length} / {questions.length} 已完成</span></div>
    <form onSubmit={submitAnswers}>
      <ol className="openmaic-quiz-runtime__questions">
        {questions.map((question, index) => <li key={question.id}>
          <fieldset>
            <legend>{index + 1}. {question.question}</legend>
            {question.type === "short" ? <input
              className="openmaic-quiz-runtime__short"
              value={answers[question.id] || ""}
              onChange={(event) => updateAnswer(question.id, event.target.value)}
              aria-label={`第 ${index + 1} 题答案`}
              placeholder="输入你的答案"
            /> : <div className="openmaic-quiz-runtime__options">
              {question.options.map((option) => {
                const multiple = question.type === "multiple";
                const checked = multiple ? (answers[question.id] || []).includes(option.value) : answers[question.id] === option.value;
                return <label key={option.value} className={checked ? "is-selected" : ""}>
                  <input
                    type={multiple ? "checkbox" : "radio"}
                    name={`question-${question.id}`}
                    value={option.value}
                    checked={checked}
                    onChange={() => updateAnswer(question.id, multiple
                      ? checked ? (answers[question.id] || []).filter((value) => value !== option.value) : [...(answers[question.id] || []), option.value]
                      : option.value)}
                  />
                  <span>{option.label}</span>
                </label>;
              })}
            </div>}
          </fieldset>
        </li>)}
      </ol>
      <Button type="submit" disabled={!allAnswered}>提交答案</Button>
    </form>
  </section>;
}

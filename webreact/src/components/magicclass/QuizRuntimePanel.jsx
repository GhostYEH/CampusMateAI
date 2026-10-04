import React from "react";
import { Button } from "../Primitives.jsx";
import { evaluateQuiz, normalizeQuizQuestions } from "../../features/magicclass/sceneRuntimeModel.js";
import * as api from "../../data/api.js";
import { userErrorMessage } from "../../data/contracts.js";

function storageKey(sceneId) {
  return sceneId ? `campusmate:magicclass:quiz:${sceneId}` : "";
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

export default function QuizRuntimePanel(props) {
  const identity = [props.courseId, props.workspaceId, props.stageId, props.sceneId].join(":");
  return <QuizAttemptPanel key={identity} {...props} />;
}

function QuizAttemptPanel({ questions: rawQuestions, sceneId, courseId, workspaceId, stageId }) {
  const questions = React.useMemo(() => normalizeQuizQuestions({ type: "quiz", questions: rawQuestions }), [rawQuestions]);
  const saved = React.useMemo(() => readSaved(sceneId), [sceneId]);
  const [phase, setPhase] = React.useState(saved?.phase === "review" ? "review" : "intro");
  const [answers, setAnswers] = React.useState(saved?.answers || {});
  const [review, setReview] = React.useState(saved?.review || null);
  const [remoteAttemptId, setRemoteAttemptId] = React.useState(saved?.attempt_id || "");
  const [syncError, setSyncError] = React.useState(saved?.pending_sync ? "上次答题记录尚未同步，请重试同步。" : "");
  const [syncing, setSyncing] = React.useState(false);
  const [loadError, setLoadError] = React.useState("");
  const [loadPending, setLoadPending] = React.useState(Boolean(courseId && workspaceId && stageId && sceneId));
  const [loadRetry, setLoadRetry] = React.useState(0);
  const mounted = React.useRef(false);
  const edited = React.useRef(Boolean(saved?.pending_sync));
  const writer = React.useRef({
    queue: Promise.resolve(), attemptId: saved?.attempt_id || `${stageId}:${sceneId}`,
    ready: null, readVersion: 0, sequence: 0, completedWrites: 0, pending: 0, startNew: Boolean(saved?.start_new_attempt),
    startNewBase: saved?.start_new_base_id || saved?.attempt_id || "",
    startNewUncertain: Boolean(saved?.start_new_attempt),
  });
  React.useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const persistRemote = React.useCallback((nextPhase, nextAnswers, nextReview = null, startNewAttempt = false, resuming = false) => {
    if (!courseId || !workspaceId || !stageId || !sceneId) return Promise.resolve(null);
    const session = writer.current;
    if (startNewAttempt) {
      session.startNew = true;
      session.startNewBase = session.attemptId;
      session.startNewUncertain = false;
    }
    const sequence = ++session.sequence;
    session.pending += 1;
    setSyncing(true);
    const snapshot = { phase: nextPhase, answers: nextAnswers, review: nextReview };
    saveAttempt(sceneId, { ...snapshot, attempt_id: session.attemptId, pending_sync: true, start_new_attempt: session.startNew, start_new_base_id: session.startNewBase });
    // Drafts and submission transitions must reach the server in order.
    const request = session.queue.then(async () => {
      const phases = nextPhase === "review" ? ["submitted", "reviewed"] : [nextPhase === "submitted" ? "submitted" : "draft"];
      let current;
      if (session.startNew && session.startNewUncertain) {
        current = await api.getMagicClassQuizAttempt(courseId, workspaceId, stageId, sceneId);
        // Creation may have committed even when its response was lost. Adopt
        // the server's successor instead of issuing another create command.
        if (current?.attempt_id && current.attempt_id !== session.startNewBase) {
          session.attemptId = current.attempt_id;
          session.startNew = false;
          session.startNewUncertain = false;
        }
      }
      if (resuming && !session.startNew) {
        current ||= await api.getMagicClassQuizAttempt(courseId, workspaceId, stageId, sceneId);
        if (current?.attempt_id) session.attemptId = current.attempt_id;
        if (mounted.current) setLoadError("");
      } else if (session.completedWrites === 0) current ||= await session.ready;
      if (current?.attempt_id && session.completedWrites === 0) session.attemptId = current.attempt_id;
      const remotePhase = current?.state?.phase;
      const remoteAnswers = current?.state?.answers || {};
      const sameAnswers = Object.keys({ ...remoteAnswers, ...nextAnswers }).every((key) => JSON.stringify(remoteAnswers[key]) === JSON.stringify(nextAnswers[key]));
      if (!session.startNew && current?.attempt_id === session.attemptId &&
          (remotePhase === "submitted" || remotePhase === "reviewed") &&
          (!sameAnswers || (nextPhase !== "review" && nextPhase !== "submitted"))) {
        // The server may have finished this attempt while the local draft was
        // offline. Preserve both records using the existing retry mechanism.
        session.startNew = true;
        session.startNewBase = session.attemptId;
        session.startNewUncertain = false;
      }
      if (!session.startNew && nextPhase === "review" && remotePhase === "reviewed") phases.shift();
      for (const phase of phases) {
        if (session.startNew) session.startNewUncertain = true;
        const remote = await api.saveMagicClassQuizAttempt(courseId, workspaceId, stageId, sceneId, {
          attempt_id: session.attemptId, phase, answers: nextAnswers,
          results: phase === "reviewed" ? nextReview?.results || [] : [],
          ...(session.startNew ? { start_new_attempt: true } : {}),
        });
        session.completedWrites += 1;
        session.startNew = false;
        session.startNewUncertain = false;
        if (remote?.attempt_id) session.attemptId = remote.attempt_id;
      }
      if (mounted.current) setRemoteAttemptId(session.attemptId);
      if (sequence === session.sequence) {
        saveAttempt(sceneId, { ...snapshot, attempt_id: session.attemptId, pending_sync: false });
        if (mounted.current) setSyncError("");
      }
      return session.attemptId;
    }).catch((error) => {
      if (mounted.current) setSyncError(userErrorMessage(error, "答题记录尚未同步，请重试同步。"));
      return null;
    }).finally(() => {
      session.pending -= 1;
      if (mounted.current && session.pending === 0) setSyncing(false);
    });
    session.queue = request;
    return request;
  }, [courseId, workspaceId, stageId, sceneId]);

  React.useEffect(() => {
    let cancelled = false;
    if (!courseId || !workspaceId || !stageId || !sceneId) return undefined;
    const session = writer.current;
    setLoadPending(true);
    const readVersion = ++session.readVersion;
    const readSequence = session.sequence;
    const ready = api.getMagicClassQuizAttempt(courseId, workspaceId, stageId, sceneId).then((remote) => {
      if (readVersion !== session.readVersion) return remote;
      if (readSequence !== session.sequence) {
        if (!cancelled) setLoadError("");
        return remote;
      }
      session.attemptId = remote?.attempt_id || session.attemptId;
      if (cancelled) return remote;
      setLoadError("");
      setRemoteAttemptId(remote?.attempt_id || "");
      if (edited.current) return remote;
      if (!remote?.state) return remote;
      const state = remote.state;
      const submitted = state.phase === "submitted";
      const nextPhase = state.phase === "reviewed" || submitted ? "review" : state.phase === "draft" && Object.keys(state.answers || {}).length ? "answering" : "intro";
      const evaluation = evaluateQuiz(questions, state.answers || {});
      const nextReview = nextPhase === "review" ? {
        ...evaluation,
        results: state.phase === "reviewed" && state.results?.length === questions.length ? state.results : evaluation.results,
      } : null;
      setPhase(nextPhase);
      setAnswers(state.answers || {});
      setReview(nextReview);
      if (submitted) {
        edited.current = true;
        setSyncError("答案已提交，结果尚未同步，请重试同步。");
      }
      saveAttempt(sceneId, { phase: nextPhase, answers: state.answers || {}, review: nextReview, attempt_id: remote.attempt_id, pending_sync: submitted });
      return remote;
    }).catch((error) => {
      if (!cancelled && readVersion === session.readVersion && readSequence === session.sequence) {
        setLoadError(userErrorMessage(error, "无法读取已保存的答题记录，请重试读取。"));
      }
      if (session.completedWrites > 0) return null;
      throw error;
    }).finally(() => {
      if (!cancelled) setLoadPending(false);
    });
    // A fast first click may update local answers, but cannot write against an
    // unresolved placeholder while the server already has a retry attempt.
    session.ready = ready;
    void ready.catch(() => {}); // The load error is displayed above; writes still receive the rejection.
    return () => { cancelled = true; };
  }, [courseId, workspaceId, stageId, sceneId, questions, loadRetry]);

  function persist(nextPhase, nextAnswers, nextReview = review) {
    edited.current = true;
    saveAttempt(sceneId, { phase: nextPhase, answers: nextAnswers, review: nextReview, attempt_id: remoteAttemptId });
  }

  function updateAnswer(questionId, value) {
    const next = { ...answers, [questionId]: value };
    setAnswers(next);
    persist(phase, next);
    void persistRemote(phase, next);
  }

  function submitAnswers(event) {
    event.preventDefault();
    const result = evaluateQuiz(questions, answers);
    setReview(result);
    setPhase("review");
    persist("review", answers, result);
    void persistRemote("review", answers, result);
  }

  function retry() {
    // A new attempt replaces the local snapshot. Recover/sync that snapshot
    // first so a failed read or write cannot discard the only saved answers.
    if (syncing || loadPending || loadError || syncError) return;
    setAnswers({});
    setReview(null);
    setPhase("answering");
    persist("answering", {}, null);
    void persistRemote("answering", {}, null, true);
  }

  const allAnswered = questions.length > 0 && questions.every((question) => isAnswered(question, answers[question.id]));
  if (!questions.length) return <p className="magicclass-hint">这份测验还没有题目。</p>;
  const syncNotice = loadError ? <div className="magicclass-hint magicclass-hint--error" role="alert">
    <p>答题记录读取失败：{loadError}</p>
    <Button type="button" variant="secondary" onClick={() => setLoadRetry((count) => count + 1)}>重试读取</Button>
  </div> : syncError ? <div className="magicclass-hint magicclass-hint--error" role="alert">
    <p>答题记录同步失败：{syncError} 当前答案仍保留在页面中。</p>
    <Button type="button" variant="secondary" disabled={syncing} onClick={() => { void persistRemote(phase, answers, review, false, true); }}>重试同步</Button>
  </div> : syncing ? <p className="magicclass-hint" role="status">正在同步答题记录…</p>
    : loadPending ? <p className="magicclass-hint" role="status">正在读取答题记录…</p> : null;

  if (phase === "intro") return <section className="magicclass-quiz-runtime" aria-label="测验开始">
    {syncNotice}
    <div className="magicclass-runtime-cover">
      <span className="magicclass-runtime-kicker">互动测验</span>
      <strong>{questions.length} 道题 · 共 {questions.reduce((sum, question) => sum + question.points, 0)} 分</strong>
      <p>完成答题后提交，系统会立即给出得分和逐题解析。</p>
      <Button type="button" disabled={loadPending} onClick={() => { setPhase("answering"); persist("answering", answers); void persistRemote("answering", answers); }}>开始答题</Button>
    </div>
  </section>;

  if (phase === "review" && review) return <section className="magicclass-quiz-runtime" aria-label="测验结果">
    {syncNotice}
    <div className="magicclass-runtime-result">
      <span className="magicclass-runtime-kicker">测验完成</span>
      <strong data-testid="quiz-score">得分 {review.score} / {review.total}</strong>
      <p>{review.score === review.total ? "全部答对，讲解内容掌握得很好。" : "查看下面的答案解析，再重新作答巩固。"}</p>
    </div>
    <ol className="magicclass-quiz-runtime__questions">
      {questions.map((question, index) => {
        const result = review.results[index];
        return <li key={question.id} className={result.correct ? "is-correct" : "is-incorrect"}>
          <div className="magicclass-quiz-runtime__question-head"><strong>{index + 1}. {question.question}</strong><span>{result.correct ? "回答正确" : "需要复习"}</span></div>
          <p className="magicclass-quiz-runtime__analysis"><b>答案解析：</b>{result.analysis}</p>
        </li>;
      })}
    </ol>
    <Button type="button" variant="secondary" disabled={syncing || loadPending || Boolean(loadError) || Boolean(syncError)} onClick={retry}>重新作答</Button>
  </section>;

  return <section className="magicclass-quiz-runtime" aria-label="测验答题">
    {syncNotice}
    <div className="magicclass-runtime-progress"><strong>答题中</strong><span>{Object.values(answers).filter((value) => isAnswered({ type: "single" }, value)).length} / {questions.length} 已完成</span></div>
    <form onSubmit={submitAnswers}>
      <ol className="magicclass-quiz-runtime__questions">
        {questions.map((question, index) => <li key={question.id}>
          <fieldset>
            <legend>{index + 1}. {question.question}</legend>
            {question.type === "short" ? <input
              className="magicclass-quiz-runtime__short"
              value={answers[question.id] || ""}
              onChange={(event) => updateAnswer(question.id, event.target.value)}
              aria-label={`第 ${index + 1} 题答案`}
              placeholder="输入你的答案"
            /> : <div className="magicclass-quiz-runtime__options">
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

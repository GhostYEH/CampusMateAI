import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../data/api.js";
import { itemsOf, logApiError, userErrorMessage } from "../data/contracts.js";
import { isSameLocalDate } from "../utils/date.js";
import { Button, Modal, PageFrame } from "../components/Primitives.jsx";
import { useWhiteNoise } from "../features/study/whiteNoise.js";
import { advancePomodoro, createPomodoroState, isPomodoroState, pausePomodoro, remainingAt, resetPomodoro, skipPomodoro, startPomodoro } from "../features/study/pomodoro.js";
import { useAmbientSound } from "../features/study/ambientSound.js";
import { readStudyScene, saveStudyScene } from "../features/study/scenes.js";
import SummerFocusRoom from "../components/study/SummerFocusRoom.jsx";
import SummerNavDock from "../components/study/SummerNavDock.jsx";

const list = itemsOf;
const POMODORO_STORAGE_KEY = "campus-study-pomodoro";

function readPomodoroState() {
  try {
    const value = JSON.parse(window.localStorage.getItem(POMODORO_STORAGE_KEY) || "null");
    return isPomodoroState(value) ? value : createPomodoroState();
  } catch {
    return createPomodoroState();
  }
}

function isDone(task) {
  return ["completed", "done", "closed"].includes(String(task?.status || "").toLowerCase());
}

export default function StudyPage() {
  const navigate = useNavigate();
  const [active, setActive] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [taskStats, setTaskStats] = useState({ total: 0, completed: 0 });
  const [dailyGoal, setDailyGoal] = useState({ target_minutes: 60 });
  const [relatedTaskId, setRelatedTaskId] = useState(null);
  const [goal, setGoal] = useState("");
  const [mode, setMode] = useState("deep");
  const [preset, setPreset] = useState(25);
  const [customMinutes, setCustomMinutes] = useState(45);
  const [seconds, setSeconds] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [breakdownOpen, setBreakdownOpen] = useState(false);
  const [breakdownGoal, setBreakdownGoal] = useState("");
  const [breakdown, setBreakdown] = useState(null);
  const [breakdownSteps, setBreakdownSteps] = useState([]);
  const [breaking, setBreaking] = useState(false);
  const [breakdownSaving, setBreakdownSaving] = useState(false);
  const [review, setReview] = useState(null);
  const [selfReport, setSelfReport] = useState("");
  const [blockNotifications, setBlockNotifications] = useState(true);
  const [pomodoro, setPomodoro] = useState(readPomodoroState);
  const pomodoroRef = useRef(pomodoro); pomodoroRef.current = pomodoro;
  const activeRef = useRef(active); activeRef.current = active;
  const whiteNoise = useWhiteNoise();
  const [sceneState, setSceneState] = useState(() => readStudyScene());
  const ambient = useAmbientSound(sceneState);
  function selectScene(nextScene) {
    const saved = saveStudyScene(nextScene);
    setSceneState(saved);
  }
  const commitPomodoro = (next) => { pomodoroRef.current = next; setPomodoro(next); setSeconds(remainingAt(next, Date.now())); try { window.localStorage.setItem(POMODORO_STORAGE_KEY, JSON.stringify(next)); } catch {} };

  function syncPomodoroWithSession(current) {
    if (current) {
      const plannedMinutes = Math.max(5, Math.round(Number(current.planned_duration_seconds || 0) / 60) || selectedMinutes);
      const started = new Date(current.started_at).getTime();
      const pausedAt = current.status === "paused" && current.paused_at ? new Date(current.paused_at).getTime() : Date.now();
      const elapsed = Math.max(0, Math.floor((pausedAt - started) / 1000) - Number(current.pause_seconds || 0));
      const remaining = Math.max(0, plannedMinutes * 60 - elapsed);
      const next = remaining > 0
        ? { ...createPomodoroState({ focusMinutes: plannedMinutes, breakMinutes: 5 }), remaining, isRunning: current.status !== "paused", expiresAt: current.status !== "paused" ? Date.now() + remaining * 1000 : null }
        : { ...createPomodoroState({ focusMinutes: plannedMinutes, breakMinutes: 5 }), mode: "break", completed: 1, remaining: 5 * 60 };
      commitPomodoro(next);
      if (remaining <= 0) {
        setActive(null);
        void api.finishStudySession(current.id, { self_report: null }).then(() => api.getStudySessions()).then((value) => setSessions(list(value))).catch((err) => { logApiError("study-finish", err); setError(userErrorMessage(err, "专注已完成，但记录同步失败")); });
        setNotice("专注完成，进入短暂休息");
      }
      return;
    }
    if (pomodoroRef.current.mode === "focus" && pomodoroRef.current.isRunning) commitPomodoro(resetPomodoro(pomodoroRef.current));
  }

  function refreshTasks() {
    return api.getTasks().then((value) => {
      const taskItems = list(value);
      setTasks(taskItems.filter((item) => !isDone(item) && item.status !== "deleted"));
      setTaskStats({ total: taskItems.filter((item) => item.status !== "deleted").length, completed: taskItems.filter(isDone).length });
    });
  }

  async function load() {
    setLoading(true); setError("");
    try {
      const [current, history, storeGoal] = await Promise.all([
        api.getActiveStudySession().catch(() => null),
        api.getStudySessions(),
        api.getDailyStudyGoal().catch(() => ({ target_minutes: 60 })),
      ]);
      setActive(current);
      setSessions(list(history));
      setDailyGoal(storeGoal?.target_minutes ? storeGoal : { target_minutes: 60 });
      syncPomodoroWithSession(current);
      await refreshTasks();
    } catch (err) {
      logApiError("study-load", err);
      setError(userErrorMessage(err, "学习数据加载失败"));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);
  useEffect(() => {
    const tick = () => {
      const current = pomodoroRef.current;
      const next = advancePomodoro(current, Date.now());
      if (current.mode === "focus" && next.mode === "break" && next.completed > current.completed) void completePomodoroRound();
      if (next !== current) commitPomodoro(next);
      else setSeconds(remainingAt(current, Date.now()));
    };
    tick();
    const timer = window.setInterval(tick, 250);
    return () => window.clearInterval(timer);
  }, []);
  const completed = useMemo(() => sessions.filter((item) => item.status === "completed"), [sessions]);
  const todayMinutes = useMemo(() => completed.filter((item) => isSameLocalDate(item.started_at)).reduce((total, item) => total + Math.round(Number(item.duration_seconds || 0) / 60), 0), [completed]);
  const selectedMinutes = preset === "custom" ? Math.max(5, Math.min(180, Number(customMinutes) || 45)) : preset;
  useEffect(() => {
    const restoredMinutes = pomodoroRef.current.focusMinutes;
    if (restoredMinutes !== 25) {
      setPreset([25, 45, 60].includes(restoredMinutes) ? restoredMinutes : "custom");
      setCustomMinutes(restoredMinutes);
    }
  }, []);
  function selectPreset(value) {
    setPreset(value);
    if (value === "custom") return;
    const current = pomodoroRef.current;
    if (!current.isRunning && current.mode === "focus") commitPomodoro({ ...current, focusMinutes: value, remaining: value * 60, expiresAt: null });
  }
  function selectCustomMinutes(value) {
    setCustomMinutes(value);
    const minutes = Math.max(5, Math.min(180, Number(value) || 45));
    const current = pomodoroRef.current;
    if (!current.isRunning && current.mode === "focus") commitPomodoro({ ...current, focusMinutes: minutes, remaining: minutes * 60, expiresAt: null });
  }
  async function start(goalOverride = goal) {
    const current = pomodoroRef.current;
    if (current.mode === "break") { commitPomodoro(startPomodoro(current, Date.now())); return; }
    if (activeRef.current) return;
    try {
      const result = await api.startStudySession({ goal: goalOverride.trim() || "完成一段专注学习", mode, minutes: selectedMinutes, relatedTaskId });
      setActive(result);
      setGoal(goalOverride.trim());
      commitPomodoro(startPomodoro({ ...createPomodoroState({ focusMinutes: selectedMinutes, breakMinutes: 5 }), remaining: selectedMinutes * 60 }, Date.now()));
      setNotice(`已开始 ${selectedMinutes} 分钟专注`);
    } catch (err) {
      logApiError("study-start", err);
      setError(userErrorMessage(err, "无法开始学习会话"));
    }
  }
  async function togglePause() {
    const current = pomodoroRef.current;
    try {
      if (current.isRunning) { if (activeRef.current) setActive(await api.pauseStudySession(activeRef.current.id, "主动休息")); commitPomodoro(pausePomodoro(current, Date.now())); }
      else { if (activeRef.current) setActive(await api.resumeStudySession(activeRef.current.id)); commitPomodoro(startPomodoro(current, Date.now())); }
    } catch (err) {
      logApiError("study-pause", err);
      setError(userErrorMessage(err, "学习状态更新失败"));
    }
  }
  function requestFinish() {
    if (!activeRef.current) return;
    setSelfReport("");
    setReview({ session: activeRef.current });
  }
  async function confirmFinish() {
    const session = review?.session;
    setReview(null);
    if (!session) return;
    try {
      await api.finishStudySession(session.id, { self_report: selfReport.trim() || null });
    } catch (err) {
      logApiError("study-finish", err);
      setError(userErrorMessage(err, "结束会话失败"));
    }
    setActive((current) => (current?.id === session.id ? null : current));
    setRelatedTaskId(null);
    setSelfReport("");
    commitPomodoro(resetPomodoro(pomodoroRef.current));
    setNotice("本次专注已记录");
    void load();
  }
  async function completePomodoroRound() {
    const session = activeRef.current;
    if (session) {
      try { await api.finishStudySession(session.id, { self_report: null }); } catch (err) { logApiError("study-round", err); setError(userErrorMessage(err, "专注完成，但记录保存失败")); }
      setActive(null);
      void api.getStudySessions().then((value) => setSessions(list(value))).catch(() => {});
    }
    setNotice("专注完成，进入短暂休息");
  }
  async function resetTimer() {
    if (activeRef.current) {
      try { await api.finishStudySession(activeRef.current.id, { self_report: selfReport.trim() || null }); } catch (err) { logApiError("study-reset", err); setError(userErrorMessage(err, "计时已重置，但记录保存失败")); }
      setActive(null);
    }
    commitPomodoro(resetPomodoro(pomodoroRef.current));
    setSelfReport("");
    setNotice("计时已重置");
  }
  async function skipTimer() {
    const currentMode = pomodoroRef.current.mode;
    if (activeRef.current) {
      try { await api.finishStudySession(activeRef.current.id, { self_report: selfReport.trim() || null }); } catch (err) { logApiError("study-skip", err); setError(userErrorMessage(err, "阶段已跳过，但记录保存失败")); }
      setActive(null);
    }
    commitPomodoro(skipPomodoro(pomodoroRef.current));
    setSelfReport("");
    setNotice(currentMode === "break" ? "已跳过休息，准备下一轮专注" : "已跳过当前专注阶段");
  }
  async function saveDailyGoal(value) {
    const target = Math.max(15, Math.min(480, Number(value) || dailyGoal.target_minutes || 60));
    try {
      setDailyGoal(await api.updateDailyStudyGoal(target));
      setNotice(`今日目标已调整为 ${target} 分钟`);
    } catch (err) {
      logApiError("study-goal", err);
      setError(userErrorMessage(err, "今日目标保存失败"));
    }
  }
  async function addTaskFromRoom(title) {
    try {
      await api.createTask({ title, source_name: "学习陪伴" });
      await refreshTasks();
      setNotice("已加入今日待办");
    } catch (err) {
      logApiError("study-add-task", err);
      setError(userErrorMessage(err, "待办添加失败"));
    }
  }

  function openPlanning(goalOverride = goal) {
    setBreakdownGoal(goalOverride.trim() || activeRef.current?.goal || "");
    setBreakdownOpen(true);
  }

  async function onBreakdown() {
    const target = breakdownGoal.trim();
    if (!target || breaking) return;
    setBreaking(true); setError("");
    try {
      const result = await api.breakdownStudyTask({ goal: target });
      setBreakdown(result);
      setBreakdownSteps((result.steps || []).map((step, index) => ({
        _key: `${index}-${step.step_number || index + 1}`,
        title: step.title || "",
        description: step.description || "",
        estimated_minutes: Number(step.estimated_minutes) || 30,
      })));
    } catch (err) {
      logApiError("study-breakdown", err);
      setError(userErrorMessage(err, "目标拆解失败，请重试"));
    } finally {
      setBreaking(false);
    }
  }

  function updateBreakdownStep(index, patch) {
    setBreakdownSteps((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  }

  function removeBreakdownStep(index) {
    setBreakdownSteps((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  async function saveBreakdownSteps() {
    const valid = breakdownSteps.filter((step) => step.title.trim());
    if (!valid.length || breakdownSaving) return;
    setBreakdownSaving(true); setError("");
    try {
      await Promise.all(valid.map((step) => api.createTask({
        title: step.title.trim(),
        description: step.description?.trim() || undefined,
        source_name: "AI 拆解步骤",
        source_text: breakdown?.goal || breakdownGoal.trim(),
      })));
      await refreshTasks();
      setBreakdownOpen(false);
      setBreakdown(null);
      setBreakdownSteps([]);
      setNotice(`已将 ${valid.length} 个步骤加入今日待办`);
    } catch (err) {
      logApiError("study-breakdown-save", err);
      setError(userErrorMessage(err, "步骤保存失败，请重试"));
    } finally {
      setBreakdownSaving(false);
    }
  }
  async function toggleTaskFromRoom(task) {
    try {
      await api.completeTask(task.id, !isDone(task));
      await refreshTasks();
    } catch (err) {
      logApiError("study-toggle-task", err);
      setError(userErrorMessage(err, "待办状态更新失败"));
    }
  }
  return <><PageFrame className="study-page" showHeading={false}>
    {notice && <div className="page-notice notice-info" role="status">{notice}</div>}{error && <div className="page-notice notice-error" role="alert">{error}<Button variant="quiet" onClick={load}>重试</Button></div>}
    {loading ? <div className="state-card loading-state" aria-busy="true"><span className="loading-orb" /><p>正在加载内容…</p></div> : <SummerFocusRoom
      active={active}
      pomodoro={pomodoro}
      seconds={seconds}
      goal={goal}
      preset={preset}
      customMinutes={customMinutes}
      mode={mode}
      blockNotifications={blockNotifications}
      whiteNoise={whiteNoise}
      tasks={tasks}
      taskTotal={taskStats.total}
      taskCompleted={taskStats.completed}
      dailyGoalMinutes={dailyGoal.target_minutes}
      todayFocusMinutes={todayMinutes}
      scene={sceneState}
      onSelectScene={selectScene}
      onSaveDailyGoal={saveDailyGoal}
      onGoalChange={setGoal}
      onPresetChange={selectPreset}
      onCustomMinutesChange={selectCustomMinutes}
      onModeChange={setMode}
      onToggleNotifications={() => setBlockNotifications((value) => !value)}
      onStart={start}
      onTogglePause={togglePause}
      onFinish={requestFinish}
      onReset={resetTimer}
      onSkip={skipTimer}
      onToggleTask={toggleTaskFromRoom}
      onAddTask={addTaskFromRoom}
      onOpenPlans={() => navigate("/plans")}
      onOpenPlanning={openPlanning}
      breakdownOpen={breakdownOpen}
      breakdownGoal={breakdownGoal}
      breakdownMode={breakdown?.mode}
      breakdownWarnings={breakdown?.warnings || []}
      breakdownSteps={breakdownSteps}
      breaking={breaking}
      breakdownSaving={breakdownSaving}
      onBreakdownGoalChange={setBreakdownGoal}
      onBreakdown={onBreakdown}
      onUpdateBreakdownStep={updateBreakdownStep}
      onRemoveBreakdownStep={removeBreakdownStep}
      onSaveBreakdownSteps={saveBreakdownSteps}
      onClosePlanning={() => setBreakdownOpen(false)}
      onRefresh={load}
    />}
    {review && <Modal title="本次学习复盘" variant="study" onClose={() => setReview(null)} actions={<><Button variant="quiet" onClick={() => setReview(null)}>返回专注</Button><Button icon="PhCheckCircle" onClick={confirmFinish}>结束并保存记录</Button></>}>
      <div className="study-review-dialog">
        <p>本次专注即将结束，写一句话记录这段时间的感受（可选）。</p>
        <textarea id="study-self-report" name="self_report" rows="3" autoFocus data-autofocus value={selfReport} onChange={(event) => setSelfReport(event.target.value)} placeholder="例如：完成了阅读，后半段注意力有些分散…" />
      </div>
    </Modal>}
  </PageFrame><SummerNavDock sceneAudio={ambient} /></>;
}

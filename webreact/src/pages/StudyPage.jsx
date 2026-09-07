import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../data/api.js";
import { itemsOf } from "../data/contracts.js";
import { isSameLocalDate } from "../utils/date.js";
import { Button, Modal, PageFrame, Panel, SectionHeading } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import TiltedCard from "../components/TiltedCard.jsx";
import { WhiteNoiseControl } from "../components/study/WhiteNoiseControl.jsx";
import { formatDateTime } from "../utils/date.js";
import { studyExperienceModel, weeklyTrend } from "../data/alignment.js";
import { useWhiteNoise } from "../features/study/whiteNoise.js";
import { advancePomodoro, createPomodoroState, isPomodoroState, pausePomodoro, remainingAt, resetPomodoro, skipPomodoro, startPomodoro } from "../features/study/pomodoro.js";
import { useAmbientSound } from "../features/study/ambientSound.js";
import SummerFocusRoom from "../components/study/SummerFocusRoom.jsx";
import SummerNavDock from "../components/study/SummerNavDock.jsx";

const list = itemsOf;
const errorText = (error, fallback = "操作失败，请稍后重试") => error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback;
const dateText = (value) => formatDateTime(value, { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }, "时间待定");
const POMODORO_STORAGE_KEY = "campus-study-pomodoro";

function readPomodoroState() {
  try {
    const value = JSON.parse(window.localStorage.getItem(POMODORO_STORAGE_KEY) || "null");
    return isPomodoroState(value) ? value : createPomodoroState();
  } catch {
    return createPomodoroState();
  }
}

function StudyTiltedCard({ children, className = "" }) {
  return <TiltedCard className={["study-tilted-card", className].filter(Boolean).join(" ")} containerHeight="auto" containerWidth="100%" rotateAmplitude={6} scaleOnHover={1.02} showMobileWarning={false} showTooltip={false}>{children}</TiltedCard>;
}

function ExperienceLayer({ experience, active, seconds, goal, mode, soundOn, blockNotifications, breaking, breakdown, onClose, onStart, onTogglePause, onFinish, onBreakdown, onGoalChange, onModeChange, onToggleSound, onToggleNotifications, onReuse, onSaveTask, onCompleteTask, onSaveBreakdown }) {
  const [range, setRange] = useState("7d"); const [compare, setCompare] = useState(true); const [taskTitle, setTaskTitle] = useState("");
  useEffect(() => { setTaskTitle(experience?.task?.title || ""); }, [experience]);
  if (!experience) return null;
  const view = experience.view; const title = { focus: "沉浸专注", plan: "AI 学习路线", metric: experience.label || "专注洞察", record: "本次学习复盘", trend: "专注趋势分析", task: "计划详情" }[view] || "专注空间";
  const timerText = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  const values = experience.trend || [];
  const closeAction = <Button variant="quiet" onClick={onClose}>返回学习陪伴</Button>;
  return <Modal title={title} onClose={onClose} actions={closeAction}>
    {view === "focus" && <div className="experience-layer"><span className="eyebrow">{active ? (active.status === "paused" ? "暂时休息" : "正在专注") : "准备开始"}</span><strong>{timerText}</strong><p>{active?.goal || experience.goal || goal || "给眼前这件事一段不被打扰的时间"}</p><div className="focus-options"><label><span>专注模式</span><select value={mode} disabled={Boolean(active)} onChange={(event) => onModeChange(event.target.value)}><option value="deep">深度专注</option><option value="steady">稳步推进</option><option value="quiet">安静阅读</option></select></label><label><span>提醒设置</span><button type="button" className="text-button" onClick={onToggleNotifications}>{blockNotifications ? "通知已阻止" : "允许通知"}</button></label><label><span>环境声音</span><button type="button" className="text-button" onClick={onToggleSound}>{soundOn ? "白噪音开启" : "环境静音"}</button></label></div><div className="form-footer">{!active ? <Button icon="PhPlay" onClick={onStart}>开始专注</Button> : <><Button variant="secondary" icon={active.status === "paused" ? "PhPlay" : "PhPause"} onClick={onTogglePause}>{active.status === "paused" ? "继续专注" : "暂停一下"}</Button><Button icon="PhStop" onClick={onFinish}>结束并记录</Button></>}</div></div>}
    {view === "plan" && <div className="experience-layer"><label className="field"><span>这次要完成什么</span><input value={goal} onChange={(event) => onGoalChange(event.target.value)} placeholder="输入一个清晰、可完成的目标" /></label><Button disabled={breaking || !goal.trim()} onClick={onBreakdown}>{breaking ? "正在规划…" : "生成学习路线"}</Button>{breakdown?.steps?.length ? <><div className="breakdown-list">{breakdown.steps.map((step, index) => <div key={`${step.title || step}-${index}`}><b>{index + 1}</b><span><strong>{step.title || step}</strong><small>{step.description || (step.estimated_minutes ? `${step.estimated_minutes} 分钟` : "下一步")}</small></span></div>)}</div><Button variant="secondary" icon="PhListPlus" onClick={onSaveBreakdown}>加入今日计划</Button></> : <p className="muted-copy">生成后会把目标拆成可执行的小步骤。</p>}</div>}
    {view === "metric" && <div className="experience-layer"><span className="eyebrow">{experience.eyebrow || "本周动态"}</span><strong>{experience.value || "0"}{experience.unit ? ` ${experience.unit}` : ""}</strong><p>{experience.insight || experience.detail || "完成一次专注后，这里会形成更清晰的变化趋势。"}</p><div className="trend-bars">{values.map((item) => <span key={item.date}><i style={{ height: `${Math.max(item.count ? 14 : 4, item.count || 4)}%` }} /><small>{item.label}</small></span>)}</div></div>}
    {view === "record" && <div className="experience-layer"><span className="eyebrow">FOCUS LOG</span><strong>{Math.round(Number(experience.duration_seconds || 0) / 60) || "—"} 分钟</strong><p>{experience.goal || "学习会话"}</p><small>{experience.started_at ? dateText(experience.started_at) : "时间未记录"} · {experience.status === "completed" ? "已完成" : "进行中"}</small>{experience.self_report && <blockquote>{experience.self_report}</blockquote>}<Button icon="PhArrowClockwise" onClick={() => onReuse(experience)}>以此目标再来一次</Button></div>}
    {view === "trend" && <div className="experience-layer"><div className="chip-row">{[["7d", "近 7 天"], ["14d", "近 14 天"], ["30d", "近 30 天"]].map(([key, label]) => <button type="button" className={range === key ? "active" : ""} key={key} onClick={() => setRange(key)}>{label}</button>)}<button type="button" className={compare ? "active" : ""} onClick={() => setCompare((value) => !value)}>对比上期</button></div><div className="trend-bars">{values.map((item) => <span key={item.date}><i style={{ height: `${Math.max(item.count ? 14 : 4, Math.min(100, item.count * (range === "30d" ? 1.2 : range === "14d" ? 1.1 : 1)))}%` }} /><small>{item.label}</small><b>{item.count || ""}</b></span>)}</div><div className="detail-grid"><div><span>累计专注</span><strong>{values.reduce((sum, item) => sum + Number(item.count || 0), 0)} 分钟</strong></div><div><span>对比</span><strong>{compare ? "已开启" : "已关闭"}</strong></div></div></div>}
    {view === "task" && <div className="experience-layer"><div className="detail-grid"><div><span>状态</span><strong>待完成计划</strong></div><div><span>截止时间</span><strong>{experience.task?.deadline ? dateText(experience.task.deadline) : "尚未安排"}</strong></div></div><label className="field"><span>计划名称</span><input value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} placeholder="输入计划名称" /></label><div className="form-footer"><Button variant="secondary" disabled={!taskTitle.trim()} onClick={() => onSaveTask({ ...experience.task, title: taskTitle.trim() })}>保存修改</Button><Button variant="quiet" icon="PhNotePencil" onClick={() => onGoalChange(taskTitle.trim())}>同步到学习计划</Button><Button icon="PhFlag" onClick={() => onReuse(experience.task)}>带入专注目标</Button><Button icon="PhCheckCircle" onClick={() => onCompleteTask(experience.task)}>标记为完成</Button></div></div>}
  </Modal>;
}

function StudyMetric({ label, value, unit, detail, icon, tone, onClick }) {
  return <StudyTiltedCard className="study-metric-card"><button type="button" className={`stat-card study-stat-trigger tone-${tone}`} onClick={onClick} aria-label={`${label}，${value}${unit || ""}，${detail}`}><span className="stat-icon"><Icon name={icon} size={22} /></span><strong>{value}<small className="study-stat-unit">{unit}</small></strong><span className="study-stat-label">{label}</span><small>{detail}</small></button></StudyTiltedCard>;
}

export default function StudyPage() {
  const [active, setActive] = useState(null); const [sessions, setSessions] = useState([]); const [tasks, setTasks] = useState([]); const [taskStats, setTaskStats] = useState({ total: 0, completed: 0 }); const [dailyGoal, setDailyGoal] = useState({ target_minutes: 60 }); const [relatedTaskId, setRelatedTaskId] = useState(null); const [goal, setGoal] = useState(""); const [mode, setMode] = useState("deep"); const [preset, setPreset] = useState(25); const [customMinutes, setCustomMinutes] = useState(45); const [seconds, setSeconds] = useState(0); const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [selfReport, setSelfReport] = useState(""); const [breaking, setBreaking] = useState(false); const [breakdown, setBreakdown] = useState(null); const [blockNotifications, setBlockNotifications] = useState(true); const [experience, setExperience] = useState(null);
  const [pomodoro, setPomodoro] = useState(readPomodoroState);
  const pomodoroRef = useRef(pomodoro); pomodoroRef.current = pomodoro;
  const activeRef = useRef(active); activeRef.current = active;
  const whiteNoise = useWhiteNoise();
  const [scene, setScene] = useState(() => {
    const stored = window.localStorage.getItem("campus_study_scene");
    const known = ["rain", "snow", "cloud"];
    return known.includes(stored) ? stored : "rain";
  });
  const ambient = useAmbientSound(scene);
  function selectScene(nextScene) { setScene(nextScene); window.localStorage.setItem("campus_study_scene", nextScene); }
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
        void api.finishStudySession(current.id, { self_report: null }).then(() => api.getStudySessions()).then((value) => setSessions(list(value))).catch(() => setError("专注已完成，但记录同步失败"));
        setNotice("专注完成，进入短暂休息");
      }
      return;
    }
    if (pomodoroRef.current.mode === "focus" && pomodoroRef.current.isRunning) commitPomodoro(resetPomodoro(pomodoroRef.current));
  }
  async function load() { setLoading(true); setError(""); try { const [current, history, allTasks, storedGoal] = await Promise.all([api.getActiveStudySession().catch(() => null), api.getStudySessions(), api.getTasks(), api.getDailyStudyGoal().catch(() => ({ target_minutes: 60 }))]); const taskItems = list(allTasks); setActive(current); setSessions(list(history)); setTasks(taskItems.filter((item) => item.status !== "completed" && item.status !== "deleted")); setTaskStats({ total: taskItems.filter((item) => item.status !== "deleted").length, completed: taskItems.filter((item) => item.status === "completed").length }); setDailyGoal(storedGoal?.target_minutes ? storedGoal : { target_minutes: 60 }); syncPomodoroWithSession(current); } catch (err) { setError(errorText(err, "学习数据加载失败")); } finally { setLoading(false); } }
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
  const weekMinutes = useMemo(() => completed.reduce((total, item) => total + Math.round(Number(item.duration_seconds || 0) / 60), 0), [completed]);
  const trend = useMemo(() => weeklyTrend(completed, new Date(), "started_at", (item) => Math.round(Number(item.duration_seconds || 0) / 60)), [completed]);
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
    try { const result = await api.startStudySession({ goal: goalOverride.trim() || "完成一段专注学习", mode, minutes: selectedMinutes, relatedTaskId }); setActive(result); setGoal(goalOverride.trim()); commitPomodoro(startPomodoro({ ...createPomodoroState({ focusMinutes: selectedMinutes, breakMinutes: 5 }), remaining: selectedMinutes * 60 }, Date.now())); setNotice(`已开始 ${selectedMinutes} 分钟专注`); } catch (err) { setError(errorText(err, "无法开始学习会话")); }
  }
  async function togglePause() {
    const current = pomodoroRef.current;
    try {
      if (current.isRunning) { if (activeRef.current) setActive(await api.pauseStudySession(activeRef.current.id, "主动休息")); commitPomodoro(pausePomodoro(current, Date.now())); }
      else { if (activeRef.current) setActive(await api.resumeStudySession(activeRef.current.id)); commitPomodoro(startPomodoro(current, Date.now())); }
    } catch (err) { setError(errorText(err, "学习状态更新失败")); }
  }
  async function finish() { if (!activeRef.current) return; try { await api.finishStudySession(activeRef.current.id, { self_report: selfReport.trim() || null }); setActive(null); setRelatedTaskId(null); setSelfReport(""); commitPomodoro(resetPomodoro(pomodoroRef.current)); setNotice("本次专注已记录"); await load(); } catch (err) { setError(errorText(err, "结束会话失败")); } }
  async function completePomodoroRound() { const session = activeRef.current; if (session) { try { await api.finishStudySession(session.id, { self_report: null }); } catch (err) { setError(errorText(err, "专注完成，但记录保存失败")); } setActive(null); setSelfReport(""); void api.getStudySessions().then((value) => setSessions(list(value))).catch(() => {}); } setNotice("专注完成，进入短暂休息"); }
  async function resetTimer() { if (activeRef.current) { try { await api.finishStudySession(activeRef.current.id, { self_report: selfReport.trim() || null }); } catch (err) { setError(errorText(err, "计时已重置，但记录保存失败")); } setActive(null); } commitPomodoro(resetPomodoro(pomodoroRef.current)); setSelfReport(""); setNotice("计时已重置"); }
  async function skipTimer() { const currentMode = pomodoroRef.current.mode; if (activeRef.current) { try { await api.finishStudySession(activeRef.current.id, { self_report: selfReport.trim() || null }); } catch (err) { setError(errorText(err, "阶段已跳过，但记录保存失败")); } setActive(null); } commitPomodoro(skipPomodoro(pomodoroRef.current)); setSelfReport(""); setNotice(currentMode === "break" ? "已跳过休息，准备下一轮专注" : "已跳过当前专注阶段"); }
  async function planBreakdown() { if (!goal.trim() || breaking || active) return; setBreaking(true); try { setBreakdown(await api.breakdownStudyTask({ goal: goal.trim() })); } catch (err) { setError(errorText(err, "任务拆解失败")); } finally { setBreaking(false); } }
  function reuseExperience(item) { const nextGoal = item?.goal || item?.title || goal; if (!active && nextGoal) setGoal(nextGoal); if (!active && item?.id) setRelatedTaskId(item.id); setExperience(null); setNotice("目标已带入专注计划"); }
  async function saveTaskFromLayer(task) { if (!task?.id || !task.title?.trim()) return; try { const updated = await api.updateTask(task.id, { title: task.title.trim() }); setTasks((current) => current.map((item) => item.id === task.id ? { ...item, ...updated, title: task.title.trim() } : item)); setExperience((current) => current ? studyExperienceModel(current.view, { ...current, task: { ...task, ...updated, title: task.title.trim() } }) : current); setNotice("计划修改已保存"); } catch (err) { setError(errorText(err, "计划保存失败")); } }
  async function completeTaskFromLayer(task) { if (!task?.id) return; try { await api.completeTask(task.id, true); setTasks((current) => current.filter((item) => item.id !== task.id)); setTaskStats((current) => ({ total: current.total, completed: current.completed + 1 })); setExperience(null); setNotice("计划已完成"); } catch (err) { setError(errorText(err, "计划状态更新失败")); } }
  async function saveDailyGoal(value) { const target = Math.max(15, Math.min(480, Number(value) || dailyGoal.target_minutes || 60)); try { setDailyGoal(await api.updateDailyStudyGoal(target)); setNotice(`今日目标已调整为 ${target} 分钟`); } catch (err) { setError(errorText(err, "今日目标保存失败")); } }
  async function saveBreakdownTasks() { if (!breakdown?.steps?.length) return; try { const created = await Promise.all(breakdown.steps.map((step) => api.createTask({ title: step.title, description: step.description, source_name: "学习陪伴 AI 学习路线", source_text: breakdown.goal }))); setTasks((current) => [...created, ...current]); setTaskStats((current) => ({ total: current.total + created.length, completed: current.completed })); setNotice(`已将 ${created.length} 个步骤加入今日计划`); } catch (err) { setError(errorText(err, "学习路线保存失败")); } }
  return <><PageFrame className="study-page" showHeading={false}>
    {notice && <div className="page-notice notice-info" role="status">{notice}</div>}{error && <div className="page-notice notice-error" role="alert">{error}<Button variant="quiet" onClick={load}>重试</Button></div>}
    {loading ? <div className="state-card loading-state" aria-busy="true"><span className="loading-orb" /><p>正在加载内容…</p></div> : <div className="stack reveal">
      <div className="study-focus-card"><SummerFocusRoom active={active} pomodoro={pomodoro} seconds={seconds} goal={goal} preset={preset} customMinutes={customMinutes} mode={mode} blockNotifications={blockNotifications} whiteNoise={whiteNoise} tasks={tasks} taskTotal={taskStats.total} taskCompleted={taskStats.completed} dailyGoalMinutes={dailyGoal.target_minutes} todayFocusMinutes={todayMinutes} scene={scene} onSelectScene={selectScene} onSaveDailyGoal={saveDailyGoal} onGoalChange={setGoal} onPresetChange={selectPreset} onCustomMinutesChange={selectCustomMinutes} onModeChange={setMode} onToggleNotifications={() => setBlockNotifications((value) => !value)} onStart={start} onTogglePause={togglePause} onFinish={finish} onReset={resetTimer} onSkip={skipTimer} onTaskSelect={(item) => { setRelatedTaskId(item.id); setExperience(studyExperienceModel("task", { title: "计划详情", value: item.title || "学习计划", detail: item.deadline ? `计划截止 ${dateText(item.deadline)}` : "打开任务页可以继续编辑和完成计划。", task: item })); }} onOpenPlan={() => setExperience(studyExperienceModel("plan", {}))} onRefresh={load} /></div>
      {active && <StudyTiltedCard className="study-report-card"><Panel className="study-report"><label htmlFor="study-report">本次学习感受（可选）</label><textarea id="study-report" name="self_report" rows="2" value={selfReport} onChange={(event) => setSelfReport(event.target.value)} placeholder="例如：完成了阅读，后半段注意力有些分散…" /></Panel></StudyTiltedCard>}
      <StudyTiltedCard className="study-plan-card"><Panel className="study-plan-panel"><SectionHeading title="今日学习计划" detail="把大目标拆成下一步" action={<Button variant="quiet" icon="PhSparkle" onClick={() => setExperience(studyExperienceModel("plan", {}))}>打开 AI 学习路线</Button>} />{tasks.slice(0, 4).length ? <div className="study-today-list">{tasks.slice(0, 4).map((item, index) => <button type="button" className="study-today-task" key={item.id} onClick={() => setExperience(studyExperienceModel("task", { title: "计划详情", value: item.title || "学习计划", detail: item.deadline ? `计划截止 ${dateText(item.deadline)}` : "打开任务页可以继续编辑和完成计划。", task: item }))}><span className={`study-today-check ${index < 2 ? "is-highlighted" : ""}`}><Icon name={index < 2 ? "PhCheck" : "PhSquare"} size={15} weight="bold" /></span><span><strong>{item.title}</strong><small>{item.deadline ? dateText(item.deadline) : "待安排"}</small></span><Icon name="PhDotsThree" size={18} weight="bold" /></button>)}</div> : <div className="inline-empty"><Icon name="PhCheckCircle" size={28} />当前没有待完成计划</div>}<Link className="study-plan-link" to="/tasks">查看完整计划 <Icon name="PhArrowRight" size={14} /></Link></Panel></StudyTiltedCard>
      <div className="stat-grid"><StudyMetric label="今日专注" value={todayMinutes} unit="分钟" detail="点击查看节奏" icon="PhClock" tone="violet" onClick={() => setExperience(studyExperienceModel("metric", { label: "今日专注", value: todayMinutes, unit: "分钟", eyebrow: "TODAY RHYTHM", insight: "午后是你的高效区间", trend }))} /><StudyMetric label="已完成会话" value={completed.length} unit="次" detail="查看累计记录" icon="PhCheckCircle" tone="green" onClick={() => setExperience(studyExperienceModel("metric", { label: "已完成会话", value: completed.length, unit: "次", eyebrow: "FOCUS ARCHIVE", insight: "完成记录正在形成你的专注画像", trend }))} /><StudyMetric label="连续专注" value={completed.length ? "—" : "0"} unit="天" detail="查看连续趋势" icon="PhSparkle" tone="orange" onClick={() => setExperience(studyExperienceModel("metric", { label: "连续专注", value: completed.length ? "—" : "0", unit: "天", eyebrow: "FOCUS STREAK", insight: "保持出现，比偶尔超常更重要", trend }))} /><StudyMetric label="专注评分" value="—" unit="/100" detail="查看评分说明" icon="PhChartLineUp" tone="blue" onClick={() => setExperience(studyExperienceModel("metric", { label: "专注评分", value: "—", unit: "/100", eyebrow: "FOCUS SCORE", insight: "完成更多会话后生成专注评分", trend }))} /></div>
      <StudyTiltedCard className="study-trend-card"><Panel className="study-trend-panel"><SectionHeading title="专注趋势（本周）" detail={`${weekMinutes} 分钟已完成`} action={<Button variant="quiet" icon="PhArrowsOut" onClick={() => setExperience(studyExperienceModel("trend", { title: "本周专注趋势", value: `${weekMinutes} 分钟`, detail: "完成会话会按开始日期累积到本周趋势中。", trend }))}>展开分析</Button>} /><div className="trend-bars" aria-label="本周专注趋势">{trend.map((item) => <span key={item.date}><i style={{ height: `${Math.max(item.count ? 14 : 4, Math.round(item.count / Math.max(...trend.map((value) => value.count), 1) * 100))}%` }} /><small>{item.label}</small><b>{item.count || ""}</b></span>)}</div></Panel></StudyTiltedCard>
      <StudyTiltedCard className="study-experience-card"><Panel className="study-experience-entry"><SectionHeading title="沉浸模式" detail="隐藏干扰，只保留当前目标和专注计时" action={<Button icon="PhArrowsDownUp" onClick={() => setExperience(studyExperienceModel("focus", { title: active ? "沉浸专注" : "准备专注", goal: active?.goal || goal || "给今天一段专注时间", value: active ? `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}` : "", detail: active ? "正在进行的学习会话" : "选择时长后开始，计时与当前页面保持同步。" }))}>进入沉浸模式</Button>} /></Panel></StudyTiltedCard>
      <div className="grid grid-2"><StudyTiltedCard className="study-records-card"><Panel><SectionHeading title="最近记录" detail="每一次完成都会留下轨迹" />{sessions.slice(0, 4).length ? <div className="list-stack">{sessions.slice(0, 4).map((item) => <button type="button" className="list-row" key={item.id} onClick={() => setExperience(studyExperienceModel("record", item))}><span className="row-icon tone-green"><Icon name="PhCheckCircle" size={18} /></span><span className="row-copy"><strong>{item.goal || "一次学习陪伴"}</strong><small>{dateText(item.started_at)} · {item.status === "completed" ? "已完成" : item.status}</small></span><span className="row-meta">{Math.round(Number(item.duration_seconds || 0) / 60)} 分钟</span></button>)}</div> : <div className="inline-empty"><Icon name="PhChartLineUp" size={30} />还没有学习记录</div>}</Panel></StudyTiltedCard><StudyTiltedCard className="study-tasks-card"><Panel><SectionHeading title="待完成计划" action={<Link className="text-link" to="/tasks">管理全部</Link>} />{tasks.slice(0, 4).length ? <div className="list-stack">{tasks.slice(0, 4).map((item) => <button type="button" className="list-row" key={item.id} onClick={() => setExperience(studyExperienceModel("task", { title: "计划详情", value: item.title || "学习计划", detail: item.deadline ? `计划截止 ${dateText(item.deadline)}` : "打开任务页可以继续编辑和完成计划。", task: item }))}><span className="row-icon tone-blue"><Icon name="PhCheckSquare" size={18} /></span><span className="row-copy"><strong>{item.title}</strong><small>{item.deadline ? dateText(item.deadline) : "待安排"}</small></span><Icon name="PhArrowsOut" size={16} /></button>)}</div> : <div className="inline-empty">当前没有待完成计划</div>}</Panel></StudyTiltedCard></div>
      {experience && <ExperienceLayer experience={experience} active={active} seconds={seconds} goal={goal} mode={mode} soundOn={whiteNoise.enabled} blockNotifications={blockNotifications} breaking={breaking} breakdown={breakdown} onClose={() => setExperience(null)} onStart={() => { start(experience.goal || goal); setExperience(null); }} onTogglePause={togglePause} onFinish={finish} onBreakdown={planBreakdown} onGoalChange={setGoal} onModeChange={setMode} onToggleSound={whiteNoise.toggle} onToggleNotifications={() => setBlockNotifications((value) => !value)} onReuse={reuseExperience} onSaveTask={saveTaskFromLayer} onCompleteTask={completeTaskFromLayer} onSaveBreakdown={saveBreakdownTasks} />}
    </div>}
  </PageFrame><SummerNavDock sceneAudio={ambient} /></>;
}

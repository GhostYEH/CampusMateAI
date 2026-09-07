import { createPortal } from "react-dom";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import { WhiteNoiseControl } from "./WhiteNoiseControl.jsx";
import { randomQuote } from "../../features/study/summerQuotes.js";

const SCENES = Object.freeze([
  { key: "rain", label: "雨景", caption: "林间雨声", asset: "/assets/study/summer-rain.webp" },
  { key: "snow", label: "雪景", caption: "安静一点", asset: "/assets/study/summer-snow.webp" },
  { key: "cloud", label: "暖云", caption: "松弛推进", asset: "/assets/study/summer-cloud.webp" },
]);

const EXIT_HOLD_MS = 1400;

function timerText(seconds) {
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export default function SummerFocusRoom({
  active,
  pomodoro,
  seconds,
  goal,
  preset,
  customMinutes,
  mode,
  blockNotifications,
  whiteNoise,
  tasks,
  taskTotal = 0,
  taskCompleted = 0,
  dailyGoalMinutes = 60,
  todayFocusMinutes = 0,
  scene,
  onSelectScene,
  onSaveDailyGoal,
  onGoalChange,
  onPresetChange,
  onCustomMinutesChange,
  onModeChange,
  onToggleNotifications,
  onStart,
  onTogglePause,
  onFinish,
  onReset,
  onSkip,
  onTaskSelect,
  onOpenPlan,
  onRefresh,
}) {
  const [immersive, setImmersive] = useState(false);
  const [quote, setQuote] = useState(() => randomQuote(scene));
  const [goalDraft, setGoalDraft] = useState(String(dailyGoalMinutes));
  const exitTimerRef = useRef(null);
  const isBreak = pomodoro?.mode === "break";
  const isRunning = Boolean(pomodoro?.isRunning);
  const sceneAsset = SCENES.find((item) => item.key === scene)?.asset;
  const totalSeconds = (isBreak ? pomodoro.breakMinutes : pomodoro.focusMinutes) * 60;
  const progress = totalSeconds ? Math.min(100, Math.max(0, ((totalSeconds - seconds) / totalSeconds) * 100)) : 0;

  useEffect(() => {
    if (!immersive) return undefined;
    document.body.classList.add("study-summer-body-lock");
    return () => document.body.classList.remove("study-summer-body-lock");
  }, [immersive]);

  function enterImmersive() {
    setQuote(randomQuote(scene));
    document.activeElement?.blur?.();
    if (!active && !isBreak && !isRunning) onStart();
    setImmersive(true);
  }

  function startImmersiveExitHold() {
    clearImmersiveExitHold();
    exitTimerRef.current = window.setTimeout(() => setImmersive(false), EXIT_HOLD_MS);
  }

  function clearImmersiveExitHold() {
    if (exitTimerRef.current) {
      window.clearTimeout(exitTimerRef.current);
      exitTimerRef.current = null;
    }
  }

  const status = isBreak ? (isRunning ? "休息中" : "准备休息") : active?.status === "paused" ? "暂时休息" : active ? "正在专注" : "准备开始";
  const focusTitle = isBreak ? "给自己几分钟喘口气" : active?.goal || "开始专注";
  const immersiveTime = timerText(seconds);

  useEffect(() => setGoalDraft(String(dailyGoalMinutes)), [dailyGoalMinutes]);

  return (
    <section className="study-summer-room" data-study-scene={scene} style={{ "--study-scene-image": `url("${sceneAsset}")` }} aria-labelledby="study-summer-title">
      <div className="study-summer-room__backdrop" aria-hidden="true" />
      <header className="study-summer-header">
        <div>
          <span className="study-summer-eyebrow">Deep focus</span>
          <h1 id="study-summer-title">学习陪伴</h1>
          <p>给眼前的事一段完整的时间，慢慢把今天推进下去。</p>
        </div>
        <div className="study-summer-header__actions">
          <div className="study-summer-scenes" role="group" aria-label="选择学习场景">
            {SCENES.map((item) => <button key={item.key} type="button" className={scene === item.key ? "is-active" : ""} aria-pressed={scene === item.key} onClick={() => onSelectScene(item.key)}><span>{item.label}</span><small>{item.caption}</small></button>)}
          </div>
          <button type="button" className="study-summer-immersive-trigger" onClick={enterImmersive} aria-label="进入沉浸模式"><Icon name="PhArrowsOut" size={15} /><span>沉浸模式</span></button>
          <button type="button" className="study-summer-refresh" onClick={onRefresh} aria-label="刷新学习记录"><Icon name="PhArrowClockwise" size={16} /></button>
        </div>
      </header>

      <div className="study-summer-grid">
        <section className={`study-summer-focus ${isRunning ? "is-active" : ""}`} aria-label="专注计时">
          <div className="study-summer-focus__heading"><div><span className="study-summer-eyebrow">{isBreak ? "Break time" : active ? "Focus in progress" : "Ready when you are"}</span><h2>{focusTitle}</h2></div><span className="study-summer-focus__status">第 {pomodoro?.round || 1} 轮 · {status}</span></div>
          <form className="study-summer-goal" onSubmit={(event) => { event.preventDefault(); onSaveDailyGoal?.(goalDraft); }}><span>今日目标 <strong>{todayFocusMinutes}/{dailyGoalMinutes} 分钟</strong></span><label htmlFor="study-daily-goal">目标分钟数</label><input id="study-daily-goal" type="number" min="15" max="480" step="15" value={goalDraft} onChange={(event) => setGoalDraft(event.target.value)} /><button type="submit">保存</button></form>
          <div className="study-summer-timer" aria-live="polite"><strong style={{ "--study-progress": `${progress}%` }}>{timerText(seconds)}</strong><span>{isBreak ? "休息计时" : status}</span></div>

          {!active && !isBreak && <div className="study-summer-presets" role="group" aria-label="选择专注时长">{[25, 45, 60].map((minutes) => <button key={minutes} type="button" className={preset === minutes ? "is-active" : ""} onClick={() => onPresetChange(minutes)}>{minutes} 分钟</button>)}<button type="button" className={preset === "custom" ? "is-active" : ""} onClick={() => onPresetChange("custom")}>自定义</button>{preset === "custom" && <input type="number" min="5" max="180" aria-label="自定义专注分钟数" value={customMinutes} onChange={(event) => onCustomMinutesChange(event.target.value)} />}</div>}

          {active || isBreak ? <div className="study-summer-focus__actions"><Button variant="secondary" icon={isRunning ? "PhPause" : "PhPlay"} onClick={onTogglePause}>{isRunning ? "暂停" : isBreak ? "开始休息" : "继续"}</Button>{!isBreak && <Button icon="PhStop" onClick={onFinish}>结束并记录</Button>}<button type="button" className="study-summer-icon-action" onClick={onReset} aria-label="重置计时"><Icon name="PhArrowCounterClockwise" size={16} /></button><button type="button" className="study-summer-icon-action" onClick={onSkip} aria-label={isBreak ? "跳过休息" : "跳过当前阶段"}><Icon name="PhSkipForward" size={16} /></button></div> : <form className="study-summer-start" onSubmit={(event) => { event.preventDefault(); onStart(); }}><label htmlFor="summer-study-goal">这次想完成什么</label><div><input id="summer-study-goal" name="study-goal" value={goal} onChange={(event) => onGoalChange(event.target.value)} placeholder="例如：完成高数第三章习题" /><Button icon="PhPlay">开始专注</Button></div></form>}

          <div className="study-summer-options"><label><span><Icon name="PhStudent" size={15} />专注模式</span><select value={mode} disabled={Boolean(active) || isBreak} onChange={(event) => onModeChange(event.target.value)}><option value="deep">深度专注</option><option value="steady">稳步推进</option><option value="quiet">安静阅读</option></select></label><label><span><Icon name="PhBell" size={15} />提醒设置</span><button type="button" onClick={onToggleNotifications}>{blockNotifications ? "阻止通知" : "允许通知"}</button></label></div>
          <WhiteNoiseControl enabled={whiteNoise.enabled} volume={whiteNoise.volume} onToggle={whiteNoise.toggle} onVolumeChange={whiteNoise.setVolume} />
        </section>

        <div className="study-summer-atmosphere" aria-hidden="true"><div className="study-summer-atmosphere__ring study-summer-atmosphere__ring--outer" /><div className="study-summer-atmosphere__ring study-summer-atmosphere__ring--inner" /><span>{isBreak ? "let the mind reset" : isRunning ? "stay with it" : "a quiet place for today"}</span></div>

        <section className="study-summer-todos" aria-labelledby="study-summer-todos-title"><header><div><span className="study-summer-todos__icon"><Icon name="PhListChecks" size={16} /></span><div><h2 id="study-summer-todos-title">今日待办</h2><p>{tasks.length ? `${tasks.length} 件等待完成 · ${taskCompleted}/${taskTotal} 已完成` : taskTotal ? `${taskCompleted}/${taskTotal} 已完成` : "从一件小事开始"}</p></div></div><strong>{tasks.length}</strong></header><div className="study-summer-todos__progress"><span style={{ width: `${taskTotal ? Math.round((taskCompleted / taskTotal) * 100) : 0}%` }} /></div><div className="study-summer-todos__list">{tasks.length ? tasks.slice(0, 6).map((task) => <button type="button" key={task.id} onClick={() => onTaskSelect(task)}><span className="study-summer-todo-check"><Icon name="PhCircle" size={15} /></span><span>{task.title}</span><Icon name="PhArrowUpRight" size={14} /></button>) : <div className="study-summer-todos__empty"><Icon name="PhSparkle" size={20} /><p>留一点空间给今天</p><small>写下一件事，然后专心完成它</small></div>}</div><div className="study-summer-todos__footer"><button type="button" onClick={onOpenPlan}><Icon name="PhSparkle" size={14} />打开 AI 学习路线</button><Link to="/plans">查看完整计划 <Icon name="PhArrowRight" size={13} /></Link></div></section>
      </div>

      {immersive && createPortal(
        <div className="study-summer-immersive" data-immersive-scene={scene}>
          <span className="study-summer-immersive__eyebrow">{isBreak ? "Break time" : "Deep focus"}</span>
          <strong className="study-summer-immersive__time">{immersiveTime}</strong>
          <p className="study-summer-immersive__quote">「{quote}」</p>
          <button type="button" className="study-summer-immersive__exit" onPointerDown={startImmersiveExitHold} onPointerUp={clearImmersiveExitHold} onPointerLeave={clearImmersiveExitHold} onPointerCancel={clearImmersiveExitHold}><span>长按退出</span></button>
        </div>,
        document.body,
      )}
    </section>
  );
}

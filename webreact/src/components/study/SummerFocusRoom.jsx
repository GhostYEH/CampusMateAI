import { createPortal } from "react-dom";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import { WhiteNoiseControl } from "./WhiteNoiseControl.jsx";
import { randomQuote } from "../../features/study/summerQuotes.js";

const SCENES = Object.freeze([
  { key: "rain", label: "雨景", caption: "林间雨声" },
  { key: "snow", label: "雪景", caption: "安静一点" },
  { key: "cloud", label: "暖云", caption: "松弛推进" },
]);

const BREAK_MINUTES = 5;
const POMODORO_KEY = "campus_study_pomodoro";
const EXIT_HOLD_MS = 1400;

const clampMinutes = (value) => Math.max(5, Math.min(180, Number(value) || 45));

function timerText(totalSeconds) {
  return `${String(Math.floor(totalSeconds / 60)).padStart(2, "0")}:${String(totalSeconds % 60).padStart(2, "0")}`;
}

const RING_RADIUS = 72;
const RING_SIZE = 168;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

function loadPomodoro() {
  try {
    const raw = window.localStorage.getItem(POMODORO_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (!value || typeof value !== "object") return null;
    return {
      phase: value.phase === "break" ? "break" : "ready",
      round: Number.isInteger(value.round) && value.round >= 1 ? value.round : 1,
      completed: Number.isInteger(value.completed) && value.completed >= 0 ? value.completed : 0,
      breakExpiresAt: Number.isFinite(value.breakExpiresAt) ? value.breakExpiresAt : null,
    };
  } catch {
    return null;
  }
}

function savePomodoro(state) {
  try {
    window.localStorage.setItem(POMODORO_KEY, JSON.stringify(state));
  } catch {
    // 忽略隐私模式下的写入失败
  }
}

export default function SummerFocusRoom({
  active,
  seconds,
  goal,
  preset,
  customMinutes,
  mode,
  blockNotifications,
  whiteNoise,
  tasks,
  scene,
  onSelectScene,
  onGoalChange,
  onPresetChange,
  onCustomMinutesChange,
  onModeChange,
  onToggleNotifications,
  onStart,
  onTogglePause,
  onFinish,
  onTaskSelect,
  onOpenPlan,
  onRefresh,
}) {
  // ── 番茄轮次（专注/休息循环），专注小节走后端会话、休息小节本地计时 ──
  const [phase, setPhase] = useState("ready"); // "ready" | "focus" | "break"
  const [round, setRound] = useState(1);
  const [completed, setCompleted] = useState(0);
  const [breakSecondsLeft, setBreakSecondsLeft] = useState(BREAK_MINUTES * 60);
  const breakDeadlineRef = useRef(null);
  const [immersive, setImmersive] = useState(false);
  const [quote, setQuote] = useState(() => randomQuote(scene));

  const selectedMinutes = preset === "custom" ? clampMinutes(customMinutes) : preset;
  const focusTotal = selectedMinutes * 60;
  const maxBreakSeconds = BREAK_MINUTES * 60;

  // 倒计时剩余：专注态用后端会话已进行秒数换算，休息态用本地剩余秒数
  const remaining = phase === "break"
    ? breakSecondsLeft
    : Math.max(0, focusTotal - seconds);

  useEffect(() => {
    const saved = loadPomodoro();
    if (!saved) return;
    setRound(saved.round);
    setCompleted(saved.completed);
    if (saved.phase === "break" && saved.breakExpiresAt && saved.breakExpiresAt > Date.now()) {
      setPhase("break");
      breakDeadlineRef.current = saved.breakExpiresAt;
      setBreakSecondsLeft(Math.max(0, Math.ceil((saved.breakExpiresAt - Date.now()) / 1000)));
    }
  }, []);

  useEffect(() => {
    savePomodoro({ phase, round, completed, breakExpiresAt: breakDeadlineRef.current });
  }, [phase, round, completed]);

  // 休息小节本地倒计时（不受刷新/后台节流影响，按截止时间计算）
  useEffect(() => {
    if (phase !== "break") return undefined;
    const update = () => {
      const next = Math.max(0, Math.ceil((breakDeadlineRef.current - Date.now()) / 1000));
      if (next <= 0) {
        setPhase("ready");
        setRound((value) => value + 1);
        breakDeadlineRef.current = null;
        return;
      }
      setBreakSecondsLeft(next);
    };
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [phase]);

  // 专注倒计时归零：记录本小节并自动进入休息
  useEffect(() => {
    if (phase !== "focus" || !active || remaining > 0) return undefined;
    onFinish();
    setCompleted((value) => value + 1);
    breakDeadlineRef.current = Date.now() + maxBreakSeconds * 1000;
    setBreakSecondsLeft(maxBreakSeconds);
    setPhase("break");
    return undefined;
  }, [remaining, phase, active, onFinish, maxBreakSeconds]);

  // 沉浸模式锁定页面滚动；离开时解锁
  useEffect(() => {
    if (!immersive) return undefined;
    document.body.classList.add("study-summer-body-lock");
    return () => document.body.classList.remove("study-summer-body-lock");
  }, [immersive]);

  function enterImmersive() {
    setQuote(randomQuote(scene));
    document.activeElement?.blur?.();
    // 未在计时时进入沉浸模式：自动开始当前轮专注
    if (!active && phase === "ready") startFocus();
    setImmersive(true);
  }

  function startFocus() {
    if (!active) onStart();
    setPhase("focus");
  }

  function skipStage() {
    if (phase === "focus") {
      if (active) onFinish(); // 跳过专注小节：记录已进行时长，避免后端会话悬挂
      breakDeadlineRef.current = Date.now() + maxBreakSeconds * 1000;
      setBreakSecondsLeft(maxBreakSeconds);
      setPhase("break");
    } else if (phase === "break") {
      setPhase("ready");
      setRound((value) => value + 1);
      breakDeadlineRef.current = null;
    }
  }

  function resetPomodoro() {
    if (active) onFinish();
    setPhase("ready");
    setRound(1);
    setCompleted(0);
    setBreakSecondsLeft(maxBreakSeconds);
    breakDeadlineRef.current = null;
    setImmersive(false);
  }

  const activeLabel = active?.status === "paused" ? "暂停中" : "专注中";
  const phaseLabel = phase === "break" ? `第 ${round} 轮 · 休息一下` : phase === "focus" ? `第 ${round} 轮 · 专注` : `第 ${round} 轮 · 就绪`;
  const progress = phase === "break"
    ? 1 - breakSecondsLeft / maxBreakSeconds
    : active ? 1 - remaining / focusTotal : 0;
  const ringOffset = RING_CIRCUMFERENCE * (1 - Math.max(0, Math.min(1, progress)));
  const immersiveTime = phase === "break" ? timerText(breakSecondsLeft) : timerText(remaining);

  return (
    <section className="study-summer-room" data-study-scene={scene} aria-labelledby="study-summer-title">
      <div className="study-summer-room__backdrop" aria-hidden="true" />
      <header className="study-summer-header">
        <div>
          <span className="study-summer-eyebrow">Deep focus</span>
          <h1 id="study-summer-title">学习陪伴</h1>
          <p>给眼前的事一段完整的时间，慢慢把今天推进下去。</p>
        </div>
        <div className="study-summer-header__actions">
          <div className="study-summer-scenes" role="group" aria-label="选择学习场景">
            {SCENES.map((item) => (
              <button
                key={item.key}
                type="button"
                className={scene === item.key ? "is-active" : ""}
                aria-pressed={scene === item.key}
                onClick={() => onSelectScene(item.key)}
              >
                <span>{item.label}</span>
                <small>{item.caption}</small>
              </button>
            ))}
          </div>
          <button type="button" className="study-summer-immersive-trigger" onClick={enterImmersive} aria-label="进入沉浸模式">
            <Icon name="PhArrowsOut" size={15} />
            <span>沉浸模式</span>
          </button>
          <button type="button" className="study-summer-refresh" onClick={onRefresh} aria-label="刷新学习记录">
            <Icon name="PhArrowClockwise" size={16} />
          </button>
        </div>
      </header>

      <div className="study-summer-grid">
        <section className={`study-summer-focus ${active ? "is-active" : ""}`} aria-label="专注计时">
          <div className="study-summer-focus__heading">
            <div>
              <span className="study-summer-eyebrow">{active ? "Focus in progress" : "Ready when you are"}</span>
              <h2>{active?.goal || "开始专注"}</h2>
            </div>
            <span className="study-summer-focus__status">{active ? activeLabel : phaseLabel}</span>
          </div>

          <div className="study-summer-timer" aria-live="polite">
            <div className="study-summer-ring" aria-hidden="true">
              <svg width={RING_SIZE} height={RING_SIZE} viewBox={`0 0 ${RING_SIZE} ${RING_SIZE}`}>
                <circle className="study-summer-ring__track" cx={RING_SIZE / 2} cy={RING_SIZE / 2} r={RING_RADIUS} />
                <circle
                  className="study-summer-ring__progress"
                  cx={RING_SIZE / 2}
                  cy={RING_SIZE / 2}
                  r={RING_RADIUS}
                  strokeDasharray={RING_CIRCUMFERENCE}
                  strokeDashoffset={ringOffset}
                />
              </svg>
            </div>
            <strong>{timerText(remaining)}</strong>
            <span>{phase === "break" ? `休息 ${BREAK_MINUTES} 分钟` : phase === "focus" ? activeLabel : `${selectedMinutes} 分钟`}</span>
          </div>

          {phase === "break" ? (
            <div className="study-summer-focus__actions">
              <Button variant="secondary" icon="PhSkipForward" onClick={skipStage}>跳过休息</Button>
              <Button variant="secondary" icon="PhArrowCounterClockwise" onClick={resetPomodoro}>重置</Button>
            </div>
          ) : active ? (
            <div className="study-summer-focus__actions">
              <Button variant="secondary" icon={active.status === "paused" ? "PhPlay" : "PhPause"} onClick={onTogglePause}>
                {active.status === "paused" ? "继续" : "暂停"}
              </Button>
              <Button variant="secondary" icon="PhSkipForward" onClick={skipStage}>跳过</Button>
              <Button icon="PhStop" onClick={onFinish}>结束并记录</Button>
            </div>
          ) : (
            <form className="study-summer-start" onSubmit={(event) => { event.preventDefault(); startFocus(); }}>
              <label htmlFor="summer-study-goal">这次想完成什么</label>
              <div>
                <input id="summer-study-goal" name="study-goal" value={goal} onChange={(event) => onGoalChange(event.target.value)} placeholder="例如：完成高数第三章习题" />
                <Button icon="PhPlay">开始专注</Button>
              </div>
            </form>
          )}

          {completed > 0 && (
            <div className="study-summer-dots" aria-label={`已完成本轮前完成的 ${completed} 个番茄`}>
              {Array.from({ length: Math.min(completed, 8) }).map((_, index) => <span key={index} />)}
              {completed > 8 && <small>×{completed}</small>}
            </div>
          )}

          {phase !== "break" && (
            <div className="study-summer-options">
              <label>
                <span><Icon name="PhStudent" size={15} />专注模式</span>
                <select value={mode} disabled={Boolean(active)} onChange={(event) => onModeChange(event.target.value)}>
                  <option value="deep">深度专注</option>
                  <option value="steady">稳步推进</option>
                  <option value="quiet">安静阅读</option>
                </select>
              </label>
              <label>
                <span><Icon name="PhBell" size={15} />提醒设置</span>
                <button type="button" onClick={onToggleNotifications}>{blockNotifications ? "阻止通知" : "允许通知"}</button>
              </label>
            </div>
          )}
          <WhiteNoiseControl enabled={whiteNoise.enabled} volume={whiteNoise.volume} onToggle={whiteNoise.toggle} onVolumeChange={whiteNoise.setVolume} />
        </section>

        <div className="study-summer-atmosphere" aria-hidden="true">
          <div className="study-summer-atmosphere__ring study-summer-atmosphere__ring--outer" />
          <div className="study-summer-atmosphere__ring study-summer-atmosphere__ring--inner" />
          <span>{active ? "stay with it" : "a quiet place for today"}</span>
        </div>

        <section className="study-summer-todos" aria-labelledby="study-summer-todos-title">
          <header>
            <div>
              <span className="study-summer-todos__icon"><Icon name="PhListChecks" size={16} /></span>
              <div>
                <h2 id="study-summer-todos-title">今日待办</h2>
                <p>{tasks.length ? `${tasks.length} 件等待完成` : "从一件小事开始"}</p>
              </div>
            </div>
            <strong>{tasks.length}</strong>
          </header>
          <div className="study-summer-todos__progress"><span style={{ width: tasks.length ? "18%" : "0%" }} /></div>
          <div className="study-summer-todos__list">
            {tasks.length ? tasks.slice(0, 6).map((task) => (
              <button type="button" key={task.id} onClick={() => onTaskSelect(task)}>
                <span className="study-summer-todo-check"><Icon name="PhCircle" size={15} /></span>
                <span>{task.title}</span>
                <Icon name="PhArrowUpRight" size={14} />
              </button>
            )) : <div className="study-summer-todos__empty"><Icon name="PhSparkle" size={20} /><p>留一点空间给今天</p><small>写下一件事，然后专心完成它</small></div>}
          </div>
          <div className="study-summer-todos__footer">
            <button type="button" onClick={onOpenPlan}><Icon name="PhSparkle" size={14} />打开 AI 学习路线</button>
            <Link to="/tasks">查看完整计划 <Icon name="PhArrowRight" size={13} /></Link>
          </div>
        </section>
      </div>

      {immersive && createPortal(
        <div className="study-summer-immersive" data-immersive-scene={scene}>
          <span className="study-summer-immersive__eyebrow">{phase === "break" ? "Break time" : "Deep focus"}</span>
          <strong className="study-summer-immersive__time">{immersiveTime}</strong>
          <p className="study-summer-immersive__quote">「{quote}」</p>
          <button type="button" className="study-summer-immersive__exit" onPointerDown={startImmersiveExitHold} onPointerUp={clearImmersiveExitHold} onPointerLeave={clearImmersiveExitHold} onPointerCancel={clearImmersiveExitHold}>
            <span>长按退出</span>
          </button>
        </div>,
        document.body,
      )}
    </section>
  );

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
}
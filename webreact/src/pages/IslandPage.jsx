import { useEffect, useMemo, useState } from "react";
import { Icon } from "../components/Icon.jsx";
import SummerNavDock from "../components/study/SummerNavDock.jsx";
import { useAmbientSound } from "../features/study/ambientSound.js";
import * as api from "../data/api.js";
import { itemsOf } from "../data/contracts.js";

const SCENES = Object.freeze([
  { key: "rain", label: "雨景", caption: "林间雨声" },
  { key: "snow", label: "雪景", caption: "安静一点" },
  { key: "cloud", label: "暖云", caption: "松弛推进" },
]);

const CHECKIN_KEY = "campus_island_checkin";

const dayKey = (value) => {
  const date = value ? new Date(value) : new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
};

const startOfDay = (value) => new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime();
const dayFromTimestamp = (ts) => new Date(ts).toISOString().slice(0, 10);

export default function IslandPage() {
  const [scene, setScene] = useState(() => {
    const stored = window.localStorage.getItem("campus_study_scene");
    const known = ["rain", "snow", "cloud"];
    return known.includes(stored) ? stored : "rain";
  });
  const ambient = useAmbientSound(scene);
  const [sessions, setSessions] = useState([]);
  const [checkin, setCheckin] = useState(() => {
    try { return JSON.parse(window.localStorage.getItem(CHECKIN_KEY) || "null"); } catch { return null; }
  });
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.getStudySessions().then((value) => setSessions(itemsOf(value))).catch(() => {}).finally(() => setLoaded(true));
  }, []);

  function selectScene(nextScene) { setScene(nextScene); window.localStorage.setItem("campus_study_scene", nextScene); }

  const stats = useMemo(() => {
    const minutesByDay = {};
    sessions.forEach((item) => {
      const key = dayFromTimestamp(item.started_at);
      if (!key) return;
      minutesByDay[key] = (minutesByDay[key] || 0) + Math.round(Number(item.duration_seconds || 0) / 60);
    });
    const todayKey = dayKey();
    const yesterdayKey = dayKey(new Date(Date.now() - 86400000));

    let streak = 0;
    let cursor = new Date();
    if (!minutesByDay[todayKey]) cursor = new Date(Date.now() - 86400000);
    while (minutesByDay[dayFromTimestamp(cursor.getTime())]) {
      streak += 1;
      cursor = new Date(cursor.getTime() - 86400000);
    }

    const monday = new Date();
    const day = monday.getDay() || 7;
    monday.setDate(monday.getDate() - (day - 1));
    const week = Array.from({ length: 7 }, (_, index) => {
      const date = new Date(monday.getTime() + index * 86400000);
      const key = dayKey(date);
      return { label: "一二三四五六日"[index], key, minutes: minutesByDay[key] || 0 };
    });
    const weekDays = week.filter((item) => item.minutes > 0).length;
    const totalMinutes = sessions.reduce((sum, item) => sum + Math.round(Number(item.duration_seconds || 0) / 60), 0);
    const islandAge = new Set(sessions.map((item) => dayFromTimestamp(item.started_at)).filter(Boolean)).size;
    return { totalMinutes, islandAge, streak, weekDays, week, todayKey, yesterdayKey };
  }, [sessions]);

  const checkedToday = Boolean(checkin && checkin.date === stats.todayKey);
  const showStreak = checkedToday ? checkin.count : stats.streak || 0;

  function doCheckin() {
    const todayStreak = stats.streak || 0;
    const count = todayStreak > 0 ? todayStreak + 1 : 1;
    const next = { date: stats.todayKey, count };
    setCheckin(next);
    window.localStorage.setItem(CHECKIN_KEY, JSON.stringify(next));
  }

  const todayText = new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date());

  return (
    <section className="study-summer-room island-room" data-study-scene={scene} aria-labelledby="island-title">
      <div className="study-summer-room__backdrop" aria-hidden="true" />
      <header className="study-summer-header">
        <div>
          <span className="study-summer-eyebrow">{todayText}</span>
          <h1 id="island-title">小岛</h1>
          <p>每天来走一走，把认真学习的样子留在这座岛上。</p>
        </div>
        <div className="study-summer-header__actions">
          <div className="study-summer-scenes" role="group" aria-label="选择岛屿场景">
            {SCENES.map((item) => <button key={item.key} type="button" className={scene === item.key ? "is-active" : ""} aria-pressed={scene === item.key} onClick={() => selectScene(item.key)}><span>{item.label}</span><small>{item.caption}</small></button>)}
          </div>
        </div>
      </header>

      {!loaded ? <div className="island-loading"><span className="loading-orb" /><p>正在登上小岛…</p></div> : (
        <div className="island-body">
          <div className="island-landscape" aria-hidden="true">
            <div className="island-landscape__sun" />
            <div className="island-landscape__sea">
              <span className="island-landscape__label">{loaded ? "今日天气正好" : ""}</span>
            </div>
          </div>

          <div className="island-stats">
            {[
              { label: "持续来访", value: showStreak, unit: "天" },
              { label: "岛龄", value: stats.islandAge, unit: "天" },
              { label: "本周足迹", value: stats.weekDays, unit: "天" },
            ].map((item) => (
              <div key={item.label} className="island-stat">
                <span>{item.label}</span>
                <strong>{item.value}<small>{item.unit}</small></strong>
              </div>
            ))}
          </div>

          <div className="island-foot">
            <div className="island-week">
              <h2>本周足迹</h2>
              <div className="island-week__bars" role="img" aria-label="本周每天的学习分钟数">
                {stats.week.map((item) => (
                  <div key={item.key} className="island-week__col">
                    <i style={{ height: `${Math.max(6, Math.min(100, item.minutes ? item.minutes / 3 : 0))}%` }} />
                    <small>{item.label}</small>
                    <b>{item.minutes || ""}</b>
                  </div>
                ))}
              </div>
            </div>

            <div className="island-checkin">
              {checkedToday ? (
                <div className="island-checkin__done"><span><Icon name="PhCheck" size={18} weight="bold" /></span><div><strong>今天来过了</strong><small>已持续 {showStreak} 天</small></div></div>
              ) : (
                <button type="button" className="island-checkin__button" onClick={doCheckin}><Icon name="PhCalendarBlank" size={16} />今天签到</button>
              )}
              <small className="island-checkin__hint">累计学习 {Math.round(stats.totalMinutes / 60)} 小时 · {stats.totalMinutes} 分钟</small>
            </div>
          </div>
        </div>
      )}

      <SummerNavDock sceneAudio={ambient} />
    </section>
  );
}
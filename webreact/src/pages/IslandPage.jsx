import { useEffect, useMemo, useState } from "react";
import { Icon } from "../components/Icon.jsx";
import SummerNavDock from "../components/study/SummerNavDock.jsx";
import { LearningIsland } from "../components/island/LearningIsland.tsx";
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

const dayFromTimestamp = (ts) => new Date(ts).toISOString().slice(0, 10);

export default function IslandPage() {
  const [scene, setSceneState] = useState(() => {
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

  // 3D 小岛按 html[data-scene] 换肤，与场景按钮保持同步
  function selectScene(nextScene) {
    setSceneState(nextScene);
    window.localStorage.setItem("campus_study_scene", nextScene);
    if (document.documentElement) document.documentElement.dataset.scene = nextScene;
  }
  useEffect(() => {
    if (document.documentElement) document.documentElement.dataset.scene = scene;
  }, []);

  const stats = useMemo(() => {
    const minutesByDay = {};
    const todayKey = dayKey();
    sessions.forEach((item) => {
      const key = dayFromTimestamp(item.started_at);
      if (!key) return;
      minutesByDay[key] = (minutesByDay[key] || 0) + Math.round(Number(item.duration_seconds || 0) / 60);
    });

    let streak = 0;
    let cursor = new Date();
    if (!minutesByDay[todayKey]) cursor = new Date(Date.now() - 86400000);
    while (minutesByDay[dayFromTimestamp(cursor.getTime())]) {
      streak += 1;
      cursor = new Date(cursor.getTime() - 86400000);
    }

    const dateKeys = new Set(Object.keys(minutesByDay));
    const days = [];
    const totalDays = 365;
    for (let index = totalDays - 1; index >= 0; index -= 1) {
      const date = new Date(Date.now() - index * 86400000);
      days.push({ key: dayKey(date), active: dateKeys.has(dayKey(date)) });
    }
    const todayCompleted = sessions.filter((item) => item.status === "completed" && dayFromTimestamp(item.started_at) === todayKey).length;
    const totalMinutes = sessions.reduce((sum, item) => sum + Math.round(Number(item.duration_seconds || 0) / 60), 0);
    return { minutesByDay, streak, days, todayCompleted, totalMinutes, todayKey };
  }, [sessions]);

  const checkedToday = Boolean(checkin && checkin.date === stats.todayKey);
  const showStreak = checkedToday ? checkin.count : stats.streak || 0;
  const islandAge = new Set(sessions.map((item) => dayFromTimestamp(item.started_at)).filter(Boolean)).size;

  function doCheckin() {
    const count = (stats.streak || 0) > 0 ? stats.streak + 1 : 1;
    const next = { date: stats.todayKey, count };
    setCheckin(next);
    window.localStorage.setItem(CHECKIN_KEY, JSON.stringify(next));
  }

  const todayText = new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date());

  return (
    <section className="island-scene" data-study-scene={scene} aria-labelledby="island-title">
      <div className="island-scene__backdrop" aria-hidden="true" />
      <div className="island-scene__shell">
        <header className="island-top">
          <div>
            <span className="study-summer-eyebrow">{todayText}</span>
            <h1 id="island-title">小岛</h1>
          </div>
          <div className="island-stats-glass">
            {[
              { label: "连续打卡", value: showStreak, unit: "天" },
              { label: "累计打卡", value: islandAge, unit: "天" },
              { label: "获得树叶", value: stats.todayCompleted || (checkedToday ? 1 : 0), unit: "个" },
            ].map((item) => (
              <div key={item.label}><span>{item.label}</span><strong>{item.value}<small>{item.unit}</small></strong></div>
            ))}
          </div>
        </header>

        <div className="island-toolbar">
          <div className="study-summer-scenes" role="group" aria-label="选择岛屿场景">
            {SCENES.map((item) => <button key={item.key} type="button" className={scene === item.key ? "is-active" : ""} aria-pressed={scene === item.key} onClick={() => selectScene(item.key)}><span>{item.label}</span><small>{item.caption}</small></button>)}
          </div>
        </div>

        <div className="island-stage" aria-hidden={!loaded}>
          {loaded ? (
            <LearningIsland totalCheckins={islandAge} streak={showStreak} totalHours={Math.round(stats.totalMinutes / 60)} todayCheckins={checkedToday ? 1 : 0} />
          ) : (
            <div className="island-loading"><span className="loading-orb" /><p>正在登上小岛…</p></div>
          )}
        </div>

        <footer className="island-bottom">
          <div className="island-heat">
            <h2>连续记录</h2>
            <div className="island-heat__grid" role="img" aria-label="近一年有学习记录的日子">
              {stats.days.map((item) => <i key={item.key} className={item.active ? "is-active" : ""} title={item.key} />)}
            </div>
          </div>
          <div className="island-sign">
            {checkedToday ? (
              <div className="island-sign__done"><Icon name="PhCheck" size={16} weight="bold" /><div><strong>今天签过了</strong><small>已连续 {showStreak} 天</small></div></div>
            ) : (
              <button type="button" className="island-sign__button" onClick={doCheckin}><Icon name="PhCalendarBlank" size={15} /><span>今天签到</span></button>
            )}
          </div>
        </footer>
      </div>

      <SummerNavDock sceneAudio={ambient} />
    </section>
  );
}
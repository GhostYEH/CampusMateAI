import { useEffect, useMemo, useState } from "react";
import { Icon } from "../components/Icon.jsx";
import SummerNavDock from "../components/study/SummerNavDock.jsx";
import { LearningIsland } from "../components/island/LearningIsland.tsx";
import { Heatmap } from "../components/island/Heatmap.jsx";
import { useAmbientSound } from "../features/study/ambientSound.js";
import * as api from "../data/api.js";
import { itemsOf } from "../data/contracts.js";
import { saveStudyScene } from "../features/study/scenes.js";

const SCENES = Object.freeze([
  { key: "rain", label: "雨景", caption: "林间雨声" },
  { key: "snow", label: "雪景", caption: "安静一点" },
  { key: "cloud", label: "暖云", caption: "松弛推进" },
]);

const dayKey = (value) => {
  const date = value ? new Date(value) : new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
};

const dayFromTimestamp = (ts) => new Date(ts).toISOString().slice(0, 10);

function isScene(value) {
  return ["rain", "snow", "cloud"].includes(value);
}

export default function IslandPage() {
  const [scene, setSceneState] = useState(() => {
    const stored = window.localStorage.getItem("campus_study_scene");
    return isScene(stored) ? stored : "rain";
  });
  const ambient = useAmbientSound(scene);
  const [sessions, setSessions] = useState([]);
  const [checkins, setCheckins] = useState({ items: [], total: 0, streak: 0, longest_streak: 0, week_count: 0, today_checked: false });
  const [loaded, setLoaded] = useState(false);
  const [checkinError, setCheckinError] = useState("");

  useEffect(() => {
    Promise.all([api.getStudySessions(), api.getStudyCheckins()]).then(([studySessions, studyCheckinSummary]) => { setSessions(itemsOf(studySessions)); setCheckins(studyCheckinSummary || { items: [], total: 0, streak: 0, longest_streak: 0, week_count: 0, today_checked: false }); if (studyCheckinSummary?.unsupported) setCheckinError("签到服务尚未加载，请重启后端后再签到。"); }).catch(() => setCheckinError("签到数据加载失败，请稍后重试。")).finally(() => setLoaded(true));
  }, []);

  // 3D 小岛按 html[data-scene] 换肤，与场景按钮保持同步
  function selectScene(nextScene) {
    setSceneState(nextScene);
    saveStudyScene(nextScene);
    if (document.documentElement) document.documentElement.dataset.scene = nextScene;
  }
  useEffect(() => {
    if (document.documentElement) document.documentElement.dataset.scene = scene;
  }, []);

  const data = useMemo(() => {
    const now = new Date();
    const todayKey = dayKey();
    const days = new Set();
    const checkinDays = new Set((checkins.items || []).map((item) => item.date));
    let totalMinutes = 0;
    let todayCompleted = 0;
    sessions.forEach((item) => {
      const key = dayFromTimestamp(item.started_at);
      if (!key) return;
      days.add(key);
      totalMinutes += Math.round(Number(item.duration_seconds || 0) / 60);
      if (item.status === "completed" && key === todayKey) todayCompleted += 1;
    });

    let streak = 0;
    let cursor = new Date();
    if (!days.has(todayKey)) cursor = new Date(Date.now() - 86400000);
    while (days.has(dayFromTimestamp(cursor.getTime()))) {
      streak += 1;
      cursor = new Date(cursor.getTime() - 86400000);
    }

    // 今年全年（1/1 → 今天），供热力图使用
    const year = now.getFullYear();
    const yearStart = new Date(year, 0, 1);
    const heatData = [];
    for (let d = new Date(yearStart); d.getTime() <= now.getTime(); d.setDate(d.getDate() + 1)) {
      const key = dayKey(d);
      heatData.push({ date: key, checked: days.has(key) || checkinDays.has(key) });
    }

    // 今年探索天数与最长连续
    const yearDays = heatData.filter((item) => item.checked).map((item) => item.date);
    const yearSet = new Set(yearDays);
    let longestStreak = 0;
    let run = 0;
    for (const d of heatData) {
      if (yearSet.has(d.date)) { run += 1; if (run > longestStreak) longestStreak = run; }
      else run = 0;
    }

    // 本周足迹
    const day = now.getDay() || 7;
    const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - (day - 1));
    const weekDays = new Set();
    for (let index = 0; index < 7; index += 1) {
      const date = new Date(monday.getTime() + index * 86400000);
      const key = dayKey(date);
      if (days.has(key)) weekDays.add(key);
    }

    return { todayKey, streak, year, heatData, exploredDays: yearSet.size, longestStreak: Math.max(longestStreak, checkins.longest_streak || 0), weekDays: Math.max(weekDays.size, checkins.week_count || 0), islandAge: Math.max(days.size, checkins.total || 0), totalMinutes, todayCompleted };
  }, [sessions, checkins]);

  const checkedToday = Boolean(checkins.today_checked);
  const showStreak = Math.max(checkins.streak || 0, data.streak || 0);

  async function doCheckin() {
    try {
      const result = await api.createStudyCheckin({ scene });
      if (result?.checkin) {
        const nextItems = [result.checkin, ...(checkins.items || []).filter((item) => item.date !== result.checkin.date)];
        const next = { ...checkins, items: nextItems, total: Math.max(checkins.total || 0, nextItems.length), today_checked: true, streak: checkins.today_checked ? (checkins.streak || 1) : (checkins.streak || 0) + 1 };
        setCheckins(next);
      }
    } catch (error) {
      setCheckinError(error?.code === "STUDY_CHECKINS_UNAVAILABLE" ? "签到服务尚未加载，请重启后端后再签到。" : "签到失败，请稍后重试。");
    }
  }

  const todayText = new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date());

  return (
    <section className="island-scene" data-study-scene={scene} aria-labelledby="island-title">
      <header className="island-top">
        <div className="island-heading">
          <p className="study-summer-eyebrow">{todayText}</p>
          <h1 id="island-title">小岛</h1>
          <div className="island-toolbar">
            <div className="study-summer-scenes" role="group" aria-label="选择岛屿场景">
              {SCENES.map((item) => <button key={item.key} type="button" className={scene === item.key ? "is-active" : ""} aria-pressed={scene === item.key} onClick={() => selectScene(item.key)}><span>{item.label}</span><small>{item.caption}</small></button>)}
            </div>
          </div>
        </div>
        <div className="island-surface-stats">
          {[
            { label: "持续来访", value: showStreak, unit: "天" },
            { label: "岛龄", value: data.islandAge, unit: "天" },
            { label: "本周足迹", value: data.weekDays, unit: "天" },
          ].map((item) => (
            <div key={item.label}><p>{item.label}</p><strong>{item.value}<small>{item.unit}</small></strong></div>
          ))}
        </div>
      </header>

      <div className="island-stage" aria-hidden={!loaded}>
        {loaded ? (
          <LearningIsland totalCheckins={data.islandAge} streak={showStreak} totalHours={Math.round(data.totalMinutes / 60)} todayCheckins={data.todayCompleted || (checkedToday ? 1 : 0)} />
        ) : (
          <div className="island-loading"><span className="loading-orb" /><p>正在登上小岛…</p></div>
        )}
      </div>

      <footer className="island-dock-panel">
        <div className="island-dock-panel__inner">
          <div className="island-heat">
            <div className="island-heat__heading"><span>足迹</span><small>今年探索了 {data.exploredDays} 天 · 最长旅程 {data.longestStreak} 天</small></div>
            <div className="island-heat__scroll"><Heatmap data={data.heatData} year={data.year} compact /></div>
          </div>
          <div className="island-dock-panel__divider" aria-hidden="true" />
          <div className="island-sign">
            {checkedToday ? (
              <div className="island-sign__done"><span><Icon name="PhCheck" size={16} weight="bold" /></span><div><strong>今天签过了</strong><small>已持续 {showStreak} 天</small></div></div>
            ) : (
              <button type="button" className="island-sign__button" onClick={doCheckin}>
                <svg className="island-sign__sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M2 12h2" /><path d="M6 8c0-2.2 1.8-4 4-4s4 1.8 4 4c0 3.3-4 7-4 7s-4-3.7-4-7Z" /><path d="M20 12h2" /><path d="M14 8c0-2.2 1.8-4 4-4s4 1.8 4 4c0 3.3-4 7-4 7s-4-3.7-4-7Z" />
                </svg>
                <span>今天签到</span>
              </button>
            )}
            {checkinError && <p className="island-sign__error" role="alert">{checkinError}</p>}
          </div>
        </div>
      </footer>

      <SummerNavDock sceneAudio={ambient} />
    </section>
  );
}

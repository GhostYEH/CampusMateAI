import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import * as api from "../data/api.js";

import { useApp } from "../app/AppContext.jsx";
import { buildHomeSearchResults } from "../data/alignment.js";
import { buildDueItems, buildMainQuests, todayScheduleItems, selectUpcomingExam } from "../data/dashboardModel.js";
import { resolveHomeLearningCommand } from "../data/homeLearningModel.js";
import { resolveHomeOverviewMetrics } from "../data/overviewMetrics.js";
import {
  activityDatesFromFacts,
  calculateLevel,
  calculateStreak,
  evaluateAchievements,
  reconcileXpEvents,
  summarizeGamification,
} from "../data/gamificationModel.js";
import { createLocalGamificationRepository } from "../data/gamificationRepository.js";
import ClassicHome from "./home/ClassicHome.jsx";
import GamifiedHome from "./home/GamifiedHome.jsx";
import SylvaCampusOverview from "./home/SylvaCampusOverview.jsx";
import SylvaHomeHero from "../components/SylvaHomeHero.jsx";
import RippleDistortion from "../components/RippleDistortion.jsx";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

const DESKTOP_SHEET_RATIO = 0.48;
const MOBILE_SHEET_RATIO = 0.7;

const HOME_BOOT_TIMEOUT_MS = 1200;
const HOME_CACHE_TTL_MS = 30_000;
const homeDashboardCache = new Map();
const homeDashboardCacheTimes = new Map();
const homeLoadInFlight = new Map();

function dashboardCacheKeyFor(session) {
  return session?.id || session?.username || session?.email || session?.name || "anonymous";
}

function isHomeCacheFresh(dashboardCacheKey) {
  const cachedAt = homeDashboardCacheTimes.get(dashboardCacheKey);
  return Boolean(cachedAt) && Date.now() - cachedAt < HOME_CACHE_TTL_MS;
}

function loadHomeState(dashboardCacheKey) {
  const existingRequest = homeLoadInFlight.get(dashboardCacheKey);
  if (existingRequest) return existingRequest;

  const request = Promise.allSettled([
    api.getDashboard(),
    api.getCourses(),
    api.getStudySessions(),
    api.getAssignments({ status: "pending" }),
    api.getTasks({ status: "pending" }),
    api.getNotices({ unread_only: true }),
    api.getScheduleItems(),
    api.getExams(),
    api.getTasks({ page_size: 200 }),
    api.getCommunityPosts({ sort: "hot", page: 1, page_size: 4 }),
    api.getAssignments(),
    api.getNotices(),
  ]).then((results) => {
    const valueAt = (index) => results[index].status === "fulfilled" ? results[index].value : null;
    const dashboard = valueAt(0);
    const courses = valueAt(1);
    const studySessions = valueAt(2);
    const pendingAssignments = valueAt(3);
    const pendingTasks = valueAt(4);
    const unreadNotices = valueAt(5);
    const scheduleItems = valueAt(6);
    const exams = valueAt(7);
    const personalTasks = valueAt(8);
    const hotPosts = valueAt(9);
    const allAssignments = valueAt(10);
    const allNotices = valueAt(11);

    if (!dashboard && !courses && !pendingAssignments && !pendingTasks) {
      throw new Error("首页数据加载失败");
    }

    return {
      dashboard,
      courses: courses?.items || [],
      studySessions: Array.isArray(studySessions) ? studySessions : [],
      personalTasks: personalTasks?.items || [],
      exams: Array.isArray(exams) ? exams : [],
      scheduleItems: scheduleItems?.items || [],
      searchFacts: { assignments: allAssignments?.items || [], notices: allNotices?.items || [] },
      liveOverview: { courses, pendingAssignments, pendingTasks, unreadNotices },
      hotPosts: hotPosts?.items || [],
    };
  });

  homeLoadInFlight.set(dashboardCacheKey, request);
  request.then(
    () => homeLoadInFlight.delete(dashboardCacheKey),
    () => homeLoadInFlight.delete(dashboardCacheKey),
  );
  return request;
}

function useStudentDashboardData(searchQuery) {
  const { session, setDashboardSummary } = useApp();
  const repository = useMemo(() => createLocalGamificationRepository(window.localStorage), []);
  const dashboardCacheKey = dashboardCacheKeyFor(session);
  const cachedHomeState = homeDashboardCache.get(dashboardCacheKey);
  const [loading, setLoading] = useState(() => !cachedHomeState);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [now, setNow] = useState(Date.now());
  const [dashboard, setDashboard] = useState(() => cachedHomeState?.dashboard || null);
  const [courses, setCourses] = useState(() => cachedHomeState?.courses || []);
  const [studySessions, setStudySessions] = useState(() => cachedHomeState?.studySessions || []);
  const [personalTasks, setPersonalTasks] = useState(() => cachedHomeState?.personalTasks || []);
  const [exams, setExams] = useState(() => cachedHomeState?.exams || []);
  const [scheduleItems, setScheduleItems] = useState(() => cachedHomeState?.scheduleItems || []);
  const [searchFacts, setSearchFacts] = useState(() => cachedHomeState?.searchFacts || { assignments: [], notices: [] });
  const [scheduleLoading, setScheduleLoading] = useState(() => !cachedHomeState);
  const [liveOverview, setLiveOverview] = useState(() => cachedHomeState?.liveOverview || { courses: null, pendingAssignments: null, pendingTasks: null, unreadNotices: null });
  const [gamificationSnapshot, setGamificationSnapshot] = useState({ version: 1, events: [], achievements: [] });
  const [hotPosts, setHotPosts] = useState(() => cachedHomeState?.hotPosts || []);
  const [reloadVersion, setReloadVersion] = useState(0);

  const reload = useCallback(() => setReloadVersion((v) => v + 1), []);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let active = true;
    const cachedHomeState = homeDashboardCache.get(dashboardCacheKey);
    const shouldRefresh = !cachedHomeState || reloadVersion > 0 || !isHomeCacheFresh(dashboardCacheKey);
    setLoading(!cachedHomeState);
    setScheduleLoading(!cachedHomeState);
    setRefreshing(Boolean(cachedHomeState && shouldRefresh));
    setError("");
    if (!shouldRefresh) return undefined;
    const bootTimer = cachedHomeState ? null : window.setTimeout(() => {
      if (!active) return;
      setLoading(false);
      setScheduleLoading(false);
    }, HOME_BOOT_TIMEOUT_MS);
    (async () => {
      try {
        const nextHomeState = await loadHomeState(dashboardCacheKey);
        homeDashboardCache.set(dashboardCacheKey, nextHomeState);
        homeDashboardCacheTimes.set(dashboardCacheKey, Date.now());
        if (!active) return;
        setDashboard(nextHomeState.dashboard);
        if (nextHomeState.dashboard) setDashboardSummary?.(nextHomeState.dashboard);
        setCourses(nextHomeState.courses);
        setStudySessions(nextHomeState.studySessions);
        setScheduleItems(nextHomeState.scheduleItems);
        setExams(nextHomeState.exams);
        setPersonalTasks(nextHomeState.personalTasks);
        setLiveOverview(nextHomeState.liveOverview);
        setHotPosts(nextHomeState.hotPosts);
        setSearchFacts(nextHomeState.searchFacts);
      } catch (loadError) {
        if (!active) return;
        setError(loadError?.response?.data?.detail || "首页数据加载失败，请检查后端服务后重试。");
      } finally {
        if (bootTimer) window.clearTimeout(bootTimer);
        if (active) { setLoading(false); setRefreshing(false); setScheduleLoading(false); }
      }
    })();
    return () => { active = false; if (bootTimer) window.clearTimeout(bootTimer); };
  }, [dashboardCacheKey, reloadVersion, setDashboardSummary]);

  const normalizedSearch = searchQuery.trim().toLocaleLowerCase();
  const matches = useCallback((item, fields) => !normalizedSearch || fields.some((field) => String(item?.[field] || "").toLocaleLowerCase().includes(normalizedSearch)), [normalizedSearch]);

  const dueItems = useMemo(() => buildDueItems(dashboard), [dashboard]);
  const filteredDueItems = useMemo(() => dueItems.filter((item) => matches(item, ["title", "kind", "course_name", "source_name"])), [dueItems, matches]);
  const filteredCourses = useMemo(() => courses.filter((item) => matches(item, ["name", "code", "semester"])), [courses, matches]);
  const searchResults = useMemo(() => buildHomeSearchResults({ courses, assignments: searchFacts.assignments, tasks: personalTasks, notices: searchFacts.notices }, searchQuery), [courses, personalTasks, searchFacts, searchQuery]);
  const overviewMetrics = useMemo(() => resolveHomeOverviewMetrics({ ...liveOverview, fallback: dashboard }), [liveOverview, dashboard]);
  const todayCourses = useMemo(() => todayScheduleItems(scheduleItems, new Date(now)), [scheduleItems, now]);
  const mainQuests = useMemo(() => buildMainQuests({ scheduleItems, dueItems, exams }, new Date(now)), [scheduleItems, dueItems, exams, now]);
  const filteredMainQuests = useMemo(() => mainQuests.filter((item) => matches(item, ["title", "meta", "sourceType"])), [mainQuests, matches]);
  const completedTasks = useMemo(() => personalTasks.filter((task) => task.status === "completed" && task.completed_at), [personalTasks]);
  const completedFocusSessions = useMemo(() => studySessions.filter((session) => session.status === "completed" && session.mode === "focus"), [studySessions]);
  const gamificationFacts = useMemo(() => ({ completedTasks, completedFocusSessions }), [completedTasks, completedFocusSessions]);

  const todayFocusSeconds = useMemo(() => {
    const current = new Date(now);
    const isToday = (value) => {
      const date = new Date(value);
      return !Number.isNaN(date.valueOf()) && date.getFullYear() === current.getFullYear() && date.getMonth() === current.getMonth() && date.getDate() === current.getDate();
    };
    return studySessions.filter((session) => isToday(session.started_at)).reduce((total, session) => {
      if (session.status === "active") {
        const started = new Date(session.started_at).getTime();
        return total + Math.max(0, Math.floor((now - started) / 1000) - Number(session.pause_seconds || 0));
      }
      return total + Math.max(0, Number(session.duration_seconds || 0));
    }, 0);
  }, [studySessions, now]);

  const accountKey = session?.id || session?.username || session?.email || session?.name || "anonymous";

  const gamification = useMemo(() => {
    const current = new Date(now);
    const stored = repository.load(accountKey);
    const withEvents = reconcileXpEvents(stored, gamificationFacts, current);
    const withAchievements = evaluateAchievements(withEvents, gamificationFacts, current);
    const snapshot = repository.save(accountKey, withAchievements);
    return summarizeGamification(snapshot, gamificationFacts, current);
  }, [repository, accountKey, gamificationFacts, now]);

  const learningCommand = useMemo(() => resolveHomeLearningCommand({
    scheduleItems,
    dueItems,
    exams,
    studySessions,
    overviewMetrics,
  }, new Date(now)), [scheduleItems, dueItems, exams, studySessions, overviewMetrics, now]);

  const visibleHotPosts = hotPosts;

  const state = useMemo(() => ({
    loading, refreshing, error, now, dashboard, courses, studySessions, personalTasks, exams, searchResults,
    user: session, scheduleItems, scheduleLoading, normalizedSearch,
    filteredDueItems, filteredCourses, overviewMetrics, todayCourses, mainQuests, filteredMainQuests,
    todayFocusSeconds, learningCommand, gamification, visibleHotPosts,
  }), [loading, refreshing, error, now, dashboard, courses, studySessions, personalTasks, exams, searchResults, session, scheduleItems, scheduleLoading, normalizedSearch, filteredDueItems, filteredCourses, overviewMetrics, todayCourses, mainQuests, filteredMainQuests, todayFocusSeconds, learningCommand, gamification, visibleHotPosts]);

  return { state, reload };
}

export default function HomePage() {
  const { dashboardStyle } = useApp();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const query = searchParams.get("q") || "";
  const { state, reload } = useStudentDashboardData(query);

  function handleNavigate(path) { navigate(path); }
  function handleOpenDue(item) {
    navigate(item.route || (item.kind === "作业" ? `/tasks/assignment/${item.id}` : `/tasks/personal/${item.id}`));
  }

  const dashboard = dashboardStyle === "gamified"
    ? <GamifiedHome state={state} onNavigate={handleNavigate} onReload={reload} />
    : <ClassicHome state={state} searchQuery={query} onNavigate={handleNavigate} onOpenDue={handleOpenDue} onReload={reload} />;

  const stageRef = useRef(null);
  const sheetRef = useRef(null);

  useEffect(() => {
    const stage = stageRef.current;
    const sheet = sheetRef.current;
    if (!stage || !sheet) return undefined;

    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    if (reducedMotion) return undefined;

    gsap.registerPlugin(ScrollTrigger);
    const ctx = gsap.context(() => {
      gsap.fromTo(stage,
        { opacity: 1 },
        {
          opacity: 0.55,
          ease: "none",
          scrollTrigger: { trigger: stage, start: "top top", end: "bottom top", scrub: true },
        }
      );

      const computeTargetScrollY = () => {
        const isCompactViewport = window.matchMedia("(max-width: 760px)").matches;
        const sheetRatio = isCompactViewport ? MOBILE_SHEET_RATIO : DESKTOP_SHEET_RATIO;
        const sheetTop = sheet.getBoundingClientRect().top + window.scrollY;
        return Math.max(0, sheetTop - window.innerHeight * sheetRatio);
      };

      ScrollTrigger.create({
        trigger: document.documentElement,
        start: 0,
        end: () => `+=${computeTargetScrollY()}`,
        snap: {
          snapTo: [0, 1],
          duration: { min: 0.35, max: 0.6 },
          ease: "power3.inOut",
          delay: 0.18,
        },
      });
    }, stageRef);

    const refreshTimer = window.setTimeout(() => ScrollTrigger.refresh(), 800);
    return () => { window.clearTimeout(refreshTimer); ctx.revert(); };
  }, []);

  return <div className="sylva-home-page">
    <SylvaHomeHero />
    <section ref={stageRef} className="home-stage">
      <SylvaCampusOverview state={state} onNavigate={handleNavigate} onOpenDue={handleOpenDue} />
    </section>
    <section ref={sheetRef} className="rising-sheet" aria-label="CampusMate 学习工作台">
      <div className="rising-sheet-video" aria-hidden="true">
        <RippleDistortion className="rising-sheet-ripple" src="/assets/login-campus.mp4" brushSize={180} strength={0.16} swirl={1} rings={4} grayscale={false} quality="low" trigger="both" clickStrength={2.5} tint="#4a7dff" tintAmount={0.08} glint={0.3} />
      </div>
      <div className="rising-sheet-scrim" aria-hidden="true" />
      <div className="rising-sheet-content">
        <div id="campus-dashboard" className="sylva-dashboard" tabIndex={-1}>{dashboard}</div>
      </div>
    </section>
  </div>;
}

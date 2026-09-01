import { computed, onMounted, onUnmounted, shallowRef, toValue } from "vue";
import { useAppStore } from "../stores/app";
import {
  eduScheduleItems,
  getPersonalTasks,
  getStudySessions,
  getStudentAssignments,
  getStudentCourses,
  getStudentDashboard,
  getStudentExams,
  getStudentNotices,
} from "../services/studentApi";
import { buildDueItems, buildMainQuests, todayScheduleItems } from "../features/dashboard/dashboardModel";
import { resolveHomeLearningCommand } from "../features/home/homeLearningModel";
import { resolveHomeOverviewMetrics } from "../features/home/overviewMetrics";
import {
  activityDatesFromFacts,
  calculateLevel,
  calculateStreak,
  evaluateAchievements,
  reconcileXpEvents,
  summarizeGamification,
} from "../features/gamification/gamificationModel";
import { createLocalGamificationRepository } from "../features/gamification/gamificationRepository";

export function useStudentDashboardData(options = {}) {
  const store = useAppStore();
  const repository = createLocalGamificationRepository(window.localStorage);
  const loading = shallowRef(true);
  const refreshing = shallowRef(false);
  const error = shallowRef("");
  const dashboard = shallowRef(null);
  const courses = shallowRef([]);
  const studySessions = shallowRef([]);
  const personalTasks = shallowRef([]);
  const exams = shallowRef([]);
  const scheduleItems = shallowRef([]);
  const scheduleLoading = shallowRef(false);
  const liveOverview = shallowRef({ courses: null, pendingAssignments: null, pendingTasks: null, unreadNotices: null });
  const now = shallowRef(Date.now());
  const gamificationSnapshot = shallowRef({ version: 1, events: [], achievements: [] });
  let clockTimer;

  const searchQuery = computed(() => String(toValue(options.searchQuery) || ""));
  const normalizedSearch = computed(() => searchQuery.value.trim().toLocaleLowerCase());
  const matches = (item, fields) => !normalizedSearch.value || fields.some((field) => String(item?.[field] || "").toLocaleLowerCase().includes(normalizedSearch.value));
  const dueItems = computed(() => buildDueItems(dashboard.value));
  const filteredDueItems = computed(() => dueItems.value.filter((item) => matches(item, ["title", "kind", "course_name", "source_name"])));
  const filteredCourses = computed(() => courses.value.filter((item) => matches(item, ["name", "code", "semester"])));
  const overviewMetrics = computed(() => resolveHomeOverviewMetrics({ ...liveOverview.value, fallback: dashboard.value }));
  const todayCourses = computed(() => todayScheduleItems(scheduleItems.value, new Date(now.value)));
  const mainQuests = computed(() => buildMainQuests({ scheduleItems: scheduleItems.value, dueItems: dueItems.value, exams: exams.value }, new Date(now.value)));
  const filteredMainQuests = computed(() => mainQuests.value.filter((item) => matches(item, ["title", "meta", "sourceType"])));
  const completedTasks = computed(() => personalTasks.value.filter((task) => task.status === "completed" && task.completed_at));
  const completedFocusSessions = computed(() => studySessions.value.filter((session) => session.status === "completed" && session.mode === "focus"));
  const gamificationFacts = computed(() => ({ completedTasks: completedTasks.value, completedFocusSessions: completedFocusSessions.value }));

  const todayFocusSeconds = computed(() => {
    const current = new Date(now.value);
    const isToday = (value) => {
      const date = new Date(value);
      return !Number.isNaN(date.valueOf()) && date.getFullYear() === current.getFullYear() && date.getMonth() === current.getMonth() && date.getDate() === current.getDate();
    };
    return studySessions.value.filter((session) => isToday(session.started_at)).reduce((total, session) => {
      if (session.status === "active") {
        const started = new Date(session.started_at).getTime();
        return total + Math.max(0, Math.floor((now.value - started) / 1000) - Number(session.pause_seconds || 0));
      }
      return total + Math.max(0, Number(session.duration_seconds || 0));
    }, 0);
  });

  const totalXp = computed(() => gamificationSnapshot.value.events.reduce((sum, event) => sum + Math.max(0, Number(event.xp || 0)), 0));
  const level = computed(() => calculateLevel(totalXp.value));
  const streak = computed(() => calculateStreak(activityDatesFromFacts(gamificationFacts.value), new Date(now.value)));
  const gamification = computed(() => summarizeGamification(gamificationSnapshot.value, gamificationFacts.value, new Date(now.value)));
  const learningCommand = computed(() => resolveHomeLearningCommand({
    scheduleItems: scheduleItems.value,
    dueItems: dueItems.value,
    exams: exams.value,
    studySessions: studySessions.value,
    overviewMetrics: overviewMetrics.value,
  }, new Date(now.value)));

  const accountKey = () => store.session?.id || store.session?.username || store.session?.email || store.session?.name || "anonymous";

  function reconcileGamification() {
    const current = new Date(now.value);
    const stored = repository.load(accountKey());
    const withEvents = reconcileXpEvents(stored, gamificationFacts.value, current);
    const withAchievements = evaluateAchievements(withEvents, gamificationFacts.value, current);
    gamificationSnapshot.value = repository.save(accountKey(), withAchievements);
  }

  async function load(isRefresh = false) {
    if (isRefresh) refreshing.value = true;
    else loading.value = true;
    scheduleLoading.value = true;
    error.value = "";
    try {
      const results = await Promise.allSettled([
        getStudentDashboard(),
        getStudentCourses(),
        getStudySessions(),
        getStudentAssignments({ status: "pending" }),
        getPersonalTasks({ status: "pending" }),
        getStudentNotices({ unread_only: true }),
        eduScheduleItems(),
        getStudentExams(),
        getPersonalTasks({ page_size: 200 }),
      ]);
      const valueAt = (index) => results[index].status === "fulfilled" ? results[index].value : null;
      const [dashboardData, courseData, sessionData, assignmentData, pendingTaskData, noticeData, scheduleData, examData, personalTaskData] = results.map((_, index) => valueAt(index));
      if (!dashboardData && !courseData && !assignmentData && !pendingTaskData) throw new Error("首页数据加载失败");
      dashboard.value = dashboardData;
      if (dashboardData) store.setDashboardSummary(dashboardData);
      courses.value = courseData?.items || [];
      studySessions.value = Array.isArray(sessionData) ? sessionData : [];
      scheduleItems.value = scheduleData?.items || [];
      exams.value = Array.isArray(examData) ? examData : [];
      personalTasks.value = personalTaskData?.items || [];
      liveOverview.value = { courses: courseData, pendingAssignments: assignmentData, pendingTasks: pendingTaskData, unreadNotices: noticeData };
      reconcileGamification();
    } catch (loadError) {
      error.value = loadError.response?.data?.detail || "首页数据加载失败，请检查后端服务后重试。";
    } finally {
      loading.value = false;
      refreshing.value = false;
      scheduleLoading.value = false;
    }
  }

  const state = computed(() => ({
    loading: loading.value,
    refreshing: refreshing.value,
    error: error.value,
    now: now.value,
    dashboard: dashboard.value,
    courses: courses.value,
    studySessions: studySessions.value,
    personalTasks: personalTasks.value,
    exams: exams.value,
    user: store.session,
    scheduleItems: scheduleItems.value,
    scheduleLoading: scheduleLoading.value,
    normalizedSearch: normalizedSearch.value,
    filteredDueItems: filteredDueItems.value,
    filteredCourses: filteredCourses.value,
    overviewMetrics: overviewMetrics.value,
    todayCourses: todayCourses.value,
    mainQuests: mainQuests.value,
    filteredMainQuests: filteredMainQuests.value,
    todayFocusSeconds: todayFocusSeconds.value,
    learningCommand: learningCommand.value,
    gamificationSnapshot: gamificationSnapshot.value,
    gamificationFacts: gamificationFacts.value,
    totalXp: totalXp.value,
    level: level.value,
    streak: streak.value,
    gamification: gamification.value,
  }));

  onMounted(() => {
    void load();
    clockTimer = window.setInterval(() => { now.value = Date.now(); }, 60000);
  });
  onUnmounted(() => window.clearInterval(clockTimer));

  return { state, load };
}

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import CampusHotPostsPanel from "../../components/CampusHotPostsPanel.vue";
import HomeSchedulePanel from "../../components/home/HomeSchedulePanel.vue";
import HomeFooter from "../../components/home/footer/HomeFooter.vue";
import { useAppStore } from "../../stores/app";
import { eduScheduleItems, getCommunityPosts, getPersonalTasks, getStudySessions, getStudentAssignments, getStudentCourses, getStudentDashboard, getStudentNotices } from "../../services/studentApi";
import { resolveHomeOverviewMetrics } from "../../features/home/overviewMetrics";
import { fetchHitokoto, formatHitokotoSource } from "../../services/hitokoto";
import { usePageMotion } from "../../composables/usePageMotion";

const props = defineProps({ searchQuery: { type: String, default: "" } });
const router = useRouter();
const store = useAppStore();
const motionRoot = ref(null);
const loading = ref(true);
const refreshing = ref(false);
const error = ref("");
const dashboard = ref(null);
const courses = ref([]);
const hotPosts = ref([]);
const studySessions = ref([]);
const scheduleItems = ref([]);
const scheduleLoading = ref(false);
const liveOverview = ref({ courses: null, pendingAssignments: null, pendingTasks: null, unreadNotices: null });
const now = ref(Date.now());
const hitokoto = ref({ uuid: "", hitokoto: "把今天过得更有把握", from: "", from_who: null });
const hitokotoLoading = ref(false);
const hitokotoKey = ref(0);
let clockTimer;

const today = computed(() => new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date(now.value)));
const referenceWeek = computed(() => new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" }).format(new Date(now.value)).replace("星期", "周"));
const normalizedSearch = computed(() => props.searchQuery.trim().toLocaleLowerCase());
const matches = (item, fields) => !normalizedSearch.value || fields.some((field) => String(item[field] || "").toLocaleLowerCase().includes(normalizedSearch.value));

const dueItems = computed(() => [
  ...(dashboard.value?.due_soon_assignments || []).map((item) => ({ ...item, kind: "作业", due: item.deadline, icon: "PhFileText", tone: "red" })),
  ...(dashboard.value?.due_soon_personal_tasks || []).map((item) => ({ ...item, kind: "待办", due: item.deadline, icon: "PhCheckSquare", tone: "amber" })),
].sort((a, b) => new Date(a.due || 8640000000000000) - new Date(b.due || 8640000000000000)).slice(0, 6));
const filteredDueItems = computed(() => dueItems.value.filter((item) => matches(item, ["title", "kind", "course_name", "source_name"])));
const filteredCourses = computed(() => courses.value.filter((item) => matches(item, ["name", "code", "semester"])));

const visibleHotPosts = computed(() => hotPosts.value.filter((item) => matches(item, ["title", "category", "content"])).slice(0, 3));

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
    return total + Number(session.duration_seconds || 0);
  }, 0);
});
const focusHours = computed(() => (todayFocusSeconds.value / 3600).toFixed(1));
const focusProgress = computed(() => Math.min(100, Math.round(todayFocusSeconds.value / 108)));
const overviewMetrics = computed(() => resolveHomeOverviewMetrics({ ...liveOverview.value, fallback: dashboard.value }));
const pendingAssignments = computed(() => overviewMetrics.value.pendingAssignmentCount);
const pendingPersonal = computed(() => overviewMetrics.value.pendingTaskCount);
const totalPending = computed(() => overviewMetrics.value.pendingCount);
const urgentItems = computed(() => filteredDueItems.value.slice(0, 2));
const summaryText = computed(() => totalPending.value ? `还有 ${totalPending.value} 项任务等待处理` : "今天暂无临近截止事项");
const recentCourses = computed(() => filteredCourses.value.slice(0, 3));
const hitokotoSource = computed(() => formatHitokotoSource(hitokoto.value));
const hitokotoDetailUrl = computed(() => hitokoto.value.uuid ? `https://hitokoto.cn/?uuid=${encodeURIComponent(hitokoto.value.uuid)}` : "");
const motionReady = computed(() => !loading.value);
const reduceMotion = computed(() => store.reduceMotion);

usePageMotion({
  root: motionRoot,
  ready: motionReady,
  reduceMotion,
  hero: [".student-focus-card", ".student-overview-card"],
  reveal: "[data-motion-reveal]",
  parallax: ".focus-hero-image",
});

const quickLinks = [
  { label: "考试安排", detail: "查看时间与地点", icon: "PhExam", path: "/exams", tone: "violet" },
  { label: "办事大厅", detail: "校园服务入口", icon: "PhClipboardText", path: "/services", tone: "blue" },
  { label: "空教室查询", detail: "找一间安静的教室", icon: "PhSquaresFour", path: "/classrooms", tone: "green" },
  { label: "失物招领", detail: "查看待招领物品", icon: "PhMagnifyingGlass", path: "/lostfound", tone: "teal" },
  { label: "通知整理", detail: "智能归类与摘要", icon: "PhBell", path: "/notifications", tone: "amber" },
  { label: "AI 校园助手", detail: "问问校园里的事", icon: "PhRobot", path: "/counselor", tone: "rose" },
];

function dateText(value) {
  if (!value) return "未设置截止时间";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function deadlineLabel(value) {
  if (!value) return "未设置截止";
  const date = new Date(value);
  const current = new Date(now.value);
  const sameDay = date.toDateString() === current.toDateString();
  return sameDay ? `今日截止 ${date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}` : dateText(value);
}

function openDue(item) {
  router.push(item.kind === "作业" ? `/tasks/assignment/${item.id}` : `/tasks/personal/${item.id}`);
}

function openHotPost(postId) {
  router.push(`/community/${postId}`);
}

async function loadHitokoto() {
  if (hitokotoLoading.value) return;
  hitokotoLoading.value = true;
  try {
    const data = await fetchHitokoto();
    hitokoto.value = data;
    hitokotoKey.value += 1;
  } catch (e) {
    if (import.meta.env.DEV) console.warn("Hitokoto unavailable; using the local fallback.", e);
  } finally {
    hitokotoLoading.value = false;
  }
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
      getCommunityPosts({ sort: "hot", page: 1, page_size: 3 }),
      getStudySessions(),
      getStudentAssignments({ status: "pending" }),
      getPersonalTasks({ status: "pending" }),
      getStudentNotices({ unread_only: true }),
      eduScheduleItems(),
    ]);
    const valueAt = (index) => results[index].status === "fulfilled" ? results[index].value : null;
    const [dashboardData, courseData, hotPostData, sessionData, assignmentData, personalTaskData, noticeData, scheduleData] = results.map((_, index) => valueAt(index));
    if (!dashboardData && !courseData && !assignmentData && !personalTaskData) throw new Error("首页数据加载失败");
    dashboard.value = dashboardData;
    if (dashboardData) store.setDashboardSummary(dashboardData);
    courses.value = courseData?.items || [];
    hotPosts.value = hotPostData?.items || [];
    studySessions.value = Array.isArray(sessionData) ? sessionData : [];
    scheduleItems.value = scheduleData?.items || [];
    liveOverview.value = {
      courses: courseData,
      pendingAssignments: assignmentData,
      pendingTasks: personalTaskData,
      unreadNotices: noticeData,
    };
  } catch (e) {
    error.value = e.response?.data?.detail || "首页数据加载失败，请检查后端服务后重试。";
  } finally {
    loading.value = false;
    refreshing.value = false;
    scheduleLoading.value = false;
  }
}

onMounted(() => {
  load();
  loadHitokoto();
  clockTimer = window.setInterval(() => { now.value = Date.now(); }, 60000);
});
onUnmounted(() => window.clearInterval(clockTimer));
</script>

<template>
  <main ref="motionRoot" class="student-page student-home">
    <div v-if="error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ error }}<button class="link-button" @click="load()">重试</button></div>

    <section v-if="loading" class="student-home-skeleton" aria-label="正在加载首页">
      <div class="home-skeleton-focus"></div><div class="home-skeleton-overview"></div>
      <div v-for="i in 4" :key="i" class="home-skeleton-panel"></div>
    </section>

    <template v-else>
      <HomeFooter>
      <section class="student-home-hero">
        <article class="student-focus-card">
          <div class="focus-card-copy">
            <span class="hero-date">{{ referenceWeek }} <span class="reference-hero-weather"><UiIcon name="PhSun" :size="17" weight="fill" />24°C 晴</span></span>
            <div class="hitokoto-quote" :class="{ 'is-loading': hitokotoLoading }" :aria-busy="hitokotoLoading" aria-live="polite">
              <h1 :key="hitokotoKey" class="hitokoto-text"><a v-if="hitokotoDetailUrl" class="hitokoto-text-link" :href="hitokotoDetailUrl" target="_blank" rel="noopener noreferrer" aria-label="查看这条一言的详情">{{ hitokoto.hitokoto }}</a><span v-else>{{ hitokoto.hitokoto }}</span></h1>
              <div v-if="hitokotoDetailUrl" class="hitokoto-meta">
                <a class="hitokoto-source" :href="hitokotoDetailUrl" target="_blank" rel="noopener noreferrer" aria-label="查看这条一言的详情">{{ hitokotoSource }}</a>
                <button class="hitokoto-refresh" type="button" :disabled="hitokotoLoading" aria-label="换一句" @click="loadHitokoto"><UiIcon name="PhArrowClockwise" :class="{ spinning: hitokotoLoading }" :size="14" />换一句</button>
              </div>
            </div>
            <span class="focus-card-actions"><button class="focus-primary" @click="router.push('/study')">开始专注<UiIcon name="PhArrowRight" :size="17" weight="bold" /></button><button class="focus-secondary" @click="router.push('/tasks')"><UiIcon name="PhListChecks" :size="18" />查看待办</button></span>
          </div>
          <img class="focus-hero-image" src="/assets/generated/home-reference-hero-calendar.png" alt="日历、时钟与书本的学习插画" />
        </article>

        <article class="student-overview-card">
          <div class="overview-card-head"><h2>概览</h2><button @click="load(true)">{{ refreshing ? "刷新中" : "全部数据" }}<UiIcon name="PhCaretRight" :size="15" /></button></div>
          <div class="overview-stats">
            <button @click="router.push('/courses')"><span class="overview-icon violet"><UiIcon name="PhBookOpen" :size="22" /></span><span><small>我的课程</small><strong>{{ overviewMetrics.courseCount }}</strong><em>已加入课程总数</em></span></button>
            <button @click="router.push('/tasks')"><span class="overview-icon green"><UiIcon name="PhCheckSquare" :size="22" /></span><span><small>待完成事项</small><strong>{{ totalPending }}</strong><em>{{ pendingAssignments }} 项作业 · {{ pendingPersonal }} 项待办</em></span></button>
            <button @click="router.push('/notifications')"><span class="overview-icon amber"><UiIcon name="PhBell" :size="22" /></span><span><small>未读通知</small><strong>{{ overviewMetrics.unreadNoticeCount }}</strong><em>来自课程与班级</em></span></button>
            <button @click="router.push('/study')"><span class="overview-icon blue"><UiIcon name="PhClock" :size="22" /></span><span><small>今日专注时长</small><strong>{{ focusHours }}<b>小时</b></strong><em>实时同步记录</em></span></button>
          </div>
        </article>
      </section>

      <div v-if="normalizedSearch" class="home-search-note" data-motion-reveal><UiIcon name="PhMagnifyingGlass" :size="16" />正在筛选“{{ props.searchQuery }}”，当前首页有 {{ filteredDueItems.length + filteredCourses.length + visibleHotPosts.length }} 条相关内容</div>

      <section class="student-home-columns">
        <article class="student-home-panel task-panel" data-motion-reveal>
          <div class="home-panel-head"><h2><UiIcon name="PhBell" :size="19" />优先处理</h2><button @click="router.push('/tasks')">查看全部（{{ totalPending }}）</button></div>
          <div v-if="urgentItems.length" class="priority-list">
            <button v-for="(item, index) in urgentItems" :key="`${item.kind}-${item.id}`" @click="openDue(item)">
              <span v-if="index === 0" class="urgent-tag">紧急任务</span><strong>{{ item.title }}</strong><time :class="{ today: deadlineLabel(item.due).startsWith('今日') }">{{ deadlineLabel(item.due) }}</time>
            </button>
          </div>
          <div v-else class="compact-empty"><UiIcon name="PhCheckCircle" :size="26" /><strong>暂无临近截止事项</strong><span>新的课程作业和个人待办会从后端同步到这里。</span></div>
          <button class="panel-footer red" @click="router.push('/tasks')">查看全部待办与作业<UiIcon name="PhArrowRight" :size="15" /></button>
        </article>

        <HomeSchedulePanel data-motion-reveal :items="scheduleItems" :loading="scheduleLoading" @open-academic="router.push('/academic')" />

          <article class="student-home-panel hot-posts-panel" data-motion-reveal>
            <div class="home-panel-head"><h2><UiIcon name="PhFire" :size="19" weight="fill" />今日热门话题</h2><button @click="router.push('/community')">查看更多<UiIcon name="PhArrowRight" :size="15" /></button></div>
            <CampusHotPostsPanel v-if="visibleHotPosts.length" :posts="visibleHotPosts" @open-post="openHotPost" />
            <div v-else class="compact-empty home-reference-hot-empty" role="status">
              <div class="hot-empty-art" aria-hidden="true">
                <svg viewBox="0 0 240 158" role="presentation">
                  <defs>
                    <radialGradient id="hot-glow" cx="50%" cy="48%" r="58%">
                      <stop offset="0" stop-color="#efe8ff" stop-opacity=".98" />
                      <stop offset=".72" stop-color="#f7f4ff" stop-opacity=".58" />
                      <stop offset="1" stop-color="#ffffff" stop-opacity="0" />
                    </radialGradient>
                    <linearGradient id="hot-bubble" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0" stop-color="#b99af8" />
                      <stop offset="1" stop-color="#7852e7" />
                    </linearGradient>
                    <filter id="hot-soft-shadow" x="-20%" y="-20%" width="140%" height="150%">
                      <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#815be1" flood-opacity=".18" />
                    </filter>
                  </defs>
                  <ellipse cx="120" cy="80" rx="103" ry="66" fill="url(#hot-glow)" />
                  <circle cx="51" cy="76" r="11" fill="#d9c9ff" opacity=".6" />
                  <circle cx="191" cy="106" r="8" fill="#e4d9ff" opacity=".76" />
                  <circle cx="207" cy="57" r="5" fill="#cbb4fb" opacity=".74" />
                  <g filter="url(#hot-soft-shadow)">
                    <path d="M73 47c0-19 20-34 47-34s47 15 47 34c0 13-9 24-23 30l-7 21-19-16c-26-1-45-15-45-35Z" fill="url(#hot-bubble)" />
                    <text x="119" y="65" fill="#ffffff" font-family="Arial, sans-serif" font-size="47" font-weight="800" text-anchor="middle">#</text>
                  </g>
                </svg>
              </div>
              <strong>暂无热门话题</strong><span>快去社区看看，发现有趣的校园话题吧～</span><button class="reference-empty-action violet" @click="router.push('/community')">去社区逛逛</button>
            </div>
            <button v-if="visibleHotPosts.length" class="panel-footer violet" @click="router.push('/community')">查看完整热门榜单<UiIcon name="PhArrowRight" :size="15" /></button>
        </article>
      </section>

      <section class="student-quick-section" data-motion-reveal>
        <div class="quick-section-head"><h2>快捷入口 <UiIcon name="PhSparkle" :size="17" weight="fill" /></h2></div>
        <div class="student-quick-grid">
          <button v-for="item in quickLinks" :key="item.path" @click="router.push(item.path)"><span class="quick-icon" :class="item.tone"><UiIcon :name="item.icon" :size="20" /></span><span><strong>{{ item.label }}</strong><small>{{ item.detail }}</small></span><UiIcon name="PhCaretRight" :size="15" /></button>
        </div>
      </section>
      </HomeFooter>
    </template>
  </main>
</template>

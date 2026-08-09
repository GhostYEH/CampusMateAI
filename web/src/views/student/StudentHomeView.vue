<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { useAppStore } from "../../stores/app";
import { getStudySessions, getStudentActivities, getStudentCourses, getStudentDashboard } from "../../services/studentApi";

const props = defineProps({ searchQuery: { type: String, default: "" } });
const router = useRouter();
const store = useAppStore();
const loading = ref(true);
const refreshing = ref(false);
const error = ref("");
const dashboard = ref(null);
const courses = ref([]);
const activities = ref([]);
const studySessions = ref([]);
const now = ref(Date.now());
let clockTimer;

const today = computed(() => new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date(now.value)));
const normalizedSearch = computed(() => props.searchQuery.trim().toLocaleLowerCase());
const matches = (item, fields) => !normalizedSearch.value || fields.some((field) => String(item[field] || "").toLocaleLowerCase().includes(normalizedSearch.value));

const dueItems = computed(() => [
  ...(dashboard.value?.due_soon_assignments || []).map((item) => ({ ...item, kind: "作业", due: item.deadline, icon: "PhFileText", tone: "red" })),
  ...(dashboard.value?.due_soon_personal_tasks || []).map((item) => ({ ...item, kind: "待办", due: item.deadline, icon: "PhCheckSquare", tone: "amber" })),
].sort((a, b) => new Date(a.due || 8640000000000000) - new Date(b.due || 8640000000000000)).slice(0, 6));
const filteredDueItems = computed(() => dueItems.value.filter((item) => matches(item, ["title", "kind", "course_name", "source_name"])));
const filteredCourses = computed(() => courses.value.filter((item) => matches(item, ["name", "code", "semester"])));

const campusItems = computed(() => [
  ...(dashboard.value?.recent_announcements || []).map((item) => ({ ...item, label: item.course_name || item.class_name || "课程通知", date: item.published_at || item.created_at, icon: "PhMegaphone", tone: "green", path: "/notifications" })),
  ...activities.value.map((item) => ({ ...item, label: item.category || "校园活动", date: item.start_at || item.start_time || item.date, icon: "PhCalendarStar", tone: "blue", path: `/campus-activities/${item.id}` })),
].filter((item) => matches(item, ["title", "label", "category", "location"])).sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0)).slice(0, 4));

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
const pendingAssignments = computed(() => Number(dashboard.value?.pending_assignment_count || 0));
const pendingPersonal = computed(() => Number(dashboard.value?.pending_personal_task_count || 0));
const totalPending = computed(() => pendingAssignments.value + pendingPersonal.value);
const urgentItems = computed(() => filteredDueItems.value.slice(0, 2));
const summaryText = computed(() => totalPending.value ? `还有 ${totalPending.value} 项任务等待处理` : "今天暂无临近截止事项");
const recentCourses = computed(() => filteredCourses.value.slice(0, 3));

const quickLinks = [
  { label: "考试安排", detail: "查看时间与地点", icon: "PhExam", path: "/exams", tone: "violet" },
  { label: "办事大厅", detail: "校园服务入口", icon: "PhClipboardText", path: "/services", tone: "blue" },
  { label: "空教室查询", detail: "找一间安静的教室", icon: "PhSquaresFour", path: "/classrooms", tone: "green" },
  { label: "失物招领", detail: "查看待招领物品", icon: "PhMagnifyingGlass", path: "/lostfound", tone: "teal" },
  { label: "通知整理", detail: "智能归类与摘要", icon: "PhBell", path: "/notifications", tone: "amber" },
  { label: "AI 导员", detail: "问问校园里的事", icon: "PhRobot", path: "/counselor", tone: "rose" },
];

function dateText(value) {
  if (!value) return "未设置截止时间";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function relativeTime(value) {
  if (!value) return "";
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return "";
  const diff = Math.max(0, now.value - time);
  if (diff < 3600000) return `${Math.max(1, Math.floor(diff / 60000))} 分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
  if (diff < 172800000) return "昨天";
  return new Date(value).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
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

async function load(isRefresh = false) {
  if (isRefresh) refreshing.value = true;
  else loading.value = true;
  error.value = "";
  try {
    const [dashboardData, courseData, activityData, sessionData] = await Promise.all([
      getStudentDashboard(), getStudentCourses(), getStudentActivities(), getStudySessions(),
    ]);
    dashboard.value = dashboardData;
    store.setDashboardSummary(dashboardData);
    courses.value = courseData.items || [];
    activities.value = activityData.items || [];
    studySessions.value = Array.isArray(sessionData) ? sessionData : [];
  } catch (e) {
    error.value = e.response?.data?.detail || "首页数据加载失败，请检查后端服务后重试。";
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

onMounted(() => {
  load();
  clockTimer = window.setInterval(() => { now.value = Date.now(); }, 60000);
});
onUnmounted(() => window.clearInterval(clockTimer));
</script>

<template>
  <main class="student-page student-home page-enter">
    <div v-if="error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ error }}<button class="link-button" @click="load()">重试</button></div>

    <section v-if="loading" class="student-home-skeleton" aria-label="正在加载首页">
      <div class="home-skeleton-focus"></div><div class="home-skeleton-overview"></div>
      <div v-for="i in 4" :key="i" class="home-skeleton-panel"></div>
    </section>

    <template v-else>
      <section class="student-home-hero">
        <article class="student-focus-card">
          <div class="focus-card-copy">
            <span class="hero-date">{{ today }}</span>
            <h1>把今天过得更有把握</h1>
            <p>课程、截止事项和校园消息，都在一个清晰的节奏里。</p>
          </div>
          <div class="focus-summary">
            <span class="summary-icon"><UiIcon name="PhClipboardText" :size="19" /></span>
            <span class="summary-copy"><small>今日任务概览</small><strong>{{ summaryText }}</strong><em>{{ totalPending ? "保持节奏，逐项完成吧！" : "保持节奏，继续加油！" }}</em></span>
            <span class="focus-card-actions"><button class="focus-primary" @click="router.push('/study')">开始专注<UiIcon name="PhPlay" :size="15" weight="fill" /></button><button class="focus-secondary" @click="router.push('/tasks')"><UiIcon name="PhListChecks" :size="17" />查看待办</button></span>
          </div>
          <img class="focus-hero-image" src="/assets/generated/focus-hero.png" alt="蓝色勾选徽章专注插画" />
          <div class="focus-progress" :style="{ '--focus-progress': `${focusProgress * 3.6}deg` }"><div><small>今日专注时长</small><strong>{{ focusHours }}<em>h</em></strong><span>来自专注记录</span></div></div>
        </article>

        <article class="student-overview-card">
          <div class="overview-card-head"><h2>概览</h2><button @click="load(true)">{{ refreshing ? "刷新中" : "全部数据" }}<UiIcon name="PhCaretRight" :size="15" /></button></div>
          <div class="overview-stats">
            <button @click="router.push('/courses')"><span class="overview-icon violet"><UiIcon name="PhBookOpen" :size="22" /></span><span><small>我的课程</small><strong>{{ dashboard?.enrolled_course_count ?? 0 }}</strong><em>本学期课程数</em></span></button>
            <button @click="router.push('/tasks')"><span class="overview-icon green"><UiIcon name="PhCheckSquare" :size="22" /></span><span><small>待完成作业</small><strong>{{ pendingAssignments }}</strong><em>{{ dashboard?.overdue_assignment_count || 0 }} 项已逾期</em></span></button>
            <button @click="router.push('/notifications')"><span class="overview-icon amber"><UiIcon name="PhBell" :size="22" /></span><span><small>未读通知</small><strong>{{ dashboard?.unread_announcement_count ?? 0 }}</strong><em>来自课程与班级</em></span></button>
            <button @click="router.push('/study')"><span class="overview-icon blue"><UiIcon name="PhClock" :size="22" /></span><span><small>今日专注时长</small><strong>{{ focusHours }}<b>小时</b></strong><em>实时同步记录</em></span></button>
          </div>
        </article>
      </section>

      <div v-if="normalizedSearch" class="home-search-note"><UiIcon name="PhMagnifyingGlass" :size="16" />正在筛选“{{ props.searchQuery }}”，当前首页有 {{ filteredDueItems.length + filteredCourses.length + campusItems.length }} 条相关内容</div>

      <section class="student-home-columns">
        <article class="student-home-panel task-panel">
          <div class="home-panel-head"><h2><UiIcon name="PhBell" :size="19" />优先处理</h2><button @click="router.push('/tasks')">查看全部（{{ totalPending }}）</button></div>
          <div v-if="urgentItems.length" class="priority-list">
            <button v-for="(item, index) in urgentItems" :key="`${item.kind}-${item.id}`" @click="openDue(item)">
              <span v-if="index === 0" class="urgent-tag">紧急任务</span><strong>{{ item.title }}</strong><time :class="{ today: deadlineLabel(item.due).startsWith('今日') }">{{ deadlineLabel(item.due) }}</time>
            </button>
          </div>
          <div v-else class="compact-empty"><UiIcon name="PhCheckCircle" :size="26" /><strong>暂无临近截止事项</strong><span>新的课程作业和个人待办会从后端同步到这里。</span></div>
          <button class="panel-footer red" @click="router.push('/tasks')">查看全部待办与作业<UiIcon name="PhArrowRight" :size="15" /></button>
        </article>

        <article class="student-home-panel course-panel">
          <div class="home-panel-head"><h2><UiIcon name="PhSparkle" :size="19" />学习空间</h2><button @click="router.push('/courses')">全部课程<UiIcon name="PhArrowRight" :size="15" /></button></div>
          <div class="learning-intro"><span><strong>快速进入学习状态</strong><small>专注当下，收获成长</small></span><img src="/assets/mycours-icon.png" alt="书本与学位帽学习插画" /></div>
          <div class="learning-actions"><button @click="router.push('/courses')"><span class="mini-icon violet"><UiIcon name="PhBookOpen" :size="19" /></span><span><strong>我的课程</strong><small>查看课程与资料</small></span></button><button @click="router.push('/study')"><span class="mini-icon blue"><UiIcon name="PhPlay" :size="19" weight="fill" /></span><span><strong>开始专注</strong><small>沉浸式专注计时</small></span></button></div>
          <div v-if="recentCourses.length" class="recent-courses"><span>最近访问：</span><button v-for="course in recentCourses" :key="course.id" @click="router.push(`/courses/${course.id}`)">{{ course.name }}</button></div>
          <div v-else class="recent-courses"><span>暂无已加入课程</span></div>
        </article>

        <article class="student-home-panel campus-panel">
          <div class="home-panel-head"><h2><UiIcon name="PhMegaphone" :size="19" />校园动态</h2><button @click="router.push('/campus-activities')">查看更多<UiIcon name="PhArrowRight" :size="15" /></button></div>
          <div v-if="campusItems.length" class="campus-list">
            <button v-for="item in campusItems.slice(0, 3)" :key="`${item.path}-${item.id}`" @click="router.push(item.path)"><span class="home-row-icon" :class="item.tone"><UiIcon :name="item.icon" :size="18" /></span><span><strong>{{ item.title }}</strong><small>{{ item.label }}</small></span><time>{{ relativeTime(item.date) }}</time></button>
          </div>
          <div v-else class="compact-empty"><UiIcon name="PhBell" :size="26" /><strong>暂无新的校园消息</strong><span>活动和课程通知会从后端同步到这里。</span></div>
          <button class="panel-footer green" @click="router.push('/campus-activities')">查看全部活动与通知<UiIcon name="PhArrowRight" :size="15" /></button>
        </article>
      </section>

      <section class="student-quick-section">
        <div class="quick-section-head"><h2>快捷入口 <UiIcon name="PhSparkle" :size="17" weight="fill" /></h2></div>
        <div class="student-quick-grid">
          <button v-for="item in quickLinks" :key="item.path" @click="router.push(item.path)"><span class="quick-icon" :class="item.tone"><UiIcon :name="item.icon" :size="20" /></span><span><strong>{{ item.label }}</strong><small>{{ item.detail }}</small></span><UiIcon name="PhCaretRight" :size="15" /></button>
        </div>
      </section>
    </template>
  </main>
</template>

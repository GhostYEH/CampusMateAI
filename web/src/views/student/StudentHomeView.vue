<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { getStudentActivities, getStudentCourses, getStudentDashboard } from "../../services/studentApi";

const props = defineProps({ searchQuery: { type: String, default: "" } });
const router = useRouter();
const loading = ref(true);
const refreshing = ref(false);
const error = ref("");
const dashboard = ref(null);
const courses = ref([]);
const activities = ref([]);

const today = computed(() => new Intl.DateTimeFormat("zh-CN", {
  month: "long",
  day: "numeric",
  weekday: "long",
}).format(new Date()));

const dueItems = computed(() => [
  ...(dashboard.value?.due_soon_assignments || []).map((item) => ({
    ...item,
    kind: "作业",
    due: item.deadline,
    icon: "PhFileText",
    tone: "blue",
  })),
  ...(dashboard.value?.due_soon_personal_tasks || []).map((item) => ({
    ...item,
    kind: "待办",
    due: item.deadline,
    icon: "PhCheckSquare",
    tone: "warm",
  })),
].slice(0, 6));

const normalizedSearch = computed(() => props.searchQuery.trim().toLocaleLowerCase());
const matches = (item, fields) => !normalizedSearch.value || fields.some((field) => String(item[field] || "").toLocaleLowerCase().includes(normalizedSearch.value));

const filteredDueItems = computed(() => dueItems.value.filter((item) => matches(item, ["title", "kind", "course_name", "source_name"])));
const filteredCourses = computed(() => courses.value.filter((item) => matches(item, ["name", "code", "semester"])));
const announcementItems = computed(() => (dashboard.value?.recent_announcements || []).map((item) => ({
  ...item,
  label: item.course_name || item.class_name || "课程通知",
  date: item.published_at || item.created_at,
  icon: "PhMegaphone",
  tone: "green",
  path: "/notifications",
})));
const activityItems = computed(() => activities.value.map((item) => ({
  ...item,
  label: item.category || "校园活动",
  date: item.start_at || item.start_time || item.date,
  icon: "PhCalendarStar",
  tone: "green",
  path: `/campus-activities/${item.id}`,
})));
const campusItems = computed(() => {
  const source = announcementItems.value.length ? announcementItems.value : activityItems.value;
  return source.filter((item) => matches(item, ["title", "label", "category"])).slice(0, 4);
});

const completion = computed(() => {
  const pending = dashboard.value?.pending_assignment_count || 0;
  const overdue = dashboard.value?.overdue_assignment_count || 0;
  return pending ? Math.max(0, Math.round(((pending - overdue) / pending) * 100)) : 100;
});
const rhythmLabel = computed(() => dueItems.value.length > 3 ? "需要留意" : "良好");
const quickLinks = [
  { label: "考试安排", detail: "查看时间与地点", icon: "PhExam", path: "/exams", tone: "violet" },
  { label: "办事大厅", detail: "校园服务入口", icon: "PhClipboardText", path: "/services", tone: "blue" },
  { label: "空教室查询", detail: "找一间安静的教室", icon: "PhSquaresFour", path: "/classrooms", tone: "green" },
  { label: "失物招领", detail: "看看有没有线索", icon: "PhMagnifyingGlass", path: "/lostfound", tone: "teal" },
  { label: "通知整理", detail: "把长通知变清楚", icon: "PhSparkle", path: "/notifications", tone: "indigo" },
  { label: "AI 导员", detail: "问问校园里的事", icon: "PhRobot", path: "/counselor", tone: "rose" },
];

function dateText(value) {
  if (!value) return "未设置截止时间";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function openDue(item) {
  router.push(item.kind === "作业" ? `/tasks/assignment/${item.id}` : `/tasks/personal/${item.id}`);
}

function clearSearch() {
  const input = document.querySelector('[name="global-search"]');
  if (!input) return;
  input.value = "";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.focus();
}

async function load(isRefresh = false) {
  if (isRefresh) refreshing.value = true;
  else loading.value = true;
  error.value = "";
  try {
    const [dashboardData, courseData, activityData] = await Promise.all([
      getStudentDashboard(),
      getStudentCourses(),
      getStudentActivities(),
    ]);
    dashboard.value = dashboardData;
    courses.value = courseData.items || [];
    activities.value = activityData.items || [];
  } catch (e) {
    error.value = e.response?.data?.detail || "首页数据加载失败，请稍后重试。";
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

onMounted(() => load());
</script>

<template>
  <main class="student-page student-home page-enter">
    <div v-if="error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ error }}<button class="link-button" @click="load()">重试</button></div>

    <template v-if="loading">
      <section class="student-home-skeleton" aria-label="正在加载首页">
        <div class="home-skeleton-focus"></div><div class="home-skeleton-overview"></div>
        <div v-for="i in 3" :key="i" class="home-skeleton-panel"></div>
      </section>
    </template>

    <template v-else>
      <section class="student-home-hero">
        <article class="student-focus-card">
          <div class="focus-card-copy">
            <span class="student-home-kicker light">{{ today }}</span>
            <h1>把今天过得更有把握</h1>
            <p>课程、截止事项和校园消息，都在一个清晰的节奏里。</p>
            <div class="focus-summary">
              <div><span>今日学习摘要</span><strong>{{ filteredDueItems.length ? `还有 ${filteredDueItems.length} 件事值得留意` : "今天暂时没有临近截止事项" }}</strong></div>
              <div class="focus-card-actions">
                <button class="primary-button" @click="router.push('/tasks')">打开待办<UiIcon name="PhArrowRight" /></button>
                <button class="focus-text-button" @click="router.push('/study')">开始专注<UiIcon name="PhPlay" :size="16" /></button>
              </div>
            </div>
          </div>
          <div class="focus-card-mark" aria-hidden="true"><span class="mark-orbit orbit-one"></span><span class="mark-orbit orbit-two"></span><span class="mark-core"><UiIcon name="PhCheck" :size="25" weight="bold" /></span></div>
          <div class="focus-progress"><strong>{{ completion }}<small>%</small></strong><span>作业节奏</span></div>
        </article>

        <article class="student-overview-card surface">
          <div class="overview-card-head"><span>我的概览</span><button class="icon-button" aria-label="刷新概览" @click="load(true)"><UiIcon name="PhArrowClockwise" :class="{ spinning: refreshing }" :size="17" /></button></div>
          <div class="overview-stats">
            <div><span class="overview-icon blue"><UiIcon name="PhBookOpen" :size="19" /></span><small>我的课程</small><strong>{{ dashboard?.enrolled_course_count ?? 0 }}</strong><em>已加入的课程</em></div>
            <div><span class="overview-icon teal"><UiIcon name="PhCheckSquare" :size="19" /></span><small>待完成作业</small><strong>{{ dashboard?.pending_assignment_count ?? 0 }}</strong><em>{{ dashboard?.overdue_assignment_count || 0 }} 项已逾期</em></div>
            <div><span class="overview-icon amber"><UiIcon name="PhBell" :size="19" /></span><small>未读通知</small><strong>{{ dashboard?.unread_announcement_count ?? 0 }}</strong><em>来自课程班级</em></div>
          </div>
          <button class="overview-link" :disabled="refreshing" @click="load(true)"><UiIcon name="PhArrowClockwise" :class="{ spinning: refreshing }" :size="16" />{{ refreshing ? "刷新中" : "刷新数据" }}</button>
        </article>
      </section>

      <div v-if="normalizedSearch" class="home-search-note"><UiIcon name="PhMagnifyingGlass" :size="16" />正在筛选“{{ props.searchQuery }}”，找到 {{ filteredDueItems.length + filteredCourses.length + campusItems.length }} 条相关内容<button class="link-button" @click="clearSearch">清除</button></div>

      <section class="student-home-columns">
        <article class="student-home-panel task-panel">
          <div class="home-panel-head"><div><span class="student-home-kicker warm">优先处理</span><h2>紧急任务 <b v-if="filteredDueItems.length">{{ filteredDueItems.length }}</b></h2></div><button class="home-panel-link" @click="router.push('/tasks')">查看全部<UiIcon name="PhArrowRight" :size="15" /></button></div>
          <div v-if="filteredDueItems.length" class="home-list">
            <button v-for="item in filteredDueItems.slice(0, 3)" :key="`${item.kind}-${item.id}`" class="home-list-row" @click="openDue(item)">
              <span class="home-row-icon" :class="item.tone"><UiIcon :name="item.icon" :size="17" /></span><span class="home-row-main"><strong>{{ item.title }}</strong><small>{{ item.kind }} · {{ item.course_name || item.source_name || "个人安排" }}</small></span><time>{{ dateText(item.due) }}</time><UiIcon name="PhCaretRight" :size="15" />
            </button>
          </div>
          <div v-else class="student-empty home-empty"><UiIcon name="PhCheckCircle" :size="27" /><strong>{{ normalizedSearch ? "没有匹配的待办" : "近期没有待处理事项" }}</strong><span>{{ normalizedSearch ? "换个关键词试试吧。" : "新的课程作业和个人待办会出现在这里。" }}</span></div>
          <div class="home-panel-subhead"><span>近期截止</span><button class="home-panel-link" @click="router.push('/tasks')">查看日程<UiIcon name="PhArrowUpRight" :size="14" /></button></div>
          <div v-if="filteredDueItems.slice(3).length" class="home-list">
            <button v-for="item in filteredDueItems.slice(3, 6)" :key="`${item.kind}-${item.id}`" class="home-list-row" @click="openDue(item)">
              <span class="home-row-icon" :class="item.tone"><UiIcon :name="item.icon" :size="17" /></span><span class="home-row-main"><strong>{{ item.title }}</strong><small>{{ item.kind }} · {{ item.course_name || item.source_name || "个人安排" }}</small></span><time>{{ dateText(item.due) }}</time><UiIcon name="PhCaretRight" :size="15" />
            </button>
          </div>
          <div v-else-if="filteredDueItems.length" class="task-empty-note"><span class="home-row-icon blue"><UiIcon name="PhCalendarBlank" :size="17" /></span><span><strong>暂无更多临近截止事项</strong><small>新的课程作业会显示在这里</small></span></div>
        </article>

        <article class="student-home-panel course-panel">
          <div class="home-panel-head"><div><span class="student-home-kicker blue">我的学习空间</span><h2>学习入口</h2></div><button class="home-panel-link" @click="router.push('/courses')">全部课程<UiIcon name="PhArrowRight" :size="15" /></button></div>
          <div v-if="filteredCourses.length" class="home-list course-list">
            <button v-for="course in filteredCourses.slice(0, 4)" :key="course.id" class="home-list-row course-row" @click="router.push(`/courses/${course.id}`)">
              <span class="course-badge"><UiIcon name="PhBookOpen" :size="16" /></span><span class="home-row-main"><strong>{{ course.name }}</strong><small>{{ course.code || course.semester || "课程详情" }}</small></span><UiIcon name="PhCaretRight" :size="15" />
            </button>
          </div>
          <div v-else class="student-empty home-empty"><UiIcon name="PhBookOpen" :size="27" /><strong>{{ normalizedSearch ? "没有匹配的课程" : "还没有已加入的课程" }}</strong><span>{{ normalizedSearch ? "换个关键词试试吧。" : "请联系任课教师获取班级邀请码。" }}</span></div>
          <button class="inline-action" @click="router.push('/study')"><span><UiIcon name="PhChartLineUp" :size="16" />开启一段专注时间</span><UiIcon name="PhArrowUpRight" :size="15" /></button>
        </article>

        <article class="student-home-panel campus-panel">
          <div class="home-panel-head"><div><span class="student-home-kicker green">校园动态</span><h2>活动与通知</h2></div><button class="home-panel-link" @click="router.push('/campus-activities')">全部活动<UiIcon name="PhArrowRight" :size="15" /></button></div>
          <div v-if="campusItems.length" class="home-list campus-list">
            <button v-for="item in campusItems" :key="item.id" class="home-list-row" @click="router.push(item.path)">
              <span class="home-row-icon green"><UiIcon :name="item.icon" :size="17" /></span><span class="home-row-main"><strong>{{ item.title }}</strong><small>{{ item.label }}</small></span><time v-if="item.date">{{ dateText(item.date).split(" ")[0] }}</time><UiIcon name="PhCaretRight" :size="15" />
            </button>
          </div>
          <div v-else class="student-empty home-empty"><UiIcon name="PhBell" :size="27" /><strong>{{ normalizedSearch ? "没有匹配的校园消息" : "暂无新的校园消息" }}</strong><span>数据更新后会在这里显示。</span></div>
          <button class="inline-action green-action" @click="router.push('/notifications')"><span><UiIcon name="PhSparkle" :size="16" />让 AI 帮你整理通知</span><UiIcon name="PhArrowUpRight" :size="15" /></button>
        </article>
      </section>

      <section class="student-quick-section">
        <div class="quick-section-head"><div><span class="student-home-kicker">随时可用</span><h2>快捷入口</h2></div><span>把常用服务放在手边</span></div>
        <div class="student-quick-grid redesigned-quick-grid">
          <button v-for="item in quickLinks" :key="item.path" class="redesigned-quick" @click="router.push(item.path)"><span class="quick-icon" :class="item.tone"><UiIcon :name="item.icon" :size="18" /></span><span class="quick-copy"><strong>{{ item.label }}</strong><small>{{ item.detail }}</small></span><UiIcon name="PhArrowUpRight" :size="15" /></button>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useAppStore } from "../../stores/app";
import PageHeader from "../../components/teacher/PageHeader.vue";
import StatCard from "../../components/teacher/StatCard.vue";
import Skeleton from "../../components/teacher/Skeleton.vue";
import ErrorState from "../../components/teacher/ErrorState.vue";
import EmptyState from "../../components/teacher/EmptyState.vue";
import StatusTag from "../../components/teacher/StatusTag.vue";
import UiIcon from "../../components/UiIcon.vue";
import { getTeacherDashboard, getTeacherToday } from "../../services/teacher/dashboard";
import { useTeacherStore } from "../../stores/teacher";
import { extractErrorMessage } from "../../composables/useToast";
import { formatRelativeTime, formatDate, daysUntil } from "../../composables/useFormat";

const store = useAppStore();
const router = useRouter();
const teacherStore = useTeacherStore();

const loading = ref(true);
const error = ref("");
const overview = ref(null);
const today = ref(null);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [ov, td] = await Promise.all([
      getTeacherDashboard(),
      getTeacherToday().catch(() => null),
    ]);
    overview.value = ov;
    today.value = td;
    await teacherStore.loadAll().catch(() => null);
  } catch (err) {
    error.value = extractErrorMessage(err, "教学工作台加载失败");
  } finally {
    loading.value = false;
  }
}

const greeting = (() => {
  const h = new Date().getHours();
  if (h < 6) return "凌晨好";
  if (h < 12) return "上午好";
  if (h < 14) return "中午好";
  if (h < 18) return "下午好";
  return "晚上好";
})();

const quickActions = [
  { key: "announce", label: "发布通知", icon: "PhMegaphone", route: "/teacher/announcements" },
  { key: "assign", label: "布置作业", icon: "PhFileText", route: "/teacher/assignments" },
  { key: "grade", label: "查看待批改", icon: "PhPencilSimpleLine", route: "/teacher/grading" },
  { key: "class", label: "管理班级", icon: "PhUsers", route: "/teacher/courses" },
  { key: "ai", label: "AI 生成教学内容", icon: "PhRobot", route: "/teacher/ai-assistant" },
  { key: "analytics", label: "学情分析", icon: "PhChartBar", route: "/teacher/analytics" },
];

onMounted(load);
</script>

<template>
  <main class="tch-page page-enter">
    <PageHeader
      :kicker="'教师工作台'"
      :title="`${greeting}，${store.session?.name || '老师'}`"
      subtitle="先处理需要关注的提交，再安排下一次教学任务。"
    >
      <template #actions>
        <button class="primary-button" @click="router.push('/teacher/assignments')">
          <UiIcon name="PhPlus" :size="18" />布置作业
        </button>
      </template>
    </PageHeader>

    <Skeleton v-if="loading" :rows="4" layout="grid" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />
    <template v-else-if="overview">
      <section class="tch-stat-strip">
        <StatCard label="本学期课程" :value="overview.course_count" icon="PhBookOpen" tone="primary" clickable @click="router.push('/teacher/courses')" />
        <StatCard label="教学班级" :value="overview.class_count" :hint="`${overview.student_count} 名学生`" icon="PhUsers" clickable @click="router.push('/teacher/courses')" />
        <StatCard label="进行中作业" :value="overview.active_assignment_count" :hint="`${overview.pending_submission_count} 份待批改`" icon="PhFileText" tone="info" clickable @click="router.push('/teacher/assignments')" />
        <StatCard label="逾期待跟进" :value="overview.overdue_student_count" hint="建议优先提醒" icon="PhClock" tone="warning" clickable @click="router.push('/teacher/grading')" />
        <StatCard label="未读通知" :value="overview.unread_announcement_count" icon="PhBell" clickable @click="router.push('/teacher/announcements')" />
      </section>

      <div class="tch-dashboard-grid">
        <section class="tch-panel">
          <div class="tch-panel-head">
            <h2>最近发布</h2>
            <button class="tch-link" @click="router.push('/teacher/assignments')">全部作业<UiIcon name="PhCaretRight" :size="14" /></button>
          </div>
          <div v-if="overview.recent_assignments?.length" class="tch-assignment-list">
            <button
              v-for="item in overview.recent_assignments"
              :key="item.assignment_id || item.id"
              class="tch-assignment-line"
              @click="router.push(`/teacher/assignments/${item.assignment_id || item.id}`)"
            >
              <span class="tch-line-date">{{ formatDate(item.deadline) }}</span>
              <span class="tch-line-main">
                <strong>{{ item.title }}</strong>
                <small>{{ item.course_name }} / {{ item.class_name }}</small>
              </span>
              <StatusTag :status="item.status" type="assignment" />
              <UiIcon name="PhCaretRight" :size="16" />
            </button>
          </div>
          <EmptyState v-else icon="PhFileText" title="还没有教学任务" description="发布第一项作业后会显示在这里。" />
        </section>

        <aside class="tch-today-panel">
          <div class="tch-today-head">
            <UiIcon name="PhFlag" :size="22" weight="fill" />
            <h2>今日待处理</h2>
          </div>
          <div v-if="today" class="tch-today-list">
            <button class="tch-today-item" @click="router.push('/teacher/grading')">
              <strong>{{ today.pending_grading_count }}</strong>
              <span>待批改提交</span>
            </button>
            <button class="tch-today-item" @click="router.push('/teacher/assignments')">
              <strong>{{ today.due_soon_assignment_count }}</strong>
              <span>临近截止作业</span>
            </button>
            <button class="tch-today-item" @click="router.push('/teacher/grading')">
              <strong class="warm">{{ today.unsubmitted_student_count }}</strong>
              <span>未提交学生</span>
            </button>
            <button class="tch-today-item" @click="router.push('/teacher/announcements')">
              <strong>{{ today.unread_announcement_count }}</strong>
              <span>通知未读</span>
            </button>
            <div class="tch-today-item static">
              <strong>{{ today.draft_assignment_count }}</strong>
              <span>作业草稿</span>
            </div>
            <div class="tch-today-item static">
              <strong>{{ today.draft_announcement_count }}</strong>
              <span>通知草稿</span>
            </div>
          </div>
          <div v-if="today?.due_soon_assignments?.length" class="tch-today-soon">
            <h3>临近截止</h3>
            <button
              v-for="a in today.due_soon_assignments"
              :key="a.assignment_id"
              class="tch-soon-line"
              @click="router.push(`/teacher/assignments/${a.assignment_id}`)"
            >
              <span><strong>{{ a.title }}</strong><small>{{ a.course_name }} / {{ a.class_name }}</small></span>
              <em>{{ formatDate(a.deadline) }}</em>
            </button>
          </div>
        </aside>
      </div>

      <section class="tch-quick-actions">
        <h2>快捷操作</h2>
        <div class="tch-quick-grid">
          <button
            v-for="action in quickActions"
            :key="action.key"
            class="tch-quick-card"
            @click="router.push(action.route)"
          >
            <span class="tch-quick-icon"><UiIcon :name="action.icon" :size="22" /></span>
            <span>{{ action.label }}</span>
          </button>
        </div>
      </section>
    </template>
  </main>
</template>
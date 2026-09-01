<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import TaskMetricCard from "../../components/tasks/TaskMetricCard.vue";
import TaskFocusSection from "../../components/tasks/TaskFocusSection.vue";
import TaskToolbar from "../../components/tasks/TaskToolbar.vue";
import TaskList from "../../components/tasks/TaskList.vue";
import TaskComposer from "../../components/tasks/TaskComposer.vue";
import {
  completePersonalTask,
  createPersonalTask,
  deletePersonalTask,
  getPersonalTasks,
  getStudentAssignments,
  updatePersonalTask,
} from "../../services/studentApi";
import {
  buildTaskModel,
  filterAndSortTasks,
  getTaskMetrics,
  groupTasks,
} from "../../features/tasks/taskModel.js";

const router = useRouter();
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const toast = ref("");
const query = ref("");
const kind = ref("all");
const status = ref("all");
const sort = ref("deadline");
const assignments = ref([]);
const personal = ref([]);
const composerOpen = ref(false);
const editingTask = ref(null);
const now = ref(new Date());
const animated = reactive({ today: 0, upcoming: 0, overdue: 0, completed: 0, completionRate: 0 });
let clockTimer;
let countTimer;
let toastTimer;

const allTasks = computed(() => buildTaskModel(assignments.value, personal.value));
const metrics = computed(() => getTaskMetrics(allTasks.value, now.value));
const visibleTasks = computed(() => filterAndSortTasks(allTasks.value, { query: query.value, kind: kind.value, status: status.value, sort: sort.value }, now.value));
const groups = computed(() => groupTasks(visibleTasks.value, now.value));
const completionCopy = computed(() => `${metrics.value.completed} / ${metrics.value.total || 0} 项已完成`);

const metricCards = computed(() => [
  { key: "today", label: "今日待办", value: metrics.value.today, note: metrics.value.overdue ? `${metrics.value.overdue} 项已逾期` : "今天安排", change: `${metrics.value.pending} 项待处理`, progress: metrics.value.total ? Math.max(0, Math.round(((metrics.value.total - metrics.value.overdue) / metrics.value.total) * 100)) : 0, icon: "PhClipboardText", tone: "violet", points: sparklinePoints(metrics.value.today, 0) },
  { key: "upcoming", label: "即将截止", value: metrics.value.upcoming, note: "未来 48 小时", change: metrics.value.upcoming ? "请提前安排" : "时间充裕", progress: metrics.value.total ? Math.round((metrics.value.upcoming / metrics.value.total) * 100) : 0, icon: "PhCalendarBlank", tone: "amber", points: sparklinePoints(metrics.value.upcoming, 1) },
  { key: "overdue", label: "已逾期", value: metrics.value.overdue, note: metrics.value.overdue ? "需要立即处理" : "没有逾期", change: metrics.value.overdue ? "尽快清理" : "状态良好", progress: metrics.value.overdue ? 0 : 100, icon: "PhWarningCircle", tone: "rose", points: sparklinePoints(metrics.value.overdue, 2) },
  { key: "completed", label: "已完成", value: metrics.value.completed, note: "全部任务", change: `${metrics.value.completionRate}% 完成率`, progress: metrics.value.completionRate, icon: "PhCheckCircle", tone: "mint", points: sparklinePoints(metrics.value.completed, 3) },
]);

const weekBars = computed(() => {
  const days = [];
  for (let offset = 6; offset >= 0; offset -= 1) {
    const day = new Date(now.value);
    day.setHours(0, 0, 0, 0);
    day.setDate(day.getDate() - offset);
    const count = allTasks.value.filter((task) => {
      const completedAt = task.completed_at ? new Date(task.completed_at) : null;
      return completedAt && !Number.isNaN(completedAt.valueOf()) && completedAt.toDateString() === day.toDateString();
    }).length;
    days.push({ label: ["日", "一", "二", "三", "四", "五", "六"][day.getDay()], count });
  }
  const max = Math.max(...days.map((item) => item.count), 1);
  return days.map((item) => ({ ...item, height: Math.max(item.count ? 20 : 7, Math.round((item.count / max) * 100)) }));
});

function sparklinePoints(value, seed) {
  const base = Math.min(27, 25 - Math.min(value, 12));
  const wave = [base, base - 5 - seed, base + 2, base - 12 + seed, base - 2, base - 9, base + 1, base - 7, base - 3, base - 13, base - 6];
  return wave.map((point, index) => `${index * 12 + 2},${Math.max(4, Math.min(29, point))}`).join(" ");
}

function flash(message) {
  toast.value = message;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => { toast.value = ""; }, 2200);
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [assignmentData, personalData] = await Promise.all([getStudentAssignments(), getPersonalTasks()]);
    assignments.value = assignmentData.items || [];
    personal.value = personalData.items || [];
  } catch (e) {
    error.value = e.response?.data?.detail || "待办数据加载失败。";
  } finally {
    loading.value = false;
  }
}

function openTask(task) { router.push(`/tasks/${task.kind}/${task.sourceId}`); }

async function toggleTask(task) {
  if (task.kind !== "personal") { openTask(task); return; }
  const current = personal.value.find((item) => item.id === task.sourceId);
  if (!current) return;
  const previousStatus = current.status;
  current.status = task.done ? "pending" : "completed";
  try {
    const updated = await completePersonalTask(task.sourceId, !task.done);
    const index = personal.value.findIndex((item) => item.id === task.sourceId);
    if (index >= 0) personal.value[index] = updated;
    flash(task.done ? "已恢复到待办" : "任务已完成，做得不错");
  } catch (e) {
    current.status = previousStatus;
    error.value = e.response?.data?.detail || "更新待办失败。";
  }
}

function startCreate() { editingTask.value = null; composerOpen.value = true; }
function startEdit(task) {
  if (task.kind !== "personal") { openTask(task); return; }
  editingTask.value = task;
  composerOpen.value = true;
}

async function saveTask(payload) {
  const wasEditing = Boolean(editingTask.value);
  saving.value = true;
  try {
    if (wasEditing) await updatePersonalTask(editingTask.value.sourceId, payload);
    else await createPersonalTask({ ...payload, source_name: "个人安排" });
    composerOpen.value = false;
    editingTask.value = null;
    await load();
    flash(wasEditing ? "待办已更新" : "待办已加入清单");
  } catch (e) {
    error.value = e.response?.data?.detail || "保存待办失败。";
  } finally {
    saving.value = false;
  }
}

async function removeTask(task) {
  if (task.kind !== "personal") { openTask(task); return; }
  if (!window.confirm("确认删除这条个人待办吗？")) return;
  try {
    await deletePersonalTask(task.sourceId);
    personal.value = personal.value.filter((item) => item.id !== task.sourceId);
    flash("待办已删除");
  } catch (e) {
    error.value = e.response?.data?.detail || "删除待办失败，请重试。";
  }
}

async function postponeTask(task) {
  if (task.kind !== "personal") { openTask(task); return; }
  const deadline = task.deadline ? new Date(task.deadline) : new Date(now.value);
  deadline.setDate(deadline.getDate() + 1);
  try {
    const updated = await updatePersonalTask(task.sourceId, { deadline: deadline.toISOString() });
    const index = personal.value.findIndex((item) => item.id === task.sourceId);
    if (index >= 0) personal.value[index] = updated;
    flash("已延期一天");
  } catch (e) {
    error.value = e.response?.data?.detail || "延期失败，请重试。";
  }
}

function handleAction({ action, task }) {
  if (action === "view") openTask(task);
  if (action === "edit") startEdit(task);
  if (action === "postpone") postponeTask(task);
  if (action === "delete") removeTask(task);
}

function reorderTasks({ sourceId, targetId }) {
  const source = allTasks.value.find((task) => task.id === sourceId);
  const target = allTasks.value.find((task) => task.id === targetId);
  if (source && target) flash("已调整当前列表顺序（仅当前视图）");
}

watch(metrics, (next) => {
  window.clearInterval(countTimer);
  const start = { ...animated };
  const target = { today: next.today, upcoming: next.upcoming, overdue: next.overdue, completed: next.completed, completionRate: next.completionRate };
  const startedAt = performance.now();
  countTimer = window.setInterval(() => {
    const progress = Math.min(1, (performance.now() - startedAt) / 480);
    Object.keys(animated).forEach((key) => { animated[key] = Math.round(start[key] + (target[key] - start[key]) * progress); });
    if (progress >= 1) window.clearInterval(countTimer);
  }, 16);
}, { immediate: true });

onMounted(() => {
  clockTimer = window.setInterval(() => { now.value = new Date(); }, 1000);
  load();
});
onUnmounted(() => { window.clearInterval(clockTimer); window.clearInterval(countTimer); window.clearTimeout(toastTimer); });
</script>

<template>
  <main class="student-page task-dashboard">
    <div v-if="toast" class="task-toast" role="status"><UiIcon name="PhCheckCircle" :size="15" />{{ toast }}</div>
    <header class="task-dashboard-head">
      <div><span class="task-section-eyebrow">STUDY PLANNER</span><h1>待办与作业</h1><p>把重要的事先完成，保持高效学习节奏。</p></div>
      <button class="task-primary-button task-create-button" type="button" @click="startCreate"><UiIcon name="PhPlus" :size="17" weight="bold" />新建待办</button>
    </header>

    <div v-if="error" class="student-alert error"><UiIcon name="PhWarningCircle" :size="16" />{{ error }}<button class="link-button" type="button" @click="load">重试</button></div>

    <section class="task-overview-grid" aria-label="任务概览">
      <template v-if="!loading"><TaskMetricCard v-for="card in metricCards" :key="card.key" v-bind="card" :value="animated[card.key]" :progress="card.key === 'completed' ? animated.completionRate : card.progress" /></template>
      <div v-else v-for="index in 4" :key="index" class="task-metric-skeleton"></div>
      <article class="task-week-card"><div class="task-week-head"><span><small>本周完成率</small><strong>{{ animated.completionRate }}%</strong></span><em><UiIcon name="PhChartLineUp" :size="12" />{{ completionCopy }}</em></div><div class="task-week-chart" aria-label="近七日完成趋势"><span v-for="bar in weekBars" :key="bar.label" class="task-week-bar"><i :style="{ height: `${bar.height}%` }"></i><small>{{ bar.label }}</small></span></div></article>
    </section>

    <TaskFocusSection :tasks="allTasks" :now="now" @open="openTask" />
    <TaskToolbar v-model:query="query" v-model:kind="kind" v-model:status="status" v-model:sort="sort" @refresh="load" />
    <TaskList :groups="groups" :now="now" @toggle="toggleTask" @open="openTask" @action="handleAction" @reorder="reorderTasks" />
    <TaskComposer :open="composerOpen" :task="editingTask" :saving="saving" @close="composerOpen = false" @save="saveTask" />
  </main>
</template>

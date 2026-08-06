<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { completePersonalTask, createPersonalTask, deletePersonalTask, getPersonalTasks, getStudentAssignments } from "../../services/studentApi";

const router = useRouter();
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const query = ref("");
const filter = ref("all");
const tab = ref("all");
const assignments = ref([]);
const personal = ref([]);
const showForm = ref(false);
const form = ref({ title: "", deadline: "", priority: "medium", description: "", reminder_minutes: 30 });

const items = computed(() => {
  return [
    ...assignments.value.map((x) => ({
      ...x,
      kind: "assignment",
      done: ["submitted", "graded"].includes(x.submission_status),
      statusLabel: x.submission_status === "graded" ? "已评分" : x.submission_status === "submitted" ? "已提交" : x.submission_status === "overdue" ? "已逾期" : "待完成"
    })),
    ...personal.value.map((x) => ({
      ...x,
      kind: "personal",
      done: x.status === "completed",
      statusLabel: x.status === "completed" ? "已完成" : "待完成"
    }))
  ]
    .filter((x) => (tab.value === "all" || x.kind === tab.value) && (filter.value === "all" || (filter.value === "done" ? x.done : !x.done)) && `${x.title} ${x.course_name || x.source_name || ""}`.toLowerCase().includes(query.value.trim().toLowerCase()))
    .sort((a, b) => String(a.deadline || "9999").localeCompare(String(b.deadline || "9999")));
});

const pendingCount = computed(() => items.value.filter(x => !x.done).length);
const doneCount = computed(() => items.value.filter(x => x.done).length);
const upcomingCount = computed(() => {
  const now = Date.now();
  const twoDays = 2 * 24 * 60 * 60 * 1000;
  return items.value.filter(x => {
    if (x.done || !x.deadline) return false;
    const d = new Date(x.deadline).getTime();
    return d - now <= twoDays && d >= now;
  }).length;
});
const personalCount = computed(() => personal.value.length);

function taskIcon(item) {
  if (item.kind === "personal") return "PhListMagnifyingGlass";
  const title = item.title || "";
  if (title.includes("实验") || title.includes("代码") || title.includes("程序")) return "PhCode";
  if (title.includes("听力") || title.includes("口语") || title.includes("英语")) return "PhHeadphones";
  if (title.includes("习题") || title.includes("练习") || title.includes("章节")) return "PhBookOpen";
  if (title.includes("项目") || title.includes("计算器")) return "PhSquaresFour";
  if (title.includes("整理")) return "PhNotebook";
  return "PhClipboardText";
}

function taskTone(item) {
  if (item.kind === "personal") return "indigo";
  const title = item.title || "";
  const code = item.course_code || "";
  if (code.includes("CS") || title.includes("实验") || title.includes("程序") || title.includes("代码") || title.includes("项目")) return "violet";
  if (code.includes("ENG") || title.includes("听力") || title.includes("口语")) return "blue";
  if (code.includes("MATH") || title.includes("习题") || title.includes("章节") || title.includes("数学")) return "green";
  return "violet";
}

function dateText(value) {
  if (!value) return "未设置截止时间";
  const d = new Date(value);
  if (Number.isNaN(d.valueOf())) return value;
  return d.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [a, p] = await Promise.all([getStudentAssignments(), getPersonalTasks()]);
    assignments.value = a.items || [];
    personal.value = p.items || [];
  } catch (e) {
    error.value = e.response?.data?.detail || "待办数据加载失败。";
  } finally {
    loading.value = false;
  }
}

async function toggle(item) {
  if (item.kind !== "personal") {
    router.push(`/tasks/assignment/${item.id}`);
    return;
  }
  try {
    item.done = !item.done;
    const updated = await completePersonalTask(item.id, item.done);
    const index = personal.value.findIndex((x) => x.id === item.id);
    if (index >= 0) personal.value[index] = updated;
  } catch (e) {
    error.value = e.response?.data?.detail || "更新待办失败。";
  }
}

async function save() {
  if (!form.value.title.trim() || saving.value) return;
  saving.value = true;
  try {
    await createPersonalTask({ ...form.value, deadline: form.value.deadline ? new Date(form.value.deadline).toISOString() : null });
    showForm.value = false;
    form.value = { title: "", deadline: "", priority: "medium", description: "", reminder_minutes: 30 };
    await load();
  } catch (e) {
    error.value = e.response?.data?.detail || "保存待办失败。";
  } finally {
    saving.value = false;
  }
}

async function remove(item) {
  if (item.kind !== "personal" || !window.confirm("确认删除这条个人待办吗？")) return;
  try {
    await deletePersonalTask(item.id);
    personal.value = personal.value.filter((x) => x.id !== item.id);
  } catch {
    error.value = "删除待办失败，请重试。";
  }
}

onMounted(() => { load(); });
</script>

<template>
  <main class="student-page tasks-redesign page-enter">
    <!-- Hero Section -->
    <section class="tasks-hero">
      <div class="tasks-hero-content">
        <span class="hero-eyebrow">TASKS / 任务节奏</span>
        <div class="student-title-line hero-title">
          <h1>待办与作业</h1>
          <UiIcon name="PhSparkle" class="heading-sparkle" :size="26" />
        </div>
        <p class="hero-desc">课程作业和你自己记录的事项分开管理，完成状态直接同步后端。</p>

        <div class="hero-stats">
          <div class="hero-stat">
            <span class="stat-icon violet"><UiIcon name="PhClipboardText" :size="18" /></span>
            <div class="stat-info">
              <strong>{{ pendingCount }}</strong>
              <small>待完成事项</small>
            </div>
          </div>
          <div class="hero-stat">
            <span class="stat-icon green"><UiIcon name="PhCheckCircle" :size="18" /></span>
            <div class="stat-info">
              <strong>{{ doneCount }}</strong>
              <small>已完成事项</small>
            </div>
          </div>
          <div class="hero-stat">
            <span class="stat-icon amber"><UiIcon name="PhCalendarCheck" :size="18" /></span>
            <div class="stat-info">
              <strong>{{ upcomingCount }}</strong>
              <small>即将到期</small>
            </div>
          </div>
          <div class="hero-stat">
            <span class="stat-icon blue"><UiIcon name="PhUser" :size="18" /></span>
            <div class="stat-info">
              <strong>{{ personalCount }}</strong>
              <small>个人待办</small>
            </div>
          </div>
        </div>
      </div>

      <div class="tasks-hero-art">
        <div class="hero-illustration tasks-illustration">
          <img src="/assets/campusmate-tasks-hero.jpg" alt="待办与作业插图" class="hero-illust-img" />
        </div>
      </div>
    </section>

    <div v-if="error" class="student-alert error">
      <UiIcon name="PhWarningCircle" />{{ error }}
      <button class="link-button" @click="load">重试</button>
    </div>

    <!-- Toolbar -->
    <section class="student-toolbar tasks-toolbar surface">
      <div class="search-field">
        <UiIcon name="PhMagnifyingGlass" />
        <input v-model="query" placeholder="搜索作业或待办" />
      </div>
      <div class="segmented">
        <button v-for="item in [{key:'all',label:'全部'},{key:'assignment',label:'课程作业'},{key:'personal',label:'个人待办'}]" :key="item.key" :class="{active:tab===item.key}" @click="tab=item.key">{{ item.label }}</button>
      </div>
      <select v-model="filter">
        <option value="all">全部状态</option>
        <option value="pending">未完成</option>
        <option value="done">已完成</option>
      </select>
      <div class="toolbar-actions">
        <button class="refresh-btn" @click="load">
          <UiIcon name="PhArrowClockwise" :size="16" />
          刷新
        </button>
        <button class="new-task-btn" @click="showForm=true">
          <UiIcon name="PhPlus" :size="16" />
          新建待办
        </button>
      </div>
    </section>

    <!-- Task List Panel -->
    <section v-if="loading" class="student-panel surface">
      <div v-for="i in 5" :key="i" class="list-skeleton"></div>
    </section>

    <section v-else class="student-panel surface tasks-panel">
      <div class="student-panel-head tasks-panel-head">
        <div>
          <h2>我的清单</h2>
        </div>
      </div>

      <div v-if="items.length" class="new-task-list">
        <div v-for="item in items" :key="`${item.kind}-${item.id}`" class="new-task-row" :class="{done:item.done}">
          <button class="task-check" @click="toggle(item)" :aria-label="item.done ? '恢复任务' : '完成任务'">
            <UiIcon v-if="!item.done" name="PhCircle" weight="regular" :size="22" />
            <span v-else class="check-filled"><UiIcon name="PhCheck" weight="bold" :size="14" /></span>
          </button>

          <span class="task-icon-wrap" :class="`ti-${taskTone(item)}`">
            <UiIcon :name="taskIcon(item)" :size="18" />
          </span>

          <button class="task-main-btn" @click="router.push(item.kind === 'assignment' ? `/tasks/assignment/${item.id}` : `/tasks/personal/${item.id}`)">
            <div class="task-text">
              <strong>{{ item.title }}</strong>
              <small>
                {{ item.kind === 'assignment' ? `${item.course_name || '课程作业'} · ${item.class_name || ''}` : `${item.source_name || '个人安排'} · ${item.reminder_minutes == null ? '提醒未设置' : `提醒 ${item.reminder_minutes} 分钟前`}` }}
              </small>
            </div>
            <time>{{ dateText(item.deadline) }}</time>
          </button>

          <span class="status-pill" :class="item.done ? 'green' : item.submission_status === 'overdue' ? 'red' : 'blue'">
            {{ item.statusLabel }}
          </span>

          <button v-if="item.kind==='personal'" class="delete-btn" @click="remove(item)" aria-label="删除待办">
            <UiIcon name="PhTrash" :size="16" />
          </button>
        </div>
      </div>

      <div v-else class="student-empty large">
        <UiIcon name="PhCheckCircle" :size="40" />
        <strong>当前筛选下没有事项</strong>
        <span>可以新建一个小目标，或等待课程作业发布。</span>
      </div>
    </section>

    <!-- New Task Modal -->
    <div v-if="showForm" class="student-modal-backdrop" @click.self="showForm=false">
      <form class="student-modal" @submit.prevent="save">
        <div class="student-modal-head">
          <div>
            <span class="eyebrow">PERSONAL TASK</span>
            <h2>新建个人待办</h2>
          </div>
          <button type="button" class="icon-button" @click="showForm=false">
            <UiIcon name="PhX" />
          </button>
        </div>
        <label class="student-field">
          事项名称
          <input v-model="form.title" required placeholder="例如：准备奖学金申请材料" />
        </label>
        <div class="student-form-grid">
          <label class="student-field">
            截止时间
            <input v-model="form.deadline" type="datetime-local" />
          </label>
          <label class="student-field">
            优先级
            <select v-model="form.priority">
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
            </select>
          </label>
        </div>
        <label class="student-field">
          提醒
          <select v-model.number="form.reminder_minutes">
            <option :value="0">截止时提醒</option>
            <option :value="30">提前 30 分钟</option>
            <option :value="1440">提前 1 天</option>
          </select>
        </label>
        <label class="student-field">
          备注
          <textarea v-model="form.description" rows="4" placeholder="补充材料、地点或下一步"></textarea>
        </label>
        <div class="student-modal-actions">
          <button type="button" class="secondary-button" @click="showForm=false">取消</button>
          <button class="primary-button" :disabled="saving || !form.title.trim()">
            {{ saving ? '保存中…' : '保存待办' }}
          </button>
        </div>
      </form>
    </div>
  </main>
</template>

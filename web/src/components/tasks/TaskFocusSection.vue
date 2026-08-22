<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import UiIcon from "../UiIcon.vue";
import { getRemainingSeconds, getTaskState } from "../../features/tasks/taskModel.js";

const props = defineProps({
  tasks: { type: Array, default: () => [] },
  now: { type: Date, required: true },
});
const emit = defineEmits(["open"]);
const clock = ref(Date.now());
let timer;

const pending = computed(() => props.tasks.filter((task) => !task.done));
const today = computed(() => pending.value.filter((task) => getTaskState(task, new Date(clock.value)) === "today").slice(0, 2));
const tomorrow = computed(() => pending.value.filter((task) => {
  const due = task.deadline ? new Date(task.deadline) : null;
  const current = new Date(clock.value);
  if (!due || Number.isNaN(due.valueOf())) return false;
  const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate());
  const tomorrowDay = new Date(current.getFullYear(), current.getMonth(), current.getDate() + 1);
  return dueDay.valueOf() === tomorrowDay.valueOf();
}).slice(0, 2));
const overdue = computed(() => pending.value.filter((task) => getTaskState(task, new Date(clock.value)) === "overdue").slice(0, 2));
const highPriority = computed(() => pending.value.filter((task) => task.priority === "high").slice(0, 2));
const urgentTask = computed(() => [...overdue.value, ...today.value].sort((a, b) => new Date(a.deadline || 0) - new Date(b.deadline || 0))[0] || pending.value[0]);

function remainingLabel(task) {
  const seconds = getRemainingSeconds(task?.deadline, new Date(clock.value));
  if (seconds == null) return "暂未设置截止时间";
  if (seconds <= 0) return "已超过截止时间";
  const hours = Math.floor(seconds / 3600).toString().padStart(2, "0");
  const minutes = Math.floor((seconds % 3600) / 60).toString().padStart(2, "0");
  const rest = (seconds % 60).toString().padStart(2, "0");
  return `距离截止还有 ${hours}:${minutes}:${rest}`;
}

function dateLabel(task) {
  if (!task?.deadline) return "未设置截止时间";
  const due = new Date(task.deadline);
  return Number.isNaN(due.valueOf()) ? task.deadline : due.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

onMounted(() => { timer = window.setInterval(() => { clock.value = Date.now(); }, 1000); });
onUnmounted(() => window.clearInterval(timer));
</script>

<template>
  <section class="task-focus-section" aria-labelledby="task-focus-title">
    <div class="task-section-title-row">
      <div><span class="task-section-eyebrow">FOCUS BOARD</span><h2 id="task-focus-title">今日重点</h2></div>
      <span class="task-focus-date">{{ now.toLocaleDateString("zh-CN", { month: "long", day: "numeric", weekday: "short" }) }}</span>
    </div>

    <div v-if="urgentTask" class="task-urgent-bar" :class="{ overdue: getTaskState(urgentTask, new Date(clock)) === 'overdue' }">
      <span class="task-urgent-pulse"><UiIcon name="PhWarning" :size="15" weight="fill" /></span>
      <span class="task-urgent-copy"><strong>{{ urgentTask.title }}</strong><small>{{ remainingLabel(urgentTask) }}</small></span>
      <button type="button" @click="emit('open', urgentTask)">去处理 <UiIcon name="PhArrowUpRight" :size="14" /></button>
    </div>

    <div class="task-focus-grid">
      <article v-for="card in [
        { key: 'today', title: '今天截止', icon: 'PhTimer', tone: 'red', tasks: today },
        { key: 'tomorrow', title: '明天截止', icon: 'PhCalendarBlank', tone: 'amber', tasks: tomorrow },
        { key: 'overdue', title: '已逾期', icon: 'PhWarningCircle', tone: 'rose', tasks: overdue },
        { key: 'priority', title: '高优先级', icon: 'PhFlag', tone: 'violet', tasks: highPriority },
      ]" :key="card.key" class="task-focus-card" :class="`tone-${card.tone}`">
        <header><span><UiIcon :name="card.icon" :size="15" />{{ card.title }}</span><b>{{ card.tasks.length }}</b></header>
        <button v-for="task in card.tasks" :key="task.id" type="button" class="task-focus-item" @click="emit('open', task)">
          <span>{{ task.title }}</span><time>{{ dateLabel(task) }}</time>
        </button>
        <p v-if="!card.tasks.length" class="task-focus-empty">暂无事项</p>
      </article>
    </div>
  </section>
</template>

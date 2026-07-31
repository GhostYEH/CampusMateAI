<script setup>
import { computed, ref } from "vue";
import { useAppStore } from "../stores/app";
import UiIcon from "../components/UiIcon.vue";

const store = useAppStore();
const activeFilter = ref("pending");
const showComposer = ref(false);
const selectedTask = ref(null);
const detailTask = ref(null);
const editingTask = ref(null);
const toast = ref("");
const newTask = ref("");
const deadline = ref("");
const course = ref("课程作业");
const description = ref("");
const priority = ref("normal");
const reminder = ref(true);

const pendingTasks = computed(() => store.tasks.filter((task) => !task.done));
const completedTasks = computed(() => store.tasks.filter((task) => task.done));
const completionRate = computed(() => store.tasks.length ? Math.round((completedTasks.value.length / store.tasks.length) * 100) : 0);
const filters = computed(() => [
  { id: "pending", label: "待完成", count: pendingTasks.value.length },
  { id: "done", label: "已完成", count: completedTasks.value.length },
  { id: "all", label: "全部", count: store.tasks.length },
  { id: "课程作业", label: "课程作业", count: store.tasks.filter((task) => task.course === "课程作业").length },
  { id: "活动报名", label: "活动报名", count: store.tasks.filter((task) => task.course === "活动报名").length },
]);
const filteredTasks = computed(() => store.tasks.filter((task) => {
  if (activeFilter.value === "pending") return !task.done;
  if (activeFilter.value === "done") return task.done;
  if (["课程作业", "活动报名"].includes(activeFilter.value)) return task.course === activeFilter.value;
  return true;
}));
const todayTasks = computed(() => pendingTasks.value.filter((task) => task.due.includes("今天")));
const focusTask = computed(() => todayTasks.value[0] || pendingTasks.value[0]);
const listTitle = computed(() => activeFilter.value === "done" ? "已完成" : activeFilter.value === "all" ? "全部任务" : activeFilter.value === "课程作业" ? "课程作业" : activeFilter.value === "活动报名" ? "活动报名" : "待完成");
const planCards = computed(() => [
  { label: "课程作业", count: store.tasks.filter((task) => task.course === "课程作业").length, note: `${store.tasks.filter((task) => task.course === "课程作业" && !task.done).length} 项未完成`, icon: "PhBookOpen", tone: "lilac" },
  { label: "活动报名", count: store.tasks.filter((task) => task.course === "活动报名").length, note: "本周安排", icon: "PhCalendarStar", tone: "mint" },
  { label: "已完成", count: completedTasks.value.length, note: "本周已完成", icon: "PhCheckCircle", tone: "peach" },
]);

function flash(message) {
  toast.value = message;
  window.setTimeout(() => { toast.value = ""; }, 2200);
}
function resetComposer(task = null) {
  editingTask.value = task;
  newTask.value = task?.title || "";
  deadline.value = "";
  course.value = task?.course || "课程作业";
  description.value = task?.description || "";
  priority.value = task?.priority || (task?.due?.includes("今天") ? "high" : "normal");
  reminder.value = task?.reminder ?? true;
}
function openComposer(task = null) {
  resetComposer(task);
  detailTask.value = null;
  showComposer.value = true;
}
function closeComposer() {
  showComposer.value = false;
  editingTask.value = null;
}
function addTask() {
  if (!newTask.value.trim()) return;
  const due = deadline.value ? new Date(deadline.value).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : editingTask.value?.due || "待设置";
  const payload = { course: course.value, description: description.value.trim(), priority: priority.value, reminder: reminder.value };
  if (editingTask.value) {
    store.updateTask(editingTask.value.id, { title: newTask.value.trim(), due, ...payload });
    closeComposer();
    flash("任务详情已更新");
  } else {
    store.addTask(newTask.value.trim(), due, course.value, { description: payload.description, priority: payload.priority, reminder: payload.reminder });
    closeComposer();
    flash("任务已加入待办");
  }
}
function toggleTask(task) {
  store.toggleTask(task.id);
  flash(task.done ? "任务已完成，做得不错" : "已恢复到待办");
}
function openDetail(task) {
  selectedTask.value = task;
  detailTask.value = task;
}
function completeDetail() {
  if (!detailTask.value) return;
  toggleTask(detailTask.value);
  detailTask.value = store.tasks.find((task) => task.id === detailTask.value.id) || null;
}
function removeTask(task) {
  store.deleteTask(task.id);
  selectedTask.value = null;
  detailTask.value = null;
  flash("任务已移除");
}
</script>

<template>
  <main class="tasks-page page-enter">
    <div v-if="toast" class="tasks-toast" role="status"><UiIcon name="PhCheckCircle" weight="fill" />{{ toast }}</div>
    <header class="tasks-heading">
      <div><span class="tasks-kicker"><i></i>今日安排</span><h1>待办</h1><p>今天先完成最重要的一小步</p></div>
      <span class="tasks-mode"><i></i>Mock 模式</span>
    </header>

    <section class="task-progress-card" aria-label="今日进度">
      <div class="task-progress-copy"><span class="micro-label">今日进度</span><strong>还有 {{ pendingTasks.length }} 项</strong><p>专注当下，不必一次完成所有事情</p><span class="task-tip"><UiIcon name="PhSparkle" size="13" />优先处理最靠近截止时间的任务</span></div>
      <div class="progress-ring" :style="{ '--progress': `${completionRate * 3.6}deg` }"><div><strong>{{ completionRate }}%</strong><span>已完成</span></div></div>
      <div class="task-progress-metrics"><div><UiIcon name="PhClockCounterClockwise" /><span><b>{{ todayTasks.length || pendingTasks.length }}</b><small>今日待办</small></span></div><div><UiIcon name="PhCheckCircle" /><span><b>{{ completedTasks.length }}</b><small>已完成</small></span></div><div><UiIcon name="PhCalendarBlank" /><span><b>{{ Math.max(pendingTasks.length - todayTasks.length, 0) }}</b><small>学习计划</small></span></div></div>
    </section>

    <nav class="task-filter-bar" aria-label="任务筛选"><button v-for="filter in filters" :key="filter.id" :class="{ active: activeFilter === filter.id }" @click="activeFilter = filter.id">{{ filter.label }}<b v-if="filter.id === 'pending'">{{ filter.count }}</b></button></nav>

    <section class="task-section task-priority-section"><div class="task-section-heading"><h2><UiIcon name="PhSparkle" size="14" />今日重点</h2><button @click="activeFilter = 'pending'">查看全部 <UiIcon name="PhArrowRight" size="13" /></button></div><div v-if="focusTask" class="priority-grid"><button v-for="task in pendingTasks.slice(0, 2)" :key="task.id" class="priority-card" :class="{ selected: selectedTask?.id === task.id }" @click="openDetail(task)"><span class="priority-ribbon">{{ task.due.includes("今天") ? "高优先级" : "中优先级" }}<UiIcon name="PhBookmarkSimple" size="13" weight="fill" /></span><span class="priority-course"><i></i>{{ task.course || "个人待办" }}</span><strong>{{ task.title }}</strong><small><UiIcon name="PhClock" size="12" />{{ task.due }}</small><span class="priority-footer"><em><UiIcon name="PhCheckCircle" size="13" />待完成</em><em><UiIcon name="PhFileText" size="13" />详情</em></span></button></div><div v-else class="task-empty compact"><UiIcon name="PhCheckCircle" size="23" weight="fill" /><strong>今天的重点已经完成</strong><span>给自己留一点轻松的时间吧</span></div></section>

    <section class="task-section task-list-section"><div class="task-section-heading"><h2>{{ listTitle }} <span>{{ filteredTasks.length }} 项</span></h2><button class="sort-button"><UiIcon name="PhSlidersHorizontal" size="13" />按截止时间</button></div><div class="task-list"><article v-for="task in filteredTasks" :key="task.id" class="task-item" :class="{ done: task.done, selected: selectedTask?.id === task.id }"><button class="task-check" :class="{ checked: task.done }" :aria-label="task.done ? '标记为未完成' : '标记为完成'" @click="toggleTask(task)"><UiIcon v-if="task.done" name="PhCheck" size="13" weight="bold" /></button><button class="task-item-main" @click="openDetail(task)"><span class="task-course-icon" :class="task.course === '活动报名' ? 'mint' : task.course === '个人待办' ? 'peach' : ''"><UiIcon :name="task.course === '活动报名' ? 'PhCalendarStar' : task.course === '个人待办' ? 'PhClipboardText' : 'PhBookOpen'" size="17" /></span><span><strong>{{ task.title }}</strong><small><UiIcon name="PhClock" size="11" />{{ task.due }} · {{ task.course || "个人待办" }}</small></span></button><span class="task-item-meta"><em :class="task.done ? 'done' : task.due.includes('今天') ? 'urgent' : 'normal'">{{ task.done ? "已完成" : task.due.includes("今天") ? "高优先级" : "中优先级" }}</em><small>提醒</small><button @click="removeTask(task)" aria-label="删除任务"><UiIcon name="PhTrash" size="14" /></button></span></article><div v-if="!filteredTasks.length" class="task-empty"><UiIcon name="PhClipboardText" size="28" /><strong>没有符合条件的任务</strong><span>换一个筛选条件，或添加一个新的小目标</span></div></div></section>

    <section class="task-section week-plan-section"><div class="task-section-heading"><h2>本周安排</h2><button>更多安排 <UiIcon name="PhArrowRight" size="13" /></button></div><div class="week-plan-grid"><article v-for="card in planCards" :key="card.label" class="week-plan-card" :class="card.tone"><span class="week-plan-icon"><UiIcon :name="card.icon" size="16" weight="fill" /></span><span><strong>{{ card.label }}</strong><small>{{ card.count }} 项 · {{ card.note }}</small></span><UiIcon name="PhCaretRight" size="13" /></article></div></section>

    <button class="task-fab" @click="openComposer()"><UiIcon name="PhPlus" size="17" weight="bold" />新建待办</button>
    <Teleport to="body"><div v-if="showComposer" class="task-overlay" @click.self="closeComposer"><form class="task-composer task-composer-rich" @submit.prevent="addTask"><div class="task-composer-head"><div><span class="micro-label">{{ editingTask ? "调整一下安排" : "新的小目标" }}</span><h2>{{ editingTask ? "编辑待办" : "新建待办" }}</h2><p>{{ editingTask ? "把任务信息更新得更清楚" : "把想做的事放下来，心里会轻一点" }}</p></div><button type="button" class="icon-button" aria-label="关闭" @click="closeComposer"><UiIcon name="PhX" /></button></div><label>任务名称<input v-model="newTask" name="task-title" autofocus maxlength="80" placeholder="例如：完成数据结构实验报告" /></label><div class="composer-field-grid"><label>截止时间<input v-model="deadline" name="task-deadline" type="datetime-local" /></label><label>归属分类<select v-model="course" name="task-course"><option>课程作业</option><option>活动报名</option><option>个人待办</option></select></label></div><fieldset class="priority-picker"><legend>优先级</legend><button v-for="option in [{id:'high',label:'高优先级',tone:'high'},{id:'normal',label:'中优先级',tone:'normal'},{id:'low',label:'低优先级',tone:'low'}]" :key="option.id" type="button" :class="['priority-option', option.tone, { active: priority === option.id }]" @click="priority = option.id"><i></i>{{ option.label }}</button></fieldset><label>任务描述 <span class="optional-label">选填</span><textarea v-model="description" name="task-description" rows="3" maxlength="240" placeholder="写下完成标准、材料位置或下一步行动"></textarea></label><label class="reminder-toggle"><span><strong><UiIcon name="PhBell" size="15" />截止前提醒我</strong><small>在任务临近截止时给你一个站内提醒</small></span><input v-model="reminder" name="task-reminder" type="checkbox" /></label><div class="task-composer-actions"><button type="button" class="secondary-button" @click="closeComposer">先放一放</button><button class="primary-button" :disabled="!newTask.trim()"><UiIcon name="PhCheck" size="16" />{{ editingTask ? "保存修改" : "保存待办" }}</button></div></form></div></Teleport>

    <Teleport to="body"><div v-if="detailTask" class="task-detail-overlay" @click.self="detailTask = null"><aside class="task-detail-drawer" role="dialog" aria-modal="true" aria-labelledby="task-detail-title"><header class="task-detail-head"><div><span class="micro-label">任务详情</span><span class="detail-status" :class="detailTask.done ? 'complete' : ''"><i></i>{{ detailTask.done ? "已完成" : "进行中" }}</span></div><button class="icon-button" aria-label="关闭详情" @click="detailTask = null"><UiIcon name="PhX" /></button></header><div class="task-detail-content"><span class="detail-course"><i></i>{{ detailTask.course || "个人待办" }}</span><h2 id="task-detail-title">{{ detailTask.title }}</h2><p class="detail-lead">{{ detailTask.done ? "这个任务已经被你稳稳完成了。" : "把注意力放在下一步，完成一件就少一件。" }}</p><div class="detail-fact-grid"><div><UiIcon name="PhClock" /><span><small>截止时间</small><strong>{{ detailTask.due }}</strong></span></div><div><UiIcon name="PhBookmarkSimple" /><span><small>优先级</small><strong>{{ detailTask.priority === 'high' || detailTask.due.includes('今天') ? '高优先级' : detailTask.priority === 'low' ? '低优先级' : '中优先级' }}</strong></span></div><div><UiIcon name="PhBell" /><span><small>提醒</small><strong>{{ detailTask.reminder === false ? "已关闭" : "截止前提醒" }}</strong></span></div><div><UiIcon name="PhCheckCircle" /><span><small>任务状态</small><strong>{{ detailTask.done ? "已完成" : "待完成" }}</strong></span></div></div><section class="detail-note"><div class="detail-note-head"><h3>任务描述</h3><span v-if="detailTask.description">{{ detailTask.description.length }}/240</span></div><p>{{ detailTask.description || "还没有补充说明。可以编辑任务，写下完成标准或下一步行动。" }}</p></section><section class="detail-next-step"><span class="detail-next-icon"><UiIcon name="PhSparkle" size="15" /></span><div><strong>给自己一个小提示</strong><p>{{ detailTask.course === "活动报名" ? "先确认报名材料和截止时间，再提交报名信息。" : detailTask.course === "课程作业" ? "先打开课程资料，完成最小可行动的一步。" : "把任务拆成 10 分钟可以开始的动作。" }}</p></div></section></div><footer class="task-detail-actions"><button class="secondary-button" @click="openComposer(detailTask)"><UiIcon name="PhFileText" size="15" />编辑任务</button><button class="primary-button" @click="completeDetail"><UiIcon :name="detailTask.done ? 'PhArrowCounterClockwise' : 'PhCheck'" size="15" />{{ detailTask.done ? "恢复待办" : "标记完成" }}</button><button class="detail-delete" aria-label="删除任务" @click="removeTask(detailTask)"><UiIcon name="PhTrash" size="15" /></button></footer></aside></div></Teleport>
  </main>
</template>

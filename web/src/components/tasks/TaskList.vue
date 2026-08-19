<script setup>
import { reactive, ref, watch } from "vue";
import UiIcon from "../UiIcon.vue";
import { formatDeadline, getPriorityLabel, getTaskState } from "../../features/tasks/taskModel.js";

const props = defineProps({
  groups: { type: Object, required: true },
  now: { type: Date, required: true },
});
const emit = defineEmits(["toggle", "open", "action", "reorder"]);
const expanded = reactive({ today: true, upcoming: true, later: true, completed: false });
const localGroups = reactive({ today: [], upcoming: [], later: [], completed: [], overdue: [] });
const dragOverId = ref("");
const groupMeta = {
  today: { label: "今天", icon: "PhSun" },
  upcoming: { label: "未来 7 天", icon: "PhCalendarBlank" },
  later: { label: "更晚", icon: "PhCalendarPlus" },
  completed: { label: "已完成", icon: "PhCheckCircle" },
};
let draggingId = "";

function syncGroups(groups) {
  Object.keys(localGroups).forEach((key) => { localGroups[key] = [...(groups[key] || [])]; });
}
watch(() => Object.keys(localGroups).map((key) => `${key}:${(props.groups[key] || []).map((item) => item.id).join(",")}`).join("|"), () => syncGroups(props.groups), { immediate: true });

function toggleGroup(key) { expanded[key] = !expanded[key]; }
function groupItems(key) { return key === "today" ? [...(localGroups.overdue || []), ...(localGroups.today || [])] : localGroups[key] || []; }
function itemState(task) { return getTaskState(task, props.now); }
function rowClass(task) { return `state-${itemState(task)}`; }
function onDragStart(task) { draggingId = task.id; }
function onDrop(task, key) {
  if (!draggingId || draggingId === task.id) return;
  const sourceItems = groupItems(key);
  const sourceIndex = sourceItems.findIndex((item) => item.id === draggingId);
  const targetIndex = sourceItems.findIndex((item) => item.id === task.id);
  if (sourceIndex >= 0 && targetIndex >= 0) {
    const [moved] = sourceItems.splice(sourceIndex, 1);
    sourceItems.splice(targetIndex, 0, moved);
    if (key === "today") {
      const overdueCount = localGroups.overdue.length;
      localGroups.overdue = sourceItems.slice(0, overdueCount);
      localGroups.today = sourceItems.slice(overdueCount);
    } else localGroups[key] = sourceItems;
  }
  emit("reorder", { sourceId: draggingId, targetId: task.id, group: key });
  draggingId = "";
  dragOverId.value = "";
}
</script>

<template>
  <section class="task-list-shell" aria-label="任务列表">
    <div v-for="key in ['today', 'upcoming', 'later', 'completed']" :key="key" class="task-group">
      <header class="task-group-head">
        <button type="button" class="task-group-toggle" :aria-expanded="expanded[key]" @click="toggleGroup(key)"><UiIcon :name="expanded[key] ? 'PhCaretDown' : 'PhCaretRight'" :size="14" /><span class="task-group-icon"><UiIcon :name="groupMeta[key].icon" :size="14" /></span><strong>{{ groupMeta[key].label }}</strong><b>{{ groupItems(key).length }}</b></button>
        <span v-if="key === 'today'" class="task-group-hint">按截止时间优先</span>
      </header>
      <Transition name="task-group-collapse">
        <div v-if="expanded[key]" class="task-group-items">
          <article v-for="task in groupItems(key)" :key="task.id" class="task-row" :class="[rowClass(task), { 'drag-target': dragOverId === task.id }]" draggable="true" @dragstart="onDragStart(task)" @dragover.prevent="dragOverId = task.id" @dragleave="dragOverId = ''" @drop="onDrop(task, key)">
            <button class="task-drag-handle" type="button" tabindex="-1" aria-hidden="true"><UiIcon name="PhDotsSixVertical" :size="16" /></button>
            <button class="task-row-check" type="button" :aria-label="task.done ? '恢复任务' : '完成任务'" @click="emit('toggle', task)"><span :class="{ checked: task.done }"><UiIcon v-if="task.done" name="PhCheck" :size="12" weight="bold" /></span></button>
            <button class="task-row-main" type="button" @click="emit('open', task)">
              <span class="task-row-icon" :class="`tone-${task.kind}`"><UiIcon :name="task.kind === 'assignment' ? 'PhBookOpen' : 'PhListChecks'" :size="17" /></span>
              <span class="task-row-copy"><strong>{{ task.title }}</strong><small>{{ task.source }} · {{ task.typeLabel }}</small><span class="task-row-progress"><i :style="{ width: `${task.progress}%` }"></i></span></span>
            </button>
            <span class="task-row-deadline"><small>{{ task.done ? '完成于' : itemState(task) === 'overdue' ? '已逾期' : '截止' }}</small><time>{{ formatDeadline(task.deadline) }}</time></span>
            <span class="task-row-priority" :class="`priority-${task.priority}`"><i></i>{{ getPriorityLabel(task.priority) }}</span>
            <span class="task-row-status" :class="task.done ? 'done' : itemState(task)">{{ task.done ? '已完成' : task.statusLabel }}</span>
            <details class="task-row-menu">
              <summary aria-label="更多操作"><UiIcon name="PhDotsThreeVertical" :size="17" /></summary>
              <div class="task-row-menu-popover">
                <button type="button" @click="emit('action', { action: 'view', task })"><UiIcon name="PhEye" :size="14" />查看</button>
                <button type="button" @click="emit('action', { action: 'edit', task })"><UiIcon name="PhPencilSimple" :size="14" />编辑</button>
                <button type="button" @click="emit('action', { action: 'postpone', task })"><UiIcon name="PhClockCounterClockwise" :size="14" />延期一天</button>
                <button type="button" class="danger" @click="emit('action', { action: 'delete', task })"><UiIcon name="PhTrash" :size="14" />删除</button>
              </div>
            </details>
          </article>
        </div>
      </Transition>
      <div v-if="expanded[key] && !groupItems(key).length" class="task-group-empty">这个分组暂时没有任务</div>
    </div>
    <div v-if="!Object.values(groups).some((items) => items?.length)" class="task-list-empty"><UiIcon name="PhClipboardText" :size="28" /><strong>没有符合条件的任务</strong><span>换一个筛选条件，或新建一条个人待办。</span></div>
  </section>
</template>

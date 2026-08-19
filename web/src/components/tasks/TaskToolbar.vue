<script setup>
import UiIcon from "../UiIcon.vue";

defineProps({
  query: { type: String, default: "" },
  kind: { type: String, default: "all" },
  status: { type: String, default: "all" },
  sort: { type: String, default: "deadline" },
});
const emit = defineEmits(["update:query", "update:kind", "update:status", "update:sort", "refresh"]);
</script>

<template>
  <section class="task-toolbar" aria-label="任务筛选和排序">
    <label class="task-search-field"><UiIcon name="PhMagnifyingGlass" :size="16" /><span class="sr-only">搜索任务</span><input :value="query" type="search" placeholder="搜索待办或作业标题、课程名…" @input="emit('update:query', $event.target.value)" /></label>
    <div class="task-kind-tabs" role="tablist" aria-label="任务类型">
      <button v-for="option in [{ key: 'all', label: '全部' }, { key: 'assignment', label: '课程作业' }, { key: 'personal', label: '个人待办' }]" :key="option.key" type="button" :class="{ active: kind === option.key }" @click="emit('update:kind', option.key)">{{ option.label }}</button>
    </div>
    <label class="task-select-field"><span class="sr-only">状态筛选</span><select :value="status" @change="emit('update:status', $event.target.value)"><option value="all">全部状态</option><option value="pending">待完成</option><option value="done">已完成</option><option value="overdue">已逾期</option></select><UiIcon name="PhCaretDown" :size="12" /></label>
    <label class="task-select-field"><span class="sr-only">截止时间排序</span><select :value="sort" @change="emit('update:sort', $event.target.value)"><option value="deadline">截止时间</option><option value="latest">最近创建</option><option value="title">标题</option></select><UiIcon name="PhCaretDown" :size="12" /></label>
    <button class="task-refresh-button" type="button" aria-label="刷新任务" @click="emit('refresh')"><UiIcon name="PhArrowClockwise" :size="15" /></button>
  </section>
</template>

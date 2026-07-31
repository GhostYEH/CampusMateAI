<script setup>
import UiIcon from "../UiIcon.vue";
const props = defineProps({
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  total: { type: Number, default: 0 },
});
const emit = defineEmits(["update:page", "change"]);
import { computed } from "vue";
const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)));
const from = computed(() => props.total === 0 ? 0 : (props.page - 1) * props.pageSize + 1);
const to = computed(() => Math.min(props.total, props.page * props.pageSize));
function go(p) {
  if (p < 1 || p > totalPages.value || p === props.page) return;
  emit("update:page", p);
  emit("change", p);
}
</script>
<template>
  <div class="tch-pagination">
    <span class="tch-pagination-info">{{ from }}-{{ to }} / 共 {{ total }} 条</span>
    <div class="tch-pagination-controls">
      <button class="icon-button" :disabled="page <= 1" @click="go(page - 1)" aria-label="上一页">
        <UiIcon name="PhCaretLeft" :size="16" />
      </button>
      <span class="tch-pagination-page">{{ page }} / {{ totalPages }}</span>
      <button class="icon-button" :disabled="page >= totalPages" @click="go(page + 1)" aria-label="下一页">
        <UiIcon name="PhCaretRight" :size="16" />
      </button>
    </div>
  </div>
</template>
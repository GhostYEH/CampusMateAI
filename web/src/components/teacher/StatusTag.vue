<script setup>
import { computed } from "vue";
const props = defineProps({
  status: { type: String, required: true },
  type: { type: String, default: "assignment" },
});
const labelMap = {
  assignment: { draft: "草稿", published: "进行中", closed: "已结束", archived: "已归档" },
  announcement: { draft: "草稿", published: "已发布", archived: "已归档" },
  course: { draft: "未发布", active: "进行中", archived: "已归档" },
  submission: {
    draft: "草稿", submitted: "已提交", resubmitted: "已重交", late: "迟交",
  },
  read: { read: "已读", unread: "未读" },
};
const toneMap = {
  draft: "neutral", published: "info", closed: "muted", archived: "muted",
  active: "info", submitted: "success", resubmitted: "info", late: "warning",
  read: "muted", unread: "warning",
};
const label = computed(() => labelMap[props.type]?.[props.status] || props.status);
const tone = computed(() => toneMap[props.status] || "neutral");
</script>
<template>
  <span class="tch-status-tag" :class="`tone-${tone}`">{{ label }}</span>
</template>
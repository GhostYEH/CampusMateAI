<script setup>
import UiIcon from "../UiIcon.vue";
defineProps({
  icon: { type: String, default: "PhClipboardText" },
  title: { type: String, default: "暂无数据" },
  description: { type: String, default: "" },
  compact: { type: Boolean, default: false },
});
</script>
<template>
  <div class="tch-empty" :class="{ compact }">
    <UiIcon :name="icon" :size="compact ? 28 : 40" />
    <strong>{{ title }}</strong>
    <span v-if="description">{{ description }}</span>
    <slot />
  </div>
</template>
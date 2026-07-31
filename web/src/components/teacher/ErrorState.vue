<script setup>
import UiIcon from "../UiIcon.vue";
defineProps({
  message: { type: String, default: "加载失败" },
  detail: { type: String, default: "" },
});
defineEmits(["retry"]);
</script>
<template>
  <div class="tch-error" role="alert">
    <UiIcon name="PhCloudSlash" :size="34" />
    <div class="tch-error-body">
      <strong>{{ message }}</strong>
      <p v-if="detail">{{ detail }}</p>
    </div>
    <button class="secondary-button" @click="$emit('retry')">
      <UiIcon name="PhArrowClockwise" :size="16" />重新加载
    </button>
  </div>
</template>
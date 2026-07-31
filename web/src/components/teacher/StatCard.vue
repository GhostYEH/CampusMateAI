<script setup>
import UiIcon from "../UiIcon.vue";
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], required: true },
  hint: { type: String, default: "" },
  icon: { type: String, default: "" },
  tone: { type: String, default: "default" },
  clickable: { type: Boolean, default: false },
});
defineEmits(["click"]);
</script>
<template>
  <component
    :is="clickable ? 'button' : 'div'"
    class="tch-stat-card"
    :class="[`tone-${tone}`, { clickable }]"
    :type="clickable ? 'button' : undefined"
    @click="clickable && $emit('click')"
  >
    <div class="tch-stat-card-head">
      <UiIcon v-if="icon" :name="icon" :size="18" />
      <span class="tch-stat-card-label">{{ label }}</span>
    </div>
    <strong class="tch-stat-card-value">{{ value }}</strong>
    <small v-if="hint" class="tch-stat-card-hint">{{ hint }}</small>
  </component>
</template>
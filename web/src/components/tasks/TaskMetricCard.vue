<script setup>
import UiIcon from "../UiIcon.vue";

defineProps({
  label: { type: String, required: true },
  value: { type: Number, required: true },
  note: { type: String, default: "" },
  change: { type: String, default: "" },
  progress: { type: Number, default: 0 },
  icon: { type: String, default: "PhCheckSquare" },
  tone: { type: String, default: "violet" },
  points: { type: String, default: "0,28 14,22 26,26 40,11 54,21 68,8 82,17 96,10 110,19 124,6" },
});
</script>

<template>
  <article class="task-metric-card" :class="`tone-${tone}`">
    <div class="task-metric-head">
      <span class="task-metric-icon"><UiIcon :name="icon" :size="18" weight="bold" /></span>
      <span class="task-metric-label">{{ label }}</span>
    </div>
    <div class="task-metric-body">
      <div>
        <strong class="task-metric-value">{{ value }}</strong>
        <span v-if="note" class="task-metric-note">{{ note }}</span>
      </div>
      <div class="task-metric-ring" :style="{ '--ring-progress': `${Math.min(progress, 100) * 3.6}deg` }" aria-hidden="true">
        <span>{{ Math.round(progress) }}%</span>
      </div>
    </div>
    <div class="task-metric-foot">
      <svg viewBox="0 0 130 32" preserveAspectRatio="none" aria-hidden="true">
        <polyline :points="points" pathLength="1" />
      </svg>
      <span v-if="change" class="task-metric-change"><UiIcon name="PhChartLineUp" :size="11" />{{ change }}</span>
    </div>
  </article>
</template>

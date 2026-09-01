<script setup>
import { computed } from "vue";
import UiIcon from "../../UiIcon.vue";

const props = defineProps({ summary: { type: Object, required: true } });
const branches = computed(() => [
  { label: "专注能力", value: props.summary.weekFocusMinutes, unit: "min", icon: "PhTimer", progress: Math.min(100, props.summary.weekFocusMinutes / 3), tone: "cyan" },
  { label: "任务执行", value: props.summary.weekCompletedTasks, unit: "项", icon: "PhCheckCircle", progress: Math.min(100, props.summary.weekCompletedTasks * 10), tone: "violet" },
  { label: "持续成长", value: props.summary.streak, unit: "天", icon: "PhFire", progress: Math.min(100, props.summary.streak / 7 * 100), tone: "gold" },
]);
const weekLabels = ["一", "二", "三", "四", "五", "六", "日"];
const chartMax = computed(() => Math.max(20, ...props.summary.weekXpSeries));
const chartPoints = computed(() => props.summary.weekXpSeries
  .map((value, index) => `${index * 16.6667},${44 - (value / chartMax.value) * 38}`)
  .join(" "));
</script>

<template>
  <section class="rpg-growth-tree rpg-hud-panel" aria-labelledby="growth-tree-title">
    <header class="rpg-panel-header">
      <div><span class="rpg-kicker">GROWTH TRACK · THIS WEEK</span><h2 id="growth-tree-title">成长轨迹</h2></div>
      <span class="rpg-week-xp">本周 <strong>+{{ summary.weekXp }} XP</strong></span>
    </header>
    <div class="rpg-growth-trunk">
      <div class="rpg-growth-level"><span>LV</span><strong>{{ summary.level }}</strong><small>{{ summary.title }}</small></div>
      <div class="rpg-growth-branches">
        <article v-for="branch in branches" :key="branch.label" :class="branch.tone">
          <span><UiIcon :name="branch.icon" :size="20" weight="duotone" /></span>
          <div><small>{{ branch.label }}</small><strong>{{ branch.value }} <em>{{ branch.unit }}</em></strong></div>
          <i role="progressbar" :aria-label="`${branch.label}本周记录`" :aria-valuenow="branch.value"><b :style="{ width: `${branch.progress}%` }"></b></i>
        </article>
      </div>
    </div>
    <div class="rpg-growth-chart" aria-label="本周每日真实经验成长曲线">
      <svg viewBox="0 0 100 48" preserveAspectRatio="none" aria-hidden="true">
        <defs><linearGradient id="rpg-growth-line" x1="0" x2="1"><stop stop-color="#43d9ff" /><stop offset="1" stop-color="#9c6cff" /></linearGradient></defs>
        <polyline :points="chartPoints" fill="none" stroke="url(#rpg-growth-line)" stroke-width="1.35" vector-effect="non-scaling-stroke" />
      </svg>
      <div><span v-for="(label, index) in weekLabels" :key="label"><i :style="{ height: `${Math.max(5, summary.weekXpSeries[index] / chartMax * 100)}%` }"></i><small>周{{ label }}</small></span></div>
    </div>
  </section>
</template>

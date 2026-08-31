<script setup>
import { computed } from "vue";
import UiIcon from "../../UiIcon.vue";

const props = defineProps({
  summary: { type: Object, required: true },
  nextExam: { type: Object, default: null },
  now: { type: Number, required: true },
});
const emit = defineEmits(["navigate"]);

const examDays = computed(() => {
  if (!props.nextExam?.exam_date) return null;
  const target = new Date(`${props.nextExam.exam_date}T${props.nextExam.start_time || "23:59"}`).getTime();
  const current = new Date(props.now);
  current.setHours(0, 0, 0, 0);
  return Number.isFinite(target) ? Math.ceil((target - current.getTime()) / 86400000) : null;
});
const examChallenge = computed(() => examDays.value !== null && examDays.value >= 0 && examDays.value <= 7);
const progress = computed(() => Math.round((props.summary.dailyAdventure.completed / props.summary.dailyAdventure.total) * 100));
const nextRoute = computed(() => props.summary.dailyAdventure.completedTasks === 0 ? "/tasks" : "/study");
const actionLabel = computed(() => props.summary.dailyAdventure.completed === props.summary.dailyAdventure.total ? "查看今日记录" : "继续校园冒险");
</script>

<template>
  <section class="game-adventure-card" aria-labelledby="daily-adventure-title">
    <div class="game-orbit-art" aria-hidden="true"><i></i><i></i><i></i><span><UiIcon name="PhGraduationCap" :size="25" weight="fill" /></span></div>
    <div class="game-adventure-copy">
      <span class="game-eyebrow">DAILY ADVENTURE · 今日校园冒险</span>
      <template v-if="examChallenge">
        <h2 id="daily-adventure-title">期末挑战 · {{ nextExam.course_name || "考试准备" }}</h2>
        <p>距离考试 {{ examDays === 0 ? "不到 1" : examDays }} 天，今天的真实学习记录会计入成长。</p>
      </template>
      <template v-else>
        <h2 id="daily-adventure-title">把今天走成一段有迹可循的旅程</h2>
        <p>完成一项待办、积累 60 分钟专注，经验会在真实记录同步后自动结算。</p>
      </template>
      <div class="game-adventure-progress"><span><strong>{{ summary.dailyAdventure.completed }} / {{ summary.dailyAdventure.total }}</strong> 项今日目标</span><small>{{ progress }}%</small></div>
      <div class="game-progress-track light" role="progressbar" aria-label="今日校园冒险进度" :aria-valuenow="summary.dailyAdventure.completed" aria-valuemin="0" :aria-valuemax="summary.dailyAdventure.total"><i :style="{ width: `${progress}%` }"></i></div>
      <div class="game-daily-checks">
        <span :class="{ done: summary.dailyAdventure.completedTasks > 0 }"><UiIcon :name="summary.dailyAdventure.completedTasks > 0 ? 'PhCheckCircle' : 'PhCircle'" :size="17" />完成 1 项待办 <b>{{ summary.dailyAdventure.completedTasks }} 项</b></span>
        <span :class="{ done: summary.dailyAdventure.focusMinutes >= 60 }"><UiIcon :name="summary.dailyAdventure.focusMinutes >= 60 ? 'PhCheckCircle' : 'PhCircle'" :size="17" />专注 60 分钟 <b>{{ summary.dailyAdventure.focusMinutes }} min</b></span>
      </div>
      <button class="game-adventure-action" @click="emit('navigate', nextRoute)">{{ actionLabel }}<UiIcon name="PhArrowRight" :size="18" weight="bold" /></button>
    </div>
  </section>
</template>

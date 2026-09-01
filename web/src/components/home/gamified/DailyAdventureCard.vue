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
const nextRewardText = computed(() => {
  const reward = props.summary.dailyAdventure.nextReward;
  if (!reward) return "今日成长目标已完成";
  if (reward.type === "focus-goal") return `再专注 ${reward.remainingMinutes} 分钟`;
  return "完成一项真实待办";
});
</script>

<template>
  <section class="game-adventure-card" aria-labelledby="daily-adventure-title">
    <div class="game-adventure-copy">
      <span class="game-eyebrow">DAILY ADVENTURE CENTER</span>
      <template v-if="examChallenge">
        <h2 id="daily-adventure-title">期末挑战 · {{ nextExam.course_name || "考试准备" }}</h2>
        <p>距离考试 {{ examDays === 0 ? "不到 1" : examDays }} 天。先推进今天的学习路线，再从容进入挑战。</p>
      </template>
      <template v-else>
        <h2 id="daily-adventure-title">今日校园冒险中心</h2>
        <p>完成一项真实待办、积累 60 分钟专注，让今天的成长留下可回看的轨迹。</p>
      </template>
      <div class="game-adventure-action-row">
        <button class="game-adventure-action" @click="emit('navigate', nextRoute)">{{ actionLabel }}<UiIcon name="PhArrowRight" :size="18" weight="bold" /></button>
        <span class="game-earned-xp"><small>今日已获得</small><strong>+{{ summary.dailyAdventure.todayXp }} XP</strong></span>
      </div>
    </div>

    <aside class="game-adventure-route" aria-label="今日成长路线">
      <div class="game-route-head"><span>今日路线</span><strong>{{ summary.dailyAdventure.completed }} / {{ summary.dailyAdventure.total }}</strong></div>
      <div class="game-route-progress"><i :style="{ width: `${progress}%` }"></i></div>
      <div class="game-route-stop" :class="{ done: summary.dailyAdventure.completedTasks > 0 }">
        <span><UiIcon :name="summary.dailyAdventure.completedTasks > 0 ? 'PhCheck' : 'PhListChecks'" :size="17" weight="bold" /></span>
        <div><small>CHECKPOINT 01</small><strong>完成一项待办</strong><em>{{ summary.dailyAdventure.completedTasks }} 项已完成</em></div>
      </div>
      <div class="game-route-stop" :class="{ done: summary.dailyAdventure.focusMinutes >= 60 }">
        <span><UiIcon :name="summary.dailyAdventure.focusMinutes >= 60 ? 'PhCheck' : 'PhTimer'" :size="17" weight="bold" /></span>
        <div><small>CHECKPOINT 02</small><strong>专注 60 分钟</strong><em>{{ Math.min(summary.dailyAdventure.focusMinutes, 60) }} / 60 min</em></div>
      </div>
      <div class="game-next-reward" :class="{ complete: !summary.dailyAdventure.nextReward }"><span><UiIcon name="PhSparkle" :size="17" weight="fill" /></span><div><small>NEXT REWARD</small><strong>{{ nextRewardText }}</strong></div><b v-if="summary.dailyAdventure.nextReward">+{{ summary.dailyAdventure.nextReward.xp }} XP</b><b v-else>COMPLETE</b></div>
    </aside>
  </section>
</template>

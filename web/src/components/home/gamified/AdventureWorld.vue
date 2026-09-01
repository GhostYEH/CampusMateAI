<script setup>
import { computed } from "vue";
import UiIcon from "../../UiIcon.vue";
import WorldMapNavigation from "./WorldMapNavigation.vue";

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
const isBossChallenge = computed(() => examDays.value !== null && examDays.value >= 0 && examDays.value <= 7);
const progressPercent = computed(() => Math.round((props.summary.dailyAdventure.completed / props.summary.dailyAdventure.total) * 100));
const nextRoute = computed(() => props.summary.dailyAdventure.completedTasks === 0 ? "/tasks" : "/study");
const missionTitle = computed(() => isBossChallenge.value
  ? `${props.nextExam.course_name || "考试"} · 期末挑战`
  : props.summary.dailyAdventure.completedTasks === 0 ? "完成今日首个任务" : "完成 60 分钟专注训练");
const missionMeta = computed(() => isBossChallenge.value
  ? `距离挑战 ${examDays.value === 0 ? "不到 1" : examDays.value} 天`
  : `${props.summary.dailyAdventure.completed} / ${props.summary.dailyAdventure.total} 个成长节点已点亮`);
const rewardText = computed(() => props.summary.dailyAdventure.nextReward
  ? `+${props.summary.dailyAdventure.nextReward.xp} XP`
  : "今日路线完成");
</script>

<template>
  <section class="rpg-adventure-world" aria-labelledby="adventure-title">
    <div class="rpg-adventure-sky" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>
    <div class="rpg-world-copy">
      <span class="rpg-world-status"><i></i>CAMPUS WORLD · ONLINE</span>
      <span v-if="isBossChallenge" class="rpg-boss-label">BOSS CHALLENGE</span>
      <h2 id="adventure-title">今日校园冒险</h2>
      <p>完成当前任务，解锁新的校园区域，获得真实成长经验。</p>

      <button class="rpg-current-mission" @click="emit('navigate', nextRoute)">
        <span><UiIcon :name="isBossChallenge ? 'PhExam' : 'PhFlagCheckered'" :size="25" weight="fill" /></span>
        <span><small>当前任务 · CURRENT QUEST</small><strong>{{ missionTitle }}</strong><em>{{ missionMeta }}</em></span>
        <b>{{ rewardText }}</b>
        <UiIcon name="PhArrowUpRight" :size="17" />
      </button>

      <div class="rpg-world-actions">
        <button @click="emit('navigate', nextRoute)">开始冒险<UiIcon name="PhPlay" :size="17" weight="fill" /></button>
        <span><small>今日已获得</small><strong>+{{ summary.dailyAdventure.todayXp }} XP</strong></span>
      </div>
    </div>

    <aside class="rpg-world-route" aria-label="今日冒险路线">
      <header><span>今日路线</span><strong>{{ summary.dailyAdventure.completed }} / {{ summary.dailyAdventure.total }}</strong></header>
      <div class="rpg-route-line"><i :style="{ height: `${progressPercent}%` }"></i></div>
      <div class="rpg-route-node" :class="{ complete: summary.dailyAdventure.completedTasks > 0 }">
        <span><UiIcon :name="summary.dailyAdventure.completedTasks > 0 ? 'PhCheck' : 'PhListChecks'" :size="18" weight="bold" /></span>
        <div><small>QUEST NODE 01</small><strong>任务推进</strong><em>{{ summary.dailyAdventure.completedTasks }} 项完成</em></div>
      </div>
      <div class="rpg-route-node" :class="{ complete: summary.dailyAdventure.focusMinutes >= 60 }">
        <span><UiIcon :name="summary.dailyAdventure.focusMinutes >= 60 ? 'PhCheck' : 'PhTimer'" :size="18" weight="bold" /></span>
        <div><small>QUEST NODE 02</small><strong>专注训练</strong><em>{{ Math.min(summary.dailyAdventure.focusMinutes, 60) }} / 60 min</em></div>
      </div>
      <div class="rpg-route-reward" :class="{ complete: !summary.dailyAdventure.nextReward }">
        <UiIcon name="PhSparkle" :size="18" weight="fill" />
        <span><small>NEXT REWARD</small><strong>{{ rewardText }}</strong></span>
      </div>
    </aside>

    <section class="rpg-digital-human-stage" aria-label="CampusMate AI 数字人伙伴">
      <div class="rpg-human-halo" aria-hidden="true"></div>
      <img class="rpg-human-fallback" src="/digital-human/fallback-avatar.png" alt="CampusMate CPM 数字人伙伴" />
      <div class="rpg-human-dialogue">
        <span>AI COMPANION · ONLINE</span>
        <strong>嗨，今天也一起探索校园吧。</strong>
        <button @click="emit('navigate', '/counselor')">与我对话<UiIcon name="PhChatCircleText" :size="15" /></button>
      </div>
    </section>

    <WorldMapNavigation @navigate="emit('navigate', $event)" />
  </section>
</template>

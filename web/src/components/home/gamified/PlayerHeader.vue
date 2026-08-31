<script setup>
import UiIcon from "../../UiIcon.vue";

defineProps({
  user: { type: Object, default: null },
  summary: { type: Object, required: true },
});
</script>

<template>
  <header class="game-player-header">
    <div class="game-player-identity">
      <img :src="user?.avatar_url || '/assets/generated/home-reference-student-avatar.png'" alt="" />
      <div>
        <span class="game-eyebrow">CAMPUS ADVENTURE</span>
        <h1>{{ user?.name || user?.username || "同学" }}</h1>
        <p><span>Lv.{{ summary.level }}</span>{{ summary.title }}</p>
      </div>
    </div>
    <div class="game-player-progress">
      <div class="game-xp-line"><span><UiIcon name="PhSparkle" :size="16" weight="fill" />经验进度</span><strong>{{ summary.currentLevelXp }} / {{ summary.nextLevelXp }} XP</strong></div>
      <div class="game-progress-track" role="progressbar" aria-label="等级经验进度" :aria-valuenow="summary.currentLevelXp" aria-valuemin="0" :aria-valuemax="summary.nextLevelXp"><i :style="{ width: `${Math.round(summary.progress * 100)}%` }"></i></div>
    </div>
    <div class="game-streak-chip" :aria-label="`连续学习 ${summary.streak} 天`"><UiIcon name="PhFire" :size="20" weight="fill" /><span><small>连续学习</small><strong>{{ summary.streak }} 天</strong></span></div>
  </header>
</template>

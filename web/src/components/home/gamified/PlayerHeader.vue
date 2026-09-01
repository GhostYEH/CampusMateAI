<script setup>
import { computed } from "vue";
import UiIcon from "../../UiIcon.vue";

const props = defineProps({
  user: { type: Object, default: null },
  summary: { type: Object, required: true },
});

const identityDetail = computed(() => props.user?.detail
  || [props.user?.college, props.user?.major].filter(Boolean).join(" · ")
  || "CampusMateAI 成长档案");
const progressPercent = computed(() => Math.round(props.summary.progress * 100));
</script>

<template>
  <header class="game-player-header">
    <div class="game-player-identity">
      <div class="game-avatar-frame">
        <img :src="user?.avatar_url || '/assets/generated/home-reference-student-avatar.png'" alt="" />
        <span aria-hidden="true">{{ summary.level }}</span>
      </div>
      <div class="game-player-copy">
        <span class="game-eyebrow">MY GROWTH PROFILE</span>
        <div><h1>{{ user?.name || user?.username || "同学" }}</h1><span class="game-player-role">{{ summary.title }}</span></div>
        <p>{{ identityDetail }}</p>
      </div>
    </div>
    <div class="game-player-progress">
      <div class="game-xp-line"><span>NEXT LEVEL · LV.{{ summary.level + 1 }}</span><strong>{{ summary.currentLevelXp }} <small>/ {{ summary.nextLevelXp }} XP</small></strong></div>
      <div class="game-progress-track" role="progressbar" aria-label="等级经验进度" :aria-valuenow="summary.currentLevelXp" aria-valuemin="0" :aria-valuemax="summary.nextLevelXp"><i :style="{ width: `${progressPercent}%` }"></i><b :style="{ left: `${progressPercent}%` }"></b></div>
      <small class="game-xp-caption">距离升级还需 {{ summary.nextLevelXp - summary.currentLevelXp }} XP</small>
    </div>
    <div class="game-streak-chip" :aria-label="`连续学习 ${summary.streak} 天`"><span><small>LEARNING STREAK</small><strong><UiIcon name="PhFire" :size="18" weight="fill" />{{ summary.streak }} 天</strong></span></div>
  </header>
</template>

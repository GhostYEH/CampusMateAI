<script setup>
import { computed } from "vue";
import UiIcon from "../../UiIcon.vue";

const props = defineProps({
  user: { type: Object, default: null },
  summary: { type: Object, required: true },
});

const progressPercent = computed(() => Math.round(props.summary.progress * 100));
const identityDetail = computed(() => props.user?.detail
  || [props.user?.college, props.user?.major].filter(Boolean).join(" · ")
  || "CampusMateAI 冒险者档案");
</script>

<template>
  <section class="rpg-character-panel" aria-labelledby="character-name">
    <div class="rpg-character-avatar">
      <img :src="user?.avatar_url || '/assets/generated/home-reference-student-avatar.png'" alt="" />
      <span>LV.{{ summary.level }}</span>
    </div>
    <div class="rpg-character-identity">
      <span class="rpg-kicker"><UiIcon name="PhIdentificationCard" :size="13" />角色档案 · CHARACTER</span>
      <div class="rpg-character-name-row">
        <h1 id="character-name">{{ user?.name || user?.username || "同学" }}</h1>
        <span>{{ summary.title }}</span>
      </div>
      <p>{{ identityDetail }}</p>
    </div>
    <div class="rpg-character-xp">
      <div><span>成长经验</span><strong>{{ summary.currentLevelXp }} <small>/ {{ summary.nextLevelXp }} XP</small></strong></div>
      <div class="rpg-xp-track" role="progressbar" aria-label="成长经验" :aria-valuenow="summary.currentLevelXp" aria-valuemin="0" :aria-valuemax="summary.nextLevelXp"><i :style="{ width: `${progressPercent}%` }"></i><b :style="{ left: `${progressPercent}%` }"></b></div>
      <small>距离 LV.{{ summary.level + 1 }} 还需 {{ summary.nextLevelXp - summary.currentLevelXp }} XP</small>
    </div>
    <dl class="rpg-character-vitals">
      <div><dt><UiIcon name="PhFire" :size="15" weight="fill" />连续学习</dt><dd>{{ summary.streak }}<small> 天</small></dd></div>
      <div><dt><UiIcon name="PhSparkle" :size="15" weight="fill" />累计经验</dt><dd>{{ summary.totalXp }}<small> XP</small></dd></div>
    </dl>
  </section>
</template>

<script setup>
import { computed, nextTick, shallowRef, useTemplateRef } from "vue";
import UiIcon from "../../UiIcon.vue";

const props = defineProps({ summary: { type: Object, required: true } });
const selectedAchievement = shallowRef(null);
const closeButton = useTemplateRef("closeButton");
const achievements = computed(() => props.summary.achievementCollection.slice(0, 5));
const unlockedCount = computed(() => achievements.value.filter((item) => item.unlocked).length);

async function openAchievement(achievement) {
  selectedAchievement.value = achievement;
  await nextTick();
  closeButton.value?.focus();
}

function closeAchievement() {
  selectedAchievement.value = null;
}

function progress(achievement) {
  return Math.min(100, Math.round((achievement.current / achievement.target) * 100));
}

function unlockedDate(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "" : date.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
}
</script>

<template>
  <section class="rpg-achievement-hall rpg-hud-panel" aria-labelledby="achievement-hall-title">
    <header class="rpg-panel-header">
      <div><span class="rpg-kicker">ACHIEVEMENT HALL · COLLECTION</span><h2 id="achievement-hall-title">荣誉大厅</h2><p>最近获得与下一里程碑</p></div>
      <span class="rpg-hall-count"><strong>{{ unlockedCount }}</strong> / {{ achievements.length }} 已点亮</span>
    </header>
    <div class="rpg-trophy-case">
      <button v-for="achievement in achievements" :key="achievement.id" :class="{ locked: !achievement.unlocked }" @click="openAchievement(achievement)">
        <span class="rpg-trophy-medal"><UiIcon :name="achievement.unlocked ? achievement.icon : 'PhLock'" :size="25" weight="duotone" /></span>
        <strong>{{ achievement.title }}</strong>
        <small v-if="achievement.unlocked">{{ unlockedDate(achievement.unlockedAt) }} 获得</small>
        <small v-else>{{ achievement.current }} / {{ achievement.target }} {{ achievement.unit }}</small>
        <i v-if="!achievement.unlocked"><b :style="{ width: `${progress(achievement)}%` }"></b></i>
        <em>{{ achievement.unlocked ? "UNLOCKED" : "LOCKED" }}</em>
      </button>
    </div>
  </section>

  <Teleport to="body">
    <div v-if="selectedAchievement" class="rpg-dialog-backdrop" @click.self="closeAchievement" @keydown.esc="closeAchievement">
      <section class="rpg-achievement-dialog" role="dialog" aria-modal="true" aria-labelledby="achievement-dialog-title">
        <button ref="closeButton" class="rpg-dialog-close" aria-label="关闭成就详情" @click="closeAchievement"><UiIcon name="PhX" :size="18" /></button>
        <span class="rpg-dialog-medal" :class="{ locked: !selectedAchievement.unlocked }"><UiIcon :name="selectedAchievement.unlocked ? selectedAchievement.icon : 'PhLock'" :size="36" weight="duotone" /></span>
        <span class="rpg-kicker">{{ selectedAchievement.unlocked ? "ACHIEVEMENT UNLOCKED" : "NEXT MILESTONE" }}</span>
        <h2 id="achievement-dialog-title">{{ selectedAchievement.title }}</h2>
        <p>{{ selectedAchievement.description }}</p>
        <small v-if="selectedAchievement.unlocked">获得于 {{ unlockedDate(selectedAchievement.unlockedAt) }}</small>
        <div v-else class="rpg-dialog-progress"><span><i :style="{ width: `${progress(selectedAchievement)}%` }"></i></span><strong>{{ selectedAchievement.current }} / {{ selectedAchievement.target }} {{ selectedAchievement.unit }}</strong></div>
      </section>
    </div>
  </Teleport>
</template>

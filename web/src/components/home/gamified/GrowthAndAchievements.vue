<script setup>
import { computed, nextTick, shallowRef, useTemplateRef } from "vue";
import UiIcon from "../../UiIcon.vue";

const props = defineProps({ summary: { type: Object, required: true } });
const selectedAchievement = shallowRef(null);
const closeButton = useTemplateRef("closeButton");
const visibleAchievements = computed(() => props.summary.achievementCollection.slice(0, 3));

async function openAchievement(achievement) {
  selectedAchievement.value = achievement;
  await nextTick();
  closeButton.value?.focus();
}

function closeAchievement() {
  selectedAchievement.value = null;
}

function achievementProgress(achievement) {
  return Math.min(100, Math.round((achievement.current / achievement.target) * 100));
}

function unlockedDate(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "" : date.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
}
</script>

<template>
  <section class="game-growth-grid">
    <article class="game-growth-card" aria-labelledby="growth-title">
      <header class="game-panel-head"><div><span class="game-eyebrow">GROWTH LOG</span><h2 id="growth-title">本周成长</h2></div><span class="game-level-mark">Lv.{{ summary.level }}</span></header>
      <div class="game-growth-level"><span><strong>+{{ summary.weekXp }}</strong><small> 本周 XP</small></span><p>你正在沿着 <b>{{ summary.title }}</b> 的成长路线继续前进。</p></div>
      <dl class="game-growth-stats">
        <div><dt><UiIcon name="PhTimer" :size="15" />专注投入</dt><dd>{{ summary.weekFocusMinutes }}<small> min</small></dd><i :style="{ '--growth': `${Math.min(100, summary.weekFocusMinutes / 3)}%` }"></i></div>
        <div><dt><UiIcon name="PhCheckCircle" :size="15" />任务推进</dt><dd>{{ summary.weekCompletedTasks }}<small> 项</small></dd><i :style="{ '--growth': `${Math.min(100, summary.weekCompletedTasks * 10)}%` }"></i></div>
        <div><dt><UiIcon name="PhFire" :size="15" />连续学习</dt><dd>{{ summary.streak }}<small> 天</small></dd><i :style="{ '--growth': `${Math.min(100, summary.streak / 7 * 100)}%` }"></i></div>
      </dl>
    </article>

    <article class="game-achievement-card" aria-labelledby="achievement-title">
      <header class="game-panel-head"><div><span class="game-eyebrow">GROWTH COLLECTION</span><h2 id="achievement-title">成长收藏</h2><p>最近获得与下一里程碑</p></div><span class="game-collection-count">{{ visibleAchievements.filter(item => item.unlocked).length }} / {{ visibleAchievements.length }}</span></header>
      <div v-if="visibleAchievements.length" class="game-achievement-list">
        <button v-for="achievement in visibleAchievements" :key="achievement.id" :class="{ locked: !achievement.unlocked }" @click="openAchievement(achievement)">
          <span><UiIcon :name="achievement.unlocked ? achievement.icon : 'PhLock'" :size="22" /></span>
          <strong>{{ achievement.title }}</strong>
          <small v-if="achievement.unlocked">{{ unlockedDate(achievement.unlockedAt) }} 获得</small>
          <small v-else>{{ achievement.current }} / {{ achievement.target }} {{ achievement.unit }}</small>
          <i v-if="!achievement.unlocked"><b :style="{ width: `${achievementProgress(achievement)}%` }"></b></i>
          <UiIcon name="PhArrowUpRight" :size="15" />
        </button>
      </div>
    </article>
  </section>

  <Teleport to="body">
    <div v-if="selectedAchievement" class="game-dialog-backdrop" @click.self="closeAchievement" @keydown.esc="closeAchievement">
      <section class="game-achievement-dialog" role="dialog" aria-modal="true" aria-labelledby="achievement-dialog-title">
        <button ref="closeButton" class="game-dialog-close" aria-label="关闭成就详情" @click="closeAchievement"><UiIcon name="PhX" :size="18" /></button>
        <span class="game-dialog-medal" :class="{ locked: !selectedAchievement.unlocked }"><UiIcon :name="selectedAchievement.unlocked ? selectedAchievement.icon : 'PhLock'" :size="34" /></span>
        <span class="game-eyebrow">{{ selectedAchievement.unlocked ? "COLLECTION UNLOCKED" : "NEXT MILESTONE" }}</span>
        <h2 id="achievement-dialog-title">{{ selectedAchievement.title }}</h2>
        <p>{{ selectedAchievement.description }}</p>
        <small v-if="selectedAchievement.unlocked">获得于 {{ new Date(selectedAchievement.unlockedAt).toLocaleString('zh-CN', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' }) }}</small>
        <div v-else class="game-dialog-progress"><span><i :style="{ width: `${achievementProgress(selectedAchievement)}%` }"></i></span><strong>{{ selectedAchievement.current }} / {{ selectedAchievement.target }} {{ selectedAchievement.unit }}</strong></div>
      </section>
    </div>
  </Teleport>
</template>

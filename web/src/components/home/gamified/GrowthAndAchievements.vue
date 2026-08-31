<script setup>
import { nextTick, shallowRef, useTemplateRef } from "vue";
import UiIcon from "../../UiIcon.vue";

const props = defineProps({ summary: { type: Object, required: true } });
const selectedAchievement = shallowRef(null);
const closeButton = useTemplateRef("closeButton");

async function openAchievement(achievement) {
  selectedAchievement.value = achievement;
  await nextTick();
  closeButton.value?.focus();
}

function closeAchievement() {
  selectedAchievement.value = null;
}
</script>

<template>
  <section class="game-growth-grid">
    <article class="game-panel game-growth-card" aria-labelledby="growth-title">
      <header class="game-panel-head"><div><span class="game-eyebrow">GROWTH LOG</span><h2 id="growth-title">本周成长</h2></div><span class="game-level-mark">Lv.{{ summary.level }}</span></header>
      <div class="game-growth-level"><span><strong>{{ summary.currentLevelXp }}</strong> / {{ summary.nextLevelXp }} XP</span><small>距离下一等级还需 {{ summary.nextLevelXp - summary.currentLevelXp }} XP</small></div>
      <div class="game-progress-track" role="progressbar" aria-label="本等级成长进度" :aria-valuenow="summary.currentLevelXp" aria-valuemin="0" :aria-valuemax="summary.nextLevelXp"><i :style="{ width: `${Math.round(summary.progress * 100)}%` }"></i></div>
      <dl class="game-growth-stats">
        <div><dt>本周 XP</dt><dd>+{{ summary.weekXp }}</dd></div>
        <div><dt>专注时长</dt><dd>{{ summary.weekFocusMinutes }}<small> min</small></dd></div>
        <div><dt>完成任务</dt><dd>{{ summary.weekCompletedTasks }}<small> 项</small></dd></div>
        <div><dt>连续学习</dt><dd>{{ summary.streak }}<small> 天</small></dd></div>
      </dl>
    </article>

    <article class="game-panel game-achievement-card" aria-labelledby="achievement-title">
      <header class="game-panel-head"><div><span class="game-eyebrow">ACHIEVEMENTS</span><h2 id="achievement-title">最近获得</h2></div><UiIcon name="PhTrophy" :size="23" /></header>
      <div v-if="summary.recentAchievements.length" class="game-achievement-list">
        <button v-for="achievement in summary.recentAchievements" :key="achievement.id" @click="openAchievement(achievement)"><span><UiIcon :name="achievement.icon" :size="22" /></span><strong>{{ achievement.title }}</strong><small>{{ achievement.description }}</small><UiIcon name="PhArrowUpRight" :size="15" /></button>
      </div>
      <div v-else class="game-empty compact" role="status"><span><UiIcon name="PhMedal" :size="28" /></span><strong>成就正在路上</strong><p>完成一次真实专注后，第一枚徽章会在这里解锁。</p></div>
    </article>
  </section>

  <Teleport to="body">
    <div v-if="selectedAchievement" class="game-dialog-backdrop" @click.self="closeAchievement" @keydown.esc="closeAchievement">
      <section class="game-achievement-dialog" role="dialog" aria-modal="true" aria-labelledby="achievement-dialog-title">
        <button ref="closeButton" class="game-dialog-close" aria-label="关闭成就详情" @click="closeAchievement"><UiIcon name="PhX" :size="18" /></button>
        <span class="game-dialog-medal"><UiIcon :name="selectedAchievement.icon" :size="34" /></span>
        <span class="game-eyebrow">ACHIEVEMENT UNLOCKED</span>
        <h2 id="achievement-dialog-title">{{ selectedAchievement.title }}</h2>
        <p>{{ selectedAchievement.description }}</p>
        <small>获得于 {{ new Date(selectedAchievement.unlockedAt).toLocaleString('zh-CN', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' }) }}</small>
      </section>
    </div>
  </Teleport>
</template>

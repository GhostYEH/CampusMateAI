<script setup>
import { computed } from "vue";
import UiIcon from "../../UiIcon.vue";

const props = defineProps({ summary: { type: Object, required: true } });
const emit = defineEmits(["navigate"]);

const currentIndex = computed(() => Math.min(6, Math.max(0, props.summary.streak)));
const days = computed(() => Array.from({ length: 7 }, (_, index) => ({
  day: index + 1,
  signed: index < Math.min(props.summary.streak, 7),
  current: index === currentIndex.value && props.summary.streak < 7,
  reward: index === 6 ? "宝箱" : index === 3 ? "+20 XP" : "+10 XP",
})));
</script>

<template>
  <section class="rpg-daily-signin rpg-hud-panel" aria-labelledby="daily-signin-title">
    <header class="rpg-panel-header">
      <div><span class="rpg-kicker">DAILY SIGN-IN · STREAK</span><h2 id="daily-signin-title">每日签到</h2><p>学习与任务记录会自动点亮签到</p></div>
      <span class="rpg-signin-streak"><UiIcon name="PhFire" :size="15" weight="fill" />{{ summary.streak }} 天</span>
    </header>
    <div class="rpg-signin-route">
      <div v-for="day in days" :key="day.day" :class="{ signed: day.signed, current: day.current, jackpot: day.day === 7 }">
        <span><UiIcon :name="day.day === 7 ? 'PhTreasureChest' : day.signed ? 'PhCheck' : 'PhStar'" :size="18" weight="fill" /></span>
        <strong>第 {{ day.day }} 天</strong>
        <small>{{ day.reward }}</small>
      </div>
    </div>
    <button class="rpg-signin-action" @click="emit('navigate', summary.dailyAdventure.completed < summary.dailyAdventure.total ? '/study' : '/profile')">
      {{ summary.dailyAdventure.completed < summary.dailyAdventure.total ? "继续今日成长" : "查看成长记录" }}<UiIcon name="PhArrowRight" :size="15" />
    </button>
  </section>
</template>

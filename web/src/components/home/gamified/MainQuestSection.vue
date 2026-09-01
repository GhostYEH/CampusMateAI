<script setup>
import { computed } from "vue";
import UiIcon from "../../UiIcon.vue";

const props = defineProps({ quests: { type: Array, default: () => [] } });
const emit = defineEmits(["navigate"]);

const sourceLabels = { course: "课程", assignment: "课程作业", "personal-task": "个人待办", exam: "考试" };
const primaryQuest = computed(() => props.quests[0] || null);
const secondaryQuests = computed(() => props.quests.slice(1, 5));

function metaText(quest) {
  if (!["assignment", "personal-task"].includes(quest.sourceType)) return quest.meta;
  const date = new Date(quest.meta);
  return Number.isNaN(date.valueOf()) ? quest.meta : date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function questSignal(quest) {
  if (quest.sourceType === "personal-task") return "+20 XP";
  return ({ course: "课程节点", assignment: "截止提醒", exam: "挑战日程" }[quest.sourceType] || "校园事项");
}
</script>

<template>
  <section class="game-panel game-main-quest" aria-labelledby="main-quest-title">
    <header class="game-panel-head"><div><span class="game-eyebrow">MAIN QUEST</span><h2 id="main-quest-title">今日主线</h2></div><button @click="emit('navigate', '/tasks')">查看全部<UiIcon name="PhArrowRight" :size="15" /></button></header>
    <div v-if="primaryQuest" class="game-quest-board">
      <button class="game-next-quest" @click="emit('navigate', primaryQuest.route)">
        <span class="game-next-label">NEXT QUEST</span>
        <span class="game-next-icon" :class="primaryQuest.sourceType"><UiIcon :name="primaryQuest.icon" :size="25" /></span>
        <span class="game-next-copy"><small>{{ sourceLabels[primaryQuest.sourceType] || "校园事项" }}</small><strong>{{ primaryQuest.title }}</strong><em>{{ metaText(primaryQuest) }}</em></span>
        <span class="game-next-signal">{{ questSignal(primaryQuest) }}</span>
        <span class="game-next-cta">进入任务<UiIcon name="PhArrowUpRight" :size="15" /></span>
      </button>
      <div v-if="secondaryQuests.length" class="game-quest-list">
        <button v-for="quest in secondaryQuests" :key="quest.id" @click="emit('navigate', quest.route)">
          <span class="game-quest-icon" :class="quest.sourceType"><UiIcon :name="quest.icon" :size="18" /></span>
          <span class="game-quest-copy"><small>{{ sourceLabels[quest.sourceType] || "校园事项" }}</small><strong>{{ quest.title }}</strong><em>{{ metaText(quest) }}</em></span>
          <span class="game-quest-signal">{{ questSignal(quest) }}</span>
          <UiIcon name="PhCaretRight" :size="15" />
        </button>
      </div>
    </div>
    <div v-else class="game-empty" role="status"><span><UiIcon name="PhFlagCheckered" :size="28" /></span><strong>今日主线暂时清空</strong><p>课程、截止事项与考试安排同步后会出现在这里。</p><button @click="emit('navigate', '/tasks')">查看全部待办</button></div>
  </section>
</template>

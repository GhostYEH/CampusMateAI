<script setup>
import UiIcon from "../../UiIcon.vue";

defineProps({ quests: { type: Array, default: () => [] } });
const emit = defineEmits(["navigate"]);

const sourceLabels = { course: "课程", assignment: "课程作业", "personal-task": "个人待办", exam: "考试" };

function metaText(quest) {
  if (!["assignment", "personal-task"].includes(quest.sourceType)) return quest.meta;
  const date = new Date(quest.meta);
  return Number.isNaN(date.valueOf()) ? quest.meta : date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
</script>

<template>
  <section class="game-panel game-main-quest" aria-labelledby="main-quest-title">
    <header class="game-panel-head"><div><span class="game-eyebrow">MAIN QUEST</span><h2 id="main-quest-title">今日主线</h2></div><button @click="emit('navigate', '/tasks')">全部任务<UiIcon name="PhArrowRight" :size="15" /></button></header>
    <div v-if="quests.length" class="game-quest-list">
      <button v-for="(quest, index) in quests" :key="quest.id" @click="emit('navigate', quest.route)">
        <span class="game-quest-marker"><i></i><b>{{ String(index + 1).padStart(2, "0") }}</b></span>
        <span class="game-quest-icon" :class="quest.sourceType"><UiIcon :name="quest.icon" :size="20" /></span>
        <span class="game-quest-copy"><small>{{ sourceLabels[quest.sourceType] || "校园事项" }}</small><strong>{{ quest.title }}</strong><em>{{ metaText(quest) }}</em></span>
        <UiIcon name="PhCaretRight" :size="16" />
      </button>
    </div>
    <div v-else class="game-empty" role="status"><span><UiIcon name="PhFlagCheckered" :size="28" /></span><strong>今日主线暂时清空</strong><p>课程、截止事项与考试安排同步后会出现在这里。</p><button @click="emit('navigate', '/tasks')">查看全部待办</button></div>
  </section>
</template>

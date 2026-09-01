<script setup>
import { computed } from "vue";
import UiIcon from "../../UiIcon.vue";

const props = defineProps({ quests: { type: Array, default: () => [] } });
const emit = defineEmits(["navigate"]);

const sourceLabels = { course: "COURSE QUEST", assignment: "DEADLINE QUEST", "personal-task": "SIDE OBJECTIVE", exam: "BOSS CHALLENGE" };
const primaryQuest = computed(() => props.quests[0] || null);
const supportingQuests = computed(() => props.quests.slice(1, 5));

function metaText(quest) {
  if (!["assignment", "personal-task"].includes(quest.sourceType)) return quest.meta;
  const date = new Date(quest.meta);
  return Number.isNaN(date.valueOf()) ? quest.meta : date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function questReward(quest) {
  if (quest.sourceType === "personal-task") return "+20 XP";
  return ({ course: "课程节点", assignment: "截止提醒", exam: "挑战日程" }[quest.sourceType] || "校园事项");
}
</script>

<template>
  <section class="rpg-quest-log rpg-hud-panel" aria-labelledby="quest-log-title">
    <header class="rpg-panel-header">
      <div><span class="rpg-kicker">QUEST LOG · ACTIVE</span><h2 id="quest-log-title">任务日志</h2></div>
      <button @click="emit('navigate', '/tasks')">全部任务<UiIcon name="PhArrowRight" :size="15" /></button>
    </header>

    <button v-if="primaryQuest" class="rpg-main-quest" @click="emit('navigate', primaryQuest.route)">
      <span class="rpg-quest-rank">MAIN</span>
      <span class="rpg-main-quest-icon"><UiIcon :name="primaryQuest.icon" :size="29" weight="duotone" /></span>
      <span class="rpg-main-quest-copy">
        <small>{{ sourceLabels[primaryQuest.sourceType] || "CAMPUS QUEST" }}</small>
        <strong>{{ primaryQuest.title }}</strong>
        <em>{{ metaText(primaryQuest) }}</em>
      </span>
      <span class="rpg-quest-state"><i></i>进行中</span>
      <span class="rpg-quest-reward"><small>QUEST SIGNAL</small><strong>{{ questReward(primaryQuest) }}</strong></span>
      <span class="rpg-main-quest-action">进入任务<UiIcon name="PhArrowUpRight" :size="15" /></span>
    </button>

    <div v-if="supportingQuests.length" class="rpg-supporting-quests" aria-label="支线任务">
      <header><span>SIDE QUESTS</span><small>{{ supportingQuests.length }} 个可推进节点</small></header>
      <button v-for="quest in supportingQuests" :key="quest.id" @click="emit('navigate', quest.route)">
        <span :class="quest.sourceType"><UiIcon :name="quest.icon" :size="18" /></span>
        <span><small>{{ sourceLabels[quest.sourceType] || "CAMPUS QUEST" }}</small><strong>{{ quest.title }}</strong><em>{{ metaText(quest) }}</em></span>
        <b>{{ questReward(quest) }}</b>
        <UiIcon name="PhCaretRight" :size="15" />
      </button>
    </div>

    <div v-else class="rpg-empty-state" role="status">
      <UiIcon name="PhFlagCheckered" :size="32" />
      <strong>任务日志已清空</strong>
      <p>课程、截止事项和考试同步后会继续生成真实任务节点。</p>
      <button @click="emit('navigate', '/tasks')">查看待办</button>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";
import UiIcon from "../../UiIcon.vue";

const props = defineProps({ summary: { type: Object, required: true } });
const emit = defineEmits(["navigate"]);

const suggestion = computed(() => {
  const reward = props.summary.dailyAdventure.nextReward;
  if (!reward) return "今天的成长路线已经完成，可以回顾成果或为明天整理计划。";
  if (reward.type === "focus-goal") return `再完成 ${reward.remainingMinutes} 分钟专注训练，即可点亮今日第二个成长节点。`;
  return "先完成一项真实待办，开启今天的校园成长路线。";
});

const quickActions = computed(() => [
  { label: "专注训练", detail: `${Math.min(props.summary.dailyAdventure.focusMinutes, 60)} / 60 min`, icon: "PhTimer", route: "/study" },
  { label: "今日任务", detail: `${props.summary.dailyAdventure.completedTasks} 项完成`, icon: "PhListChecks", route: "/tasks" },
]);
</script>

<template>
  <section class="rpg-ai-companion" aria-labelledby="ai-companion-title">
    <div class="rpg-ai-portrait"><img src="/digital-human/fallback-avatar.png" alt="CampusMate CPM 数字人伙伴" /><i></i></div>
    <div class="rpg-ai-copy">
      <span class="rpg-kicker">AI COMPANION · ONLINE</span>
      <h2 id="ai-companion-title">AI 伙伴</h2>
      <p>{{ suggestion }}</p>
      <div class="rpg-ai-actions">
        <button v-for="action in quickActions" :key="action.route" @click="emit('navigate', action.route)">
          <UiIcon :name="action.icon" :size="15" /><span><strong>{{ action.label }}</strong><small>{{ action.detail }}</small></span>
        </button>
      </div>
    </div>
    <button class="rpg-ai-chat" @click="emit('navigate', '/counselor')">与伙伴对话<UiIcon name="PhChatCircleText" :size="15" /></button>
  </section>
</template>

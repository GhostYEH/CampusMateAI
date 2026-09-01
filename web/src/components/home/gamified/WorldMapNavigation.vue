<script setup>
import UiIcon from "../../UiIcon.vue";

const emit = defineEmits(["navigate"]);

const nodes = [
  { label: "冒险首页", code: "ADVENTURE HOME", icon: "PhHouse", route: "/home", x: "8%", y: "55%", tone: "cyan" },
  { label: "课程表", code: "SCHEDULE", icon: "PhCalendarBlank", route: "/courses", x: "18%", y: "78%", tone: "gold" },
  { label: "任务日志", code: "QUEST LOG", icon: "PhListChecks", route: "/tasks", x: "30%", y: "46%", tone: "violet", badge: "!" },
  { label: "考试试炼", code: "EXAM BOSS", icon: "PhExam", route: "/exams", x: "40%", y: "73%", tone: "ember" },
  { label: "专注训练", code: "FOCUS TRAINING", icon: "PhTimer", route: "/study", x: "51%", y: "40%", tone: "cyan" },
  { label: "AI 导师", code: "AI MENTOR", icon: "PhSparkle", route: "/counselor", x: "63%", y: "69%", tone: "violet" },
  { label: "校园探索", code: "CAMPUS MAP", icon: "PhMapTrifold", route: "/classrooms", x: "74%", y: "38%", tone: "cyan" },
  { label: "校园社区", code: "CAMPUS WORLD", icon: "PhChatsCircle", route: "/community", x: "86%", y: "68%", tone: "emerald" },
  { label: "成长记录", code: "GROWTH", icon: "PhChartLineUp", route: "/profile", x: "91%", y: "31%", tone: "violet" },
  { label: "设置中心", code: "SETTINGS", icon: "PhGear", route: "/profile/settings", x: "95%", y: "83%", tone: "cyan" },
];

const utilityNodes = [
  { label: "办事大厅", icon: "PhBuildings", route: "/services" },
  { label: "失物中心", icon: "PhMagnifyingGlass", route: "/lostfound" },
];
</script>

<template>
  <nav class="rpg-world-map" aria-label="校园世界地图导航">
    <div class="rpg-energy-road" aria-hidden="true"><i></i><i></i><i></i></div>
    <button
      v-for="node in nodes"
      :key="node.route"
      class="rpg-world-node"
      :class="node.tone"
      :style="{ '--node-x': node.x, '--node-y': node.y }"
      :aria-label="`${node.label} ${node.code}`"
      @click="emit('navigate', node.route)"
    >
      <span><UiIcon :name="node.icon" :size="20" weight="duotone" /><b v-if="node.badge">{{ node.badge }}</b></span>
      <strong>{{ node.label }}</strong>
      <small>{{ node.code }}</small>
    </button>
    <div class="rpg-world-utilities">
      <button v-for="node in utilityNodes" :key="node.route" @click="emit('navigate', node.route)">
        <UiIcon :name="node.icon" :size="17" /><span>{{ node.label }}</span><UiIcon name="PhArrowUpRight" :size="13" />
      </button>
    </div>
  </nav>
</template>

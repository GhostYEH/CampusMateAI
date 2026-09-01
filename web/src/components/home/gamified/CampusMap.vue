<script setup>
import UiIcon from "../../UiIcon.vue";

const emit = defineEmits(["navigate"]);
const locations = [
  { label: "专注训练场", code: "FOCUS", icon: "PhTimer", route: "/study", position: "north-west" },
  { label: "AI 基地", code: "AI BASE", icon: "PhSparkle", route: "/counselor", position: "north-east" },
  { label: "教学空间", code: "CLASSROOM", icon: "PhChalkboardTeacher", route: "/classrooms", position: "mid-west" },
  { label: "校园中心", code: "SERVICES", icon: "PhBuildings", route: "/services", position: "mid-east" },
  { label: "失物中心", code: "LOST & FOUND", icon: "PhMagnifyingGlass", route: "/lostfound", position: "south-west" },
  { label: "挑战大厅", code: "EXAMS", icon: "PhExam", route: "/exams", position: "south-east" },
];
</script>

<template>
  <section class="rpg-campus-map rpg-hud-panel" aria-labelledby="campus-map-title">
    <header class="rpg-panel-header">
      <div><span class="rpg-kicker">CAMPUS MAP · 6 LOCATIONS</span><h2 id="campus-map-title">校园地图</h2></div>
      <UiIcon name="PhMapTrifold" :size="22" />
    </header>
    <div class="rpg-map-field">
      <div class="rpg-map-core" aria-hidden="true"><UiIcon name="PhGraduationCap" :size="25" weight="duotone" /><small>CAMPUS</small><strong>CORE</strong></div>
      <button v-for="location in locations" :key="location.route" :class="location.position" @click="emit('navigate', location.route)">
        <span><UiIcon :name="location.icon" :size="19" /></span>
        <strong>{{ location.label }}</strong>
        <small>{{ location.code }}</small>
      </button>
    </div>
  </section>
</template>

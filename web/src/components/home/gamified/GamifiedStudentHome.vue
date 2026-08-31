<script setup>
import UiIcon from "../../UiIcon.vue";

defineProps({ state: { type: Object, required: true } });
const emit = defineEmits(["navigate", "reload"]);
</script>

<template>
  <main class="student-page gamified-home">
    <div v-if="state.error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ state.error }}<button class="link-button" @click="emit('reload')">重试</button></div>
    <section v-if="state.loading" class="student-home-skeleton" aria-label="正在加载游戏化首页"><div v-for="i in 4" :key="i" class="home-skeleton-panel"></div></section>
    <section v-else class="gamified-home-placeholder" aria-label="成长首页"><h1>校园成长地图</h1><p>你的真实课程、任务与专注记录正在汇聚到这里。</p><button class="primary-button" @click="emit('navigate', '/study')">开始一次专注</button></section>
  </main>
</template>

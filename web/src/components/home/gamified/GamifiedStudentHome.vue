<script setup>
import { computed } from "vue";
import CampusHotPostsPanel from "../../CampusHotPostsPanel.vue";
import UiIcon from "../../UiIcon.vue";
import HomeFooter from "../footer/HomeFooter.vue";
import { selectUpcomingExam } from "../../../features/dashboard/dashboardModel";
import DailyAdventureCard from "./DailyAdventureCard.vue";
import GrowthAndAchievements from "./GrowthAndAchievements.vue";
import MainQuestSection from "./MainQuestSection.vue";
import PlayerHeader from "./PlayerHeader.vue";

const props = defineProps({ state: { type: Object, required: true } });
const emit = defineEmits(["navigate", "reload"]);

const nextExam = computed(() => selectUpcomingExam(props.state.exams, new Date(props.state.now)));
const sideQuests = [
  { label: "专注挑战", detail: "开始一段真实专注", icon: "PhTimer", route: "/study", tone: "streak" },
  { label: "AI 校园助手", detail: "梳理学习与校园问题", icon: "PhRobot", route: "/counselor", tone: "quest" },
  { label: "探索地点", detail: "查询当前空教室", icon: "PhMapTrifold", route: "/classrooms", tone: "map" },
  { label: "校园办事", detail: "进入校园服务大厅", icon: "PhBuildings", route: "/services", tone: "service" },
  { label: "校园寻物", detail: "浏览失物招领信息", icon: "PhMagnifyingGlass", route: "/lostfound", tone: "find" },
  { label: "挑战日程", detail: "查看考试安排", icon: "PhExam", route: "/exams", tone: "xp" },
];

function openPost(postId) {
  emit("navigate", `/community/${postId}`);
}
</script>

<template>
  <main class="student-page gamified-home">
    <div v-if="state.error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ state.error }}<button class="link-button" @click="emit('reload')">重试</button></div>
    <section v-if="state.loading" class="game-loading" aria-label="正在加载游戏化首页" aria-busy="true">
      <div class="game-loading-player"></div><div class="game-loading-hero"></div><div class="game-loading-panel"></div><div class="game-loading-panel"></div>
    </section>

    <HomeFooter v-else>
      <PlayerHeader :user="state.user" :summary="state.gamification" />
      <DailyAdventureCard :summary="state.gamification" :next-exam="nextExam" :now="state.now" @navigate="emit('navigate', $event)" />

      <div v-if="state.normalizedSearch" class="game-search-note"><UiIcon name="PhMagnifyingGlass" :size="16" />正在筛选首页内容，当前主线有 {{ state.filteredMainQuests.length }} 条匹配结果</div>

      <section class="game-dashboard-grid">
        <MainQuestSection :quests="state.filteredMainQuests" @navigate="emit('navigate', $event)" />
        <section class="game-panel game-side-quests" aria-labelledby="side-quest-title">
          <header class="game-panel-head"><div><span class="game-eyebrow">SIDE QUESTS</span><h2 id="side-quest-title">校园探索</h2></div><UiIcon name="PhMapTrifold" :size="23" /></header>
          <div class="game-side-grid">
            <button v-for="quest in sideQuests" :key="quest.route" @click="emit('navigate', quest.route)"><span :class="quest.tone"><UiIcon :name="quest.icon" :size="21" /></span><strong>{{ quest.label }}</strong><small>{{ quest.detail }}</small><UiIcon name="PhCaretRight" :size="14" /></button>
          </div>
        </section>
      </section>

      <GrowthAndAchievements :summary="state.gamification" />

      <section class="game-panel game-campus-world" aria-labelledby="campus-world-title">
        <header class="game-panel-head"><div><span class="game-eyebrow">CAMPUS WORLD</span><h2 id="campus-world-title">校园世界</h2></div><button @click="emit('navigate', '/community')">进入社区<UiIcon name="PhArrowRight" :size="15" /></button></header>
        <CampusHotPostsPanel v-if="state.visibleHotPosts.length" :posts="state.visibleHotPosts" @open-post="openPost" />
        <div v-else class="game-empty compact" role="status"><span><UiIcon name="PhChatsCircle" :size="28" /></span><strong>校园世界暂时安静</strong><p>社区出现新的公开动态后，会继续使用原数据源显示在这里。</p><button @click="emit('navigate', '/community')">去社区看看</button></div>
      </section>
    </HomeFooter>
  </main>
</template>

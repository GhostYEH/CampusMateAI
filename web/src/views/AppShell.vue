<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter, RouterView } from "vue-router";
import { useAppStore } from "../stores/app";
import UiIcon from "../components/UiIcon.vue";

const store = useAppStore();
const route = useRoute();
const router = useRouter();
const collapsed = ref(false);
const mobileOpen = ref(false);
const search = ref("");
const roleMenus = {
  student: [
    ["home","首页","PhHouse"],["courses","课程","PhBookOpen"],["tasks","待办","PhCheckSquare"],["counselor","AI 导员","PhRobot"],["notifications","通知整理","PhBell"],["study","学习陪伴","PhChartLineUp"],["profile","个人中心","PhUser"],
  ],
  teacher: [
    ["home","教师工作台","PhSquaresFour"],["courses","课程管理","PhBookOpen"],["publish","发布中心","PhPaperPlaneTilt"],["stats","教学统计","PhChartBar"],["profile","个人中心","PhUser"],
  ],
  admin: [
    ["home","管理概览","PhSquaresFour"],["users","用户管理","PhUsers"],["courses","课程管理","PhBookOpen"],["system","系统状态","PhGear"],
  ],
};
const menus = computed(() => roleMenus[store.session?.role || "student"]);
function go(section) { router.push(`/${section}`); mobileOpen.value = false; }
function logout() { store.logout(); router.replace("/login"); }
</script>

<template>
  <div class="app-layout" :class="{ collapsed }">
    <button class="mobile-menu" @click="mobileOpen = true" aria-label="打开导航"><UiIcon name="PhList" /></button>
    <div v-if="mobileOpen" class="mobile-backdrop" @click="mobileOpen = false"></div>
    <aside class="sidebar" :class="{ open: mobileOpen }">
      <div class="brand"><span class="brand-mark"><UiIcon name="PhGraduationCap" :size="23" weight="fill" /></span><div><strong>CampusMate AI</strong><small>校园信息中枢</small></div></div>
      <div class="profile-mini"><div class="avatar">{{ store.session?.name?.slice(0,1) }}</div><div><strong>{{ store.session?.name }}</strong><small>{{ store.session?.detail }}</small></div></div>
      <nav>
        <button v-for="[key,label,icon] in menus" :key="key" :class="{ active: route.path === `/${key}` }" @click="go(key)">
          <UiIcon :name="icon" :size="21" /><span>{{ label }}</span><b v-if="key === 'tasks' && store.pendingCount">{{ store.pendingCount }}</b><em v-if="key === 'counselor'">Mock</em>
        </button>
      </nav>
      <div class="sidebar-bottom"><button @click="collapsed = !collapsed"><UiIcon name="PhSidebarSimple" /><span>{{ collapsed ? "展开" : "收起" }}</span></button><button @click="logout"><UiIcon name="PhSignOut" /><span>退出登录</span></button></div>
    </aside>
    <div class="workspace">
      <header class="topbar">
        <div class="command-search"><UiIcon name="PhMagnifyingGlass" /><input v-model="search" placeholder="搜索课程、通知、文件、服务…" /><kbd>⌘ K</kbd></div>
        <div class="top-date"><UiIcon name="PhCalendarBlank" />第 12 周 · 2026年7月30日</div>
        <button class="icon-button notification-button" aria-label="通知"><UiIcon name="PhBell" /><i></i></button>
      </header>
      <RouterView :search-query="search" />
    </div>
  </div>
</template>

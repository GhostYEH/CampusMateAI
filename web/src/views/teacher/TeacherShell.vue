<script setup>
import { computed, ref } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import { useAppStore } from "../../stores/app";
import UiIcon from "../../components/UiIcon.vue";
import ToastHost from "../../components/teacher/ToastHost.vue";
import ConfirmHost from "../../components/teacher/ConfirmHost.vue";

const store = useAppStore();
const route = useRoute();
const router = useRouter();
const collapsed = ref(false);
const mobileOpen = ref(false);

const gridTemplate = computed(() => (collapsed.value ? "72px 1fr" : "232px 1fr"));

const menus = [
  { key: "home", label: "工作台", icon: "PhHouse", path: "/teacher", available: false },
  { key: "ai", label: "AI 教学助理", icon: "PhRobot", path: "/teacher/ai-assistant", available: false },
  { key: "analytics", label: "学情分析", icon: "PhChartBar", path: "/teacher/analytics", available: false },
  { key: "assignments", label: "作业管理", icon: "PhFileText", path: "/teacher/assignments", available: false },
  { key: "grading", label: "批改", icon: "PhPencilSimpleLine", path: "/teacher/grading", available: false },
  { key: "chaoxing", label: "学习通同步", icon: "PhGraduationCap", path: "/teacher/chaoxing", available: true },
];

const profileDetail = computed(
  () => store.session?.detail || store.session?.name || "教师端",
);

function go(path) {
  router.push(path);
  mobileOpen.value = false;
}

function isActive(path) {
  return route.path === path || route.path.startsWith(`${path}/`);
}

function logout() {
  store.logout();
  router.replace("/login");
}
</script>

<template>
  <div class="app-layout teacher-layout" :class="{ collapsed }" :style="{ gridTemplateColumns: gridTemplate }">
    <ToastHost /><ConfirmHost />
    <button class="mobile-menu" aria-label="打开导航" @click="mobileOpen = true"><UiIcon name="PhList" /></button>
    <div v-if="mobileOpen" class="mobile-backdrop" @click="mobileOpen = false"></div>
    <aside class="sidebar" :class="{ open: mobileOpen }">
      <div class="brand">
        <span class="brand-mark"><UiIcon name="PhGraduationCap" :size="23" weight="fill" /></span>
        <div><strong>CampusMate AI</strong><small>教师端</small></div>
      </div>
      <button class="profile-mini" @click="go('/teacher/chaoxing')">
        <span class="avatar">{{ store.session?.name?.slice(0, 1) || "师" }}</span>
        <span class="profile-mini-copy"><strong>{{ store.session?.name || "教师" }}</strong><small>{{ profileDetail }}</small></span>
        <UiIcon name="PhCaretRight" :size="16" />
      </button>
      <nav aria-label="主导航">
        <button
          v-for="m in menus"
          :key="m.key"
          :class="{ active: m.available && isActive(m.path), disabled: !m.available }"
          :disabled="!m.available"
          :title="collapsed ? m.label : undefined"
          :aria-label="m.label"
          @click="m.available && go(m.path)"
        >
          <UiIcon :name="m.icon" :size="20" /><span>{{ m.label }}</span>
          <em v-if="!m.available" class="soon">即将上线</em>
        </button>
      </nav>
      <div class="sidebar-bottom">
        <button :title="collapsed ? '展开导航' : '收起导航'" :aria-label="collapsed ? '展开导航' : '收起导航'" @click="collapsed = !collapsed">
          <UiIcon :name="collapsed ? 'PhCaretRight' : 'PhCaretLeft'" /><span>{{ collapsed ? "展开" : "收起" }}</span>
        </button>
        <button title="退出登录" aria-label="退出登录" @click="logout"><UiIcon name="PhSignOut" /><span>退出登录</span></button>
      </div>
    </aside>
    <div class="workspace">
      <header class="topbar">
        <div class="top-title"><UiIcon name="PhChalkboardTeacher" :size="20" />教师工作台</div>
        <button class="icon-button" aria-label="学习通同步" @click="go('/teacher/chaoxing')"><UiIcon name="PhGraduationCap" :size="20" /></button>
      </header>
      <RouterView />
    </div>
  </div>
</template>

<style scoped>
.teacher-layout {
  min-height: 100dvh;
  display: grid;

  background: #f5f7fa;
}
.teacher-layout :deep(.mobile-menu) {
  display: none;
}
.teacher-layout :deep(.mobile-backdrop) {
  display: none;
}
.sidebar {
  background: #fff;
  border-right: 1px solid var(--line);
  padding: 18px 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: sticky;
  top: 0;
  height: 100dvh;
  overflow: auto;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 11px;
  background: var(--primary-soft);
  color: var(--primary);
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
}
.brand strong {
  font-size: 14px;
  display: block;
}
.brand small {
  font-size: 11px;
  color: var(--muted);
}
.profile-mini {
  width: 100%;
  border: 1px solid var(--line);
  background: #fbfcfd;
  border-radius: 12px;
  padding: 9px 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  text-align: left;
}
.profile-mini .avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  display: inline-grid;
  place-items: center;
  font-size: 14px;
  font-weight: 700;
  flex: 0 0 auto;
}
.profile-mini-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}
.profile-mini-copy strong {
  font-size: 13px;
}
.profile-mini-copy small {
  font-size: 11px;
  color: var(--muted);
}
nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}
nav button {
  border: 0;
  background: transparent;
  color: var(--text);
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  align-items: center;
  gap: 11px;
  font-size: 13px;
  font-weight: 550;
  width: 100%;
  text-align: left;
  position: relative;
}
nav button:hover:not(.disabled) {
  background: var(--primary-soft);
  color: var(--primary);
}
nav button.active {
  background: var(--primary-soft);
  color: var(--primary);
}
nav button.disabled {
  color: var(--muted);
  cursor: not-allowed;
  opacity: 0.7;
}
nav button span {
  flex: 1;
}
nav button .soon {
  font-size: 10px;
  font-style: normal;
  color: var(--muted);
  background: #eef1f4;
  padding: 1px 6px;
  border-radius: 999px;
}
.sidebar-bottom {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-top: 1px solid var(--line);
  padding-top: 10px;
}
.sidebar-bottom button {
  border: 0;
  background: transparent;
  color: var(--muted);
  border-radius: 10px;
  padding: 9px 12px;
  display: flex;
  align-items: center;
  gap: 11px;
  font-size: 12px;
  width: 100%;
  text-align: left;
}
.sidebar-bottom button:hover {
  background: #f1f4f7;
  color: var(--text);
}
.workspace {
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 56px;
  background: #fff;
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
  position: sticky;
  top: 0;
  z-index: 10;
}
.top-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 650;
  color: var(--text);
}
.icon-button {
  border: 0;
  background: transparent;
  color: var(--text);
  width: 36px;
  height: 36px;
  border-radius: 9px;
  display: inline-grid;
  place-items: center;
}
.icon-button:hover {
  background: var(--primary-soft);
  color: var(--primary);
}
@media (max-width: 880px) {
  .teacher-layout {
    grid-template-columns: 1fr;
  }
  .teacher-layout :deep(.mobile-menu) {
    display: inline-grid;
    place-items: center;
    position: fixed;
    top: 12px;
    left: 12px;
    z-index: 30;
    width: 40px;
    height: 40px;
    border-radius: 9px;
    border: 1px solid var(--line);
    background: #fff;
  }
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 25;
    width: 248px;
    transform: translateX(-100%);
    transition: transform 0.2s;
  }
  .sidebar.open {
    transform: none;
  }
  .teacher-layout :deep(.mobile-backdrop) {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(2, 12, 25, 0.45);
    z-index: 24;
  }
}
</style>
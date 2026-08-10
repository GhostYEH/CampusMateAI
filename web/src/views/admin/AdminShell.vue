<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import { useAppStore } from "../../stores/app";
import UiIcon from "../../components/UiIcon.vue";

const store = useAppStore();
const route = useRoute();
const router = useRouter();
const collapsed = ref(false);
const mobileOpen = ref(false);

const menus = [
  ["admin", "控制台", "PhGauge"],
  ["admin/knowledge", "知识库管理", "PhBooks"],
  ["admin/documents", "文档维护", "PhFileText"],
  ["admin/users", "账号管理", "PhUsers"],
];

function go(path) {
  router.push(`/${path}`);
  mobileOpen.value = false;
}

function isActive(key) {
  const path = `/${key}`;
  return route.path === path || route.path.startsWith(`${path}/`);
}

function logout() {
  store.logout();
  router.replace("/login");
}

const todayLabel = computed(() => new Intl.DateTimeFormat("zh-CN", {
  month: "long",
  day: "numeric",
  weekday: "short",
}).format(new Date()));

onMounted(() => { if (!store.backendOnline) void store.backendOnline; });
onUnmounted(() => {});
</script>

<template>
  <div class="admin-layout" :class="{ collapsed }">
    <button class="mobile-menu" aria-label="打开导航" @click="mobileOpen = true"><UiIcon name="PhList" /></button>
    <div v-if="mobileOpen" class="mobile-backdrop" @click="mobileOpen = false"></div>
    <aside class="admin-sidebar" :class="{ open: mobileOpen }">
      <div class="brand">
        <span class="brand-mark"><UiIcon name="PhShieldCheck" :size="23" weight="fill" /></span>
        <div><strong>CampusMate AI</strong><small>管理员控制台</small></div>
      </div>
      <button class="profile-mini">
        <span class="avatar">{{ store.session?.name?.slice(0, 1) || "管" }}</span>
        <span class="profile-mini-copy"><strong>{{ store.session?.name || "管理员" }}</strong><small>系统维护</small></span>
      </button>
      <nav aria-label="管理员导航">
        <button v-for="[key, label, icon] in menus" :key="key" :class="{ active: isActive(key) }" :aria-label="label" @click="go(key)">
          <UiIcon :name="icon" :size="20" /><span>{{ label }}</span>
        </button>
      </nav>
      <div class="sidebar-bottom">
        <button title="退出登录" aria-label="退出登录" @click="logout"><UiIcon name="PhSignOut" /><span>退出登录</span></button>
      </div>
    </aside>
    <div class="admin-workspace">
      <header class="admin-topbar">
        <div class="top-title">管理员控制台</div>
        <div class="top-date"><UiIcon name="PhCalendarBlank" :size="18" />{{ todayLabel }}</div>
        <div class="sync-pill" :class="{ offline: !store.backendOnline }"><UiIcon :name="store.backendOnline ? 'PhCheckCircle' : 'PhCloudSlash'" :size="18" />{{ store.backendOnline ? "后端已连接" : "后端未连接" }}</div>
      </header>
      <RouterView />
    </div>
  </div>
</template>

<style scoped>
.admin-layout { display: flex; min-height: 100vh; background: #f5f7fa; }
.admin-sidebar {
  width: 240px; background: #1f2937; color: #e5e7eb; display: flex; flex-direction: column;
  transition: width .2s; flex-shrink: 0;
}
.admin-layout.collapsed .admin-sidebar { width: 64px; }
.brand { display: flex; align-items: center; gap: 10px; padding: 18px 16px; border-bottom: 1px solid #374151; }
.brand-mark { width: 36px; height: 36px; border-radius: 10px; background: #2563eb; display: flex; align-items: center; justify-content: center; color: #fff; }
.brand strong { display: block; font-size: 14px; color: #fff; }
.brand small { font-size: 11px; color: #9ca3af; }
.profile-mini { display: flex; align-items: center; gap: 10px; padding: 12px 16px; background: transparent; border: none; color: #e5e7eb; cursor: pointer; text-align: left; }
.profile-mini .avatar { width: 32px; height: 32px; border-radius: 50%; background: #2563eb; display: flex; align-items: center; justify-content: center; font-weight: 600; }
.profile-mini-copy strong { display: block; font-size: 13px; }
.profile-mini-copy small { font-size: 11px; color: #9ca3af; }
nav { flex: 1; padding: 12px 8px; display: flex; flex-direction: column; gap: 4px; }
nav button { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border: none; background: transparent; color: #9ca3af; cursor: pointer; border-radius: 8px; font-size: 14px; text-align: left; }
nav button:hover { background: #374151; color: #fff; }
nav button.active { background: #2563eb; color: #fff; }
.sidebar-bottom { padding: 12px 8px; border-top: 1px solid #374151; }
.sidebar-bottom button { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border: none; background: transparent; color: #9ca3af; cursor: pointer; border-radius: 8px; font-size: 13px; width: 100%; }
.sidebar-bottom button:hover { background: #374151; color: #fff; }
.admin-workspace { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.admin-topbar { height: 56px; background: #fff; border-bottom: 1px solid #e5e7eb; display: flex; align-items: center; padding: 0 24px; gap: 16px; }
.top-title { font-weight: 600; font-size: 15px; }
.top-date { display: flex; align-items: center; gap: 6px; color: #6b7280; font-size: 13px; margin-left: auto; }
.sync-pill { display: flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 12px; background: #ecfdf5; color: #059669; }
.sync-pill.offline { background: #fef2f2; color: #dc2626; }
.mobile-menu { display: none; }
.mobile-backdrop { display: none; }
@media (max-width: 768px) {
  .mobile-menu { display: flex; position: fixed; top: 12px; left: 12px; z-index: 50; background: #1f2937; color: #fff; border: none; border-radius: 8px; padding: 8px; }
  .admin-sidebar { position: fixed; left: -260px; top: 0; bottom: 0; z-index: 40; transition: left .2s; }
  .admin-sidebar.open { left: 0; }
  .mobile-backdrop { display: block; position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 35; }
}
</style>
import { createRouter, createWebHistory } from "vue-router";
import LoginView from "./views/LoginView.vue";
import AppShell from "./views/AppShell.vue";
import DashboardView from "./views/DashboardView.vue";
import FeatureView from "./views/FeatureView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: LoginView, meta: { public: true } },
    { path: "/", component: AppShell, children: [
      { path: "", redirect: "/home" },
      { path: "home", component: DashboardView },
      { path: ":section", component: FeatureView },
    ]},
  ],
});
router.beforeEach((to) => {
  const session = localStorage.getItem("campus_session");
  if (!to.meta.public && !session) return "/login";
  if (to.path === "/login" && session) return "/home";
});
export default router;

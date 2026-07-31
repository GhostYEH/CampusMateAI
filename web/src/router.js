import { createRouter, createWebHistory } from "vue-router";
import LoginView from "./views/LoginView.vue";
import AppShell from "./views/AppShell.vue";
import DashboardView from "./views/DashboardView.vue";
import FeatureView from "./views/FeatureView.vue";
import TeacherPortalView from "./views/TeacherPortalView.vue";
import AdminPortalView from "./views/AdminPortalView.vue";
import StudentActivitiesView from "./views/StudentActivitiesView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: LoginView, meta: { public: true } },
    { path: "/", component: AppShell, children: [
      { path: "", redirect: "/home" },
      { path: "home", component: DashboardView },
      { path: "publish", component: TeacherPortalView, meta: { roles: ["teacher"] } },
      { path: "stats", component: TeacherPortalView, meta: { roles: ["teacher"] } },
      { path: "teacher-courses", component: TeacherPortalView, props: { section: "courses" }, meta: { roles: ["teacher"] } },
      { path: "users", component: AdminPortalView, meta: { roles: ["admin"] } },
      { path: "activities", component: AdminPortalView, meta: { roles: ["admin"] } },
      { path: "system", component: AdminPortalView, meta: { roles: ["admin"] } },
      { path: "campus-activities", component: StudentActivitiesView, meta: { roles: ["student"] } },
      { path: ":section", component: FeatureView, meta: { roles: ["student", "teacher", "admin"] } },
    ]},
  ],
});
router.beforeEach((to) => {
  const saved = localStorage.getItem("campus_session");
  let session = null;
  try { session = saved ? JSON.parse(saved) : null; } catch { localStorage.removeItem("campus_session"); }
  if (!to.meta.public && !session) return "/login";
  if (to.path === "/login" && session) return "/home";
  const roles = to.matched.flatMap((record) => record.meta.roles || []);
  if (session && roles.length && !roles.includes(session.role)) return "/home";
});
export default router;

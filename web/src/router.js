import { createRouter, createWebHistory } from "vue-router";
import LoginView from "./views/LoginView.vue";
import AppShell from "./views/AppShell.vue";
import DashboardView from "./views/DashboardView.vue";
import FeatureView from "./views/FeatureView.vue";
import AdminPortalView from "./views/AdminPortalView.vue";
import StudentActivitiesView from "./views/StudentActivitiesView.vue";

const TeacherDashboardView = () => import("./views/teacher/TeacherDashboardView.vue");
const TeacherCoursesView = () => import("./views/teacher/TeacherCoursesView.vue");
const TeacherCourseDetailView = () => import("./views/teacher/TeacherCourseDetailView.vue");
const TeacherAnnouncementsView = () => import("./views/teacher/TeacherAnnouncementsView.vue");
const TeacherAssignmentsView = () => import("./views/teacher/TeacherAssignmentsView.vue");
const TeacherAssignmentDetailView = () => import("./views/teacher/TeacherAssignmentDetailView.vue");
const TeacherGradingView = () => import("./views/teacher/TeacherGradingView.vue");
const TeacherAnalyticsView = () => import("./views/teacher/TeacherAnalyticsView.vue");
const TeacherAiAssistantView = () => import("./views/teacher/TeacherAiAssistantView.vue");

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: LoginView, meta: { public: true } },
    { path: "/", component: AppShell, children: [
      { path: "", redirect: "/home" },
      { path: "home", component: DashboardView },

      { path: "teacher/dashboard", component: TeacherDashboardView, meta: { roles: ["teacher"] } },
      { path: "teacher/courses", component: TeacherCoursesView, meta: { roles: ["teacher"] } },
      { path: "teacher/courses/:courseId", component: TeacherCourseDetailView, meta: { roles: ["teacher"] } },
      { path: "teacher/announcements", component: TeacherAnnouncementsView, meta: { roles: ["teacher"] } },
      { path: "teacher/assignments", component: TeacherAssignmentsView, meta: { roles: ["teacher"] } },
      { path: "teacher/assignments/:assignmentId", component: TeacherAssignmentDetailView, meta: { roles: ["teacher"] } },
      { path: "teacher/grading", component: TeacherGradingView, meta: { roles: ["teacher"] } },
      { path: "teacher/analytics", component: TeacherAnalyticsView, meta: { roles: ["teacher"] } },
      { path: "teacher/ai-assistant", component: TeacherAiAssistantView, meta: { roles: ["teacher"] } },

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
  const hasToken = Boolean(localStorage.getItem("campus_access_token"));
  let session = null;
  try { session = saved ? JSON.parse(saved) : null; } catch { localStorage.removeItem("campus_session"); }
  if (!hasToken) session = null;
  if (!to.meta.public && !session) return "/login";
  if (to.path === "/login" && session) return "/home";
  const roles = to.matched.flatMap((record) => record.meta.roles || []);
  if (session && roles.length && !roles.includes(session.role)) return "/home";
});
export default router;

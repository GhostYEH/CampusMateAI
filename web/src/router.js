import { createRouter, createWebHistory } from "vue-router";
import LoginView from "./views/LoginView.vue";
import AppShell from "./views/AppShell.vue";
import { createAppRoutes } from "./appRoutes";

const studentViews = {
  StudentSettingsView: () => import("./views/student/StudentSettingsView.vue"),
  StudentExamDetailView: () => import("./views/student/StudentExamDetailView.vue"),
  StudentExamEditView: () => import("./views/student/StudentExamEditView.vue"),
  StudentHomeView: () => import("./views/student/StudentHomeView.vue"),
  StudentCoursesView: () => import("./views/student/StudentCoursesView.vue"),
  StudentCourseDetailView: () => import("./views/student/StudentCourseDetailView.vue"),
  StudentTasksView: () => import("./views/student/StudentTasksView.vue"),
  StudentTaskDetailView: () => import("./views/student/StudentTaskDetailView.vue"),
  StudentCounselorView: () => import("./views/student/StudentCounselorView.vue"),
  StudentNotificationsView: () => import("./views/student/StudentNotificationsView.vue"),
  StudentAnnouncementDetailView: () => import("./views/student/StudentAnnouncementDetailView.vue"),
  StudentStudyView: () => import("./views/student/StudentStudyView.vue"),
  StudentProfileView: () => import("./views/student/StudentProfileView.vue"),
  StudentProfileHubView: () => import("./views/student/StudentProfileHubView.vue"),
  StudentExamsView: () => import("./views/student/StudentExamsView.vue"),
  StudentServicesView: () => import("./views/student/StudentServicesView.vue"),
  StudentServiceDetailView: () => import("./views/student/StudentServiceDetailView.vue"),
  StudentClassroomsView: () => import("./views/student/StudentClassroomsView.vue"),
  StudentLostFoundView: () => import("./views/student/StudentLostFoundView.vue"),
  StudentLostFoundDetailView: () => import("./views/student/StudentLostFoundDetailView.vue"),
  StudentChaoxingView: () => import("./views/student/StudentChaoxingView.vue"),
  StudentUniversityView: () => import("./views/student/StudentUniversityView.vue"),
  StudentCommunityView: () => import("./views/student/StudentCommunityView.vue"),
  StudentCommunityCreateView: () => import("./views/student/StudentCommunityCreateView.vue"),
  StudentCommunityDetailView: () => import("./views/student/StudentCommunityDetailView.vue"),
  StudentAcademicView: () => import("./views/student/StudentAcademicView.vue"),
};

const router = createRouter({
  history: createWebHistory(),
  routes: createAppRoutes({
    loginView: LoginView,
    appShell: AppShell,
    loadStudentView: (name) => studentViews[name],
  }),
});

router.beforeEach((to) => {
  const saved = localStorage.getItem("campus_session");
  const hasToken = Boolean(localStorage.getItem("campus_access_token"));
  let session = null;
  try { session = saved ? JSON.parse(saved) : null; } catch { localStorage.removeItem("campus_session"); }
  if (!hasToken) session = null;

  if (session && session.role !== "student") {
    localStorage.removeItem("campus_session");
    localStorage.removeItem("campus_access_token");
    localStorage.removeItem("campus_refresh_token");
    session = null;
  }

  if (!to.meta.public && !session) return "/login";
  if (to.path === "/login" && session) return "/home";

  const roles = to.matched.flatMap((record) => record.meta.roles || []);
  if (session && roles.length && !roles.includes(session.role)) return "/login";
});

export default router;

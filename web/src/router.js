import { createRouter, createWebHistory } from "vue-router";
import LoginView from "./views/LoginView.vue";
import AppShell from "./views/AppShell.vue";
import AdminShell from "./views/admin/AdminShell.vue";

const AdminDashboardView = () => import("./views/admin/AdminDashboardView.vue");
const AdminKnowledgeView = () => import("./views/admin/AdminKnowledgeView.vue");
const AdminRagIndexView = () => import("./views/admin/AdminRagIndexView.vue");
const AdminSystemView = () => import("./views/admin/AdminSystemView.vue");
const AdminUsersView = () => import("./views/admin/AdminUsersView.vue");
const AdminEduDiscoveryView = () => import("./views/admin/AdminEduDiscoveryView.vue");
const AdminCommunityView = () => import("./views/admin/AdminCommunityView.vue");
const StudentSettingsView = () => import("./views/student/StudentSettingsView.vue");
const StudentExamDetailView = () => import("./views/student/StudentExamDetailView.vue");
const StudentExamEditView = () => import("./views/student/StudentExamEditView.vue");
const StudentHomeView = () => import("./views/student/StudentHomeView.vue");
const StudentCoursesView = () => import("./views/student/StudentCoursesView.vue");
const StudentCourseDetailView = () => import("./views/student/StudentCourseDetailView.vue");
const StudentTasksView = () => import("./views/student/StudentTasksView.vue");
const StudentTaskDetailView = () => import("./views/student/StudentTaskDetailView.vue");
const StudentCounselorView = () => import("./views/student/StudentCounselorView.vue");
const StudentNotificationsView = () => import("./views/student/StudentNotificationsView.vue");
const StudentAnnouncementDetailView = () => import("./views/student/StudentAnnouncementDetailView.vue");
const StudentStudyView = () => import("./views/student/StudentStudyView.vue");
const StudentProfileView = () => import("./views/student/StudentProfileView.vue");
const StudentProfileHubView = () => import("./views/student/StudentProfileHubView.vue");
const StudentExamsView = () => import("./views/student/StudentExamsView.vue");
const StudentServicesView = () => import("./views/student/StudentServicesView.vue");
const StudentServiceDetailView = () => import("./views/student/StudentServiceDetailView.vue");
const StudentClassroomsView = () => import("./views/student/StudentClassroomsView.vue");
const StudentLostFoundView = () => import("./views/student/StudentLostFoundView.vue");
const StudentLostFoundDetailView = () => import("./views/student/StudentLostFoundDetailView.vue");
const StudentChaoxingView = () => import("./views/student/StudentChaoxingView.vue");
const StudentUniversityView = () => import("./views/student/StudentUniversityView.vue");
const StudentCommunityView = () => import("./views/student/StudentCommunityView.vue");
const StudentCommunityCreateView = () => import("./views/student/StudentCommunityCreateView.vue");
const StudentCommunityDetailView = () => import("./views/student/StudentCommunityDetailView.vue");
const StudentAcademicView = () => import("./views/student/StudentAcademicView.vue");

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: LoginView, meta: { public: true } },
    // 管理员控制台
    { path: "/admin", component: AdminShell, meta: { roles: ["admin"] }, children: [
      { path: "", name: "admin-home", component: AdminDashboardView },
      { path: "knowledge", component: AdminKnowledgeView },
      { path: "documents", component: AdminKnowledgeView },
      { path: "rag-index", component: AdminRagIndexView },
      { path: "system", component: AdminSystemView },
      { path: "users", component: AdminUsersView },
      { path: "edu-discovery", component: AdminEduDiscoveryView },
      { path: "community", component: AdminCommunityView },
    ]},
    // 学生端
    { path: "/", component: AppShell, children: [
      { path: "", redirect: "/home" },
      { path: "home", component: StudentHomeView, meta: { roles: ["student", "admin"] } },
      { path: "courses", component: StudentCoursesView, meta: { roles: ["student"] } },
      { path: "courses/:courseId", component: StudentCourseDetailView, meta: { roles: ["student"] } },
      { path: "tasks", component: StudentTasksView, meta: { roles: ["student"] } },
      { path: "tasks/:kind/:id", component: StudentTaskDetailView, meta: { roles: ["student"] } },
      { path: "community", component: StudentCommunityView, meta: { roles: ["student"] } },
      { path: "community/create", component: StudentCommunityCreateView, meta: { roles: ["student"] } },
      { path: "community/:postId", component: StudentCommunityDetailView, meta: { roles: ["student"] } },
      { path: "university", component: StudentUniversityView, meta: { roles: ["student"] } },
      { path: "counselor", component: StudentCounselorView, meta: { roles: ["student"] } },
      { path: "notifications", component: StudentNotificationsView, meta: { roles: ["student"] } },
      { path: "announcements/:announcementId", component: StudentAnnouncementDetailView, meta: { roles: ["student"] } },
      { path: "study", component: StudentStudyView, meta: { roles: ["student"] } },
      { path: "exams", component: StudentExamsView, meta: { roles: ["student"] } },
      { path: "exams/:examId", component: StudentExamDetailView, meta: { roles: ["student"] } },
      { path: "exams/:examId/edit", component: StudentExamEditView, meta: { roles: ["student"] } },
      { path: "services", component: StudentServicesView, meta: { roles: ["student"] } },
      { path: "services/:requestId", component: StudentServiceDetailView, meta: { roles: ["student"] } },
      { path: "classrooms", component: StudentClassroomsView, meta: { roles: ["student"] } },
      { path: "lostfound", component: StudentLostFoundView, meta: { roles: ["student"] } },
      { path: "lostfound/:itemId", component: StudentLostFoundDetailView, meta: { roles: ["student"] } },
      { path: "profile", component: StudentProfileView, meta: { roles: ["student"] } },
      { path: "profile/chaoxing", name: "student-chaoxing", component: StudentChaoxingView, meta: { roles: ["student"] } },
      { path: "profile/academic", component: StudentAcademicView, meta: { roles: ["student"] } },
      { path: "profile/settings", component: StudentSettingsView, meta: { roles: ["student"] } },
      { path: "profile/:section", component: StudentProfileHubView, meta: { roles: ["student"] } },
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
  if (to.path === "/login" && session) {
    // 按角色跳转到对应入口
    return session.role === "admin" ? "/admin" : "/home";
  }
  const roles = to.matched.flatMap((record) => record.meta.roles || []);
  if (session && roles.length && !roles.includes(session.role)) {
    // 角色不匹配:admin → /admin,其他 → /home
    return session.role === "admin" ? "/admin" : "/home";
  }
});
export default router;

import { createRouter, createWebHistory } from "vue-router";
import LoginView from "./views/LoginView.vue";
import AppShell from "./views/AppShell.vue";
import DashboardView from "./views/DashboardView.vue";
import FeatureView from "./views/FeatureView.vue";
import StudentActivitiesView from "./views/StudentActivitiesView.vue";
import StudentHomeView from "./views/student/StudentHomeView.vue";
import StudentCoursesView from "./views/student/StudentCoursesView.vue";
import StudentCourseDetailView from "./views/student/StudentCourseDetailView.vue";
import StudentTasksView from "./views/student/StudentTasksView.vue";
import StudentTaskDetailView from "./views/student/StudentTaskDetailView.vue";
import StudentActivityDetailView from "./views/student/StudentActivityDetailView.vue";
import StudentCounselorView from "./views/student/StudentCounselorView.vue";
import StudentNotificationsView from "./views/student/StudentNotificationsView.vue";
import StudentStudyView from "./views/student/StudentStudyView.vue";
import StudentProfileView from "./views/student/StudentProfileView.vue";
import StudentProfileHubView from "./views/student/StudentProfileHubView.vue";
import StudentExamsView from "./views/student/StudentExamsView.vue";
import StudentServicesView from "./views/student/StudentServicesView.vue";
import StudentServiceDetailView from "./views/student/StudentServiceDetailView.vue";
import StudentClassroomsView from "./views/student/StudentClassroomsView.vue";
import StudentLostFoundView from "./views/student/StudentLostFoundView.vue";
import StudentLostFoundDetailView from "./views/student/StudentLostFoundDetailView.vue";
import ProfileRouteView from "./views/ProfileRouteView.vue";
import AdminProfileView from "./views/admin/AdminProfileView.vue";
import HomeRouteView from "./views/HomeRouteView.vue";

const TeacherDashboardView = () => import("./views/teacher/TeacherDashboardView.vue");
const TeacherCoursesView = () => import("./views/teacher/TeacherCoursesView.vue");
const TeacherCourseDetailView = () => import("./views/teacher/TeacherCourseDetailView.vue");
const TeacherAnnouncementsView = () => import("./views/teacher/TeacherAnnouncementsView.vue");
const TeacherAssignmentsView = () => import("./views/teacher/TeacherAssignmentsView.vue");
const TeacherAssignmentDetailView = () => import("./views/teacher/TeacherAssignmentDetailView.vue");
const TeacherGradingView = () => import("./views/teacher/TeacherGradingView.vue");
const TeacherAnalyticsView = () => import("./views/teacher/TeacherAnalyticsView.vue");
const TeacherAiAssistantView = () => import("./views/teacher/TeacherAiAssistantView.vue");
const AdminDashboardView = () => import("./views/admin/AdminDashboardView.vue");
const AdminUsersView = () => import("./views/admin/AdminUsersView.vue");
const AdminActivitiesView = () => import("./views/admin/AdminActivitiesView.vue");
const AdminSystemView = () => import("./views/admin/AdminSystemView.vue");
const AdminPlaceholderView = () => import("./views/admin/AdminPlaceholderView.vue");
const AdminCoursesView = () => import("./views/admin/AdminCoursesView.vue");
const AdminCourseDetailView = () => import("./views/admin/AdminCourseDetailView.vue");
const AdminKnowledgeView = () => import("./views/admin/AdminKnowledgeView.vue");
const AdminAuditLogsView = () => import("./views/admin/AdminAuditLogsView.vue");
const AdminUserDetailView = () => import("./views/admin/AdminUserDetailView.vue");

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: LoginView, meta: { public: true } },
    { path: "/", component: AppShell, children: [
      { path: "", redirect: "/home" },
      { path: "home", component: HomeRouteView, meta: { roles: ["student", "teacher", "admin"] } },
      { path: "courses", component: StudentCoursesView, meta: { roles: ["student"] } },
      { path: "courses/:courseId", component: StudentCourseDetailView, meta: { roles: ["student"] } },
      { path: "tasks", component: StudentTasksView, meta: { roles: ["student"] } },
      { path: "tasks/:kind/:id", component: StudentTaskDetailView, meta: { roles: ["student"] } },
      { path: "campus-activities", component: StudentActivitiesView, meta: { roles: ["student"] } },
      { path: "campus-activities/:activityId", component: StudentActivityDetailView, meta: { roles: ["student"] } },
      { path: "counselor", component: StudentCounselorView, meta: { roles: ["student"] } },
      { path: "notifications", component: StudentNotificationsView, meta: { roles: ["student"] } },
      { path: "study", component: StudentStudyView, meta: { roles: ["student"] } },
      { path: "exams", component: StudentExamsView, meta: { roles: ["student"] } },
      { path: "services", component: StudentServicesView, meta: { roles: ["student"] } },
      { path: "services/:requestId", component: StudentServiceDetailView, meta: { roles: ["student"] } },
      { path: "classrooms", component: StudentClassroomsView, meta: { roles: ["student"] } },
      { path: "lostfound", component: StudentLostFoundView, meta: { roles: ["student"] } },
      { path: "lostfound/:itemId", component: StudentLostFoundDetailView, meta: { roles: ["student"] } },
      { path: "profile", component: ProfileRouteView, meta: { roles: ["student", "teacher", "admin"] } },
      { path: "profile/:section", component: StudentProfileHubView, meta: { roles: ["student"] } },

      { path: "teacher/dashboard", component: TeacherDashboardView, meta: { roles: ["teacher"] } },
      { path: "teacher/courses", component: TeacherCoursesView, meta: { roles: ["teacher"] } },
      { path: "teacher/courses/:courseId", component: TeacherCourseDetailView, meta: { roles: ["teacher"] } },
      { path: "teacher/announcements", component: TeacherAnnouncementsView, meta: { roles: ["teacher"] } },
      { path: "teacher/assignments", component: TeacherAssignmentsView, meta: { roles: ["teacher"] } },
      { path: "teacher/assignments/:assignmentId", component: TeacherAssignmentDetailView, meta: { roles: ["teacher"] } },
      { path: "teacher/grading", component: TeacherGradingView, meta: { roles: ["teacher"] } },
      { path: "teacher/analytics", component: TeacherAnalyticsView, meta: { roles: ["teacher"] } },
      { path: "teacher/ai-assistant", component: TeacherAiAssistantView, meta: { roles: ["teacher"] } },

      { path: "admin", redirect: "/admin/dashboard", meta: { roles: ["admin"] } },
      { path: "admin/dashboard", component: AdminDashboardView, meta: { roles: ["admin"] } },
      { path: "admin/users", component: AdminUsersView, meta: { roles: ["admin"] } },
      { path: "admin/users/:userId", component: AdminUserDetailView, meta: { roles: ["admin"] } },
      { path: "admin/activities", component: AdminActivitiesView, meta: { roles: ["admin"] } },
      { path: "admin/system", component: AdminSystemView, meta: { roles: ["admin"] } },
      { path: "admin/courses", component: AdminCoursesView, meta: { roles: ["admin"] } },
      { path: "admin/courses/:courseId", component: AdminCourseDetailView, meta: { roles: ["admin"] } },
      { path: "admin/knowledge", component: AdminKnowledgeView, meta: { roles: ["admin"] } },
      { path: "admin/audit", component: AdminAuditLogsView, meta: { roles: ["admin"] } },
      { path: "admin/courses", component: AdminPlaceholderView, props: { title: "课程与班级", detail: "课程、教学班和成员管理将在阶段二接入管理员专用接口。" }, meta: { roles: ["admin"] } },
      { path: "admin/knowledge", component: AdminPlaceholderView, props: { title: "内容与知识库", detail: "知识库管理员操作将在阶段三接入，并保留上传、解析与索引的真实状态。" }, meta: { roles: ["admin"] } },
      { path: "admin/audit", component: AdminPlaceholderView, props: { title: "操作日志", detail: "审计日志将在阶段二接入；当前页面不会伪造操作记录。" }, meta: { roles: ["admin"] } },
      { path: "profile-legacy", component: AdminProfileView, meta: { roles: ["admin"] } },
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

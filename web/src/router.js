import { createRouter, createWebHistory } from "vue-router";
import LoginView from "./views/LoginView.vue";
import AppShell from "./views/AppShell.vue";
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



const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: LoginView, meta: { public: true } },
    { path: "/", component: AppShell, children: [
      { path: "", redirect: "/home" },
      { path: "home", component: HomeRouteView, meta: { roles: ["student", "admin"] } },
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
      { path: "profile", component: StudentProfileView, meta: { roles: ["student"] } },
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
  if (to.path === "/login" && session) return "/home";
  const roles = to.matched.flatMap((record) => record.meta.roles || []);
  if (session && roles.length && !roles.includes(session.role)) return "/home";
});
export default router;

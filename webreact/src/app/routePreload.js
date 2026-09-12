const routePreloaders = Object.freeze({
  home: () => import("../pages/HomePage.jsx"),
  courses: () => import("../pages/ParityPages.jsx"),
  community: () => import("../pages/CommunityPage.jsx"),
  tasks: () => import("../pages/TasksPage.jsx"),
  counselor: () => import("../pages/CounselorPage.jsx"),
  notifications: () => import("../pages/NoticeCenterPage.jsx"),
  study: () => import("../pages/StudyPage.jsx"),
  profile: () => import("../pages/ProfilePage.jsx"),
  "agent": (path) => {
    const sub = String(path || "").split("/").filter(Boolean)[1];
    if (sub === "final-review") return import("../pages/FinalReviewPage.jsx");
    if (sub === "course-research") return import("../pages/CourseResearchPage.jsx");
    if (sub === "notice-workflow") return import("../pages/NoticeWorkflowPage.jsx");
    return null;
  },
});

export function preloadRoute(path) {
  const parts = String(path || "").split("/").filter(Boolean);
  const routeKey = parts[0];
  if (routeKey === "agent") return routePreloaders.agent?.(path);
  return routePreloaders[routeKey]?.();
}

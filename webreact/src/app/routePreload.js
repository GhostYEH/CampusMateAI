const routePreloaders = Object.freeze({
  home: () => import("../pages/HomePage.jsx"),
  courses: () => import("../pages/ParityPages.jsx"),
  community: () => import("../pages/CommunityPage.jsx"),
  tasks: () => import("../pages/TasksPage.jsx"),
  counselor: () => import("../pages/CounselorPage.jsx"),
  notifications: () => import("../pages/NoticeCenterPage.jsx"),
  study: () => import("../pages/StudyPage.jsx"),
  profile: () => import("../pages/ProfilePage.jsx"),
  "final-review": () => import("../pages/FinalReviewPage.jsx"),
  "course-research": () => import("../pages/CourseResearchPage.jsx"),
});

export function preloadRoute(path) {
  const routeKey = String(path || "").split("/").filter(Boolean)[0];
  return routePreloaders[routeKey]?.();
}

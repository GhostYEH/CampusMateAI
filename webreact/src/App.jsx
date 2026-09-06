import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppProvider, useApp } from "./app/AppContext.jsx";
import AppShell from "./components/AppShell.jsx";
import TypingPlaceholderLayer from "./components/TypingPlaceholderLayer.jsx";
import LoginPage from "./pages/LoginPage.jsx";

const lazyIntegrationPage = (name) => name === "SettingsPage" ? lazy(() => import("./pages/SettingsPage.jsx")) : lazy(() => import("./pages/IntegrationPages.jsx").then((module) => ({ default: module[name] })));
const lazyProfilePage = (name) => lazy(() => import("./pages/ProfileSecondaryPage.jsx").then((module) => ({ default: module[name] })));
const lazyToolPage = (name) => name === "NotificationsPage" ? lazy(() => import("./pages/NoticeCenterPage.jsx")) : name === "CommunityDetailPage" ? lazy(() => import("./pages/CommunityDetailPage.jsx")) : lazy(() => import("./pages/StudentToolPages.jsx").then((module) => ({ default: module[name] })));
const CounselorPage = lazy(() => import("./pages/CounselorPage.jsx"));
const TasksPage = lazy(() => import("./pages/TasksPage.jsx"));
const StudyPage = lazy(() => import("./pages/StudyPage.jsx"));
const CourseDetailPage = lazy(() => import("./pages/CourseDetailPage.jsx"));
const ProfilePage = lazy(() => import("./pages/ProfilePage.jsx"));
const CommunityPage = lazy(() => import("./pages/CommunityPage.jsx"));
const HomePage = lazy(() => import("./pages/HomePage.jsx"));
const TaskDetailPage = lazy(() => import("./pages/TaskDetailPage.jsx"));
const CommunityCreatePage = lazy(() => import("./pages/CommunityCreatePage.jsx"));
const UniversityPage = lazy(() => import("./pages/UniversityPage.jsx"));
const AnnouncementDetailPage = lazy(() => import("./pages/AnnouncementPage.jsx"));
const CoursesPage = lazy(() => import("./pages/ParityPages.jsx").then((module) => ({ default: module.CoursesParityPage })));
const ExamDetailPage = lazy(() => import("./pages/ParityPages.jsx").then((module) => ({ default: module.ExamDetailParityPage })));
const pages = {
  HomePage, CoursesPage, CourseDetailPage,
  TasksPage, TaskDetailPage, StudyPage,
  CommunityPage, CommunityCreatePage, CommunityDetailPage: lazyToolPage("CommunityDetailPage"),
  UniversityPage, CounselorPage, NotificationsPage: lazyToolPage("NotificationsPage"),
  AnnouncementDetailPage, ExamsPage: lazyToolPage("ExamsPage"), ExamDetailPage,
  ExamEditPage: lazyToolPage("ExamEditPage"),
  ProfilePage, ProfileSectionPage: lazyProfilePage("ProfileSectionPage"),
  SettingsPage: lazyIntegrationPage("SettingsPage"), AcademicPage: lazyIntegrationPage("AcademicPage"), ChaoxingPage: lazyIntegrationPage("ChaoxingPage"),
};

function GuardedLayout() {
  const { session } = useApp();
  const location = useLocation();
  if (!session) return <Navigate to="/login" replace state={{ from: location }} />;
  return <AppShell />;
}

function Page({ name }) {
  return <Suspense fallback={<div className="state-card loading-state page-loading"><span className="loading-orb" /><p>正在打开页面…</p></div>}><PageResolver name={name} /></Suspense>;
}

function PageResolver({ name }) {
  const Component = pages[name];
  return Component ? <Component /> : <Navigate to="/home" replace />;
}

export default function App() {
  useEffect(() => { document.documentElement.lang = "zh-CN"; }, []);
  return <AppProvider><TypingPlaceholderLayer /><Routes><Route path="/login" element={<LoginPage />} /><Route element={<GuardedLayout />}><Route path="/" element={<Navigate to="/home" replace />} /><Route path="/home" element={<Page name="HomePage" />} /><Route path="/courses" element={<Page name="CoursesPage" />} /><Route path="/courses/:courseId" element={<Page name="CourseDetailPage" />} /><Route path="/tasks" element={<Page name="TasksPage" />} /><Route path="/tasks/:kind/:id" element={<Page name="TaskDetailPage" />} /><Route path="/community" element={<Page name="CommunityPage" />} /><Route path="/community/create" element={<Page name="CommunityCreatePage" />} /><Route path="/community/:postId" element={<Page name="CommunityDetailPage" />} /><Route path="/university" element={<Page name="UniversityPage" />} /><Route path="/counselor" element={<Page name="CounselorPage" />} /><Route path="/notifications" element={<Page name="NotificationsPage" />} /><Route path="/announcements/:announcementId" element={<Page name="AnnouncementDetailPage" />} /><Route path="/study" element={<Page name="StudyPage" />} /><Route path="/exams" element={<Page name="ExamsPage" />} /><Route path="/exams/:examId" element={<Page name="ExamDetailPage" />} /><Route path="/exams/:examId/edit" element={<Page name="ExamEditPage" />} /><Route path="/profile" element={<Page name="ProfilePage" />} /><Route path="/profile/chaoxing" element={<Page name="ChaoxingPage" />} /><Route path="/profile/academic" element={<Page name="AcademicPage" />} /><Route path="/profile/settings" element={<Page name="SettingsPage" />} /><Route path="/profile/:section" element={<Page name="ProfileSectionPage" />} /></Route><Route path="*" element={<Navigate to="/" replace />} /></Routes></AppProvider>;
}

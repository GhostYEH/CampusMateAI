import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { Avatar, IconButton, SearchField } from "open-glass-ui";
import { getAssignments, getCourses } from "../data/api.js";
import { itemsOf } from "../data/contracts.js";
import { useApp } from "../app/AppContext.jsx";
import { preloadRoute } from "../app/routePreload.js";
import { isMagicClassImmersivePath } from "../app/shellMode.js";
import SmoothCursor from "./SmoothCursor.jsx";
import GlassSurface from "./GlassSurface.jsx";
import { Icon } from "./Icon.jsx";
import FloatingNav from "./FloatingNav/FloatingNav.jsx";
import VisualEffectBoundary from "./VisualEffectBoundary.jsx";
import { readStudyScene, STUDY_SCENE_ASSETS } from "../features/study/scenes.js";

const list = itemsOf;
const IRIDESCENCE_COLOR = Object.freeze([0.68, 0.78, 1]);
const Iridescence = lazy(() => import("./Iridescence.jsx"));
const Prism = lazy(() => import("./Prism.jsx"));

const topbarGlassProps = Object.freeze({
  height: "var(--topbar-control-height)",
  borderRadius: 32,
  borderWidth: 0.075,
  brightness: 72,
  opacity: 0.9,
  blur: 9,
  backgroundOpacity: 0.18,
  saturation: 1.35,
  distortionScale: -125,
  redOffset: 4,
  greenOffset: 12,
  blueOffset: 20,
  mixBlendMode: "screen",
});

function TopbarGlass({ children, className, disableEffects = false, ...props }) {
  return <GlassSurface {...topbarGlassProps} {...props} className={`topbar-chrome-glass ${className}`} displace={disableEffects ? 0 : 10}>{children}</GlassSurface>;
}

function SearchBox({ disableEffects = false }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const timer = useRef();
  useEffect(() => {
    if (query.trim().length < 2) { setResults([]); return undefined; }
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      setLoading(true);
      try {
        const [courses, assignments] = await Promise.all([getCourses(), getAssignments()]);
        const needle = query.trim().toLocaleLowerCase();
        const includes = (...values) => values.some((value) => String(value || "").toLocaleLowerCase().includes(needle));
        setResults([
          ...(list(courses).filter((item) => includes(item.name, item.code, item.semester)).map((item) => ({ title: item.name, detail: item.code || "课程详情", path: `/courses/${item.id}` }))),
          ...(list(assignments).filter((item) => includes(item.title, item.course_name, item.class_name)).map((item) => ({ title: item.title, detail: item.course_name || "课程作业", path: `/tasks/assignment/${item.id}` }))),
        ].slice(0, 8));
      } catch { setResults([]); } finally { setLoading(false); }
    }, 220);
    return () => clearTimeout(timer.current);
  }, [query]);
  const submitSearch = (event) => { if (event.key === "Enter" && query.trim()) { event.preventDefault(); navigate(`/home?q=${encodeURIComponent(query.trim())}`); setOpen(false); } };
  return <div className="search-wrap"><TopbarGlass className="topbar-search-surface" width="100%" disableEffects={disableEffects} role="search" aria-label="全局搜索"><SearchField className="topbar-search" label="全局搜索" name="global-search" value={query} onFocus={() => setOpen(true)} onValueChange={(value) => { setQuery(value); setOpen(true); }} onKeyDown={submitSearch} placeholder="搜索课程、作业…" /><kbd className="topbar-search-shortcut">⌘ K</kbd></TopbarGlass>{open && query.trim().length >= 2 && <div className="search-results" role="listbox">{loading ? <span>正在搜索…</span> : <>{results.map((item) => <button key={item.path} onClick={() => { navigate(item.path); setQuery(""); setOpen(false); }}><Icon name="PhArrowUpRight" size={15} /><span><strong>{item.title}</strong><small>{item.detail}</small></span></button>)}<button className="search-home-result" onClick={() => { navigate(`/home?q=${encodeURIComponent(query.trim())}`); setQuery(""); setOpen(false); }}><Icon name="PhMagnifyingGlass" size={15} /><span><strong>在首页筛选全部结果</strong><small>{query.trim()}</small></span></button></>}</div>}</div>;
}

export default function AppShell() {
  const { session, unreadCount, pendingCount, reduceMotion } = useApp();
  const location = useLocation();
  const navigate = useNavigate();
  const [systemReducedMotion, setSystemReducedMotion] = useState(() => window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false);
  const isHome = location.pathname === "/home";
  const isCourses = location.pathname.startsWith("/courses");
  const isMagicClassImmersive = isMagicClassImmersivePath(location.pathname);
  const isCounselor = location.pathname.startsWith("/counselor");
  const isProfile = location.pathname === "/profile";
  const isStudy = ["/study", "/island", "/plans", "/docs", "/statistics"].some((route) => location.pathname === route || location.pathname.startsWith(`${route}/`));
  const [studyScene, setStudyScene] = useState(() => readStudyScene());
  const motionPaused = reduceMotion || systemReducedMotion;
  const today = useMemo(() => new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" }).format(new Date()).replace("星期", "周"), []);
  const displayName = session?.name || session?.username || "同学";
  useEffect(() => { const onKey = (event) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); document.querySelector('[name="global-search"]')?.focus(); } }; window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey); }, []);
  useEffect(() => {
    const mediaQuery = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mediaQuery) return undefined;
    const syncMotionPreference = () => setSystemReducedMotion(mediaQuery.matches);
    mediaQuery.addEventListener?.("change", syncMotionPreference);
    return () => mediaQuery.removeEventListener?.("change", syncMotionPreference);
  }, []);
  useEffect(() => {
    const syncStudyScene = (event) => setStudyScene(event.detail || readStudyScene());
    window.addEventListener("campus-study-scene-change", syncStudyScene);
    return () => window.removeEventListener("campus-study-scene-change", syncStudyScene);
  }, []);
  const studyBackgroundStyle = isStudy ? { "--study-global-image": `url("${STUDY_SCENE_ASSETS[studyScene]}")` } : undefined;
  const pageEffects = <VisualEffectBoundary><Suspense fallback={null}>{isCourses && <Iridescence className="app-iridescence" color={IRIDESCENCE_COLOR} speed={0.38} amplitude={0.14} mouseReact={!motionPaused} paused={motionPaused} />}{isCounselor && <Prism className="app-counselor-prism" animationType="3drotate" timeScale={0.34} height={4.8} baseWidth={7.4} scale={2.2} hueShift={-0.12} colorFrequency={1.05} noise={0.012} glow={0.75} bloom={1.1} suspendWhenOffscreen={false} paused={motionPaused} />}{isProfile && <Prism className="app-profile-prism" animationType="3drotate" timeScale={0.2} height={4.3} baseWidth={5.8} scale={1.25} hueShift={0.1} colorFrequency={0.95} noise={0.008} glow={0.9} bloom={1.05} suspendWhenOffscreen={false} paused={motionPaused} />}</Suspense></VisualEffectBoundary>;
  return <div style={studyBackgroundStyle} className={`app-layout ${isCourses ? "iridescence-background-active" : ""} ${isMagicClassImmersive ? "magicclass-shell" : ""} ${isCounselor ? "counselor-mode" : ""} ${isProfile ? "profile-mode" : ""} ${isStudy ? "study-mode" : ""} ${reduceMotion ? "reduce-motion" : ""}`}>{pageEffects}{!isProfile && <SmoothCursor pointsCount={32} lineWidth={0.45} springStrength={0.38} dampening={0.52} color="var(--blue)" blur={3} mixBlendMode="screen" velocityScale trailOpacity={0.24} smoothFactor={1.4} paused={motionPaused} />}<a className="skip-link" href="#main-content">跳到主要内容</a>
    <div className="app-content"><header className="topbar"><SearchBox disableEffects={motionPaused} /><FloatingNav pendingCount={pendingCount} unreadCount={unreadCount} reduceMotion={motionPaused} onIntent={preloadRoute} /><TopbarGlass className="topbar-info-surface" width="auto" disableEffects={motionPaused} role="group" aria-label="账户与通知"><div className="topbar-info"><span className="topbar-date">{today}</span><div className="topbar-actions"><IconButton className="topbar-notification" aria-label="通知" onClick={() => navigate("/notifications")}><Icon name="PhBell" size={18} /></IconButton><button className="topbar-account" aria-label="个人中心" onClick={() => navigate("/profile")}><Avatar name={displayName} src={session?.avatar_url || "/assets/generated/home-reference-student-avatar.png"} size="small" /><Icon name="PhCaretDown" size={14} /></button></div></div></TopbarGlass></header><div className="route-stage"><Outlet /></div></div>
  </div>;
}

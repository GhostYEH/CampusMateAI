import { useEffect, useMemo, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { getAssignments, getCourses } from "../data/api.js";
import { itemsOf } from "../data/contracts.js";
import { useApp } from "../app/AppContext.jsx";
import Iridescence from "./Iridescence.jsx";
import Prism from "./Prism.jsx";
import SmoothCursor from "./SmoothCursor.jsx";
import { Icon } from "./Icon.jsx";
import FloatingNav from "./FloatingNav/FloatingNav.jsx";

const list = itemsOf;
const IRIDESCENCE_COLOR = Object.freeze([0.68, 0.78, 1]);

function SearchBox() {
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
  return <div className="search-wrap"><label className="topbar-search"><Icon name="PhMagnifyingGlass" size={17} /><input name="global-search" value={query} onFocus={() => setOpen(true)} onChange={(event) => { setQuery(event.target.value); setOpen(true); }} onKeyDown={submitSearch} placeholder="搜索课程、作业…" /><kbd>⌘ K</kbd></label>{open && query.trim().length >= 2 && <div className="search-results" role="listbox">{loading ? <span>正在搜索…</span> : <>{results.map((item) => <button key={item.path} onClick={() => { navigate(item.path); setQuery(""); setOpen(false); }}><Icon name="PhArrowUpRight" size={15} /><span><strong>{item.title}</strong><small>{item.detail}</small></span></button>)}<button className="search-home-result" onClick={() => { navigate(`/home?q=${encodeURIComponent(query.trim())}`); setQuery(""); setOpen(false); }}><Icon name="PhMagnifyingGlass" size={15} /><span><strong>在首页筛选全部结果</strong><small>{query.trim()}</small></span></button></>}</div>}</div>;
}

export default function AppShell() {
  const { session, unreadCount, pendingCount, reduceMotion, dashboardStyle } = useApp();
  const location = useLocation();
  const navigate = useNavigate();
  const [systemReducedMotion, setSystemReducedMotion] = useState(() => window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false);
  const isHome = location.pathname === "/home";
  const isCounselor = location.pathname.startsWith("/counselor");
  const isProfile = location.pathname === "/profile";
  const floatingNavTone = isCounselor || dashboardStyle === "gamified" ? "light" : "dark";
  const motionPaused = reduceMotion || systemReducedMotion;
  const today = useMemo(() => new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" }).format(new Date()).replace("星期", "周"), []);
  useEffect(() => { const onKey = (event) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); document.querySelector('[name="global-search"]')?.focus(); } }; window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey); }, []);
  useEffect(() => {
    const mediaQuery = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mediaQuery) return undefined;
    const syncMotionPreference = () => setSystemReducedMotion(mediaQuery.matches);
    mediaQuery.addEventListener?.("change", syncMotionPreference);
    return () => mediaQuery.removeEventListener?.("change", syncMotionPreference);
  }, []);
  return <div className={`app-layout ${isHome ? "home-background-active" : ""} ${isCounselor ? "counselor-mode" : ""} ${isProfile ? "profile-mode" : ""} ${reduceMotion ? "reduce-motion" : ""}`}>{isHome && <Iridescence className="app-iridescence" color={IRIDESCENCE_COLOR} speed={0.38} amplitude={0.14} mouseReact={!motionPaused} paused={motionPaused} />}{isCounselor && <Prism className="app-counselor-prism" animationType="3drotate" timeScale={0.34} height={4.8} baseWidth={7.4} scale={2.2} hueShift={-0.12} colorFrequency={1.05} noise={0.012} glow={0.75} bloom={1.1} suspendWhenOffscreen={false} paused={motionPaused} />}{isProfile && <Prism className="app-profile-prism" animationType="3drotate" timeScale={0.2} height={4.3} baseWidth={5.8} scale={1.25} hueShift={0.1} colorFrequency={0.95} noise={0.008} glow={0.9} bloom={1.05} suspendWhenOffscreen={false} paused={motionPaused} />}<SmoothCursor pointsCount={32} lineWidth={0.45} springStrength={0.38} dampening={0.52} color="var(--blue)" blur={3} mixBlendMode="screen" velocityScale trailOpacity={0.24} smoothFactor={1.4} paused={motionPaused} /><a className="skip-link" href="#main-content">跳到主要内容</a>
    <div className="app-content"><header className="topbar"><SearchBox /><FloatingNav tone={floatingNavTone} pendingCount={pendingCount} unreadCount={unreadCount} reduceMotion={reduceMotion} /><div className="topbar-info"><span className="topbar-date">{today}</span><div className="topbar-actions"><button className="icon-button" aria-label="通知" onClick={() => navigate("/notifications")}><Icon name="PhBell" size={18} /></button><button className="topbar-account" aria-label="个人中心" onClick={() => navigate("/profile")}><span className="avatar"><img src={session?.avatar_url || "/assets/generated/home-reference-student-avatar.png"} alt="" width="30" height="30" /></span><Icon name="PhCaretDown" size={14} /></button></div></div></header><div className="route-stage"><Outlet /></div></div>
  </div>;
}

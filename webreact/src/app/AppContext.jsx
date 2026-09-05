import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { applyTokenPair, getDashboard, login as loginRequest, probeBackend, revokeTrustedDevice, trustedDeviceAutoLogin } from "../data/api.js";
import { clearStoredSession, readStoredSession } from "./auth.js";

const AppContext = createContext(null);

function normalizeUser(user) {
  return {
    ...user,
    name: user?.name || user?.display_name || user?.username || "同学",
    detail: user?.detail || [user?.college, user?.major || user?.grade].filter(Boolean).join(" · ") || "学生",
  };
}

function readBoolean(key, fallback = false) {
  return localStorage.getItem(key) === "true" ? true : fallback;
}

export function AppProvider({ children }) {
  const [session, setSession] = useState(() => readStoredSession());
  const [backendOnline, setBackendOnline] = useState(false);
  const [dashboardSummary, setDashboardSummary] = useState(null);
  const [reduceMotion, setReduceMotionState] = useState(() => readBoolean("campus_reduce_motion"));
  const [dashboardStyle, setDashboardStyleState] = useState(() => localStorage.getItem("campus_dashboard_style") || "classic");
  const [tasks, setTasks] = useState(() => {
    try { return JSON.parse(localStorage.getItem("campus_tasks") || "[]"); } catch { return []; }
  });

  useEffect(() => { let active = true; probeBackend().then((online) => active && setBackendOnline(online)); return () => { active = false; }; }, []);
  useEffect(() => { localStorage.setItem("campus_tasks", JSON.stringify(tasks)); }, [tasks]);

  const persistSession = useCallback((user) => {
    const normalized = normalizeUser(user);
    localStorage.setItem("campus_session", JSON.stringify(normalized));
    setSession(normalized);
    return normalized;
  }, []);

  const login = useCallback(async (username, password) => {
    setBackendOnline(await probeBackend());
    const user = await loginRequest(username, password);
    return persistSession(user);
  }, [persistSession]);

  const applyQrLoginResult = useCallback((tokenPair) => {
    applyTokenPair(tokenPair);
    return persistSession(tokenPair.user);
  }, [persistSession]);

  const tryTrustedLogin = useCallback(async () => {
    try {
      const tokenPair = await trustedDeviceAutoLogin();
      applyTokenPair(tokenPair);
      persistSession(tokenPair.user);
      return true;
    } catch { return false; }
  }, [persistSession]);

  const logout = useCallback(() => {
    void revokeTrustedDevice();
    clearStoredSession();
    setSession(null);
  }, []);

  const toggleTask = useCallback((id) => setTasks((current) => current.map((task) => task.id === id ? { ...task, done: !task.done } : task)), []);
  const addTask = useCallback((title, due = "待设置", course = "个人待办", details = {}) => setTasks((current) => [{ id: Date.now(), title, due, course, done: false, ...details }, ...current]), []);
  const updateTask = useCallback((id, updates) => setTasks((current) => current.map((task) => task.id === id ? { ...task, ...updates } : task)), []);
  const deleteTask = useCallback((id) => setTasks((current) => current.filter((task) => task.id !== id)), []);
  const setReduceMotion = useCallback((value) => { setReduceMotionState(Boolean(value)); localStorage.setItem("campus_reduce_motion", String(Boolean(value))); }, []);
  const setDashboardStyle = useCallback((value) => { const next = value === "gamified" ? "gamified" : "classic"; setDashboardStyleState(next); localStorage.setItem("campus_dashboard_style", next); }, []);
  const refreshDashboard = useCallback(async () => { const value = await getDashboard(); setDashboardSummary(value); return value; }, []);
  useEffect(() => {
    if (!session) { setDashboardSummary(null); return undefined; }
    let active = true;
    getDashboard().then((value) => active && setDashboardSummary(value)).catch(() => {});
    return () => { active = false; };
  }, [session]);

  const value = useMemo(() => ({
    session, backendOnline, dashboardSummary, reduceMotion, dashboardStyle, tasks,
    pendingCount: Number(dashboardSummary?.pending_assignment_count || 0) + Number(dashboardSummary?.pending_personal_task_count || 0),
    unreadCount: Number(dashboardSummary?.unread_announcement_count || 0),
    setDashboardSummary, refreshDashboard, login, applyQrLoginResult, tryTrustedLogin, logout,
    toggleTask, addTask, updateTask, deleteTask, setReduceMotion, setDashboardStyle,
  }), [session, backendOnline, dashboardSummary, reduceMotion, dashboardStyle, tasks, refreshDashboard, login, applyQrLoginResult, tryTrustedLogin, logout, toggleTask, addTask, updateTask, deleteTask, setReduceMotion, setDashboardStyle]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const value = useContext(AppContext);
  if (!value) throw new Error("useApp must be used inside AppProvider");
  return value;
}

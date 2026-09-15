import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { applyTokenPair, getChaoxingStatus, getDashboard, getTodayAgenda, login as loginRequest, probeBackend, revokeTrustedDevice, trustedDeviceAutoLogin } from "../data/api.js";
import { createInFlightDeduper, normalizeTodayAgenda } from "../data/agendaModel.js";
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
  const [todayAgenda, setTodayAgenda] = useState(null);
  const [agendaLoading, setAgendaLoading] = useState(false);
  const [agendaError, setAgendaError] = useState("");
  const [chaoxingAuthState, setChaoxingAuthState] = useState("unknown");
  // 并发去重: 多个组件同时挂载时只允许一个在途请求，避免请求风暴。
  const agendaOnce = useRef(createInFlightDeduper());
  // 登录态探测每次会话最多自动触发一次，避免反复打学习通。
  const authProbeOnce = useRef(false);
  const [reduceMotion, setReduceMotionState] = useState(() => readBoolean("campus_reduce_motion"));
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
    localStorage.setItem("campus_trusted_device_enabled", "true");
    return persistSession(tokenPair.user);
  }, [persistSession]);

  const tryTrustedLogin = useCallback(async () => {
    if (localStorage.getItem("campus_trusted_device_enabled") !== "true") return false;
    try {
      const tokenPair = await trustedDeviceAutoLogin();
      if (!tokenPair) {
        localStorage.removeItem("campus_trusted_device_enabled");
        return false;
      }
      applyTokenPair(tokenPair);
      persistSession(tokenPair.user);
      return true;
    } catch { return false; }
  }, [persistSession]);

  const logout = useCallback(() => {
    void revokeTrustedDevice();
    localStorage.removeItem("campus_trusted_device_enabled");
    clearStoredSession();
    setSession(null);
  }, []);

  const toggleTask = useCallback((id) => setTasks((current) => current.map((task) => task.id === id ? { ...task, done: !task.done } : task)), []);
  const addTask = useCallback((title, due = "待设置", course = "个人待办", details = {}) => setTasks((current) => [{ id: Date.now(), title, due, course, done: false, ...details }, ...current]), []);
  const updateTask = useCallback((id, updates) => setTasks((current) => current.map((task) => task.id === id ? { ...task, ...updates } : task)), []);
  const deleteTask = useCallback((id) => setTasks((current) => current.filter((task) => task.id !== id)), []);
  const setReduceMotion = useCallback((value) => { setReduceMotionState(Boolean(value)); localStorage.setItem("campus_reduce_motion", String(Boolean(value))); }, []);
  const refreshDashboard = useCallback(async () => { const value = await getDashboard(); setDashboardSummary(value); return value; }, []);
  const refreshAgenda = useCallback(() => {
    setAgendaLoading(true);
    return agendaOnce.current(() => getTodayAgenda()
      .then((value) => {
        const normalized = normalizeTodayAgenda(value);
        setTodayAgenda(normalized);
        setAgendaError("");
        // 今日待办接口不触网，登录态只能读服务端进程内缓存。缓存为空且确实绑定了
        // 学习通时，非阻塞地探一次 /chaoxing/status（服务端 30s 缓存，不会形成风暴），
        // 否则用户会把"登录态过期"误读成"今天没有待办"。
        const chaoxing = normalized?.sources?.chaoxing;
        if (chaoxing?.authState && chaoxing.authState !== "unknown") {
          setChaoxingAuthState(chaoxing.authState);
        } else if (chaoxing && chaoxing.state !== "not_bound" && !authProbeOnce.current) {
          authProbeOnce.current = true;
          getChaoxingStatus()
            .then((status) => setChaoxingAuthState(status?.status || "unknown"))
            .catch(() => setChaoxingAuthState("unknown"));
        }
        return normalized;
      })
      .catch((error) => {
        setAgendaError(error?.response?.data?.detail || "今日待办加载失败，请稍后重试");
        return null;
      })
      .finally(() => { setAgendaLoading(false); }));
  }, []);
  useEffect(() => {
    if (!session) { setDashboardSummary(null); setTodayAgenda(null); setAgendaError(""); return undefined; }
    let active = true;
    getDashboard().then((value) => active && setDashboardSummary(value)).catch(() => {});
    void refreshAgenda();
    return () => { active = false; };
  }, [session, refreshAgenda]);

  const value = useMemo(() => ({
    session, backendOnline, dashboardSummary, reduceMotion, tasks,
    todayAgenda, agendaLoading, agendaError, refreshAgenda, chaoxingAuthState,
    // 全局待办角标与首页"待办事项"共用统一今日待办的 summary，
    // 不再由 dashboard 的 pending_assignment_count + pending_personal_task_count 拼出来。
    pendingCount: todayAgenda
      ? todayAgenda.summary.pending
      : Number(dashboardSummary?.pending_assignment_count || 0) + Number(dashboardSummary?.pending_personal_task_count || 0),
    unreadCount: Number(dashboardSummary?.unread_announcement_count || 0),
    setDashboardSummary, refreshDashboard, login, applyQrLoginResult, tryTrustedLogin, logout,
    toggleTask, addTask, updateTask, deleteTask, setReduceMotion,
  }), [session, backendOnline, dashboardSummary, reduceMotion, tasks, todayAgenda, agendaLoading, agendaError, refreshAgenda, chaoxingAuthState, refreshDashboard, login, applyQrLoginResult, tryTrustedLogin, logout, toggleTask, addTask, updateTask, deleteTask, setReduceMotion]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const value = useContext(AppContext);
  if (!value) throw new Error("useApp must be used inside AppProvider");
  return value;
}

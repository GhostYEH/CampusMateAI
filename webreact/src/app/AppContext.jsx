import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { applyTokenPair, getChaoxingStatus, getDashboard, getTodayAgenda, login as loginRequest, probeBackend, revokeTrustedDevice, trustedDeviceAutoLogin } from "../data/api.js";
import { createSessionScopedLoader, normalizeTodayAgenda, shouldProbeChaoxingAuth } from "../data/agendaModel.js";
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
  // 登录态探测每次会话最多自动触发一次，避免反复打学习通。
  const authProbeOnce = useRef(false);
  // 今日待办加载器：内部同时做"并发去重"和"按身份隔离 + 拒绝迟到回写"。
  // 身份一变就 reset()（见下面的 session effect 与 logout）。
  const agendaLoader = useRef(null);
  if (agendaLoader.current === null) {
    agendaLoader.current = createSessionScopedLoader({
      load: getTodayAgenda,
      onLoadingChange: setAgendaLoading,
      onError: (error) => setAgendaError(error?.response?.data?.detail || "今日待办加载失败，请稍后重试"),
      onData: (value, isCurrent) => {
        const normalized = normalizeTodayAgenda(value);
        setTodayAgenda(normalized);
        setAgendaError("");
        // 今日待办接口不触网，登录态只能读服务端进程内缓存。缓存为空、或缓存说
        // "已过期"（用户可能已在别处重新登录）时，每个会话非阻塞地复检一次
        // /chaoxing/status（服务端 30s 去重，不会形成风暴），否则用户会把
        // "登录态过期"误读成"今天没有待办"，或看到已经失效的过期提示。
        const chaoxing = normalized?.sources?.chaoxing;
        if (chaoxing?.authState && chaoxing.authState !== "unknown") {
          setChaoxingAuthState(chaoxing.authState);
        }
        if (shouldProbeChaoxingAuth(chaoxing) && !authProbeOnce.current) {
          authProbeOnce.current = true;
          getChaoxingStatus()
            .then((status) => { if (isCurrent()) setChaoxingAuthState(status?.status || "unknown"); })
            .catch(() => { if (isCurrent()) setChaoxingAuthState("unknown"); });
        }
      },
    });
  }
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
    // 立即作废在途请求：退出后账号 A 的迟到响应不得再回写任何状态。
    agendaLoader.current?.reset();
    // 立即清掉上一个用户的登录态观测与探测闸门，否则退出后仍会看到
    // "学习通登录态已过期"，且下一个用户不会触发自己的探测。
    authProbeOnce.current = false;
    setChaoxingAuthState("unknown");
    setTodayAgenda(null);
    setAgendaError("");
    setAgendaLoading(false);
  }, []);

  const toggleTask = useCallback((id) => setTasks((current) => current.map((task) => task.id === id ? { ...task, done: !task.done } : task)), []);
  const addTask = useCallback((title, due = "待设置", course = "个人待办", details = {}) => setTasks((current) => [{ id: Date.now(), title, due, course, done: false, ...details }, ...current]), []);
  const updateTask = useCallback((id, updates) => setTasks((current) => current.map((task) => task.id === id ? { ...task, ...updates } : task)), []);
  const deleteTask = useCallback((id) => setTasks((current) => current.filter((task) => task.id !== id)), []);
  const setReduceMotion = useCallback((value) => { setReduceMotionState(Boolean(value)); localStorage.setItem("campus_reduce_motion", String(Boolean(value))); }, []);
  const refreshDashboard = useCallback(async () => { const value = await getDashboard(); setDashboardSummary(value); return value; }, []);
  const refreshAgenda = useCallback(() => agendaLoader.current.refresh(), []);
  useEffect(() => {
    // 身份变化（登录/切换/退出）：作废在途请求并换新去重器。
    // 否则新账号会复用上一个账号还在途中的 Promise，拿到别人的数据；
    // 而 setTodayAgenda(null) 也拦不住迟到响应回写。
    agendaLoader.current.reset();
    // 登录态观测同样必须重置：否则第二个用户会继承前一个用户的 expired 提示，
    // 而且因为探测闸门已置位，永远不会触发属于自己的那次探测。
    authProbeOnce.current = false;
    setChaoxingAuthState("unknown");
    if (!session) { setDashboardSummary(null); setTodayAgenda(null); setAgendaError(""); setAgendaLoading(false); return undefined; }
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

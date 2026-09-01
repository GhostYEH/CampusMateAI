import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { probeBackend, realLogin, applyTokenPair, trustedDeviceAutoLogin, revokeTrustedDevice } from "../services/api";
import { loadDashboardStyle, persistDashboardStyle } from "../features/dashboard/dashboardStyle";

function _normalizeUser(user) {
  return {
    ...user,
    name: user.name || user.display_name || user.username,
    detail: user.detail || [user.college, user.major || user.grade].filter(Boolean).join(" · ") || "学生",
  };
}

function _persistSession(user) {
  const normalized = _normalizeUser(user);
  localStorage.setItem("campus_session", JSON.stringify(normalized));
  return normalized;
}

export const useAppStore = defineStore("app", () => {
  const accessToken = localStorage.getItem("campus_access_token");
  const savedSession = localStorage.getItem("campus_session");
  let parsedSession = null;
  try { parsedSession = savedSession ? JSON.parse(savedSession) : null; } catch { /* ignore invalid local state */ }
  if (!accessToken) localStorage.removeItem("campus_session");
  const session = ref(accessToken ? parsedSession : null);
  const backendOnline = ref(false);
  void probeBackend().then((online) => { backendOnline.value = online; });
  const reduceMotion = ref(localStorage.getItem("campus_reduce_motion") === "true");
  const dashboardStyle = ref(loadDashboardStyle(localStorage));
  const tasks = ref(JSON.parse(localStorage.getItem("campus_tasks") || "null") || []);
  const notices = ref([]);
  const dashboardSummary = ref(null);
  const pendingCount = computed(() => Number(dashboardSummary.value?.pending_assignment_count || 0) + Number(dashboardSummary.value?.pending_personal_task_count || 0));
  const unreadCount = computed(() => Number(dashboardSummary.value?.unread_announcement_count || 0));
  function setDashboardSummary(value) { dashboardSummary.value = value || null; }
  const persist = () => localStorage.setItem("campus_tasks", JSON.stringify(tasks.value));
  function toggleTask(id) { const t = tasks.value.find((x) => x.id === id); if (t) t.done = !t.done; persist(); }
  function addTask(title, due = "待设置", course = "个人待办", details = {}) { tasks.value.unshift({ id: Date.now(), title, due, course, done: false, ...details }); persist(); }
  function updateTask(id, updates) { const task = tasks.value.find((item) => item.id === id); if (task) Object.assign(task, updates); persist(); }
  function deleteTask(id) { tasks.value = tasks.value.filter((x) => x.id !== id); persist(); }
  async function login(username, password) {
    backendOnline.value = await probeBackend();
    if (!backendOnline.value) throw new Error("无法连接后端服务，请确认 FastAPI 已启动");
    const user = await realLogin(username, password);
    session.value = _persistSession(user);
    return session.value;
  }
  /** 扫码 exchange 成功后应用 TokenPair 并建立 session。 */
  function applyQrLoginResult(tokenPair) {
    applyTokenPair(tokenPair);
    session.value = _persistSession(tokenPair.user);
    return session.value;
  }
  /** 尝试用 trusted device cookie 自动登录，成功返回 true。 */
  async function tryTrustedDeviceAutoLogin() {
    try {
      const tokenPair = await trustedDeviceAutoLogin();
      applyTokenPair(tokenPair);
      session.value = _persistSession(tokenPair.user);
      return true;
    } catch {
      return false;
    }
  }
  function logout() {
    // 撤销可信设备凭据（避免退出后又被自动登录）
    void revokeTrustedDevice();
    localStorage.removeItem("campus_session");
    localStorage.removeItem("campus_access_token");
    localStorage.removeItem("campus_refresh_token");
    session.value = null;
  }
  function setReduceMotion(v) { reduceMotion.value = v; localStorage.setItem("campus_reduce_motion", String(v)); }
  function setDashboardStyle(value) { dashboardStyle.value = persistDashboardStyle(localStorage, value); }
  return { session, backendOnline, reduceMotion, dashboardStyle, tasks, notices, dashboardSummary, pendingCount, unreadCount, setDashboardSummary, login, applyQrLoginResult, tryTrustedDeviceAutoLogin, logout, toggleTask, addTask, updateTask, deleteTask, setReduceMotion, setDashboardStyle };
});

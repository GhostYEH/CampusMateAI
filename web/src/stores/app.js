import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { probeBackend, realLogin } from "../services/api";

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
  const tasks = ref(JSON.parse(localStorage.getItem("campus_tasks") || "null") || []);
  const notices = ref([]);
  const pendingCount = computed(() => tasks.value.filter((t) => !t.done).length);
  const persist = () => localStorage.setItem("campus_tasks", JSON.stringify(tasks.value));
  function toggleTask(id) { const t = tasks.value.find((x) => x.id === id); if (t) t.done = !t.done; persist(); }
  function addTask(title, due = "待设置", course = "个人待办", details = {}) { tasks.value.unshift({ id: Date.now(), title, due, course, done: false, ...details }); persist(); }
  function updateTask(id, updates) { const task = tasks.value.find((item) => item.id === id); if (task) Object.assign(task, updates); persist(); }
  function deleteTask(id) { tasks.value = tasks.value.filter((x) => x.id !== id); persist(); }
  async function login(username, password) {
    backendOnline.value = await probeBackend();
    if (!backendOnline.value) throw new Error("无法连接后端服务，请确认 FastAPI 已启动");
    const user = await realLogin(username, password);
    const normalized = {
      ...user,
      name: user.name || user.display_name || user.username,
      detail: user.detail || [user.college, user.major || user.grade].filter(Boolean).join(" · ") || ({ student: "学生", teacher: "教师", admin: "管理员" }[user.role]),
    };
    session.value = normalized;
    localStorage.setItem("campus_session", JSON.stringify(normalized));
    return normalized;
  }
  function logout() {
    localStorage.removeItem("campus_session");
    localStorage.removeItem("campus_access_token");
    localStorage.removeItem("campus_refresh_token");
    session.value = null;
  }
  function setReduceMotion(v) { reduceMotion.value = v; localStorage.setItem("campus_reduce_motion", String(v)); }
  return { session, backendOnline, reduceMotion, tasks, notices, pendingCount, login, logout, toggleTask, addTask, updateTask, deleteTask, setReduceMotion };
});

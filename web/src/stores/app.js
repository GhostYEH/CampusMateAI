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
  const tasks = ref(JSON.parse(localStorage.getItem("campus_tasks") || "null") || [
    { id: 1, title: "《数据结构》作业三：链表与栈", due: "今天 23:59", course: "课程作业", done: false },
    { id: 2, title: "《高等数学》习题课报告提交", due: "明天 20:00", course: "课程作业", done: false },
    { id: 3, title: "“互联网+”大赛校内选拔报名", due: "5月21日 18:00", course: "活动报名", done: false },
    { id: 4, title: "图书馆座位预约", due: "今天 14:00", course: "学习安排", done: true },
  ]);
  const notices = ref([
    { id: 1, title: "关于开展暑期社会实践活动的通知", source: "学生事务", time: "10:15", unread: true },
    { id: 2, title: "第十六届程序设计竞赛报名通知", source: "创新实践中心", time: "昨天", unread: true },
    { id: 3, title: "期末考试安排及相关事项说明", source: "教务处", time: "5月17日", unread: false },
    { id: 4, title: "图书馆数据库试用资源更新通知", source: "图书馆", time: "5月16日", unread: false },
  ]);
  const pendingCount = computed(() => tasks.value.filter((t) => !t.done).length);
  const persist = () => localStorage.setItem("campus_tasks", JSON.stringify(tasks.value));
  function toggleTask(id) { const t = tasks.value.find((x) => x.id === id); if (t) t.done = !t.done; persist(); }
  function addTask(title, due = "待设置", course = "个人待办", details = {}) { tasks.value.unshift({ id: Date.now(), title, due, course, done: false, ...details }); persist(); }
  function updateTask(id, updates) { const task = tasks.value.find((item) => item.id === id); if (task) Object.assign(task, updates); persist(); }
  function deleteTask(id) { tasks.value = tasks.value.filter((x) => x.id !== id); persist(); }
  async function login(username, password, expectedRole) {
    backendOnline.value = await probeBackend();
    if (!backendOnline.value) throw new Error("无法连接后端服务，请确认 FastAPI 已启动");
    const user = await realLogin(username, password);
    const normalized = {
      ...user,
      name: user.name || user.display_name || user.username,
      detail: user.detail || [user.college, user.major || user.grade].filter(Boolean).join(" · ") || ({ student: "学生", teacher: "教师", admin: "管理员" }[user.role]),
    };
    if (expectedRole && normalized.role !== expectedRole) {
      localStorage.removeItem("campus_access_token");
      localStorage.removeItem("campus_refresh_token");
      throw new Error(`该账号不是${{ student: "学生", teacher: "教师", admin: "管理员" }[expectedRole]}账号，请切换登录入口`);
    }
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

import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { probeBackend, realLogin } from "../services/api";

const demos = {
  student_demo: { name: "林知夏", role: "student", detail: "计算机学院 · 大二" },
  teacher_demo: { name: "张明远", role: "teacher", detail: "计算机学院 · 副教授" },
  admin_demo: { name: "系统管理员", role: "admin", detail: "信息中心" },
};
export const useAppStore = defineStore("app", () => {
  const session = ref(JSON.parse(localStorage.getItem("campus_session") || "null"));
  const backendOnline = ref(false);
  const mockMode = ref(localStorage.getItem("campus_mock_mode") !== "false");
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
  function addTask(title, due = "待设置") { tasks.value.unshift({ id: Date.now(), title, due, course: "个人待办", done: false }); persist(); }
  function deleteTask(id) { tasks.value = tasks.value.filter((x) => x.id !== id); persist(); }
  async function login(username, password) {
    backendOnline.value = mockMode.value ? false : await probeBackend();
    let user;
    if (backendOnline.value && !mockMode.value) user = await realLogin(username, password);
    else {
      if (!demos[username] || password !== "Demo123456") throw new Error("账号或密码不正确");
      user = demos[username];
    }
    session.value = user;
    localStorage.setItem("campus_session", JSON.stringify(user));
    return user;
  }
  function logout() { localStorage.removeItem("campus_session"); localStorage.removeItem("campus_access_token"); session.value = null; }
  function setReduceMotion(v) { reduceMotion.value = v; localStorage.setItem("campus_reduce_motion", String(v)); }
  return { session, backendOnline, mockMode, reduceMotion, tasks, notices, pendingCount, login, logout, toggleTask, addTask, deleteTask, setReduceMotion };
});

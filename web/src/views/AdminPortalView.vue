<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiIcon from "../components/UiIcon.vue";
import { useAppStore } from "../stores/app";
import {
  createActivity,
  createAdminUser,
  getActivities,
  getAdminOverview,
  getAdminUsers,
  updateActivityStatus,
  updateAdminUser,
} from "../services/portalRepository";

const props = defineProps({ section: { type: String, default: "" } });
const store = useAppStore();
const route = useRoute();
const router = useRouter();
const current = computed(() => props.section || route.path.slice(1) || "home");
const loading = ref(true);
const error = ref("");
const saving = ref(false);
const overview = ref(null);
const users = ref([]);
const activities = ref([]);
const userTotal = ref(0);
const activityTotal = ref(0);
const userQuery = ref("");
const userRole = ref("");
const userStatus = ref("");
const activityQuery = ref("");
const activityStatus = ref("");
const showUserForm = ref(false);
const showActivityForm = ref(false);
const toast = ref("");
const userForm = reactive({
  username: "",
  password: "",
  display_name: "",
  role: "student",
  student_number: "",
  teacher_number: "",
  college: "",
  major: "",
  grade: "",
});
const activityForm = reactive({
  title: "",
  summary: "",
  content: "",
  category: "campus",
  location: "",
  registration_deadline: "",
  starts_at: "",
  ends_at: "",
  capacity: null,
  status: "published",
});
const roleLabel = { student: "学生", teacher: "教师", admin: "管理员" };
const activityStatusLabel = { draft: "草稿", published: "报名中", closed: "已结束", archived: "已归档" };
const categoryLabel = { campus: "校园活动", academic: "学术交流", volunteer: "志愿服务", competition: "竞赛", lecture: "讲座", sports: "体育" };

function flash(message) {
  toast.value = message;
  window.setTimeout(() => { toast.value = ""; }, 2200);
}
function formatDate(value) {
  if (!value) return "待定";
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
function iso(value) {
  return value ? new Date(value).toISOString() : null;
}
async function loadOverview() {
  overview.value = await getAdminOverview();
}
async function loadUsers() {
  const response = await getAdminUsers({
    query: userQuery.value || undefined,
    role: userRole.value || undefined,
    is_active: userStatus.value === "" ? undefined : userStatus.value === "active",
  });
  users.value = response.items;
  userTotal.value = response.total;
}
async function loadActivities() {
  const response = await getActivities({
    query: activityQuery.value || undefined,
    status: activityStatus.value || undefined,
  });
  activities.value = response.items;
  activityTotal.value = response.total;
}
async function load() {
  loading.value = true;
  error.value = "";
  try { await Promise.all([loadOverview(), loadUsers(), loadActivities()]); }
  catch (err) { error.value = err.response?.data?.message || err.message || "管理数据加载失败"; }
  finally { loading.value = false; }
}
function resetUserForm() {
  Object.assign(userForm, { username: "", password: "", display_name: "", role: "student", student_number: "", teacher_number: "", college: "", major: "", grade: "" });
}
function resetActivityForm() {
  Object.assign(activityForm, { title: "", summary: "", content: "", category: "campus", location: "", registration_deadline: "", starts_at: "", ends_at: "", capacity: null, status: "published" });
}
async function submitUser() {
  saving.value = true;
  try {
    const payload = {
      username: userForm.username.trim(),
      password: userForm.password,
      display_name: userForm.display_name.trim() || null,
      role: userForm.role,
      student_number: userForm.role === "student" ? userForm.student_number.trim() || null : null,
      teacher_number: userForm.role === "teacher" ? userForm.teacher_number.trim() || null : null,
      college: userForm.college.trim() || null,
      major: userForm.major.trim() || null,
      grade: userForm.role === "student" ? userForm.grade.trim() || null : null,
    };
    await createAdminUser(payload);
    showUserForm.value = false;
    resetUserForm();
    await Promise.all([loadUsers(), loadOverview()]);
    flash("账号已创建，可以使用新账号登录");
  } catch (err) {
    error.value = err.response?.data?.message || err.message || "账号创建失败";
  } finally { saving.value = false; }
}
async function toggleUser(user) {
  try {
    const updated = await updateAdminUser(user.id, { is_active: !user.is_active });
    user.is_active = updated.is_active;
    await loadOverview();
    flash(user.is_active ? "账号已恢复使用" : "账号已停用");
  } catch (err) { flash(err.response?.data?.message || "账号状态更新失败"); }
}
async function submitActivity() {
  saving.value = true;
  try {
    const payload = {
      ...activityForm,
      title: activityForm.title.trim(),
      summary: activityForm.summary.trim() || null,
      content: activityForm.content.trim(),
      location: activityForm.location.trim() || null,
      registration_deadline: iso(activityForm.registration_deadline),
      starts_at: iso(activityForm.starts_at),
      ends_at: iso(activityForm.ends_at),
      capacity: activityForm.capacity ? Number(activityForm.capacity) : null,
    };
    await createActivity(payload);
    showActivityForm.value = false;
    resetActivityForm();
    await Promise.all([loadActivities(), loadOverview()]);
    flash(payload.status === "published" ? "活动已发布到学生端" : "活动已保存为草稿");
  } catch (err) {
    error.value = err.response?.data?.message || err.message || "活动保存失败";
  } finally { saving.value = false; }
}
async function changeActivityStatus(activity, status) {
  try {
    const updated = await updateActivityStatus(activity.id, status);
    activity.status = updated.status;
    await loadOverview();
    flash(status === "published" ? "活动已发布" : "活动已结束");
  } catch (err) { flash(err.response?.data?.message || "活动状态更新失败"); }
}
function openUserForm() { resetUserForm(); showUserForm.value = true; }
function openActivityForm() { resetActivityForm(); showActivityForm.value = true; }

let userTimer;
watch([userQuery, userRole, userStatus], () => {
  window.clearTimeout(userTimer);
  userTimer = window.setTimeout(() => loadUsers().catch(() => flash("账号筛选失败")), 220);
});
let activityTimer;
watch([activityQuery, activityStatus], () => {
  window.clearTimeout(activityTimer);
  activityTimer = window.setTimeout(() => loadActivities().catch(() => flash("活动筛选失败")), 220);
});
onMounted(load);
</script>

<template>
  <main class="portal-page admin-portal page-enter">
    <div v-if="toast" class="portal-toast" role="status"><UiIcon name="PhCheckCircle" weight="fill" />{{ toast }}</div>
    <div class="portal-heading">
      <div>
        <span class="portal-kicker">校园管理端</span>
        <h1>{{ current === "home" ? "管理概览" : current === "users" ? "账号与角色" : current === "activities" ? "校园活动" : "平台运行状态" }}</h1>
        <p>{{ current === "home" ? "关注账号、活动与课程的关键变化。" : current === "users" ? "统一创建、筛选和停用学生与教师账号。" : current === "activities" ? "发布全校活动，让学生及时看到报名与时间安排。" : "当前核心服务均可正常访问。" }}</p>
      </div>
      <button v-if="current === 'users'" class="primary-button" @click="openUserForm"><UiIcon name="PhUserPlus" />创建账号</button>
      <button v-else-if="current === 'activities' || current === 'home'" class="primary-button" @click="openActivityForm"><UiIcon name="PhPlus" />发布活动</button>
    </div>

    <div v-if="loading" class="portal-loading" aria-label="正在加载"><i v-for="n in 6" :key="n"></i></div>
    <div v-else-if="error" class="portal-error"><UiIcon name="PhCloudSlash" :size="34" /><div><strong>管理数据加载失败</strong><p>{{ error }}</p></div><button class="secondary-button" @click="load">重新加载</button></div>

    <template v-else-if="current === 'home'">
      <section class="metric-strip admin-metrics">
        <article><span>平台账号</span><strong>{{ overview.user_count }}</strong><small>{{ overview.student_count }} 名学生</small></article>
        <article><span>教师账号</span><strong>{{ overview.teacher_count }}</strong><small>覆盖多个院系</small></article>
        <article><span>正在报名</span><strong>{{ overview.published_activity_count }}</strong><small>共 {{ overview.activity_count }} 项活动</small></article>
        <article><span>需关注账号</span><strong class="warm-number">{{ overview.inactive_count }}</strong><small>当前处于停用状态</small></article>
      </section>
      <div class="admin-overview-grid">
        <section class="portal-panel">
          <div class="portal-section-title"><div><h2>近期活动</h2><p>发布与报名状态</p></div><button @click="router.push('/activities')">活动管理<UiIcon name="PhArrowRight" /></button></div>
          <article v-for="activity in overview.recent_activities" :key="activity.id" class="admin-activity-line">
            <span class="activity-calendar"><b>{{ new Date(activity.starts_at || activity.created_at).getDate() }}</b>{{ new Date(activity.starts_at || activity.created_at).toLocaleString("zh-CN", { month: "short" }) }}</span>
            <span><strong>{{ activity.title }}</strong><small>{{ activity.location || "地点待定" }}</small></span>
            <em :class="`status-${activity.status}`">{{ activityStatusLabel[activity.status] }}</em>
          </article>
        </section>
        <section class="portal-panel">
          <div class="portal-section-title"><div><h2>最近账号</h2><p>按创建时间显示</p></div><button @click="router.push('/users')">账号管理<UiIcon name="PhArrowRight" /></button></div>
          <article v-for="user in overview.recent_users" :key="user.id" class="recent-user-line">
            <span class="user-initial">{{ (user.display_name || user.username).slice(0, 1) }}</span>
            <span><strong>{{ user.display_name || user.username }}</strong><small>{{ user.student_number || user.teacher_number || user.username }}</small></span>
            <em>{{ roleLabel[user.role] }}</em>
          </article>
        </section>
      </div>
    </template>

    <template v-else-if="current === 'users'">
      <section class="portal-toolbar">
        <div class="portal-search"><UiIcon name="PhMagnifyingGlass" /><input v-model="userQuery" name="user-search" placeholder="搜索姓名、用户名、学号或工号" /></div>
        <select v-model="userRole" name="user-role-filter" aria-label="筛选角色"><option value="">全部角色</option><option value="student">学生</option><option value="teacher">教师</option><option value="admin">管理员</option></select>
        <select v-model="userStatus" name="user-status-filter" aria-label="筛选状态"><option value="">全部状态</option><option value="active">正常</option><option value="inactive">已停用</option></select>
        <span>{{ userTotal }} 个账号</span>
      </section>
      <section class="portal-panel account-table">
        <div class="account-head"><span>用户</span><span>学号 / 工号</span><span>院系</span><span>角色</span><span>状态</span><span>操作</span></div>
        <article v-for="user in users" :key="user.id" class="account-row">
          <div><span class="user-initial">{{ (user.display_name || user.username).slice(0, 1) }}</span><span><strong>{{ user.display_name || user.username }}</strong><small>@{{ user.username }}</small></span></div>
          <span>{{ user.student_number || user.teacher_number || "-" }}</span>
          <span>{{ user.college || "未填写" }}<small>{{ user.major }}</small></span>
          <em>{{ roleLabel[user.role] }}</em>
          <b :class="{ inactive: !user.is_active }">{{ user.is_active ? "正常" : "已停用" }}</b>
          <button :disabled="user.id === store.session?.id" @click="toggleUser(user)">{{ user.is_active ? "停用" : "恢复" }}</button>
        </article>
        <div v-if="!users.length" class="portal-empty"><UiIcon name="PhUsers" :size="34" />没有符合条件的账号。</div>
      </section>
    </template>

    <template v-else-if="current === 'activities'">
      <section class="portal-toolbar">
        <div class="portal-search"><UiIcon name="PhMagnifyingGlass" /><input v-model="activityQuery" name="activity-search" placeholder="搜索活动名称或地点" /></div>
        <select v-model="activityStatus" name="activity-status-filter" aria-label="筛选活动状态"><option value="">全部状态</option><option value="published">报名中</option><option value="draft">草稿</option><option value="closed">已结束</option></select>
        <span>{{ activityTotal }} 项活动</span>
      </section>
      <section class="activity-manage-grid">
        <article v-for="activity in activities" :key="activity.id" class="activity-manage-card">
          <div class="activity-card-top"><span>{{ categoryLabel[activity.category] }}</span><em :class="`status-${activity.status}`">{{ activityStatusLabel[activity.status] }}</em></div>
          <h2>{{ activity.title }}</h2>
          <p>{{ activity.summary || activity.content }}</p>
          <dl>
            <div><dt><UiIcon name="PhMapPin" /></dt><dd>{{ activity.location || "地点待定" }}</dd></div>
            <div><dt><UiIcon name="PhCalendarBlank" /></dt><dd>{{ formatDate(activity.starts_at) }}</dd></div>
            <div><dt><UiIcon name="PhTimer" /></dt><dd>报名截止 {{ formatDate(activity.registration_deadline) }}</dd></div>
          </dl>
          <footer><span>{{ activity.capacity ? `限 ${activity.capacity} 人` : "不限人数" }}</span><button v-if="activity.status === 'draft'" @click="changeActivityStatus(activity, 'published')">发布</button><button v-if="activity.status === 'published'" @click="changeActivityStatus(activity, 'closed')">结束活动</button></footer>
        </article>
        <button class="activity-create-card" @click="openActivityForm"><UiIcon name="PhPlusCircle" :size="32" /><strong>发布新的校园活动</strong><span>补充报名时间、地点和活动说明</span></button>
      </section>
    </template>

    <template v-else>
      <section class="system-status-board">
        <article v-for="service in [
          ['Web 与 API','正常','教师端、管理端和学生端请求正常','PhGlobe'],
          ['SQLite 数据库','正常','账号、任务和活动数据可读写','PhDatabase'],
          ['校园知识库',store.backendOnline ? '正常' : '离线',store.backendOnline ? '检索服务已连接' : '后端服务未连接','PhBooks'],
          ['任务调度','正常','截止提醒与发布状态同步正常','PhClockCounterClockwise']
        ]" :key="service[0]">
          <span><UiIcon :name="service[3]" :size="24" /></span><div><h2>{{ service[0] }}</h2><p>{{ service[2] }}</p></div><em>{{ service[1] }}</em>
        </article>
      </section>
    </template>

    <div v-if="showUserForm" class="portal-overlay" @click.self="showUserForm = false">
      <form class="portal-drawer" @submit.prevent="submitUser">
        <div class="drawer-head"><div><span>账号管理</span><h2>创建校内账号</h2></div><button type="button" class="icon-button" @click="showUserForm = false" aria-label="关闭"><UiIcon name="PhX" /></button></div>
        <label>账号角色<div class="role-segment"><button v-for="item in [['student','学生'],['teacher','教师'],['admin','管理员']]" :key="item[0]" type="button" :class="{ active: userForm.role === item[0] }" @click="userForm.role = item[0]">{{ item[1] }}</button></div></label>
        <div class="form-pair"><label>姓名<input v-model="userForm.display_name" name="display-name" placeholder="请输入真实姓名" required /></label><label>{{ userForm.role === "student" ? "学号" : userForm.role === "teacher" ? "工号" : "所属部门" }}<input v-if="userForm.role === 'student'" v-model="userForm.student_number" name="student-number" placeholder="例如 2024010132" /><input v-else-if="userForm.role === 'teacher'" v-model="userForm.teacher_number" name="teacher-number" placeholder="例如 T20180456" /><input v-else v-model="userForm.college" name="admin-department" placeholder="例如 信息中心" /></label></div>
        <label>登录用户名<input v-model="userForm.username" name="new-username" minlength="3" maxlength="64" pattern="[a-zA-Z0-9_]+" placeholder="仅字母、数字和下划线" required /></label>
        <label>初始密码<input v-model="userForm.password" name="new-password" type="password" minlength="8" maxlength="128" autocomplete="new-password" placeholder="至少 8 位，首次登录后建议修改" required /></label>
        <div v-if="userForm.role !== 'admin'" class="form-pair"><label>学院<input v-model="userForm.college" name="college" placeholder="例如 计算机学院" /></label><label>{{ userForm.role === "student" ? "专业" : "系部" }}<input v-model="userForm.major" name="major" /></label></div>
        <label v-if="userForm.role === 'student'">年级<input v-model="userForm.grade" name="grade" placeholder="例如 2024" /></label>
        <div class="drawer-actions"><button type="button" class="secondary-button" @click="showUserForm = false">取消</button><button class="primary-button" :disabled="saving">{{ saving ? "正在创建" : "创建账号" }}<UiIcon name="PhUserPlus" /></button></div>
      </form>
    </div>

    <div v-if="showActivityForm" class="portal-overlay" @click.self="showActivityForm = false">
      <form class="portal-drawer activity-drawer" @submit.prevent="submitActivity">
        <div class="drawer-head"><div><span>全校活动</span><h2>发布到学生端</h2></div><button type="button" class="icon-button" @click="showActivityForm = false" aria-label="关闭"><UiIcon name="PhX" /></button></div>
        <label>活动名称<input v-model="activityForm.title" name="activity-title" maxlength="200" placeholder="例如：暑期社会实践项目成果展" required /></label>
        <div class="form-pair"><label>活动类型<select v-model="activityForm.category" name="activity-category"><option v-for="(label,key) in categoryLabel" :key="key" :value="key">{{ label }}</option></select></label><label>人数上限<input v-model.number="activityForm.capacity" name="activity-capacity" type="number" min="1" max="100000" placeholder="留空表示不限" /></label></div>
        <label>一句话简介<input v-model="activityForm.summary" name="activity-summary" maxlength="500" placeholder="学生在活动列表中首先看到的内容" /></label>
        <label>活动说明<textarea v-model="activityForm.content" name="activity-content" rows="5" placeholder="说明活动内容、参与方式和注意事项" required></textarea></label>
        <label>活动地点<input v-model="activityForm.location" name="activity-location" placeholder="例如：大学生活动中心一楼" /></label>
        <div class="form-pair"><label>报名截止<input v-model="activityForm.registration_deadline" name="activity-deadline" type="datetime-local" /></label><label>活动开始<input v-model="activityForm.starts_at" name="activity-start" type="datetime-local" /></label></div>
        <label>活动结束<input v-model="activityForm.ends_at" name="activity-end" type="datetime-local" /></label>
        <div class="drawer-actions"><button type="button" class="secondary-button" :disabled="saving" @click="activityForm.status = 'draft'; submitActivity()">保存草稿</button><button class="primary-button" :disabled="saving || !activityForm.title.trim() || !activityForm.content.trim()" @click="activityForm.status = 'published'">{{ saving ? "正在保存" : "确认发布" }}<UiIcon name="PhPaperPlaneTilt" /></button></div>
      </form>
    </div>
  </main>
</template>

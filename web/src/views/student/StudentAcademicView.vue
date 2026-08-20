<script setup>
import { onMounted, onUnmounted, ref, computed } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import {
  getAcademicProviders,
  getAcademicStatus,
  getEduBinding,
  eduUnbind,
  eduSync,
  getEduSyncRecords,
  getUniversities,
  selectUniversity,
  submitEduUrl,
  eduProbe,
  eduCreateConnectionFromUrl,
  eduContinueConnection,
  eduPollConnection,
  eduScheduleItems,
  eduGradeItems,
} from "../../services/studentApi";

const loading = ref(false);
const error = ref("");
const status = ref({ status: "unsupported", provider: "unsupported" });
const providers = ref([]);
const eduBinding = ref(null);
const syncRecords = ref([]);
const syncResult = ref(null);
const syncBusy = ref("");
const bindForm = ref({ username: "", password: "" });
const bindBusy = ref(false);
const bindError = ref("");
const universities = ref([]);
const universityQuery = ref("");
const universityPickerOpen = ref(false);
const manualUrl = ref("");
const manualUrlBusy = ref(false);
const manualUrlResult = ref(null);
const manualUrlError = ref("");

// ===== Connection 状态机（probe + from-url + continue） =====
const probeResult = ref(null);
const connection = ref(null);
const connectionBusy = ref(false);
const connectionError = ref("");
const polling = ref(false);
let pollTimer = null;

const isBound = computed(() => !!eduBinding.value && eduBinding.value.connection_status === "active");
const hasUniversity = computed(() => status.value && status.value.status !== "unbound" || isBound.value);

const connectionStateText = {
  idle: "未连接",
  connecting: "连接中…",
  auth_required: "需要登录验证",
  waiting_user_login: "等待用户登录",
  need_captcha: "学校要求完成人机验证",
  need_slider: "需要完成滑块验证",
  need_sms: "需要短信验证码",
  need_mfa: "需要多因素认证",
  need_user_action: "需要用户操作",
  authenticated: "已认证",
  syncing: "同步中…",
  connected: "已连接",
  session_expired: "登录状态已过期，请重新验证",
  auth_failed: "认证失败",
  network_error: "网络错误",
  system_unavailable: "教务系统暂不可用",
  unsupported: "该教务系统暂未完成适配",
  error: "连接出错",
};

function stateText(state) {
  return connectionStateText[state] || state || "未知";
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [s, p, b, r] = await Promise.all([
      getAcademicStatus().catch(() => ({ status: "unsupported", provider: "unsupported" })),
      getAcademicProviders().catch(() => ({ items: [] })),
      getEduBinding().catch(() => null),
      getEduSyncRecords(10).catch(() => []),
    ]);
    status.value = s;
    providers.value = p.items || [];
    eduBinding.value = b;
    syncRecords.value = r || [];
  } catch (e) {
    error.value = e.response?.data?.code === "UNIVERSITY_REQUIRED"
      ? "请先选择你的大学。"
      : (e.response?.data?.message || "教务状态加载失败");
  } finally {
    loading.value = false;
  }
}

async function searchUniversities() {
  try {
    const data = await getUniversities({ q: universityQuery.value, page_size: 20 });
    universities.value = data.items || [];
  } catch {
    universities.value = [];
  }
}

async function pickUniversity(id) {
  try {
    await selectUniversity(id);
    universityPickerOpen.value = false;
    await load();
  } catch (e) {
    error.value = e.response?.data?.message || "选择大学失败";
  }
}

async function submitBind() {
  if (connection.value?.state === "auth_required") {
    await submitCredentialConnect();
    return;
  }
  bindError.value = "请先输入并连接教务系统网址，再提交账号密码。";
}

async function submitUnbind() {
  if (!confirm("确认解绑教务账号？")) return;
  try {
    await eduUnbind();
    eduBinding.value = null;
    syncResult.value = null;
  } catch (e) {
    error.value = e.response?.data?.message || "解绑失败";
  }
}

async function submitSync(type) {
  syncBusy.value = type;
  syncResult.value = null;
  try {
    syncResult.value = await eduSync(type);
    await load();
  } catch (e) {
    error.value = e.response?.data?.message || "同步失败";
  } finally {
    syncBusy.value = "";
  }
}

async function submitManualUrl() {
  if (!manualUrl.value.trim()) return;
  manualUrlBusy.value = true;
  manualUrlError.value = "";
  manualUrlResult.value = null;
  try {
    manualUrlResult.value = await submitEduUrl(manualUrl.value.trim());
  } catch (e) {
    manualUrlError.value = e.response?.data?.message || "提交失败";
  } finally {
    manualUrlBusy.value = false;
  }
}

// ===== Probe + 创建连接 =====
async function probeAndConnect() {
  const url = manualUrl.value.trim();
  if (!url) return;
  connectionBusy.value = true;
  connectionError.value = "";
  probeResult.value = null;
  connection.value = null;
  try {
    probeResult.value = await eduProbe(url);
    connection.value = await eduCreateConnectionFromUrl(url);
    if (connection.value.login_execution_mode === "client_webview") {
      startPolling(connection.value.id);
    }
  } catch (e) {
    connectionError.value = e.response?.data?.message || "探测或创建连接失败";
  } finally {
    connectionBusy.value = false;
  }
}

// ===== backend_http 路径：账密登录 =====
async function submitCredentialConnect() {
  if (!connection.value || !bindForm.value.username || !bindForm.value.password) return;
  bindBusy.value = true;
  bindError.value = "";
  try {
    connection.value = await eduContinueConnection(connection.value.id, {
      username: bindForm.value.username,
      password: bindForm.value.password,
    });
    if (connection.value.state === "connected") {
      await load();
      bindForm.value = { username: "", password: "" };
    } else if (connection.value.state === "auth_failed") {
      bindError.value = connection.value.error_message || "账号或密码错误";
    } else {
      bindError.value = connection.value.error_message || "登录失败";
    }
  } catch (e) {
    bindError.value = e.response?.data?.message || "登录失败";
  } finally {
    bindBusy.value = false;
  }
}

// ===== 轮询连接状态（client_webview 模式，移动端登录后 Web 端轮询） =====
function startPolling(connId) {
  stopPolling();
  polling.value = true;
  let count = 0;
  pollTimer = setInterval(async () => {
    count++;
    if (count > 60) { stopPolling(); return; }
    try {
      const conn = await eduPollConnection(connId);
      connection.value = conn;
      if (conn.state === "connected") {
        stopPolling();
        await load();
      }
    } catch { /* ignore poll error */ }
  }, 3000);
}
function stopPolling() {
  polling.value = false;
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

async function refreshConnectionStatus() {
  if (!connection.value) { await load(); return; }
  try {
    connection.value = await eduPollConnection(connection.value.id);
    await load();
  } catch (e) {
    connectionError.value = e.response?.data?.message || "刷新失败";
  }
}

async function reconnect() {
  stopPolling();
  connection.value = null;
  probeResult.value = null;
  connectionError.value = "";
  bindForm.value = { username: "", password: "" };
}

// ===== 课表展示 =====
const WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const scheduleItems = ref([]);
const scheduleLoading = ref(false);
const currentWeek = ref(1);
const selectedCourse = ref(null);
const showScheduleModal = ref(false);

function weeksContains(weeks, weekText, week) {
  const w = (weeks || "").trim();
  if (!w) return true;
  if (weekText && weekText.includes("单") && week % 2 === 0) return false;
  if (weekText && weekText.includes("双") && week % 2 === 1) return false;
  const cleaned = w.replace(/周/g, "").replace(/ /g, "");
  const parts = cleaned.split(/[,，;；]/);
  for (const part of parts) {
    const p = part.trim();
    if (!p) continue;
    if (p.endsWith("单") && week % 2 === 0) continue;
    if (p.endsWith("双") && week % 2 === 1) continue;
    const core = p.replace(/单$/, "").replace(/双$/, "");
    if (core.includes("-")) {
      const [s, e] = core.split("-").map(Number);
      if (s && e && week >= s && week <= e) return true;
    } else {
      const n = parseInt(core, 10);
      if (n === week) return true;
    }
  }
  return false;
}

function formatTeachers(teachers, teacher) {
  if (teachers && teachers.length) {
    const filtered = teachers.filter((t) => t && t.trim());
    if (filtered.length) return filtered.join("、");
  }
  return teacher || "";
}
function formatTime(weekday, start, end, startTime, endTime) {
  if (weekday == null && start == null) return "";
  let sb = "";
  if (weekday >= 1 && weekday <= 7) sb += WEEKDAY_NAMES[weekday - 1];
  if (start != null) {
    sb += ` 第${start}`;
    if (end != null && end !== start) sb += `-${end}`;
    sb += "节";
  }
  if (startTime || endTime) sb += `\n${startTime || ""}${endTime ? "-" + endTime : ""}`;
  return sb;
}
function formatWeeks(weeks, weekText) {
  if (weekText) return weeks ? `${weekText}（${weeks}）` : weekText;
  return weeks || "";
}
function formatCredit(credit) {
  return credit === Math.floor(credit) ? `${Math.floor(credit)} 学分` : `${credit} 学分`;
}
function formatHours(hours) {
  return hours === Math.floor(hours) ? `${Math.floor(hours)}` : `${hours}`;
}

const allScheduleItems = computed(() => (scheduleItems.value || []).filter((it) => !it.is_stale));
const weekFiltered = computed(() => allScheduleItems.value.filter((it) => weeksContains(it.weeks, it.week_text, currentWeek.value)));
const byWeekday = computed(() => {
  const map = {};
  for (let wd = 1; wd <= 7; wd++) {
    map[wd] = weekFiltered.value
      .filter((it) => it.weekday === wd)
      .sort((a, b) => (a.start_section ?? 99) - (b.start_section ?? 99));
  }
  return map;
});

async function loadSchedule() {
  scheduleLoading.value = true;
  try {
    const resp = await eduScheduleItems(null);
    scheduleItems.value = resp.items || [];
  } catch {
    scheduleItems.value = [];
  } finally {
    scheduleLoading.value = false;
  }
}

function openCourseDetail(item) {
  selectedCourse.value = item;
  showScheduleModal.value = true;
}
function closeCourseDetail() {
  showScheduleModal.value = false;
  selectedCourse.value = null;
}

onMounted(load);
onUnmounted(stopPolling);
</script>
<template>
  <main class="student-page campus-redesign page-enter">
    <div class="redesign-heading">
      <div>
        <span class="redesign-kicker">ACADEMIC CONNECTION</span>
        <h1>教务系统</h1>
        <p>连接学生自己的教务账号，用于同步课程、课表、成绩和考试。</p>
      </div>
      <button class="redesign-button secondary" @click="load"><UiIcon name="PhArrowClockwise" />刷新</button>
    </div>

    <div v-if="error" class="redesign-alert error"><UiIcon name="PhWarningCircle" />{{ error }}</div>
    <div v-if="loading" class="profile-loading"><div class="profile-loading-grid"><i></i><i></i><i></i></div></div>

    <section v-else class="redesign-panel v3-academic">
      <span class="v3-academic-icon"><UiIcon name="PhGraduationCap" :size="36" /></span>
      <div>
        <small>当前连接状态</small>
        <h2>{{ isBound ? "已绑定" : (status?.status === "unsupported" ? "暂未支持自动教务同步" : stateText(eduBinding?.connection_status || status?.status || "unbound")) }}</h2>
        <p>Provider：{{ eduBinding?.provider || status?.provider || "unsupported" }}。未确认数据不会编造 URL，所有教务网址必须经过真实数据确认。</p>
      </div>
    </section>

    <section v-if="isBound" class="redesign-panel">
      <header><h3>教务账号已绑定</h3></header>
      <dl class="edu-meta">
        <dt>Provider</dt><dd>{{ eduBinding.provider }}</dd>
        <dt>外部学号</dt><dd>{{ eduBinding.external_student_id || "—" }}</dd>
        <dt>最后同步</dt><dd>{{ eduBinding.last_synced_at || "—" }}</dd>
        <dt>同步状态</dt><dd>{{ eduBinding.last_sync_status || "—" }}</dd>
      </dl>
      <div v-if="eduBinding.last_error" class="redesign-alert warning">上次错误：{{ eduBinding.last_error }}</div>
      <div class="edu-actions">
        <button class="redesign-button" :disabled="syncBusy" @click="submitSync('profile')"><UiIcon name="PhUser" />{{ syncBusy === 'profile' ? "同步中…" : "同步基本信息" }}</button>
        <button class="redesign-button" :disabled="syncBusy" @click="submitSync('schedule')"><UiIcon name="PhCalendar" />{{ syncBusy === 'schedule' ? "同步中…" : "同步课表" }}</button>
        <button class="redesign-button" :disabled="syncBusy" @click="submitSync('grade')"><UiIcon name="PhChartLine" />{{ syncBusy === 'grade' ? "同步中…" : "同步成绩" }}</button>
        <button class="redesign-button" :disabled="syncBusy" @click="submitSync('exam')"><UiIcon name="PhClipboardText" />{{ syncBusy === 'exam' ? "同步中…" : "同步考试" }}</button>
        <button class="redesign-button secondary" @click="submitUnbind"><UiIcon name="PhX" />解绑</button>
      </div>
    </section>

    <section v-else class="redesign-panel">
      <header><h3>完成当前连接认证</h3></header>
      <p class="edu-hint">先输入教务系统网址创建连接，再提交账号密码。密码只用于本次认证，不会明文保存。</p>
      <div v-if="bindError" class="redesign-alert error">{{ bindError }}</div>
      <form class="edu-form" @submit.prevent="submitBind">
        <label>账号<input v-model="bindForm.username" type="text" autocomplete="username" required /></label>
        <label>密码<input v-model="bindForm.password" type="password" autocomplete="current-password" required /></label>
        <button class="redesign-button" type="submit" :disabled="bindBusy">{{ bindBusy ? "绑定中…" : "绑定" }}</button>
      </form>
    </section>

    <section v-if="!isBound" class="redesign-panel">
      <header><h3>连接教务系统</h3></header>
      <p class="edu-hint">输入高校教务系统网址，CampusMate 将自动识别系统类型并创建连接。</p>
      <div v-if="connectionError" class="redesign-alert error">{{ connectionError }}</div>
      <form class="edu-form" @submit.prevent="probeAndConnect">
        <label>教务系统地址<input v-model="manualUrl" type="url" placeholder="https://jwxt.yourschool.edu.cn/" required /></label>
        <button class="redesign-button" type="submit" :disabled="connectionBusy">{{ connectionBusy ? "检测中…" : "检测教务系统" }}</button>
      </form>

      <div v-if="probeResult" class="manual-url-result">
        <h4>检测结果</h4>
        <dl class="edu-meta">
          <dt>厂商</dt><dd>{{ probeResult.provider }}</dd>
          <dt>可访问</dt><dd>{{ probeResult.reachable ? "是" : "否" }}</dd>
          <dt>登录方式</dt><dd>{{ probeResult.suggested_login_mode === 'client_webview' ? '客户端浏览器登录' : '账号密码登录' }}</dd>
        </dl>
      </div>

      <div v-if="connection && connection.login_execution_mode === 'backend_http'" class="edu-credential-block">
        <h4>账号密码登录</h4>
        <div v-if="bindError" class="redesign-alert error">{{ bindError }}</div>
        <form class="edu-form" @submit.prevent="submitCredentialConnect">
          <label>学号<input v-model="bindForm.username" type="text" required /></label>
          <label>密码<input v-model="bindForm.password" type="password" required /></label>
          <button class="redesign-button" type="submit" :disabled="bindBusy">{{ bindBusy ? "验证中…" : "登录" }}</button>
        </form>
        <p class="edu-hint">密码仅用于本次登录校验，不会明文保存。</p>
      </div>

      <div v-if="connection && connection.login_execution_mode === 'client_webview'" class="edu-webview-block">
        <div class="redesign-alert info">
          <UiIcon name="PhDeviceMobile" />
          <div>
            <strong>该教务系统需要在移动客户端中完成网页登录。</strong>
            <p>请使用 CampusMate Android / Harmony 客户端完成首次连接。连接成功后，本页面将自动显示已同步的课表和成绩。</p>
          </div>
        </div>
        <div class="edu-actions">
          <button class="redesign-button secondary" :disabled="polling" @click="refreshConnectionStatus">
            <UiIcon name="PhArrowClockwise" />{{ polling ? "轮询中…" : "刷新连接状态" }}
          </button>
        </div>
      </div>
    </section>

    <section v-if="isBound" class="redesign-panel">
      <header><h3>教务课表</h3></header>
      <div class="edu-actions" style="margin-bottom: 12px;">
        <button class="redesign-button secondary" :disabled="currentWeek <= 1" @click="currentWeek--">上一周</button>
        <strong style="margin: 0 12px;">第 {{ currentWeek }} 周</strong>
        <button class="redesign-button secondary" :disabled="currentWeek >= 25" @click="currentWeek++">下一周</button>
        <button class="redesign-button secondary" @click="loadSchedule"><UiIcon name="PhArrowClockwise" />刷新课表</button>
      </div>
      <div v-if="scheduleLoading" class="profile-loading"><div class="profile-loading-grid"><i></i><i></i><i></i></div></div>
      <div v-else-if="allScheduleItems.length === 0" class="edu-hint">本学期暂无课程，请先同步课表。</div>
      <div v-else>
        <div v-for="wd in 7" :key="wd">
          <template v-if="byWeekday[wd] && byWeekday[wd].length">
            <h4 class="schedule-day-title">{{ ['','周一','周二','周三','周四','周五','周六','周日'][wd] }}</h4>
            <div class="schedule-card-list">
              <div v-for="item in byWeekday[wd]" :key="item.id || `${wd}_${item.course_code}_${item.start_section}_${item.location}`" class="schedule-course-card" @click="openCourseDetail(item)">
                <div class="schedule-course-name">{{ item.course_name || "未命名课程" }}</div>
                <div v-if="item.location" class="schedule-course-loc">{{ item.location }}</div>
                <div v-if="item.start_section" class="schedule-course-sec">第{{ item.start_section }}{{ item.end_section && item.end_section !== item.start_section ? '-' + item.end_section : '' }}节</div>
              </div>
            </div>
          </template>
        </div>
        <div v-if="weekFiltered.length === 0" class="edu-hint">本周没有课程。</div>
      </div>
    </section>

    <section v-if="isBound" class="redesign-panel">
      <header><h3>连接管理</h3></header>
      <div class="edu-actions">
        <button class="redesign-button secondary" @click="reconnect"><UiIcon name="PhArrowClockwise" />重新连接</button>
        <button class="redesign-button secondary" @click="submitUnbind"><UiIcon name="PhX" />断开连接</button>
      </div>
    </section>

    <section v-if="syncResult" class="redesign-panel">
      <header><h3>同步结果（{{ syncResult.sync_type }}）</h3></header>
      <p>状态：{{ syncResult.status }}，条目数：{{ syncResult.items_count }}</p>
      <pre v-if="syncResult.profile || syncResult.schedule || syncResult.grade || syncResult.exam" class="edu-result">{{ JSON.stringify(syncResult, null, 2) }}</pre>
      <p v-if="syncResult.error_message" class="redesign-alert warning">{{ syncResult.error_message }}</p>
    </section>

    <section v-if="syncRecords.length" class="redesign-panel">
      <header><h3>同步记录</h3></header>
      <ul class="edu-records">
        <li v-for="r in syncRecords" :key="r.id">
          <strong>{{ r.sync_type }}</strong>
          <span>{{ r.status }}</span>
          <span>{{ r.items_count }} 条</span>
          <time>{{ r.started_at }}</time>
        </li>
      </ul>
    </section>

    <section class="v3-security redesign-panel">
      <UiIcon name="PhShieldCheck" :size="28" />
      <div>
        <h2>凭证安全</h2>
        <p>教务密码只会通过 HTTPS 发送到 Backend 进行一次认证，不会保存在浏览器 localStorage 或 sessionStorage，也不会出现在 API 响应和日志中。</p>
      </div>
    </section>

    <section class="redesign-panel v3-empty">
      <strong>移动端连接</strong>
      <span>部分教务系统当前仅支持移动端连接（CLIENT_WEBVIEW），Web 端将提示"该教务系统当前仅支持移动端连接"。</span>
    </section>

    <section class="redesign-panel v3-empty">
      <strong>手动课程仍然可用</strong>
      <span>自动同步未支持时，可以继续使用手动课程、个人待办和学习陪伴。</span>
      <em>不会保存在浏览器的教务密码</em>
    </section>

    <div v-if="showScheduleModal && selectedCourse" class="schedule-modal-overlay" @click.self="closeCourseDetail">
      <div class="schedule-modal">
        <button class="schedule-modal-close" @click="closeCourseDetail">&times;</button>
        <h2>{{ selectedCourse.course_name || "未命名课程" }}</h2>
        <p v-if="selectedCourse.course_code" class="schedule-modal-code">{{ selectedCourse.course_code }}</p>
        <dl class="schedule-detail-list">
          <template v-if="formatTeachers(selectedCourse.teachers, selectedCourse.teacher)"><dt>教师</dt><dd>{{ formatTeachers(selectedCourse.teachers, selectedCourse.teacher) }}</dd></template>
          <template v-if="formatTime(selectedCourse.weekday, selectedCourse.start_section, selectedCourse.end_section, selectedCourse.start_time, selectedCourse.end_time)"><dt>上课时间</dt><dd style="white-space: pre-line;">{{ formatTime(selectedCourse.weekday, selectedCourse.start_section, selectedCourse.end_section, selectedCourse.start_time, selectedCourse.end_time) }}</dd></template>
          <template v-if="selectedCourse.location"><dt>地点</dt><dd>{{ selectedCourse.location }}</dd></template>
          <template v-if="formatWeeks(selectedCourse.weeks, selectedCourse.week_text)"><dt>周次</dt><dd>{{ formatWeeks(selectedCourse.weeks, selectedCourse.week_text) }}</dd></template>
          <template v-if="selectedCourse.credit != null"><dt>学分</dt><dd>{{ formatCredit(selectedCourse.credit) }}</dd></template>
          <template v-if="selectedCourse.course_nature"><dt>课程性质</dt><dd>{{ selectedCourse.course_nature }}</dd></template>
          <template v-if="selectedCourse.course_category"><dt>课程类别</dt><dd>{{ selectedCourse.course_category }}</dd></template>
          <template v-if="selectedCourse.course_type"><dt>课程类型</dt><dd>{{ selectedCourse.course_type }}</dd></template>
          <template v-if="selectedCourse.teaching_class"><dt>教学班</dt><dd>{{ selectedCourse.teaching_class }}</dd></template>
          <template v-if="selectedCourse.assessment_method"><dt>考核方式</dt><dd>{{ selectedCourse.assessment_method }}</dd></template>
          <template v-if="selectedCourse.exam_type"><dt>考试类型</dt><dd>{{ selectedCourse.exam_type }}</dd></template>
          <template v-if="selectedCourse.college"><dt>开课学院</dt><dd>{{ selectedCourse.college }}</dd></template>
          <template v-if="selectedCourse.department"><dt>开课系</dt><dd>{{ selectedCourse.department }}</dd></template>
          <template v-if="selectedCourse.campus"><dt>校区</dt><dd>{{ selectedCourse.campus }}</dd></template>
          <template v-if="selectedCourse.class_name"><dt>班级</dt><dd>{{ selectedCourse.class_name }}</dd></template>
          <template v-if="selectedCourse.total_hours != null"><dt>总学时</dt><dd>{{ formatHours(selectedCourse.total_hours) }}</dd></template>
          <template v-if="selectedCourse.theory_hours != null"><dt>理论学时</dt><dd>{{ formatHours(selectedCourse.theory_hours) }}</dd></template>
          <template v-if="selectedCourse.practice_hours != null"><dt>实践学时</dt><dd>{{ formatHours(selectedCourse.practice_hours) }}</dd></template>
          <template v-if="selectedCourse.language"><dt>授课语言</dt><dd>{{ selectedCourse.language }}</dd></template>
          <template v-if="selectedCourse.semester"><dt>学期</dt><dd>{{ selectedCourse.semester }}</dd></template>
          <template v-if="selectedCourse.note"><dt>备注</dt><dd>{{ selectedCourse.note }}</dd></template>
        </dl>
        <template v-if="selectedCourse.extra_info && Object.keys(selectedCourse.extra_info).length">
          <h4 class="schedule-extra-title">更多信息</h4>
          <dl class="schedule-detail-list">
            <template v-for="(v, k) in selectedCourse.extra_info" :key="k">
              <template v-if="v != null && String(v).trim()"><dt>{{ k }}</dt><dd>{{ String(v) }}</dd></template>
            </template>
          </dl>
        </template>
        <p class="schedule-modal-source">数据来源：学校教务系统</p>
      </div>
    </div>
  </main>
</template>
<style scoped>
.schedule-day-title { color: var(--primary, #5b68f2); font-size: 14px; font-weight: 700; margin: 16px 0 8px; }
.schedule-card-list { display: flex; flex-direction: column; gap: 8px; }
.schedule-course-card { background: var(--surface, #fff); border-radius: 12px; padding: 12px; cursor: pointer; border: 1px solid var(--border, #e5e7eb); transition: border-color .15s; }
.schedule-course-card:hover { border-color: var(--primary, #5b68f2); }
.schedule-course-name { font-size: 14px; font-weight: 700; color: var(--text, #1b2730); overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.schedule-course-loc { font-size: 11px; color: var(--muted, #667784); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.schedule-course-sec { font-size: 10px; color: var(--primary, #5b68f2); margin-top: 2px; }
.schedule-modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 16px; }
.schedule-modal { background: var(--surface, #fff); border-radius: 16px; padding: 24px; max-width: 480px; width: 100%; max-height: 80vh; overflow-y: auto; position: relative; }
.schedule-modal-close { position: absolute; top: 12px; right: 16px; font-size: 24px; background: none; border: none; cursor: pointer; color: var(--muted, #667784); }
.schedule-modal h2 { font-size: 22px; font-weight: 800; margin: 0 0 4px; }
.schedule-modal-code { font-size: 12px; color: var(--muted, #667784); margin: 0 0 12px; }
.schedule-detail-list { display: grid; grid-template-columns: 80px 1fr; gap: 6px 12px; font-size: 13px; }
.schedule-detail-list dt { color: var(--muted, #667784); font-size: 12px; }
.schedule-detail-list dd { font-weight: 600; margin: 0; }
.schedule-extra-title { font-size: 13px; font-weight: 700; margin: 16px 0 8px; }
.schedule-modal-source { font-size: 10px; color: var(--muted, #667784); margin-top: 16px; }
</style>

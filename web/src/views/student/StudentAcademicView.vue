<script setup>
import { onMounted, ref, computed } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import {
  getAcademicProviders,
  getAcademicStatus,
  getEduBinding,
  eduBind,
  eduUnbind,
  eduSync,
  getEduSyncRecords,
  getUniversities,
  selectUniversity,
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
  bindBusy.value = true;
  bindError.value = "";
  try {
    eduBinding.value = await eduBind(bindForm.value.username, bindForm.value.password);
    bindForm.value = { username: "", password: "" };
  } catch (e) {
    bindError.value = e.response?.data?.message || "绑定失败";
  } finally {
    bindBusy.value = false;
  }
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

onMounted(load);
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
      <header><h3>绑定教务账号</h3></header>
      <p class="edu-hint">输入教务系统账号密码进行一次认证。密码不会明文保存，也不会出现在 API 响应或日志中。</p>
      <div v-if="bindError" class="redesign-alert error">{{ bindError }}</div>
      <form class="edu-form" @submit.prevent="submitBind">
        <label>账号<input v-model="bindForm.username" type="text" autocomplete="username" required /></label>
        <label>密码<input v-model="bindForm.password" type="password" autocomplete="current-password" required /></label>
        <button class="redesign-button" type="submit" :disabled="bindBusy">{{ bindBusy ? "绑定中…" : "绑定" }}</button>
      </form>
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
  </main>
</template>

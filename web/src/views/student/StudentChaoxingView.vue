<script setup>
import { computed, onMounted, ref } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import { useToast } from "../../composables/useToast";
import {
  disconnectChaoxing,
  getChaoxingStatus,
  loginChaoxing,
  syncChaoxing,
} from "../../services/chaoxing";

const toast = useToast();
const status = ref("checking");
const lastConfirmedStatus = ref("offline");
const lastSyncedAt = ref(null);
const summary = ref({ source: null, courses: 0, teachers: 0, pending_assignments: 0, notices: 0 });
const username = ref("");
const password = ref("");
const showPassword = ref(false);
const checking = ref(true);
const loggingIn = ref(false);
const syncing = ref(false);
const disconnecting = ref(false);
const message = ref("");
const messageTone = ref("info");
const LAST_STATUS_KEY = "campus_chaoxing_last_status";

const isConnected = computed(() => status.value === "online");
const needsLogin = computed(() => status.value === "offline" || status.value === "expired" || status.value === "verification_required");
const statusLabel = computed(() => ({
  checking: "正在检查",
  online: "已连接",
  offline: "未连接",
  expired: "登录已失效",
  verification_required: "需要验证",
  unavailable: "暂时无法验证",
}[status.value] || "未知状态"));

function errorDetail(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || String(item)).join("；");
  return error?.message || "未知错误";
}

function friendlyError(error, fallback) {
  const detail = errorDetail(error);
  if (detail.includes("verification_required")) return "当前登录需要验证码，请先在学习通官方 App 或网页完成验证后重试。";
  if (detail.includes("reauth_required") || error?.response?.status === 401) return "学习通登录已失效，请重新输入账号密码。";
  return detail || fallback;
}

function applyStatus(data) {
  status.value = data?.status || "offline";
  if (["online", "offline", "expired"].includes(status.value)) {
    lastConfirmedStatus.value = status.value;
    localStorage.setItem(LAST_STATUS_KEY, status.value);
  }
  lastSyncedAt.value = data?.last_synced_at || null;
  summary.value = {
    source: data?.source || null,
    courses: data?.courses || 0,
    teachers: data?.teachers || 0,
    pending_assignments: data?.pending_assignments || 0,
    notices: data?.notices || 0,
  };
  if (status.value === "unavailable") {
    message.value = "学习通服务暂时不可用，已保留上一次确认的连接信息。";
    messageTone.value = "warning";
  }
}

async function checkStatus({ preserveMessage = false } = {}) {
  checking.value = true;
  if (!preserveMessage) message.value = "";
  const storedStatus = localStorage.getItem(LAST_STATUS_KEY);
  if (["online", "offline", "expired"].includes(storedStatus)) lastConfirmedStatus.value = storedStatus;
  try {
    applyStatus(await getChaoxingStatus());
  } catch (error) {
    status.value = "unavailable";
    message.value = "暂时无法检查学习通连接，请检查网络后重试。";
    messageTone.value = "warning";
  } finally {
    checking.value = false;
  }
}

async function login() {
  if (!username.value.trim() || !password.value || loggingIn.value) return;
  loggingIn.value = true;
  message.value = "";
  try {
    await loginChaoxing(username.value.trim(), password.value);
    password.value = "";
    message.value = "学习通连接成功，现在可以同步课程、作业和通知。";
    messageTone.value = "success";
    toast.success("学习通连接成功");
    await checkStatus({ preserveMessage: true });
  } catch (error) {
    message.value = friendlyError(error, "登录失败，请稍后重试。");
    messageTone.value = "danger";
  } finally {
    loggingIn.value = false;
  }
}

async function syncNow() {
  if (syncing.value) return;
  syncing.value = true;
  message.value = "";
  try {
    const data = await syncChaoxing();
    const stats = data?.stats || {};
    const summaryText = `${stats.courses_fetched || 0} 门课程、${stats.assignments_pending || 0} 项未完成作业、${stats.notices_fetched || 0} 条通知`;
    message.value = data?.complete === false
      ? `已完成部分同步：${summaryText}。个别数据源暂不可用，可稍后再次同步。`
      : `同步完成：${summaryText}。`;
    messageTone.value = data?.complete === false ? "warning" : "success";
    data?.complete === false ? toast.warning("学习通已完成部分同步") : toast.success("学习通同步成功");
    await checkStatus({ preserveMessage: true });
  } catch (error) {
    const detail = errorDetail(error);
    if (detail.includes("reauth_required") || detail.includes("verification_required") || error?.response?.status === 401) {
      status.value = "expired";
      lastConfirmedStatus.value = "expired";
    }
    message.value = friendlyError(error, "同步失败，请稍后重试。");
    messageTone.value = "danger";
  } finally {
    syncing.value = false;
  }
}

async function disconnect() {
  if (disconnecting.value) return;
  disconnecting.value = true;
  message.value = "";
  try {
    await disconnectChaoxing();
    status.value = "offline";
    lastConfirmedStatus.value = "offline";
    localStorage.setItem(LAST_STATUS_KEY, "offline");
    lastSyncedAt.value = null;
    summary.value = { source: null, courses: 0, teachers: 0, pending_assignments: 0, notices: 0 };
    message.value = "已解除学习通连接，历史同步数据仍会保留。";
    messageTone.value = "success";
    toast.success("已解除学习通连接");
  } catch (error) {
    message.value = friendlyError(error, "解除连接失败，请稍后重试。");
    messageTone.value = "danger";
  } finally {
    disconnecting.value = false;
  }
}

function formatTime(value) {
  if (!value) return "尚未同步";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("zh-CN", { dateStyle: "medium", timeStyle: "short" });
}

onMounted(checkStatus);
</script>

<template>
  <main class="student-page chaoxing-page page-enter">
    <div class="redesign-heading chaoxing-heading">
      <div>
        <span class="redesign-kicker">CHAOXING / 学习数据</span>
        <h1>学习通同步</h1>
        <p>连接后将课程、作业与课程通知保存到当前 CampusMate 账号，多端使用同一份数据。</p>
      </div>
      <button class="redesign-button secondary" :disabled="checking" @click="checkStatus">
        <UiIcon name="PhArrowClockwise" :class="{ spinning: checking }" />刷新状态
      </button>
    </div>

    <section class="chaoxing-layout">
      <article class="redesign-panel chaoxing-status-card">
        <div class="chaoxing-status-head">
          <span class="chaoxing-brand"><UiIcon name="PhGraduationCap" :size="27" weight="duotone" /></span>
          <div><span class="redesign-label">ACCOUNT CONNECTION</span><h2>学习通账号</h2></div>
          <span class="chaoxing-status" :class="status">{{ statusLabel }}</span>
        </div>

        <div v-if="checking" class="chaoxing-checking"><span></span><span></span><span></span></div>

        <template v-else-if="isConnected">
          <div class="chaoxing-stats">
            <div><small>课程</small><strong>{{ summary.courses }}</strong></div>
            <div><small>教师</small><strong>{{ summary.teachers }}</strong></div>
            <div><small>未完成作业</small><strong>{{ summary.pending_assignments }}</strong></div>
            <div><small>通知</small><strong>{{ summary.notices }}</strong></div>
          </div>
          <dl class="chaoxing-details">
            <div><dt>上次同步</dt><dd>{{ formatTime(lastSyncedAt) }}</dd></div>
            <div><dt>数据来源</dt><dd>{{ summary.source === "chaoxing_live" ? "学习通实时数据" : "学习通" }}</dd></div>
            <div><dt>同步位置</dt><dd>CampusMate 后端数据库</dd></div>
          </dl>
          <div class="chaoxing-actions">
            <button class="redesign-button primary" :disabled="syncing" @click="syncNow">
              <UiIcon name="PhArrowsClockwise" :class="{ spinning: syncing }" />{{ syncing ? "同步中…" : "立即同步" }}
            </button>
            <button class="redesign-button secondary" :disabled="disconnecting" @click="disconnect">
              <UiIcon name="PhLinkBreak" />{{ disconnecting ? "解除中…" : "解除连接" }}
            </button>
          </div>
        </template>

        <template v-else-if="needsLogin">
          <div v-if="status === 'expired'" class="chaoxing-expired"><UiIcon name="PhWarningCircle" />学习通会话已失效，重新登录后即可继续同步。</div>
          <div v-else-if="status === 'verification_required'" class="chaoxing-expired"><UiIcon name="PhWarningCircle" />学习通要求额外验证，请先前往学习通官方 App / 网页完成验证后重新登录。</div>
          <form class="chaoxing-form" @submit.prevent="login">
            <label><span>学号 / 手机号</span><input v-model="username" autocomplete="username" placeholder="请输入学习通账号" :disabled="loggingIn" /></label>
            <label><span>密码</span><div class="password-field"><input v-model="password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="请输入学习通密码" :disabled="loggingIn" /><button type="button" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword"><UiIcon :name="showPassword ? 'PhEyeSlash' : 'PhEye'" /></button></div></label>
            <button class="redesign-button primary" type="submit" :disabled="loggingIn || !username.trim() || !password">
              <UiIcon name="PhLink" />{{ loggingIn ? "连接中…" : status === 'expired' ? "重新登录" : "登录并连接" }}
            </button>
          </form>
          <p class="chaoxing-privacy"><UiIcon name="PhShieldCheck" />密码仅用于本次登录，浏览器和数据库都不会保存密码。</p>
          <button v-if="status === 'expired'" class="chaoxing-disconnect-link" :disabled="disconnecting" @click="disconnect">解除连接并保留历史数据</button>
        </template>

        <div v-else class="chaoxing-unavailable">
          <UiIcon name="PhCloudSlash" :size="34" />
          <h3>暂时无法验证连接</h3>
          <p>上次确认状态：{{ lastConfirmedStatus === "online" ? "已连接" : lastConfirmedStatus === "expired" ? "登录已失效" : "未连接" }}。网络恢复后可重新检查。</p>
          <button class="redesign-button secondary" @click="checkStatus"><UiIcon name="PhArrowClockwise" />重新检查</button>
        </div>
      </article>

      <aside class="chaoxing-side">
        <article class="redesign-panel chaoxing-flow"><span class="redesign-label">SYNC FLOW</span><h2>同步后会出现在哪里？</h2><div><span><UiIcon name="PhBookOpen" /></span><p><strong>课程</strong><small>在「我的课程」查看学习通课程与教师。</small></p></div><div><span><UiIcon name="PhCheckSquare" /></span><p><strong>作业</strong><small>未完成作业进入「待办与作业」。</small></p></div><div><span><UiIcon name="PhBell" /></span><p><strong>课程通知</strong><small>统一显示在「通知整理」。</small></p></div></article>
        <article class="redesign-panel chaoxing-note"><UiIcon name="PhDevices" :size="24" /><div><strong>同账号多端同步</strong><p>数据保存在后端，Web、Android 和鸿蒙登录同一 CampusMate 账号即可读取。</p></div></article>
      </aside>
    </section>

    <div v-if="message" class="redesign-alert chaoxing-message" :class="messageTone">
      <UiIcon :name="messageTone === 'success' ? 'PhCheckCircle' : 'PhWarningCircle'" />{{ message }}
    </div>
  </main>
</template>

<style scoped>
.chaoxing-heading { align-items: flex-end; }
.chaoxing-layout { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(280px, .75fr); gap: 18px; align-items: start; }
.chaoxing-status-card { padding: 24px; }
.chaoxing-status-head { display: flex; align-items: center; gap: 13px; }
.chaoxing-status-head h2, .chaoxing-flow h2 { margin: 3px 0 0; font-size: 20px; }
.chaoxing-brand { width: 50px; height: 50px; border-radius: 16px; display: grid; place-items: center; color: var(--primary); background: var(--primary-soft); }
.chaoxing-status { margin-left: auto; padding: 6px 11px; border-radius: 999px; font-size: 12px; font-weight: 750; color: var(--muted); background: #eef1f4; }
.chaoxing-status.online { color: #167a5b; background: #e4f6ee; }
.chaoxing-status.expired { color: #b64a32; background: #fdece8; }
.chaoxing-status.verification_required { color: #b64a32; background: #fdece8; }
.chaoxing-status.unavailable { color: #8b6814; background: #fff2cf; }
.chaoxing-checking { height: 150px; display: flex; align-items: center; justify-content: center; gap: 7px; }
.chaoxing-checking span { width: 9px; height: 9px; border-radius: 50%; background: var(--primary); animation: pulse 1s infinite alternate; }
.chaoxing-checking span:nth-child(2) { animation-delay: .2s; }.chaoxing-checking span:nth-child(3) { animation-delay: .4s; }
.chaoxing-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 22px 0; }
.chaoxing-stats div { padding: 15px; border-radius: 14px; background: var(--primary-soft); display: grid; gap: 4px; }.chaoxing-stats small { color: var(--muted); }.chaoxing-stats strong { color: var(--text); font-size: 24px; }
.chaoxing-details { margin: 0; border-top: 1px solid var(--line); }.chaoxing-details div { display: flex; justify-content: space-between; gap: 20px; padding: 12px 0; border-bottom: 1px solid var(--line); font-size: 13px; }.chaoxing-details dt { color: var(--muted); }.chaoxing-details dd { margin: 0; color: var(--text); font-weight: 650; text-align: right; }
.chaoxing-actions { display: flex; gap: 10px; margin-top: 20px; }.chaoxing-actions button { flex: 1; justify-content: center; }
.chaoxing-form { display: grid; gap: 15px; margin-top: 22px; max-width: 520px; }.chaoxing-form label { display: grid; gap: 7px; font-size: 13px; font-weight: 700; color: var(--text); }.chaoxing-form input { width: 100%; height: 46px; border: 1px solid var(--line); border-radius: 12px; padding: 0 13px; outline: none; background: var(--background); color: var(--text); }.chaoxing-form input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-soft); }.chaoxing-form > button { justify-content: center; height: 46px; }
.password-field { position: relative; }.password-field input { padding-right: 45px; }.password-field button { position: absolute; top: 5px; right: 5px; width: 36px; height: 36px; border: 0; border-radius: 9px; background: transparent; color: var(--muted); display: grid; place-items: center; }
.chaoxing-privacy, .chaoxing-expired { display: flex; align-items: center; gap: 7px; font-size: 12px; }.chaoxing-privacy { color: var(--muted); margin: 14px 0 0; }.chaoxing-expired { margin-top: 18px; padding: 11px; border-radius: 11px; background: #fdece8; color: #b64a32; }.chaoxing-disconnect-link { margin-top: 14px; padding: 0; border: 0; background: transparent; color: var(--muted); font-size: 12px; }
.chaoxing-unavailable { min-height: 210px; display: grid; place-items: center; align-content: center; text-align: center; color: var(--muted); }.chaoxing-unavailable h3 { margin: 9px 0 0; color: var(--text); }.chaoxing-unavailable p { max-width: 380px; line-height: 1.7; }.chaoxing-unavailable button { margin-top: 5px; }
.chaoxing-side { display: grid; gap: 14px; }.chaoxing-flow { padding: 20px; }.chaoxing-flow > div { display: flex; gap: 11px; margin-top: 17px; }.chaoxing-flow > div > span { width: 38px; height: 38px; border-radius: 11px; background: var(--primary-soft); color: var(--primary); display: grid; place-items: center; flex: 0 0 auto; }.chaoxing-flow p { margin: 0; display: grid; gap: 4px; }.chaoxing-flow small, .chaoxing-note p { color: var(--muted); line-height: 1.55; }.chaoxing-note { padding: 17px; display: flex; gap: 11px; color: var(--primary); }.chaoxing-note p { margin: 5px 0 0; font-size: 12px; }.chaoxing-note strong { color: var(--text); }
.chaoxing-message { margin-top: 16px; }.chaoxing-message.success { background: #e4f6ee; color: #167a5b; }.chaoxing-message.warning { background: #fff2cf; color: #8b6814; }
@keyframes pulse { to { opacity: .3; transform: translateY(-3px); } }
@media (max-width: 900px) { .chaoxing-layout { grid-template-columns: 1fr; }.chaoxing-stats { grid-template-columns: repeat(2, 1fr); }.chaoxing-heading { align-items: flex-start; }.chaoxing-actions { flex-direction: column; } }
</style>

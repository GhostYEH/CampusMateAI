<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import { useAppStore } from "../stores/app";
import UiIcon from "../components/UiIcon.vue";
import QRCode from "qrcode";
import { qrCreate, qrStatus, qrExchange } from "../services/api";

const store = useAppStore();
const router = useRouter();

// ===== 登录方式切换 =====
const mode = ref("account"); // "account" | "qr"

// ===== 账号密码登录 =====
const username = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");
const showPassword = ref(false);
async function submit() {
  error.value = "";
  loading.value = true;
  try { await store.login(username.value.trim(), password.value); router.push("/home"); }
  catch (e) { error.value = e.message || "登录失败，请稍后重试"; }
  finally { loading.value = false; }
}

// ===== 扫码登录 =====
const qrState = ref("idle"); // idle | generating | pending | scanned | confirmed | expired | cancelled | error
const qrError = ref("");
const qrDataUrl = ref("");
const qrSession = ref(null); // { session_id, browser_token }
let pollTimer = null;

function _stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

async function _generateQr() {
  _stopPolling();
  qrState.value = "generating";
  qrError.value = "";
  qrDataUrl.value = "";
  try {
    const resp = await qrCreate();
    qrSession.value = { session_id: resp.session_id, browser_token: resp.browser_token };
    qrDataUrl.value = await QRCode.toDataURL(resp.qr_payload, {
      width: 220,
      margin: 1,
      color: { dark: "#17232d", light: "#ffffff" },
      errorCorrectionLevel: "M",
    });
    qrState.value = "pending";
    _startPolling();
  } catch (e) {
    qrState.value = "error";
    const code = e.response?.data?.code;
    if (code === "QR_RATE_LIMITED") qrError.value = "生成过于频繁，请稍后再试";
    else qrError.value = e.message || "生成二维码失败，请重试";
  }
}

function _startPolling() {
  _stopPolling();
  pollTimer = setInterval(async () => {
    if (!qrSession.value) return;
    try {
      const status = await qrStatus(qrSession.value.session_id, qrSession.value.browser_token);
      if (status.status === "SCANNED" && qrState.value === "pending") {
        qrState.value = "scanned";
      } else if (status.status === "CONFIRMED") {
        qrState.value = "confirmed";
        _stopPolling();
        await _exchange();
      } else if (status.status === "EXPIRED") {
        qrState.value = "expired";
        _stopPolling();
      } else if (status.status === "CANCELLED") {
        qrState.value = "cancelled";
        _stopPolling();
      } else if (status.status === "CONSUMED") {
        // 可能是另一个 tab 已消费
        _stopPolling();
        qrState.value = "error";
        qrError.value = "二维码已被使用";
      }
    } catch (e) {
      // 网络错误不立即停止，保留上次状态
    }
  }, 1000);
}

async function _exchange() {
  try {
    const tokenPair = await qrExchange(qrSession.value.session_id, qrSession.value.browser_token);
    store.applyQrLoginResult(tokenPair);
    router.push("/home");
  } catch (e) {
    const code = e.response?.data?.code;
    if (code === "QR_ALREADY_CONSUMED") {
      qrState.value = "error";
      qrError.value = "二维码已被使用，请重新生成";
    } else if (code === "QR_EXPIRED") {
      qrState.value = "expired";
    } else if (code === "QR_CANCELLED") {
      qrState.value = "cancelled";
    } else {
      qrState.value = "error";
      qrError.value = e.message || "登录失败，请重试";
    }
  }
}

function _switchToQr() {
  mode.value = "qr";
  error.value = "";
  _generateQr();
}

function _switchToAccount() {
  mode.value = "account";
  _stopPolling();
  qrState.value = "idle";
  qrError.value = "";
  qrDataUrl.value = "";
}

function _refreshQr() {
  _generateQr();
}

// ===== trusted device 自动登录 =====
const autoLoginChecking = ref(true);
onMounted(async () => {
  // 如果已有登录态，不尝试自动登录
  if (store.session) { autoLoginChecking.value = false; return; }
  try {
    const ok = await store.tryTrustedDeviceAutoLogin();
    if (ok) {
      router.push("/home");
      return;
    }
  } catch { /* 忽略，正常显示登录页 */ }
  autoLoginChecking.value = false;
});

onBeforeUnmount(() => { _stopPolling(); });
</script>

<template>
  <main class="login-page">
    <div class="login-media" aria-hidden="true"><video src="/assets/login-campus.mp4" autoplay muted loop playsinline></video></div>
    <div class="login-shade"></div>
    <section class="login-story enter">
      <div class="brand brand-light"><span class="brand-mark"><UiIcon name="PhGraduationCap" :size="24" weight="fill" /></span><div><strong>CampusMate AI</strong><small>校园信息中枢</small></div></div>
      <div class="login-copy">
        <p class="eyebrow">你的校园事务工作台</p>
        <h1>把今天的校园生活<br />理清楚。</h1>
        <p>通知、课程、任务和 AI 导员，都在一个清晰的入口。</p>
      </div>
      <div class="login-feature"><span><UiIcon name="PhBell" />通知智能整理</span><span><UiIcon name="PhCheckSquare" />任务协同管理</span><span><UiIcon name="PhRobot" />AI 导员陪伴</span></div>
    </section>
    <section class="login-panel enter enter-delay">
      <div v-if="autoLoginChecking" class="qr-loading-zone"><div class="qr-spinner"></div><p>正在检查登录状态…</p></div>
      <template v-else>
        <div class="panel-head"><p class="eyebrow">欢迎回来</p><h2>登录 CampusMate</h2><p>查看校园通知、课程与个人待办</p></div>
        <div class="login-mode-switch">
          <button :class="{ active: mode === 'account' }" @click="_switchToAccount"><UiIcon name="PhUser" />账号登录</button>
          <button :class="{ active: mode === 'qr' }" @click="_switchToQr"><UiIcon name="PhQrCode" />扫码登录</button>
        </div>
        <!-- 账号密码登录 -->
        <form v-if="mode === 'account'" @submit.prevent="submit">
          <label>学号或用户名<div class="input-wrap"><UiIcon name="PhUser" /><input v-model="username" name="username" autocomplete="username" placeholder="请输入学号或用户名" /></div></label>
          <label>密码<div class="input-wrap"><UiIcon name="PhLock" /><input v-model="password" name="password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="请输入密码" /><button type="button" class="icon-button" @click="showPassword = !showPassword" :aria-label="showPassword ? '隐藏密码' : '显示密码'"><UiIcon :name="showPassword ? 'PhEyeSlash' : 'PhEye'" /></button></div></label>
          <div v-if="error" class="alert error"><UiIcon name="PhWarningCircle" />{{ error }}</div>
          <button class="primary-button login-submit" :disabled="loading">{{ loading ? "正在登录…" : "登录" }}<UiIcon v-if="!loading" name="PhArrowRight" /></button>
        </form>
        <!-- 扫码登录 -->
        <div v-if="mode === 'qr'" class="qr-login-zone">
          <div class="qr-frame">
            <div v-if="qrState === 'generating'" class="qr-overlay"><div class="qr-spinner"></div><p>正在生成二维码…</p></div>
            <img v-if="qrDataUrl" :src="qrDataUrl" alt="CampusMate 登录二维码" class="qr-image" :class="{ dim: qrState === 'scanned' || qrState === 'confirmed' }" />
            <div v-if="qrState === 'scanned'" class="qr-overlay qr-overlay-success"><UiIcon name="PhCheckCircle" :size="40" weight="fill" /><p>扫描成功</p><small>请在手机上确认登录</small></div>
            <div v-if="qrState === 'confirmed'" class="qr-overlay qr-overlay-success"><div class="qr-spinner"></div><p>正在登录…</p></div>
            <div v-if="qrState === 'expired'" class="qr-overlay qr-overlay-warn"><UiIcon name="PhClock" :size="40" weight="fill" /><p>二维码已过期</p><button class="qr-refresh-btn" @click="_refreshQr"><UiIcon name="PhArrowClockwise" />刷新二维码</button></div>
            <div v-if="qrState === 'cancelled'" class="qr-overlay qr-overlay-warn"><UiIcon name="PhXCircle" :size="40" weight="fill" /><p>已取消本次登录</p><button class="qr-refresh-btn" @click="_refreshQr"><UiIcon name="PhArrowClockwise" />重新生成</button></div>
            <div v-if="qrState === 'error'" class="qr-overlay qr-overlay-warn"><UiIcon name="PhWarningCircle" :size="40" weight="fill" /><p>{{ qrError || '发生错误' }}</p><button class="qr-refresh-btn" @click="_refreshQr"><UiIcon name="PhArrowClockwise" />重试</button></div>
          </div>
          <div class="qr-hint">
            <p v-if="qrState === 'pending'">打开 CampusMate 手机端<br />在「我的」右上角点击扫一扫</p>
            <p v-else-if="qrState === 'scanned'">请在手机上确认登录</p>
            <p v-else-if="qrState === 'confirmed'">正在登录，请稍候…</p>
            <p v-else>打开 CampusMate 手机端扫码登录</p>
          </div>
        </div>
        <div class="login-foot-actions"><span>请使用学校统一身份账号登录</span></div>
      </template>
    </section>
  </main>
</template>

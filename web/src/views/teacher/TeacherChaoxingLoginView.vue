<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import PageHeader from "../../components/teacher/PageHeader.vue";
import UiIcon from "../../components/UiIcon.vue";
import { useToast } from "../../composables/useToast";
import { loginChaoxing } from "../../services/teacher/chaoxing";

const router = useRouter();
const toast = useToast();

const username = ref("");
const password = ref("");
const showPassword = ref(false);
const isLoading = ref(false);
const error = ref("");

function errorDetail(err) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  return err?.message || "";
}

async function submit() {
  if (!username.value.trim() || !password.value) return;
  isLoading.value = true;
  error.value = "";
  try {
    await loginChaoxing(username.value.trim(), password.value);
    toast.success("学习通连接成功");
    router.replace("/teacher/chaoxing");
  } catch (err) {
    const detail = errorDetail(err);
    if (detail.includes("verification_required")) {
      error.value = "当前登录需要验证码，请先在学习通官方 App 或网页完成验证后重试。";
    } else if (detail.includes("reauth_required")) {
      error.value = "账号或密码不正确，请确认后重试。";
    } else {
      error.value = detail || "登录失败，请稍后重试";
    }
  } finally {
    isLoading.value = false;
  }
}

function back() {
  router.push("/teacher/chaoxing");
}
</script>

<template>
  <main class="tch-page page-enter">
    <PageHeader kicker="学习通同步" title="学习通账号登录" subtitle="仅用于连接学习通，本地不会保存你的密码。" />

    <section class="cx-login-card tch-panel">
      <div class="cx-login-head">
        <span class="cx-icon"><UiIcon name="PhGraduationCap" :size="20" weight="fill" /></span>
        <div>
          <strong>学习通账号登录</strong>
          <p>仅用于连接学习通，本地不会保存你的密码。</p>
        </div>
      </div>

      <form class="cx-form" @submit.prevent="submit">
        <label class="cx-field">
          <span>学号 / 手机号</span>
          <input
            v-model="username"
            type="text"
            autocomplete="username"
            placeholder="请输入学号或手机号"
            :disabled="isLoading"
          />
        </label>
        <label class="cx-field">
          <span>密码</span>
          <div class="cx-password">
            <input
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              placeholder="请输入密码"
              :disabled="isLoading"
            />
            <button type="button" class="cx-eye" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
              <UiIcon :name="showPassword ? 'PhEyeSlash' : 'PhEye'" :size="16" />
            </button>
          </div>
        </label>

        <button type="submit" class="primary-button" :disabled="!username.trim() || !password || isLoading">
          <UiIcon :name="isLoading ? 'PhCircleNotch' : 'PhGraduationCap'" :size="16" />
          {{ isLoading ? "登录中…" : "登录" }}
        </button>
      </form>

      <p v-if="error" class="cx-error">
        <UiIcon name="PhWarningCircle" :size="14" />{{ error }}
      </p>

      <button class="cx-back" @click="back"><UiIcon name="PhArrowLeft" :size="14" />返回</button>
    </section>
  </main>
</template>

<style scoped>
.cx-login-card {
  max-width: 460px;
}
.cx-login-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}
.cx-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: var(--primary-soft);
  color: var(--primary);
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
}
.cx-login-head strong {
  font-size: 15px;
  color: var(--text);
}
.cx-login-head p {
  margin: 3px 0 0;
  font-size: 12px;
  color: var(--muted);
}
.cx-form {
  display: grid;
  gap: 14px;
}
.cx-field {
  display: grid;
  gap: 6px;
}
.cx-field > span {
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
}
.cx-field input {
  width: 100%;
  height: 42px;
  padding: 0 12px;
  border: 1px solid #dfe5eb;
  border-radius: 10px;
  background: #fbfcfd;
  color: var(--text);
  font-size: 13px;
  outline: 0;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.cx-field input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-soft);
}
.cx-password {
  position: relative;
}
.cx-password input {
  padding-right: 40px;
}
.cx-eye {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  border: 0;
  background: transparent;
  color: var(--muted);
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: inline-grid;
  place-items: center;
}
.cx-eye:hover {
  color: var(--primary);
  background: var(--primary-soft);
}
.cx-form .primary-button {
  width: 100%;
  justify-content: center;
  height: 44px;
  margin-top: 4px;
}
.cx-error {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #c0432a;
}
.cx-back {
  margin-top: 16px;
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 0;
}
.cx-back:hover {
  color: var(--primary);
}
</style>
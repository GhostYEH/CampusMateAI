<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAppStore } from "../stores/app";
import UiIcon from "../components/UiIcon.vue";

const store = useAppStore();
const router = useRouter();
const username = ref("");
const password = ref("");
const loginRole = ref("student");
const loading = ref(false);
const error = ref("");
const showPassword = ref(false);
const videoFailed = ref(false);
async function submit() {
  error.value = "";
  loading.value = true;
  try { await store.login(username.value.trim(), password.value, loginRole.value); router.push("/home"); }
  catch (e) { error.value = e.message || "登录失败，请稍后重试"; }
  finally { loading.value = false; }
}
function selectRole(role) {
  loginRole.value = role;
  username.value = "";
  password.value = "";
  error.value = "";
}
function toggleAdmin() { selectRole(loginRole.value === "admin" ? "student" : "admin"); }
</script>

<template>
  <main class="login-page">
    <div class="login-media">
      <video v-if="!videoFailed" autoplay muted loop playsinline preload="auto" poster="/assets/campus-night.jpg" @error="videoFailed = true">
        <source src="/assets/login-campus.mp4" type="video/mp4" />
      </video>
      <img v-else src="/assets/campus-night.jpg" alt="夜色中的校园教学楼" />
    </div>
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
      <div class="panel-head"><p class="eyebrow">欢迎回来</p><h2>{{ loginRole === "student" ? "学生登录" : loginRole === "teacher" ? "教师登录" : "管理员登录" }}</h2><p>{{ loginRole === "student" ? "查看校园通知、课程与个人待办" : loginRole === "teacher" ? "发布教学任务并跟踪学生完成情况" : "管理校园活动与校内账号" }}</p></div>
      <div v-if="loginRole !== 'admin'" class="login-role-switch" aria-label="选择登录身份">
        <button type="button" :class="{ active: loginRole === 'student' }" @click="selectRole('student')"><UiIcon name="PhStudent" /><span><strong>学生</strong><small>校园事务与学习</small></span></button>
        <button type="button" :class="{ active: loginRole === 'teacher' }" @click="selectRole('teacher')"><UiIcon name="PhChalkboardTeacher" /><span><strong>教师</strong><small>课程任务与学情</small></span></button>
      </div>
      <div v-else class="login-admin-context"><UiIcon name="PhShieldCheck" :size="22" /><span><strong>受限管理入口</strong><small>仅限学校授权管理员使用</small></span></div>
      <form @submit.prevent="submit">
        <label>{{ loginRole === "student" ? "学号或用户名" : loginRole === "teacher" ? "工号或用户名" : "管理员账号" }}<div class="input-wrap"><UiIcon name="PhUser" /><input v-model="username" name="username" autocomplete="username" :placeholder="loginRole === 'student' ? '请输入学号或用户名' : loginRole === 'teacher' ? '请输入工号或用户名' : '请输入管理员账号'" /></div></label>
        <label>密码<div class="input-wrap"><UiIcon name="PhLock" /><input v-model="password" name="password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="请输入密码" /><button type="button" class="icon-button" @click="showPassword = !showPassword" :aria-label="showPassword ? '隐藏密码' : '显示密码'"><UiIcon :name="showPassword ? 'PhEyeSlash' : 'PhEye'" /></button></div></label>
        <div v-if="error" class="alert error"><UiIcon name="PhWarningCircle" />{{ error }}</div>
        <button class="primary-button login-submit" :disabled="loading">{{ loading ? "正在登录…" : "登录" }}<UiIcon v-if="!loading" name="PhArrowRight" /></button>
      </form>
      <div class="login-foot-actions"><button type="button" @click="toggleAdmin"><UiIcon name="PhShieldCheck" />{{ loginRole === "admin" ? "返回学生登录" : "管理员入口" }}</button><span>请使用学校统一身份账号登录</span></div>
    </section>
  </main>
</template>

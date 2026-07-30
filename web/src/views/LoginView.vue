<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAppStore } from "../stores/app";
import UiIcon from "../components/UiIcon.vue";

const store = useAppStore();
const router = useRouter();
const username = ref("student_demo");
const password = ref("Demo123456");
const loading = ref(false);
const error = ref("");
const showPassword = ref(false);
const videoFailed = ref(false);
async function submit() {
  error.value = "";
  loading.value = true;
  try { await store.login(username.value.trim(), password.value); router.push("/home"); }
  catch (e) { error.value = e.message || "登录失败，请稍后重试"; }
  finally { loading.value = false; }
}
function useDemo(name) { username.value = name; password.value = "Demo123456"; }
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
      <div class="panel-head"><p class="eyebrow">欢迎回来</p><h2>账号登录</h2><p>使用学号、工号或管理员账号登录</p></div>
      <form @submit.prevent="submit">
        <label>账号<div class="input-wrap"><UiIcon name="PhUser" /><input v-model="username" autocomplete="username" placeholder="请输入学号 / 工号 / 用户名" /></div></label>
        <label>密码<div class="input-wrap"><UiIcon name="PhLock" /><input v-model="password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="请输入密码" /><button type="button" class="icon-button" @click="showPassword = !showPassword" :aria-label="showPassword ? '隐藏密码' : '显示密码'"><UiIcon :name="showPassword ? 'PhEyeSlash' : 'PhEye'" /></button></div></label>
        <div v-if="error" class="alert error"><UiIcon name="PhWarningCircle" />{{ error }}</div>
        <button class="primary-button login-submit" :disabled="loading">{{ loading ? "正在登录…" : "登录" }}<UiIcon v-if="!loading" name="PhArrowRight" /></button>
      </form>
      <div class="demo-login"><span>演示账号</span><button @click="useDemo('student_demo')">学生</button><button @click="useDemo('teacher_demo')">教师</button><button @click="useDemo('admin_demo')">管理员</button></div>
      <p class="mode-note"><span class="status-dot"></span>{{ store.mockMode ? "当前为 Mock 演示模式" : "将连接真实后端" }}</p>
    </section>
  </main>
</template>

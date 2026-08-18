<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { useAppStore } from "../../stores/app";
import { getStudentProfile } from "../../services/studentApi";

const router = useRouter();
const store = useAppStore();
const loading = ref(true);
const error = ref("");
const saved = ref("");
const profile = ref({});

const preferences = ref({
  reduceMotion: localStorage.getItem("campus_reduce_motion") === "true",
  noticeReminder: localStorage.getItem("campus_notice_reminder") !== "false",
  compactList: localStorage.getItem("campus_compact_list") === "true",
  autoPlayVoice: localStorage.getItem("campus_autoplay_voice") === "true",
});

const privacy = ref({
  shareFocusStats: localStorage.getItem("campus_share_focus_stats") !== "false",
  showOnlineStatus: localStorage.getItem("campus_show_online") !== "false",
});

const notifications = ref({
  examReminder: localStorage.getItem("campus_exam_reminder") !== "false",
  taskDue: localStorage.getItem("campus_task_due") !== "false",
  announcement: localStorage.getItem("campus_announcement_notify") !== "false",
});

const theme = ref(localStorage.getItem("campus_theme") || "auto");

async function load() {
  loading.value = true;
  error.value = "";
  try {
    profile.value = await getStudentProfile().catch(() => ({}));
  } catch (e) {
    error.value = e.response?.data?.detail || "个人资料加载失败。";
  } finally {
    loading.value = false;
  }
}

function setPreference(key, value) {
  preferences.value[key] = value;
  const map = {
    reduceMotion: "campus_reduce_motion",
    noticeReminder: "campus_notice_reminder",
    compactList: "campus_compact_list",
    autoPlayVoice: "campus_autoplay_voice",
  };
  localStorage.setItem(map[key], String(value));
  if (key === "reduceMotion") store.setReduceMotion(value);
  flash("偏好已保存");
}

function setPrivacy(key, value) {
  privacy.value[key] = value;
  const map = { shareFocusStats: "campus_share_focus_stats", showOnlineStatus: "campus_show_online" };
  localStorage.setItem(map[key], String(value));
  flash("隐私设置已保存");
}

function setNotification(key, value) {
  notifications.value[key] = value;
  const map = {
    examReminder: "campus_exam_reminder",
    taskDue: "campus_task_due",
    announcement: "campus_announcement_notify",
  };
  localStorage.setItem(map[key], String(value));
  flash("通知设置已保存");
}

function setTheme(value) {
  theme.value = value;
  localStorage.setItem("campus_theme", value);
  flash("主题已保存");
}

function flash(msg) {
  saved.value = msg;
  window.setTimeout(() => { saved.value = ""; }, 1600);
}

function logout() {
  store.logout();
  router.replace("/login");
}

onMounted(load);
</script>

<template>
  <main class="student-page page-enter settings-page profile-settings-redesign">
    <div class="student-heading">
      <div>
        <button class="back-link" @click="router.push('/profile')"><UiIcon name="PhArrowLeft" />返回个人中心</button>
        <span class="eyebrow">PREFERENCES / 偏好设置</span>
        <h1>设置</h1>
        <p>管理账号、通知、隐私和界面偏好，设置保存在当前设备。</p>
      </div>
      <button class="secondary-button" :disabled="loading" @click="load"><UiIcon name="PhArrowClockwise" />刷新</button>
    </div>

    <div v-if="error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ error }}</div>
    <div v-if="saved" class="settings-flash"><UiIcon name="PhCheckCircle" />{{ saved }}</div>

    <div v-if="loading" class="settings-loading">加载中…</div>
    <template v-else>
      <section class="settings-section">
        <header><span class="settings-icon blue"><UiIcon name="PhUser" /></span><div><h2>账号设置</h2><p>查看你的身份信息与登录状态。</p></div></header>
        <div class="settings-card">
          <div class="settings-row"><span>姓名</span><strong>{{ profile.display_name || profile.username || "—" }}</strong></div>
          <div class="settings-row"><span>学号</span><strong>{{ profile.student_number || "—" }}</strong></div>
          <div class="settings-row"><span>学院</span><strong>{{ profile.college || "—" }}</strong></div>
          <div class="settings-row"><span>专业</span><strong>{{ profile.major || "—" }}</strong></div>
          <div class="settings-row"><span>邮箱</span><strong>{{ profile.email || "—" }}</strong></div>
          <div class="settings-actions">
            <button class="secondary-button" @click="router.push('/profile')"><UiIcon name="PhPencil" />编辑资料</button>
            <button class="danger-button" @click="logout"><UiIcon name="PhSignOut" />退出登录</button>
          </div>
        </div>
      </section>

      <section class="settings-section">
        <header><span class="settings-icon indigo"><UiIcon name="PhBell" /></span><div><h2>通知设置</h2><p>选择希望接收的提醒类型。</p></div></header>
        <div class="settings-card">
          <div class="toggle-row">
            <span><strong>考试提醒</strong><small>临近考试时提示复习与考场信息</small></span>
            <button class="preference-toggle" :class="{ on: notifications.examReminder }" :aria-pressed="notifications.examReminder" @click="setNotification('examReminder', !notifications.examReminder)"><i></i></button>
          </div>
          <div class="toggle-row">
            <span><strong>待办到期</strong><small>个人待办与作业临近截止时提醒</small></span>
            <button class="preference-toggle" :class="{ on: notifications.taskDue }" :aria-pressed="notifications.taskDue" @click="setNotification('taskDue', !notifications.taskDue)"><i></i></button>
          </div>
          <div class="toggle-row">
            <span><strong>校园通知</strong><small>接收校园公告与课程通知</small></span>
            <button class="preference-toggle" :class="{ on: notifications.announcement }" :aria-pressed="notifications.announcement" @click="setNotification('announcement', !notifications.announcement)"><i></i></button>
          </div>
        </div>
      </section>

      <section class="settings-section">
        <header><span class="settings-icon amber"><UiIcon name="PhLock" /></span><div><h2>隐私设置</h2><p>控制个人数据的可见范围。</p></div></header>
        <div class="settings-card">
          <div class="toggle-row">
            <span><strong>共享专注统计</strong><small>允许将学习陪伴时长纳入校园统计</small></span>
            <button class="preference-toggle" :class="{ on: privacy.shareFocusStats }" :aria-pressed="privacy.shareFocusStats" @click="setPrivacy('shareFocusStats', !privacy.shareFocusStats)"><i></i></button>
          </div>
          <div class="toggle-row">
            <span><strong>展示在线状态</strong><small>在其他同学视图中显示在线</small></span>
            <button class="preference-toggle" :class="{ on: privacy.showOnlineStatus }" :aria-pressed="privacy.showOnlineStatus" @click="setPrivacy('showOnlineStatus', !privacy.showOnlineStatus)"><i></i></button>
          </div>
        </div>
      </section>

      <section class="settings-section">
        <header><span class="settings-icon teal"><UiIcon name="PhPaintBrush" /></span><div><h2>主题与界面</h2><p>调整界面外观与交互偏好。</p></div></header>
        <div class="settings-card">
          <div class="settings-row"><span>主题模式</span>
            <div class="segmented">
              <button :class="{ active: theme === 'auto' }" @click="setTheme('auto')">跟随系统</button>
              <button :class="{ active: theme === 'light' }" @click="setTheme('light')">浅色</button>
              <button :class="{ active: theme === 'dark' }" @click="setTheme('dark')">深色</button>
            </div>
          </div>
          <div class="toggle-row">
            <span><strong>减少动态效果</strong><small>关闭页面进入动画与过渡</small></span>
            <button class="preference-toggle" :class="{ on: preferences.reduceMotion }" :aria-pressed="preferences.reduceMotion" @click="setPreference('reduceMotion', !preferences.reduceMotion)"><i></i></button>
          </div>
          <div class="toggle-row">
            <span><strong>紧凑列表</strong><small>在列表视图中使用更紧凑的间距</small></span>
            <button class="preference-toggle" :class="{ on: preferences.compactList }" :aria-pressed="preferences.compactList" @click="setPreference('compactList', !preferences.compactList)"><i></i></button>
          </div>
          <div class="toggle-row">
            <span><strong>AI 语音自动播放</strong><small>AI 校园助手回复后自动朗读</small></span>
            <button class="preference-toggle" :class="{ on: preferences.autoPlayVoice }" :aria-pressed="preferences.autoPlayVoice" @click="setPreference('autoPlayVoice', !preferences.autoPlayVoice)"><i></i></button>
          </div>
        </div>
      </section>

      <section class="settings-section">
        <header><span class="settings-icon violet"><UiIcon name="PhSignOut" /></span><div><h2>账号操作</h2><p>退出当前账号或返回个人中心。</p></div></header>
        <div class="settings-card">
          <div class="settings-actions">
            <button class="secondary-button" @click="router.push('/home')"><UiIcon name="PhHouse" />回到首页</button>
            <button class="danger-button" @click="logout"><UiIcon name="PhSignOut" />退出登录</button>
          </div>
        </div>
      </section>
    </template>
  </main>
</template>

<style scoped>
.settings-page { display: flex; flex-direction: column; gap: 20px; }
.settings-flash { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; background: #ecfdf5; color: #059669; border-radius: 8px; font-size: 13px; align-self: flex-start; }
.settings-loading { padding: 40px; text-align: center; color: #6b7280; }
.settings-section { background: #fff; border-radius: 14px; box-shadow: 0 1px 3px rgba(15,23,42,.04); overflow: hidden; }
.settings-section header { display: flex; align-items: center; gap: 14px; padding: 18px 22px; border-bottom: 1px solid #f1f5f9; }
.settings-icon { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #fff; }
.settings-icon.blue { background: #2563eb; }
.settings-icon.indigo { background: #4f46e5; }
.settings-icon.amber { background: #d97706; }
.settings-icon.teal { background: #0d9488; }
.settings-icon.violet { background: #7c3aed; }
.settings-section h2 { margin: 0; font-size: 16px; }
.settings-section p { margin: 2px 0 0; color: #6b7280; font-size: 12px; }
.settings-card { padding: 8px 22px 18px; display: flex; flex-direction: column; gap: 4px; }
.settings-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #f8fafc; font-size: 14px; }
.settings-row span { color: #6b7280; }
.settings-row strong { color: #111827; font-weight: 500; }
.toggle-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #f8fafc; gap: 16px; }
.toggle-row strong { display: block; font-size: 14px; color: #111827; }
.toggle-row small { display: block; font-size: 12px; color: #6b7280; margin-top: 2px; }
.preference-toggle { width: 42px; height: 24px; border-radius: 999px; background: #cbd5e1; border: none; cursor: pointer; position: relative; transition: background .2s; padding: 0; flex-shrink: 0; }
.preference-toggle i { position: absolute; top: 2px; left: 2px; width: 20px; height: 20px; border-radius: 50%; background: #fff; transition: left .2s; box-shadow: 0 1px 2px rgba(0,0,0,.2); }
.preference-toggle.on { background: #2563eb; }
.preference-toggle.on i { left: 20px; }
.segmented { display: inline-flex; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }
.segmented button { background: #fff; border: none; padding: 6px 12px; font-size: 12px; cursor: pointer; color: #6b7280; }
.segmented button.active { background: #2563eb; color: #fff; }
.settings-actions { display: flex; gap: 10px; padding-top: 12px; flex-wrap: wrap; }
.secondary-button, .danger-button { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 8px; font-size: 13px; cursor: pointer; border: none; }
.secondary-button { background: #f3f4f6; color: #374151; }
.danger-button { background: #fef2f2; color: #dc2626; }
.secondary-button:hover { background: #e5e7eb; }
.danger-button:hover { background: #fee2e2; }
</style>

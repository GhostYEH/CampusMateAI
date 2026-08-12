<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import {
  getLostFound,
  getServiceRequests,
  getStudentProfile,
  getStudySessions,
} from "../../services/studentApi";

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const error = ref("");
const notice = ref("");
const profile = ref({});
const items = ref([]);
const sessions = ref([]);
const query = ref("");

const section = computed(() => String(route.params.section || "favorites"));

const sectionItems = [
  { key: "favorites", label: "我的收藏", icon: "PhBookmarkSimple" },
  { key: "files", label: "课程资料", icon: "PhFiles" },
  { key: "requests", label: "申请记录", icon: "PhClipboardText" },
  { key: "published", label: "我的发布", icon: "PhMegaphone" },
  { key: "learning", label: "学习记录", icon: "PhChartLineUp" },
  { key: "id-card", label: "校园身份卡", icon: "PhIdentificationCard" },
];

const sectionMeta = {
  favorites: {
    eyebrow: "SAVED / 收藏中心",
    title: "我的收藏",
    desc: "把重要的活动、教室和校园内容留在这里，之后继续处理。",
    icon: "PhBookmarkSimple",
    tone: "violet",
  },
  files: {
    eyebrow: "FILES / 课程资料",
    title: "课程资料",
    desc: "从课程详情进入课程附件，统一查看和下载学习资料。",
    icon: "PhFiles",
    tone: "blue",
  },
  requests: {
    eyebrow: "REQUESTS / 办事申请",
    title: "申请记录",
    desc: "跟进你提交给校园服务中心的每一条申请。",
    icon: "PhClipboardText",
    tone: "green",
  },
  published: {
    eyebrow: "PUBLISHED / 失物招领",
    title: "我的发布",
    desc: "查看你发布的失物与招领信息，及时跟进认领状态。",
    icon: "PhMegaphone",
    tone: "amber",
  },
  learning: {
    eyebrow: "LEARNING / 学习记录",
    title: "学习记录",
    desc: "回看每一次专注学习，把投入的时间变成清晰的进步。",
    icon: "PhChartLineUp",
    tone: "indigo",
  },
  "id-card": {
    eyebrow: "IDENTITY / 校园身份",
    title: "校园身份卡",
    desc: "集中查看你的校园身份信息，需要时快速出示或复制学号。",
    icon: "PhIdentificationCard",
    tone: "blue",
  },
};

const meta = computed(() => sectionMeta[section.value] || sectionMeta.favorites);
const displayName = computed(() => profile.value.display_name || profile.value.username || "同学");
const initial = computed(() => displayName.value.slice(0, 1));
const identityLine = computed(() => [profile.value.college, profile.value.major, profile.value.grade].filter(Boolean).join(" · ") || "完善你的校园资料，让陪伴更贴近");
const completedSessions = computed(() => sessions.value.filter((item) => item.status === "completed"));
const totalMinutes = computed(() => completedSessions.value.reduce((total, item) => total + Math.round((item.duration_seconds || 0) / 60), 0));
const averageMinutes = computed(() => completedSessions.value.length ? Math.round(totalMinutes.value / completedSessions.value.length) : 0);
const requestStats = computed(() => ({
  total: items.value.length,
  active: items.value.filter((item) => !["completed", "closed"].includes(item.status)).length,
  done: items.value.filter((item) => ["completed", "closed"].includes(item.status)).length,
}));
const filteredItems = computed(() => {
  const value = query.value.trim().toLocaleLowerCase();
  if (!value) return items.value;
  return items.value.filter((item) => `${item.title || ""} ${item.content || ""} ${item.kind || ""} ${item.location || ""}`.toLocaleLowerCase().includes(value));
});
const timeline = computed(() => [...sessions.value].sort((a, b) => new Date(b.started_at || b.created_at || 0) - new Date(a.started_at || a.created_at || 0)).slice(0, 12));

function formatDate(value, withTime = false) {
  if (!value) return "时间待记录";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return date.toLocaleString("zh-CN", withTime ? { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" } : { year: "numeric", month: "long", day: "numeric" });
}

function durationText(item) {
  const minutes = Math.round((item.duration_seconds || 0) / 60);
  return minutes ? `${minutes} 分钟` : item.status === "completed" ? "已完成" : "进行中";
}

function statusLabel(value) {
  return ({ submitted: "已提交", processing: "处理中", completed: "已办结", closed: "已关闭", open: "寻找中", claimed: "已认领" }[value] || value || "待更新");
}

function statusTone(value) {
  return ["completed", "closed", "claimed"].includes(value) ? "green" : ["processing", "open"].includes(value) ? "amber" : "blue";
}

function itemTitle(item) {
  return item.title || item.name || (item.kind === "found" ? "招领信息" : "校园申请");
}

function itemSubtitle(item) {
  if (section.value === "requests") return `${item.kind || "校园服务"} · ${formatDate(item.created_at)}`;
  return `${item.location || item.kind || "校园服务"} · ${formatDate(item.created_at)}`;
}

function openItem(item) {
  if (!item?.id) return;
  if (section.value === "requests") router.push(`/services/${item.id}`);
  if (section.value === "published") router.push(`/lostfound/${item.id}`);
}

function goSection(key) {
  router.push(`/profile/${key}`);
}

function goBack() {
  router.push("/profile");
}

function flash(message) {
  notice.value = message;
  window.setTimeout(() => {
    if (notice.value === message) notice.value = "";
  }, 1800);
}

async function copyStudentNumber() {
  if (!profile.value.student_number || !navigator.clipboard) {
    flash("当前没有可复制的学号");
    return;
  }
  await navigator.clipboard.writeText(profile.value.student_number);
  flash("学号已复制");
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    profile.value = await getStudentProfile().catch(() => ({}));
    if (section.value === "requests") {
      const data = await getServiceRequests();
      items.value = Array.isArray(data) ? data : data?.items || [];
    } else if (section.value === "published") {
      const data = await getLostFound({ mine: true });
      items.value = Array.isArray(data) ? data : data?.items || [];
    } else if (section.value === "learning") {
      const data = await getStudySessions();
      sessions.value = Array.isArray(data) ? data : data?.items || [];
    } else {
      items.value = [];
      sessions.value = [];
    }
  } catch (err) {
    error.value = err.response?.data?.detail || "个人中心数据加载失败，请稍后重试。";
  } finally {
    loading.value = false;
  }
}

watch(section, () => {
  query.value = "";
  void load();
});
onMounted(load);
</script>

<template>
  <main class="student-page profile-secondary-page page-enter">
    <section class="profile-secondary-hero redesign-panel">
      <div class="profile-secondary-hero-copy">
        <button class="profile-secondary-back" @click="goBack"><UiIcon name="PhArrowLeft" :size="16" />返回个人中心</button>
        <span class="redesign-kicker">{{ meta.eyebrow }}</span>
        <div class="profile-secondary-title-row"><span class="profile-secondary-title-icon" :class="meta.tone"><UiIcon :name="meta.icon" :size="22" /></span><h1>{{ meta.title }}</h1></div>
        <p>{{ meta.desc }}</p>
      </div>
      <div class="profile-secondary-hero-side">
        <div class="profile-secondary-identity"><span class="profile-secondary-avatar">{{ initial }}</span><span><strong>{{ displayName }}</strong><small>{{ identityLine }}</small></span></div>
        <button class="redesign-button secondary" :disabled="loading" @click="load"><UiIcon name="PhArrowClockwise" :class="{ spinning: loading }" />刷新</button>
      </div>
    </section>

    <nav class="profile-secondary-nav" aria-label="个人中心二级导航">
      <button v-for="item in sectionItems" :key="item.key" :class="{ active: section === item.key }" @click="goSection(item.key)"><UiIcon :name="item.icon" :size="16" />{{ item.label }}</button>
    </nav>

    <div v-if="notice" class="profile-secondary-notice"><UiIcon name="PhCheckCircle" />{{ notice }}</div>
    <div v-if="error" class="redesign-alert error"><UiIcon name="PhWarningCircle" /><span>{{ error }}</span><button @click="load">重试</button></div>

    <div v-if="loading" class="profile-secondary-loading"><span></span><span></span><span></span></div>

    <template v-else>
      <section v-if="section === 'id-card'" class="profile-id-layout">
        <article class="profile-id-card redesign-panel">
          <div class="profile-id-card-top"><span class="redesign-kicker">CAMPUSMATE IDENTITY</span><UiIcon name="PhSealCheck" :size="24" weight="duotone" /></div>
          <div class="profile-id-card-main"><div class="profile-id-seal">{{ initial }}</div><div><span class="profile-id-label">校园身份</span><h2>{{ displayName }}</h2><p>{{ profile.student_number || "学号待完善" }}</p></div><span class="profile-id-student-tag">本科生</span></div>
          <div class="profile-id-divider"></div>
          <dl class="profile-id-details"><div><dt>所属学院</dt><dd>{{ profile.college || "待完善" }}</dd></div><div><dt>专业方向</dt><dd>{{ profile.major || "待完善" }}</dd></div><div><dt>年级</dt><dd>{{ profile.grade || "待完善" }}</dd></div><div><dt>账户状态</dt><dd class="success">正常</dd></div></dl>
          <div class="profile-id-card-foot"><span><UiIcon name="PhCheckCircle" />身份信息来自 CampusMate 登录账户</span><button class="text-action" @click="copyStudentNumber"><UiIcon name="PhCopy" />复制学号</button></div>
        </article>
        <aside class="profile-id-side">
          <article class="redesign-panel profile-id-qr"><div class="profile-id-qr-art"><UiIcon name="PhQrCode" :size="80" weight="duotone" /></div><span class="redesign-label">QUICK VERIFY</span><h2>需要出示身份？</h2><p>在课程、校园活动或办事服务中，可直接打开这张身份卡核对个人信息。</p><button class="redesign-button primary" @click="copyStudentNumber"><UiIcon name="PhCopy" />复制学号</button></article>
          <article class="redesign-panel profile-id-tip"><UiIcon name="PhShieldCheck" :size="22" /><div><strong>信息安全提示</strong><p>请勿将身份卡截图分享给不熟悉的人，涉及账号安全时请联系学校服务中心。</p></div></article>
        </aside>
      </section>

      <section v-else-if="section === 'learning'" class="profile-learning-layout">
        <div class="profile-learning-main">
          <div class="profile-learning-stats"><article class="redesign-panel"><span class="profile-summary-icon indigo"><UiIcon name="PhClock" /></span><span><small>累计专注时长</small><strong>{{ totalMinutes ? `${(totalMinutes / 60).toFixed(1)}h` : "—" }}</strong><em>来自已完成的学习记录</em></span></article><article class="redesign-panel"><span class="profile-summary-icon green"><UiIcon name="PhCheckCircle" /></span><span><small>完成学习次数</small><strong>{{ completedSessions.length || "—" }}</strong><em>保持自己的节奏</em></span></article><article class="redesign-panel"><span class="profile-summary-icon amber"><UiIcon name="PhChartLineUp" /></span><span><small>平均单次时长</small><strong>{{ averageMinutes ? `${averageMinutes}m` : "—" }}</strong><em>完成记录的平均值</em></span></article></div>
          <article class="redesign-panel profile-timeline-panel"><div class="redesign-panel-head"><div><span class="redesign-label">ACTIVITY TIMELINE</span><h2>专注记录</h2></div><button class="link-action" @click="router.push('/study')">打开学习陪伴 <UiIcon name="PhArrowRight" :size="14" /></button></div><div v-if="timeline.length" class="profile-timeline"><div v-for="item in timeline" :key="item.id" class="profile-timeline-item"><span class="profile-timeline-dot" :class="item.status === 'completed' ? 'done' : 'active'"><UiIcon :name="item.status === 'completed' ? 'PhCheck' : 'PhClock'" :size="12" weight="bold" /></span><span class="profile-timeline-copy"><strong>{{ item.goal || "一次学习陪伴" }}</strong><small>{{ formatDate(item.started_at || item.created_at, true) }} · {{ durationText(item) }}</small><em>{{ item.status === "completed" ? "已完成" : "进行中" }}</em></span></div></div><div v-else class="profile-secondary-empty"><UiIcon name="PhChartLineUp" :size="42" /><strong>还没有学习记录</strong><span>去学习陪伴开始一次专注，完成后会在这里留下轨迹。</span><button class="redesign-button primary" @click="router.push('/study')"><UiIcon name="PhPlay" />开始专注</button></div></article>
        </div>
        <aside class="profile-learning-side"><article class="redesign-panel profile-next-step"><span class="redesign-label">NEXT STEP</span><h2>让下一次专注更轻松</h2><p>先设定一个小目标，再交给 CampusMate 帮你守住这段时间。</p><button class="redesign-button primary" @click="router.push('/study')"><UiIcon name="PhPlay" />开始学习</button></article><article class="redesign-panel profile-learning-note"><UiIcon name="PhSparkle" :size="22" /><strong>小建议</strong><p>把大任务拆成 25–45 分钟的小段，每完成一次就回来看看自己的进步。</p></article></aside>
      </section>

      <section v-else-if="section === 'favorites'" class="profile-secondary-workspace favorites-workspace">
        <div class="profile-summary-grid"><article class="redesign-panel"><span class="profile-summary-icon violet"><UiIcon name="PhBookmarkSimple" /></span><span><small>已收藏内容</small><strong>—</strong><em>收藏服务尚未接入统一数据源</em></span></article><article class="redesign-panel"><span class="profile-summary-icon blue"><UiIcon name="PhCalendarStar" /></span><span><small>活动收藏</small><strong>—</strong><em>浏览活动时可继续关注</em></span></article><article class="redesign-panel"><span class="profile-summary-icon green"><UiIcon name="PhBuildings" /></span><span><small>空间收藏</small><strong>—</strong><em>空教室收藏保存在对应页面</em></span></article></div>
        <article class="redesign-panel profile-secondary-empty profile-favorites-empty"><span class="profile-empty-orbit violet"><UiIcon name="PhBookmarkSimple" :size="26" /></span><span class="redesign-label">YOUR SAVED SPACE</span><h2>收藏中心正在等你放入第一条内容</h2><p>活动详情和空教室页面都支持收藏。收藏服务接入后，你可以在这里集中查看，不需要重复搜索。</p><div class="profile-empty-actions"><button class="redesign-button primary" @click="router.push('/campus-activities')"><UiIcon name="PhCalendarStar" />浏览校园活动</button><button class="redesign-button secondary" @click="router.push('/classrooms')"><UiIcon name="PhBuildings" />查找空教室</button></div></article>
      </section>

      <section v-else-if="section === 'files'" class="profile-secondary-workspace files-workspace">
        <article class="redesign-panel profile-file-guide"><div class="profile-file-guide-icon"><UiIcon name="PhFolderOpen" :size="28" /></div><div><span class="redesign-label">COURSE MATERIALS</span><h2>课程资料从课程详情进入</h2><p>每门课程的公告、作业和附件会按照课程组织，进入课程后可以继续查看上下文。</p><button class="redesign-button primary" @click="router.push('/courses')"><UiIcon name="PhBookOpen" />打开我的课程</button></div><div class="profile-file-guide-art"><UiIcon name="PhFiles" :size="74" weight="duotone" /></div></article>
        <div class="profile-file-columns"><article class="redesign-panel profile-secondary-empty"><UiIcon name="PhFiles" :size="42" /><strong>这里还没有独立文件</strong><span>个人文件存储尚未接入学校文件系统。课程资料会保留在具体课程详情中，方便你理解文件对应的作业和通知。</span><button class="link-action" @click="router.push('/courses')">查看课程列表 <UiIcon name="PhArrowRight" /></button></article><article class="redesign-panel profile-file-tips"><span class="redesign-label">FILE FLOW</span><h2>资料使用路径</h2><div><span>01</span><p><strong>打开课程</strong><small>从课程列表选择对应课程</small></p></div><div><span>02</span><p><strong>查看课程详情</strong><small>在公告和作业中找到附件</small></p></div><div><span>03</span><p><strong>下载或继续学习</strong><small>回到学习陪伴完成下一步</small></p></div></article></div>
      </section>

      <section v-else class="profile-secondary-workspace records-workspace">
        <div class="profile-summary-grid"><article class="redesign-panel"><span class="profile-summary-icon blue"><UiIcon :name="meta.icon" /></span><span><small>{{ section === "published" ? "我的发布" : "全部申请" }}</small><strong>{{ requestStats.total }}</strong><em>来自服务端实时记录</em></span></article><article class="redesign-panel"><span class="profile-summary-icon amber"><UiIcon name="PhHourglass" /></span><span><small>处理中</small><strong>{{ requestStats.active }}</strong><em>需要继续关注的事项</em></span></article><article class="redesign-panel"><span class="profile-summary-icon green"><UiIcon name="PhSealCheck" /></span><span><small>已完成</small><strong>{{ requestStats.done }}</strong><em>已经闭环的记录</em></span></article></div>
        <article class="redesign-panel profile-records-panel"><div class="redesign-panel-head"><div><span class="redesign-label">RECORDS</span><h2>{{ section === "published" ? "发布记录" : "申请进度" }}</h2></div><label class="profile-record-search"><UiIcon name="PhMagnifyingGlass" :size="16" /><input v-model="query" placeholder="搜索标题或类型" /></label></div><div v-if="filteredItems.length" class="profile-record-list"><button v-for="item in filteredItems" :key="item.id" class="profile-record-row" @click="openItem(item)"><span class="profile-record-icon" :class="statusTone(item.status)"><UiIcon :name="section === 'published' ? 'PhMegaphone' : 'PhClipboardText'" :size="19" /></span><span class="profile-record-copy"><strong>{{ itemTitle(item) }}</strong><small>{{ itemSubtitle(item) }}</small></span><span class="status-pill" :class="statusTone(item.status)">{{ statusLabel(item.status) }}</span><UiIcon name="PhCaretRight" :size="16" /></button></div><div v-else class="profile-secondary-empty compact"><UiIcon :name="meta.icon" :size="42" /><strong>{{ query ? "没有匹配的记录" : section === "published" ? "还没有发布记录" : "还没有申请记录" }}</strong><span>{{ query ? "换个关键词试试，或清除搜索条件。" : section === "published" ? "在失物招领页面发布信息后，会在这里继续跟进。" : "从办事大厅提交第一条申请后，会在这里查看进度。" }}</span><button class="redesign-button primary" @click="router.push(section === 'published' ? '/lostfound' : '/services')"><UiIcon name="PhPlus" />{{ section === "published" ? "去失物招领" : "去办事大厅" }}</button></div></article>
      </section>
    </template>
  </main>
</template>

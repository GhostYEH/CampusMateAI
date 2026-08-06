<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { chatStream } from "../../services/api";
import { createPersonalTask } from "../../services/studentApi";

const route = useRoute();
const router = useRouter();
const input = ref("");
const sending = ref(false);
const messages = ref([]);
const sources = ref([]);
const conversationId = ref("");
const sessions = ref([]);
const error = ref("");
const chatEl = ref(null);
const aborter = ref(null);

const suggestions = [
  "期末考试周怎么安排复习？",
  "我要申请课程重修，需要准备什么？",
  "帮我把这周任务排一个轻重缓急",
  "校园卡丢失了，怎么挂失补办？",
];

const quickServices = [
  { label: "学籍与成绩", hint: "学籍异动、成绩查询、证明开具", icon: "PhShieldCheck" },
  { label: "奖助与资助", hint: "奖学金、助学金申请", icon: "PhThumbsUp" },
  { label: "住宿与生活", hint: "宿舍申请、报修服务", icon: "PhHouse" },
  { label: "教材与选课", hint: "教材预订、选课指南", icon: "PhBookOpen" },
  { label: "校园卡与消费", hint: "校园卡挂失、充值查询", icon: "PhTag" },
];

const sampleAnswer = `期末考试周的复习建议如下，结合近期课程安排与常见复习方法，帮你高效备考：

1. 制定复习计划：按科目和权重分配时间，优先复习高难度与高分值内容。
2. 梳理知识框架：先搭建各科知识框架，再填充细节，形成完整体系。
3. 真题与错题：近年真题至少做两遍，错题本定期回顾避免重复错误。
4. 合理作息：保持规律作息，每天保证 7-8 小时睡眠，适度运动放松。

需要我帮你生成一份个性化复习计划表吗？`;

const sampleSources = [
  { title: "教务处：期末考试安排通知", section: "官方通知" },
  { title: "学风建设中心：高效复习指南", section: "学习建议" },
  { title: "心理中心：考试周期压力调适建议", section: "心理支持" },
];

const sessionPreview = [
  { id: "preview-1", title: "关于期末考试复习安排", displayTime: "10:42", messages: [{ role: "user", text: "期末考试周怎么安排复习？" }, { role: "assistant", text: sampleAnswer }], sources: sampleSources },
  { id: "preview-2", title: "申请课程重修流程", displayTime: "昨天", messages: [{ role: "user", text: "我想申请课程重修，需要准备什么？" }, { role: "assistant", text: "可以先确认重修申请时间，再准备成绩单、课程信息和申请表。" }] },
  { id: "preview-3", title: "校园网故障报修怎么操作", displayTime: "8月9日", messages: [{ role: "user", text: "校园网故障应该怎么报修？" }, { role: "assistant", text: "可在校园服务中提交网络报修，填写宿舍楼栋、房间号和故障现象。" }] },
  { id: "preview-4", title: "奖学金评定标准是什么？", displayTime: "8月7日", messages: [{ role: "user", text: "奖学金评定标准是什么？" }, { role: "assistant", text: "不同奖项的评定条件会有差异，建议先查看学生手册中的评定细则。" }] },
];

const displaySessions = computed(() => (sessions.value.length ? sessions.value : sessionPreview));

function scroll() {
  setTimeout(() => {
    if (chatEl.value) chatEl.value.scrollTop = chatEl.value.scrollHeight;
  }, 20);
}

function newSession() {
  conversationId.value = `web-${Date.now()}`;
  messages.value = [
    { role: "user", text: "期末考试周怎么安排复习？" },
    { role: "assistant", text: sampleAnswer },
  ];
  sources.value = sampleSources;
  input.value = "";
  error.value = "";
}

function loadSessions() {
  try {
    sessions.value = JSON.parse(localStorage.getItem("campus_counselor_sessions") || "[]");
  } catch {
    sessions.value = [];
  }
}

function saveSession() {
  const first = messages.value.find((item) => item.role === "user");
  if (!first) return;
  const next = [{ id: conversationId.value, title: first.text.slice(0, 24), updatedAt: new Date().toISOString(), messages: messages.value, sources: sources.value }, ...sessions.value.filter((item) => item.id !== conversationId.value)].slice(0, 12);
  sessions.value = next;
  localStorage.setItem("campus_counselor_sessions", JSON.stringify(next));
}

function restoreSession(item) {
  conversationId.value = item.id;
  messages.value = item.messages || [];
  sources.value = item.sources || [];
  error.value = "";
  scroll();
}

function sessionTime(item) {
  if (item.displayTime) return item.displayTime;
  const date = new Date(item.updatedAt);
  return Number.isNaN(date.getTime()) ? "刚刚" : date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

async function send(text = input.value) {
  const value = text.trim();
  if (!value || sending.value) return;
  messages.value.push({ role: "user", text: value });
  input.value = "";
  sending.value = true;
  sources.value = [];
  const pending = { role: "assistant", text: "", streaming: true };
  messages.value.push(pending);
  aborter.value = new AbortController();
  scroll();
  try {
    await chatStream(value, {
      signal: aborter.value.signal,
      onSources: (items) => { sources.value = items || []; },
      onChunk: (chunk) => { pending.text += chunk; messages.value = [...messages.value]; scroll(); },
      onDone: (meta) => { conversationId.value = meta?.conversation_id || conversationId.value; pending.streaming = false; pending.meta = meta; messages.value = [...messages.value]; saveSession(); },
      onError: (e) => { pending.streaming = false; pending.text = pending.text || `暂时无法连接校园知识库：${e.message}`; messages.value = [...messages.value]; },
    });
  } finally {
    sending.value = false;
    aborter.value = null;
    scroll();
  }
}

async function turnToTask() {
  const last = [...messages.value].reverse().find((item) => item.role === "assistant" && item.text);
  if (!last) return;
  try {
    await createPersonalTask({ title: last.text.slice(0, 80), description: last.text, source_name: "AI 导员对话", source_text: last.text });
    error.value = "已保存为个人待办，可在待办与作业页面继续编辑。";
  } catch (e) {
    error.value = e.response?.data?.detail || "保存待办失败，请稍后重试。";
  }
}

async function copyAnswer(text) {
  try {
    await navigator.clipboard?.writeText(text);
    error.value = "回答已复制。";
    setTimeout(() => { if (error.value === "回答已复制。") error.value = ""; }, 1800);
  } catch {
    error.value = "当前浏览器不支持复制，请手动选择文字。";
  }
}

onMounted(() => {
  loadSessions();
  newSession();
  if (route.query.prompt) send(String(route.query.prompt));
});

onBeforeUnmount(() => aborter.value?.abort());
</script>

<template>
  <main class="student-page counselor-page page-enter">
    <section class="counselor-hero counselor-hero-bg">
      <div class="counselor-hero-content">
        <span class="hero-eyebrow">AI COUNSELOR / 校园智能向导</span>
        <div class="student-title-line hero-title">
          <h1>AI 导员</h1>
          <UiIcon name="PhSparkle" class="heading-sparkle" :size="26" />
        </div>
        <p class="hero-desc">多轮对话、深系引用和行动建议都集中在这里，AI 不替代学校正式答复。</p>
      </div>
    </section>

    <div v-if="error" class="student-alert info"><UiIcon name="PhInfo" />{{ error }}</div>

    <section class="counselor-layout counselor-layout-wide">
      <aside class="counselor-side">
        <section class="student-panel surface">
          <div class="student-panel-head">
            <h2>会话记录</h2>
            <button class="new-session-button" @click="newSession"><UiIcon name="PhPlus" />新会话</button>
          </div>
          <div class="session-list">
            <button v-for="session in displaySessions" :key="session.id" :class="{ active: session.id === conversationId }" @click="restoreSession(session)">
              <UiIcon name="PhChatCircleText" />
              <span><strong>{{ session.title }}</strong><small>{{ sessionTime(session) }}</small></span>
            </button>
          </div>
        </section>

        <section class="student-panel surface counselor-suggestions">
          <div class="student-panel-head">
            <h2>推荐问题</h2>
            <button class="text-button" @click="newSession">换一换 <UiIcon name="PhArrowClockwise" /></button>
          </div>
          <button v-for="question in suggestions" :key="question" @click="send(question)">{{ question }}<UiIcon name="PhArrowUpRight" /></button>
        </section>
      </aside>

      <section class="student-panel surface counselor-chat">
        <div ref="chatEl" class="chat-messages">
          <div v-for="(message, index) in messages" :key="`${conversationId}-${index}`" class="chat-message" :class="message.role">
            <div class="chat-avatar"><UiIcon :name="message.role === 'user' ? 'PhUser' : 'PhRobot'" /></div>
            <div class="chat-bubble">
              <p>{{ message.text }}<span v-if="message.streaming" class="typing-cursor">▌</span></p>
              <div v-if="message.role === 'assistant' && index === messages.length - 1 && message.text && sources.length" class="chat-reference-list">
                <button v-for="source in sources" :key="source.document_id || source.title" type="button" @click="copyAnswer(source.title || source.document_title || '引用来源')">{{ source.title || source.document_title || "知识库资料" }} <UiIcon name="PhArrowUpRight" /></button>
              </div>
              <div v-if="message.role === 'assistant' && index === messages.length - 1 && message.text" class="chat-actions">
                <button @click="turnToTask"><UiIcon name="PhCheckSquare" />转为待办</button>
                <button @click="copyAnswer(message.text)"><UiIcon name="PhCopy" />复制回答</button>
              </div>
            </div>
          </div>
        </div>

        <form class="chat-composer" @submit.prevent="send()">
          <div class="chat-input-box">
            <textarea v-model="input" rows="3" :disabled="sending" placeholder="输入你的问题，Enter 发送；Shift + Enter 换行" @keydown.enter.exact.prevent="send()"></textarea>
            <div class="chat-composer-tools">
              <span><UiIcon name="PhPaperclip" />附件 <i>联网搜索</i></span>
              <button class="primary-button" :disabled="sending || !input.trim()"><UiIcon name="PhPaperPlaneTilt" />{{ sending ? "回答中…" : "发送" }}</button>
            </div>
          </div>
          <p class="chat-disclaimer">AI 生成的内容仅供参考，请以学校官方通知为准　服务条款　隐私政策</p>
        </form>
      </section>

      <aside class="counselor-right">
        <section class="student-panel surface">
          <div class="student-panel-head">
            <h2>校园办事帮助</h2>
            <button class="text-button">更多 <UiIcon name="PhArrowRight" /></button>
          </div>
          <button v-for="item in quickServices" :key="item.label" class="service-help" @click="send(`请介绍${item.label}相关的办理流程`)" >
            <span class="service-icon"><UiIcon :name="item.icon" /></span>
            <span><strong>{{ item.label }}</strong><small>{{ item.hint }}</small></span>
            <UiIcon name="PhArrowUpRight" />
          </button>
        </section>

        <section class="exam-card">
          <span class="eyebrow">考前冲刺专区</span>
          <h2>把复习计划安排得更从容</h2>
          <p>复习资料 · 真题汇总 · 心理减压</p>
          <button class="primary-button" @click="send('帮我安排一份考前复习计划')">立即查看 <UiIcon name="PhArrowRight" /></button>
        </section>

        <section class="student-panel surface quick-service-panel">
          <div class="student-panel-head"><h2>常用快捷服务</h2></div>
          <div class="quick-service-grid">
            <button @click="router.push('/services')"><UiIcon name="PhUser" /><span>请假申请</span></button>
            <button @click="router.push('/courses')"><UiIcon name="PhCalendarBlank" /><span>课程表</span></button>
            <button @click="router.push('/exams')"><UiIcon name="PhSealCheck" /><span>成绩查询</span></button>
            <button @click="router.push('/classrooms')"><UiIcon name="PhMagnifyingGlass" /><span>空教室查询</span></button>
          </div>
        </section>
      </aside>
    </section>
  </main>
</template>

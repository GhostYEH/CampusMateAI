<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import DigitalHumanPanel from "../../components/counselor/DigitalHumanPanel.vue";
import { useDigitalHumanSpeech } from "../../composables/useDigitalHumanSpeech";
import { chatStream } from "../../services/api";
import { createPersonalTask } from "../../services/studentApi";
import { marked } from "marked";

const route = useRoute();
const input = ref("");
const sending = ref(false);
const messages = ref([]);
const sources = ref([]);
const conversationId = ref("");
const sessions = ref([]);
const notice = ref("");
const chatEl = ref(null);
const aborter = ref(null);
const suggestionPage = ref(0);
const attachmentInput = ref(null);
const attachment = ref(null);
const webSearchEnabled = ref(false);
const policyDialog = ref(null);
const showAllSessions = ref(false);
const digitalHuman = useDigitalHumanSpeech({ onNotice: (message) => { notice.value = message; } });
const supportedTextTypes = new Set(["text/plain", "text/markdown", "application/json", "text/csv"]);

const suggestionSets = [
  ["期末考试如何高效复习？", "我要申请课程重修，需要准备什么？", "帮我把这周的任务排一个轻重缓急", "校园卡充值和退款流程是怎样的？"],
  ["校园卡丢失了，怎么挂失补办？", "如何申请奖学金？", "宿舍断电了找谁报修？", "图书馆借阅规则是什么？"],
];
const suggestions = computed(() => suggestionSets[suggestionPage.value]);
const actionSuggestions = [
  { label: "生成个性化复习计划", icon: "PhCalendarBlank" },
  { label: "制定每日任务清单", icon: "PhClipboardText" },
  { label: "推荐复习资料", icon: "PhBookOpen" },
  { label: "更多建议", icon: "PhSquaresFour" },
];
const fallbackSessions = [
  { id: "sample-main", title: "期末复习计划怎么安排？", displayTime: "10:24" },
  { id: "sample-card", title: "校园卡丢失了，怎么办？", displayTime: "昨天" },
  { id: "sample-scholar", title: "如何申请奖学金？", displayTime: "昨天" },
  { id: "sample-library", title: "图书馆借阅规则是什么？", displayTime: "08/10" },
  { id: "sample-dorm", title: "宿舍断电了找谁报修？", displayTime: "08/09" },
];

const sampleQuestion = "期末考试周的复习计划应该怎么安排更高效？";
const sampleAnswer = `期末考试周的复习建议如下，结合近期课程安排与常见复习方法，帮助你高效备考：

1. **制定复习计划：** 按科目和难度分配时间，优先复习高难度与高分值内容。
2. **梳理知识框架：** 先搭建各科知识框架，再填充细节，形成完整体系。
3. **真题与错题：** 近年真题至少做两遍，错题本定期回顾避免重复错误。
4. **合理作息：** 保持规律作息，每天保证 7–8 小时睡眠，适度运动放松。

需要我帮你生成一份个性化复习计划表吗？`;
const sampleSources = [
  { title: "教务处：期末考试安排通知" },
  { title: "学习建议中心：高效复习指南" },
  { title: "心理中心：考试周压力法" },
];
const displaySessions = computed(() => {
  const stored = sessions.value.filter((item) => item.id !== "sample-main");
  const all = [...fallbackSessions, ...stored];
  return showAllSessions.value ? all : all.slice(0, 5);
});

function renderMarkdown(text) { return text ? marked(text, { breaks: true, gfm: true }) || "" : ""; }
function scroll() { setTimeout(() => { if (chatEl.value) chatEl.value.scrollTop = chatEl.value.scrollHeight; }, 20); }
function seedSample() {
  conversationId.value = "sample-main";
  messages.value = [{ role: "user", text: sampleQuestion }, { role: "assistant", text: sampleAnswer }];
  sources.value = sampleSources;
  input.value = "";
  notice.value = "";
}
function newSession() {
  digitalHuman.stop();
  conversationId.value = `web-${Date.now()}`;
  messages.value = [];
  sources.value = [];
  input.value = "";
  attachment.value = null;
  notice.value = "已创建新对话";
  requestAnimationFrame(() => document.querySelector(".counselor-reference textarea")?.focus());
}
function loadSessions() {
  try { sessions.value = JSON.parse(localStorage.getItem("campus_counselor_sessions") || "[]"); }
  catch { sessions.value = []; }
}
function saveSession() {
  const first = messages.value.find((item) => item.role === "user");
  if (!first) return;
  sessions.value = [{ id: conversationId.value, title: first.text.slice(0, 24), updatedAt: new Date().toISOString(), messages: messages.value, sources: sources.value }, ...sessions.value.filter((item) => item.id !== conversationId.value)].slice(0, 12);
  localStorage.setItem("campus_counselor_sessions", JSON.stringify(sessions.value));
}
function restoreSession(item) {
  digitalHuman.stop();
  if (item.id === "sample-main") { seedSample(); return; }
  if (item.messages?.length) {
    conversationId.value = item.id; messages.value = item.messages; sources.value = item.sources || []; notice.value = "";
  } else {
    conversationId.value = item.id;
    messages.value = [{ role: "user", text: item.title }, { role: "assistant", text: `关于“${item.title}”，我可以为你查询学校规定、整理办理步骤，并生成一份行动清单。` }];
    sources.value = [];
  }
  scroll();
}
function sessionTime(item) {
  if (item.displayTime) return item.displayTime;
  const date = new Date(item.updatedAt);
  return Number.isNaN(date.getTime()) ? "刚刚" : date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}
function rotateSuggestions() { suggestionPage.value = (suggestionPage.value + 1) % suggestionSets.length; }
async function send(text = input.value) {
  const value = text.trim();
  if (!value || sending.value) return;
  digitalHuman.stop();
  if (!conversationId.value || conversationId.value.startsWith("sample-")) conversationId.value = `web-${Date.now()}`;
  messages.value.push({ role: "user", text: value });
  input.value = ""; sending.value = true; sources.value = []; notice.value = "";
  const pending = { role: "assistant", text: "", streaming: true };
  messages.value.push(pending); aborter.value = new AbortController(); scroll();
  try {
    await chatStream(value, {
      webSearch: webSearchEnabled.value,
      attachment: attachment.value,
      signal: aborter.value.signal,
      onSources: (items) => { sources.value = items || []; },
      onChunk: (chunk) => { pending.text += chunk; messages.value = [...messages.value]; scroll(); },
      onDone: (meta) => { conversationId.value = meta?.conversation_id || conversationId.value; pending.streaming = false; messages.value = [...messages.value]; saveSession(); digitalHuman.speak(pending.text); },
      onError: () => { pending.streaming = false; pending.text = pending.text || "校园知识库暂时未连接，我已记录你的问题，请稍后再试。"; messages.value = [...messages.value]; saveSession(); },
    });
  } finally { sending.value = false; aborter.value = null; scroll(); }
}
async function turnToTask() {
  const last = [...messages.value].reverse().find((item) => item.role === "assistant" && item.text);
  if (!last) return;
  try { await createPersonalTask({ title: last.text.slice(0, 80), description: last.text, source_name: "AI 校园助手对话", source_text: last.text }); notice.value = "已保存为个人待办"; }
  catch { notice.value = "待办保存失败，请稍后重试"; }
}
async function copyText(text, message = "内容已复制") {
  try { await navigator.clipboard?.writeText(text); notice.value = message; }
  catch { notice.value = "当前浏览器不支持自动复制"; }
}
function handleAttachment() { attachmentInput.value?.click(); }
async function selectAttachment(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  if (file.size > 1_000_000) {
    notice.value = "附件不能超过 1 MB";
    event.target.value = "";
    return;
  }
  const isText = supportedTextTypes.has(file.type) || /\.(txt|md|csv|json)$/i.test(file.name);
  if (!isText) {
    notice.value = "当前支持 TXT、Markdown、CSV 和 JSON 文本附件";
    event.target.value = "";
    return;
  }
  attachment.value = { name: file.name, type: file.type || "text/plain", size: file.size, content: await file.text() };
  notice.value = `已选择附件：${file.name}`;
  event.target.value = "";
}
function removeAttachment() { attachment.value = null; notice.value = "附件已移除"; }
function handleWebSearch() {
  webSearchEnabled.value = !webSearchEnabled.value;
  notice.value = webSearchEnabled.value ? "联网搜索已开启" : "联网搜索已关闭";
}
function openPolicy(type) { policyDialog.value = type; }
function closePolicy() { policyDialog.value = null; }

onMounted(() => { loadSessions(); seedSample(); if (route.query.prompt) send(String(route.query.prompt)); });
onBeforeUnmount(() => { aborter.value?.abort(); digitalHuman.stop(); });
</script>

<template>
  <main class="counselor-reference">
    <section class="counselor-reference-hero">
      <img src="/assets/counselor-campus-hero-reference.png" alt="校园智能机器人与校园植物插画" />
      <div class="counselor-reference-hero-copy">
        <div class="counselor-reference-title"><h1>AI校园助手</h1><UiIcon name="PhSparkle" :size="28" weight="duotone" /></div>
        <p>你的专属校园智能伙伴，随时为你解答疑问，<br />提供学习与生活的贴心帮助。</p>
      </div>
    </section>

    <div v-if="notice" class="counselor-toast" role="status"><UiIcon name="PhInfo" :size="16" />{{ notice }}</div>

    <section class="counselor-reference-grid">
      <aside class="counselor-reference-left">
        <section class="counselor-panel history-panel">
          <div class="counselor-panel-head"><h2>会话记录</h2><button class="new-chat" @click="newSession"><UiIcon name="PhPlus" :size="16" />新建对话</button></div>
          <div class="reference-session-list">
            <button v-for="session in displaySessions" :key="session.id" :class="{ active: session.id === conversationId }" @click="restoreSession(session)">
              <UiIcon name="PhChatCircleText" :size="15" /><strong>{{ session.title }}</strong><small>{{ sessionTime(session) }}</small>
            </button>
          </div>
          <button class="all-history" @click="showAllSessions = !showAllSessions">{{ showAllSessions ? "收起记录" : "查看全部记录" }} <UiIcon :name="showAllSessions ? 'PhCaretDown' : 'PhCaretRight'" :size="14" /></button>
        </section>

        <section class="counselor-panel recommendations-panel">
          <div class="counselor-panel-head"><h2>推荐问题</h2><button class="switch-link" @click="rotateSuggestions">换一换 <UiIcon name="PhArrowClockwise" :size="15" /></button></div>
          <div class="reference-question-list">
            <button v-for="question in suggestions" :key="question" @click="send(question)"><UiIcon name="PhQuestion" :size="14" /><span>{{ question }}</span></button>
          </div>
        </section>
      </aside>

      <section class="counselor-panel reference-chat-panel">
        <div ref="chatEl" class="reference-chat-messages">
          <div v-if="!messages.length" class="empty-conversation"><span class="assistant-face"><UiIcon name="PhRobot" :size="22" weight="duotone" /></span><h2>开始一段新对话</h2><p>告诉我你想了解的校园问题，我会尽力帮你。</p></div>
          <div v-for="(message, index) in messages" :key="`${conversationId}-${index}`" class="reference-message" :class="message.role">
            <div class="reference-avatar"><UiIcon :name="message.role === 'user' ? 'PhUser' : 'PhRobot'" :size="19" :weight="message.role === 'user' ? 'fill' : 'duotone'" /></div>
            <div class="reference-bubble">
              <div class="markdown-body" v-html="renderMarkdown(message.text)"></div><span v-if="message.streaming" class="typing-cursor">▍</span>
              <div v-if="message.role === 'assistant' && index === messages.length - 1 && message.text && sources.length" class="reference-sources">
                <span>相关来源：</span><button v-for="source in sources" :key="source.document_id || source.title" @click="copyText(source.title || source.document_title || '引用来源', '来源标题已复制')">{{ source.title || source.document_title || "知识库资料" }} <UiIcon name="PhArrowUpRight" :size="12" /></button>
              </div>
            </div>
          </div>
        </div>

        <div class="reference-action-row">
          <button v-for="action in actionSuggestions" :key="action.label" @click="send(action.label)"><UiIcon :name="action.icon" :size="18" />{{ action.label }}</button>
        </div>
        <form class="reference-composer" @submit.prevent="send()">
          <div v-if="attachment" class="reference-attachment-chip"><UiIcon name="PhFileText" :size="15" /><span>{{ attachment.name }}</span><button type="button" aria-label="移除附件" @click="removeAttachment"><UiIcon name="PhX" :size="13" /></button></div>
          <textarea v-model="input" :disabled="sending" placeholder="请输入你的问题，Enter 发送；Shift + Enter 换行" @keydown.enter.exact.prevent="send()"></textarea>
          <div class="reference-composer-tools">
            <input ref="attachmentInput" class="reference-file-input" type="file" accept=".txt,.md,.csv,.json,text/plain,text/markdown,text/csv,application/json" @change="selectAttachment" />
            <span><button type="button" @click="handleAttachment"><UiIcon name="PhPaperclip" :size="20" />附件</button><button type="button" :class="{ active: webSearchEnabled }" :aria-pressed="webSearchEnabled" @click="handleWebSearch"><UiIcon name="PhMagnifyingGlass" :size="20" />联网搜索</button></span>
            <button class="reference-send" :disabled="sending || !input.trim()"><UiIcon name="PhPaperPlaneTilt" :size="20" />{{ sending ? "回答中" : "发送" }}</button>
          </div>
        </form>
        <footer class="reference-disclaimer"><span>AI 生成的内容仅供参考，请以学校官方信息为准</span><button @click="openPolicy('terms')">服务条款</button><button @click="openPolicy('privacy')">隐私政策</button></footer>
      </section>

      <aside class="counselor-reference-right">
        <DigitalHumanPanel
          :speaking="digitalHuman.speaking.value"
          :muted="digitalHuman.muted.value"
          :status="digitalHuman.unityStatus.value"
          :can-replay="Boolean(digitalHuman.lastText.value)"
          @ready="digitalHuman.setUnityReady"
          @error="digitalHuman.setUnityError"
          @toggle-muted="digitalHuman.toggleMuted"
          @stop="digitalHuman.stop"
          @replay="digitalHuman.replay"
        />
      </aside>
    </section>

    <div v-if="policyDialog" class="reference-policy-overlay" @click.self="closePolicy">
      <section class="reference-policy-dialog" role="dialog" aria-modal="true" :aria-label="policyDialog === 'terms' ? '服务条款' : '隐私政策'">
        <header><h2>{{ policyDialog === "terms" ? "服务条款" : "隐私政策" }}</h2><button aria-label="关闭弹窗" @click="closePolicy"><UiIcon name="PhX" :size="19" /></button></header>
        <template v-if="policyDialog === 'terms'"><p>CampusMate AI 提供校园学习与生活信息辅助，生成内容仅供参考，正式安排请以学校官方通知为准。</p><p>请勿提交违法、有害或侵犯他人权益的内容。服务可能因校园系统维护而短暂不可用。</p></template>
        <template v-else><p>我们仅在完成当前功能所需范围内处理你的提问、会话记录和所选附件信息。</p><p>附件不会在未发送时上传；你可以随时移除附件或清除浏览器中的本地会话记录。</p></template>
        <button class="reference-policy-confirm" @click="closePolicy">我知道了</button>
      </section>
    </div>
  </main>
</template>

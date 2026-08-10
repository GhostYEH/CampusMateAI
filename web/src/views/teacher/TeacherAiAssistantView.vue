<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import PageHeader from "../../components/teacher/PageHeader.vue";
import EmptyState from "../../components/teacher/EmptyState.vue";
import UiIcon from "../../components/UiIcon.vue";
import { useTeacherStore } from "../../stores/teacher";
import { useToast, extractErrorMessage } from "../../composables/useToast";
import { teacherChatStream } from "../../services/teacher/ai";
import { listTeacherAssignments } from "../../services/teacher/assignments";
import { listTeacherAnnouncements } from "../../services/teacher/announcements";
import { copyToClipboard } from "../../composables/useFormat";

const teacherStore = useTeacherStore();
const toast = useToast();

const messages = ref([]);
const input = ref("");
const sending = ref(false);
const chatBodyEl = ref(null);
let abortController = null;

const context = reactive({
  course_id: "",
  class_id: "",
  assignment_id: "",
  announcement_id: "",
});
const assignments = ref([]);
const announcements = ref([]);

const draft = ref("");
const draftSource = ref("");
const draftCopied = ref(false);

const classOptions = computed(() => teacherStore.classOptionsWithCourse());

const assignmentOptions = computed(() => assignments.value.map((a) => ({
  value: a.id, label: `${a.title}（${a.course_name || ""} / ${a.class_name || ""}）`,
})));

const announcementOptions = computed(() => announcements.value.map((a) => ({
  value: a.id, label: a.title,
})));

const quickPatterns = [
  {
    key: "outline", label: "生成教学大纲草稿", icon: "PhListChecks",
    prompt: "请帮我起草本课程一个章节的教学大纲，包含教学目标、知识点拆分、课时安排建议与考核方式。结果仅作为草稿参考。",
  },
  {
    key: "quiz", label: "生成练习题草稿", icon: "PhQuestion",
    prompt: "请帮我起草 5 道本课程练习题，包含题干、参考答案与简要解析。结果仅作为草稿参考，发布前需要我确认。",
  },
  {
    key: "feedback", label: "撰写班级反馈草稿", icon: "PhChatCircleText",
    prompt: "请基于本班近期的作业完成情况，帮我起草一段给学生的班级反馈，语气平和，客观描述完成情况与建议。结果仅作为草稿参考。",
  },
  {
    key: "reminder", label: "撰写催交提醒草稿", icon: "PhBell",
    prompt: "请帮我起草一条作业催交提醒通知，语气友好，说明截止时间与提交方式。结果仅作为草稿参考。",
  },
  {
    key: "rubric", label: "生成评分标准草稿", icon: "PhScales",
    prompt: "请帮我起草本次作业的评分标准（rubric），分维度列出分值与描述。结果仅作为草稿参考。",
  },
  {
    key: "summary", label: "总结本章要点", icon: "PhBookOpen",
    prompt: "请帮我总结本课程最近一章的核心要点，便于学生复习。结果仅作为草稿参考。",
  },
];

async function loadContext() {
  await teacherStore.loadAll().catch(() => null);
  if (!assignments.value.length) {
    const page = await listTeacherAssignments({ page_size: 200 }).catch(() => ({ items: [] }));
    assignments.value = page.items || [];
  }
  if (!announcements.value.length) {
    const page = await listTeacherAnnouncements({ page_size: 100 }).catch(() => ({ items: [] }));
    announcements.value = page.items || [];
  }
}

function buildContext() {
  const ctx = {};
  if (context.course_id) ctx.course_id = context.course_id;
  if (context.class_id) ctx.class_id = context.class_id;
  if (context.assignment_id) ctx.assignment_id = context.assignment_id;
  if (context.announcement_id) ctx.announcement_id = context.announcement_id;
  return ctx;
}

function scrollToBottom() {
  nextTick(() => {
    const el = chatBodyEl.value;
    if (el) el.scrollTop = el.scrollHeight;
  });
}

async function send(text) {
  const content = (text ?? input.value).trim();
  if (!content || sending.value) return;
  messages.value.push({ role: "user", text: content });
  if (text === undefined) input.value = "";
  sending.value = true;
  draft.value = "";
  draftSource.value = "";
  draftCopied.value = false;

  const pendingMsg = { role: "assistant", text: "", streaming: true, sources: [] };
  messages.value.push(pendingMsg);
  scrollToBottom();

  abortController = new AbortController();
  try {
    await teacherChatStream(content, buildContext(), {
      onSources(sources) {
        pendingMsg.sources = sources || [];
        messages.value = [...messages.value];
      },
      onChunk(chunkText) {
        pendingMsg.text += chunkText;
        messages.value = [...messages.value];
        scrollToBottom();
      },
      onDone(meta) {
        pendingMsg.streaming = false;
        if (!pendingMsg.text.trim()) {
          pendingMsg.text = "暂时无法生成回复，请稍后重试。";
        }
        draft.value = pendingMsg.text;
        draftSource.value = meta?.context_used ? "已结合所选教学上下文" : "通用知识库";
        messages.value = [...messages.value];
        scrollToBottom();
      },
      onError(err) {
        pendingMsg.streaming = false;
        if (!pendingMsg.text.trim()) {
          pendingMsg.text = `生成失败：${err.message || "未知错误"}`;
        }
        messages.value = [...messages.value];
        scrollToBottom();
      },
      signal: abortController.signal,
    });
  } catch (err) {
    pendingMsg.streaming = false;
    if (!pendingMsg.text.trim()) {
      pendingMsg.text = `生成失败：${err.message || "未知错误"}`;
    }
    messages.value = [...messages.value];
  } finally {
    sending.value = false;
    abortController = null;
  }
}

function stopGenerating() {
  if (abortController) abortController.abort();
  sending.value = false;
}

function applyQuick(pattern) {
  send(pattern.prompt);
}

async function copyDraft() {
  if (!draft.value) return;
  try {
    await copyToClipboard(draft.value);
    draftCopied.value = true;
    toast.success("草稿已复制到剪贴板");
    setTimeout(() => { draftCopied.value = false; }, 2000);
  } catch {
    toast.error("复制失败");
  }
}

function editDraft() {
  if (!draft.value) return;
  input.value = draft.value;
  toast.info("草稿已填入输入框，可编辑后重新发送或自行保存");
}

function clearChat() {
  messages.value = [];
  draft.value = "";
  draftSource.value = "";
}

onMounted(loadContext);
onBeforeUnmount(() => { if (abortController) abortController.abort(); });
</script>

<template>
  <main class="tch-page page-enter">
    <PageHeader kicker="AI 教学助理" title="教学内容生成助手" subtitle="基于校园知识库与教学上下文生成草稿，所有结果仅供参考，发布前需教师确认。">
      <template #actions>
        <button class="secondary-button" @click="clearChat" :disabled="!messages.length"><UiIcon name="PhEraser" :size="16" />清空对话</button>
      </template>
    </PageHeader>

    <div class="tch-ai-layout">
      <aside class="tch-ai-side">
        <section class="tch-panel">
          <h2>教学上下文</h2>
          <p class="tch-hint">选择课程/班级/作业/通知后，AI 会结合对应教学资料生成更贴合的草稿。</p>
          <div class="tch-form">
            <label class="tch-field">
              <span>课程</span>
              <select v-model="context.course_id">
                <option value="">不指定</option>
                <option v-for="c in teacherStore.courses" :key="c.id" :value="c.id">{{ c.name }}</option>
              </select>
            </label>
            <label class="tch-field">
              <span>班级</span>
              <select v-model="context.class_id">
                <option value="">不指定</option>
                <option v-for="cls in classOptions" :key="cls.id" :value="cls.id">{{ cls.course?.name }} / {{ cls.name }}</option>
              </select>
            </label>
            <label class="tch-field">
              <span>作业</span>
              <select v-model="context.assignment_id">
                <option value="">不指定</option>
                <option v-for="a in assignmentOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
              </select>
            </label>
            <label class="tch-field">
              <span>通知</span>
              <select v-model="context.announcement_id">
                <option value="">不指定</option>
                <option v-for="a in announcementOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
              </select>
            </label>
          </div>
        </section>

        <section class="tch-panel">
          <h2>快捷生成</h2>
          <p class="tch-hint">点击即发送预设提示词，结果作为草稿，不会自动发布。</p>
          <div class="tch-quick-patterns">
            <button
              v-for="p in quickPatterns"
              :key="p.key"
              class="tch-quick-pattern"
              :disabled="sending"
              @click="applyQuick(p)"
            >
              <UiIcon :name="p.icon" :size="18" />
              <span>{{ p.label }}</span>
            </button>
          </div>
        </section>

        <section v-if="draft" class="tch-panel tch-draft-panel">
          <div class="tch-draft-head">
            <h2><UiIcon name="PhPencilSimpleLine" :size="16" />最新草稿</h2>
            <span class="tch-draft-source">{{ draftSource || 'AI 生成' }}</span>
          </div>
          <p class="tch-hint warn">此草稿由 AI 生成，仅供参考。请核对内容后再决定是否使用，不会自动发布到任何地方。</p>
          <article class="tch-draft-body">{{ draft }}</article>
          <div class="tch-draft-actions">
            <button class="secondary-button" @click="copyDraft">
              <UiIcon :name="draftCopied ? 'PhCheck' : 'PhCopy'" :size="16" />{{ draftCopied ? '已复制' : '复制' }}
            </button>
            <button class="secondary-button" @click="editDraft"><UiIcon name="PhPencil" :size="16" />填入编辑</button>
          </div>
        </section>
      </aside>

      <section class="tch-ai-chat">
        <div ref="chatBodyEl" class="tch-ai-chat-body">
          <EmptyState v-if="!messages.length" icon="PhRobot" title="开始与 AI 教学助理对话" description="选择左侧教学上下文后，输入问题或使用快捷生成。" />
          <div v-for="(msg, idx) in messages" :key="idx" class="tch-chat-msg" :class="msg.role">
            <div class="tch-chat-avatar">
              <UiIcon :name="msg.role === 'user' ? 'PhUser' : 'PhRobot'" :size="18" />
            </div>
            <div class="tch-chat-content">
              <p class="tch-chat-text">{{ msg.text }}<span v-if="msg.streaming" class="tch-cursor">▍</span></p>
              <div v-if="msg.sources?.length" class="tch-chat-sources">
                <UiIcon name="PhQuotes" :size="14" />
                <span>检索证据：</span>
                <small v-for="(src, i) in msg.sources" :key="i">{{ src.title || src.source || src }}</small>
              </div>
            </div>
          </div>
        </div>

        <form class="tch-ai-input" @submit.prevent="send()">
          <textarea
            v-model="input"
            rows="3"
            placeholder="输入你的问题或教学需求，回车发送，Shift+回车换行"
            :disabled="sending"
            @keydown.enter.exact.prevent="send()"
          ></textarea>
          <div class="tch-ai-input-actions">
            <span class="tch-hint">AI 输出仅为草稿，不会自动发布</span>
            <button v-if="sending" type="button" class="secondary-button" @click="stopGenerating"><UiIcon name="PhStop" :size="16" />停止</button>
            <button type="submit" class="primary-button" :disabled="sending || !input.trim()">
              <UiIcon v-if="sending" name="PhCircleNotch" :size="16" />
              <UiIcon v-else name="PhPaperPlaneTilt" :size="16" />发送
            </button>
          </div>
        </form>
      </section>
    </div>
  </main>
</template>
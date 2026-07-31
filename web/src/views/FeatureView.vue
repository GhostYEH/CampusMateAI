<script setup>
import { computed, onBeforeUnmount, ref } from "vue";
import { useRoute } from "vue-router";
import { useAppStore } from "../stores/app";
import { chatStream, extractNotice } from "../services/api";
import { marked } from "marked";
import UiIcon from "../components/UiIcon.vue";
import TasksView from "./TasksView.vue";

// Markdown 渲染配置
marked.setOptions({ breaks: true, gfm: true });
function renderMarkdown(text) {
  if (!text) return "";
  // 简单防 XSS：过滤 script 标签
  const sanitized = text.replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "");
  return marked.parse(sanitized);
}

const route = useRoute();
const store = useAppStore();
const section = computed(() => route.params.section);
const titleMap = { courses:"课程中心", tasks:"待办事项", counselor:"AI 导员", notifications:"通知整理", study:"学习陪伴", profile:"个人中心", publish:"发布中心", stats:"教学统计", users:"用户管理", system:"系统状态" };
const newTask = ref("");
const deadline = ref("");
const noticeText = ref("【教务处通知】请各班同学于本周五17:00前完成2026年秋季学期选课确认，登录教务系统核对课程信息。如有冲突请联系学院教务办公室。");
const extracting = ref(false);
const extracted = ref(null);
const message = ref("");
const sending = ref(false);
const chatAreaEl = ref(null);
const messages = ref([{ role:"assistant", text:"你好，我是 AI 导员小夏。你可以问我课程流程、奖助政策、校园服务等问题。当前回答来自 Mock 知识库，仅供辅助参考。" }]);
const seconds = ref(25 * 60);
const timerRunning = ref(false);
let timer;
const timerText = computed(() => `${String(Math.floor(seconds.value/60)).padStart(2,"0")}:${String(seconds.value%60).padStart(2,"0")}`);
const courses = ["数据结构","计算机组成原理","高等数学（下）","大学英语 IV","操作系统原理","计算机网络"];
const users = ref([
  { name:"林知夏", id:"2024010132", role:"学生", status:"正常" },{ name:"张明远", id:"T20180456", role:"教师", status:"正常" },{ name:"刘文静", id:"T20170628", role:"教师", status:"正常" },{ name:"陈一诺", id:"2024010108", role:"学生", status:"正常" },
]);
function addTask() { if (!newTask.value.trim()) return; store.addTask(newTask.value.trim(), deadline.value || "待设置"); newTask.value=""; deadline.value=""; }
async function runExtract() {
  if (!noticeText.value.trim()) return; extracting.value = true;
  try {
    extracted.value = store.backendOnline && !store.mockMode ? await extractNotice(noticeText.value) : { title:"2026年秋季学期选课确认", source:"教务处", deadline:"本周五 17:00", tasks:["登录教务系统核对课程信息","如有冲突联系学院教务办公室"], confidence:0.94 };
  } catch { extracted.value = { error:"提取服务暂时不可用，请稍后重试。" }; } finally { extracting.value=false; }
}
function saveExtracted() { if (!extracted.value?.title) return; store.addTask(extracted.value.title, extracted.value.deadline); extracted.value.saved=true; }
async function send() {
  const text = message.value.trim(); if (!text) return;
  messages.value.push({ role: "user", text });
  message.value = "";
  sending.value = true;

  // 创建一个"流式写入中"的临时消息
  const pendingMsg = { role: "assistant", text: "", streaming: true };
  messages.value.push(pendingMsg);
  scrollToBottom();

  try {
    if (store.backendOnline && !store.mockMode) {
      await chatStream(text, {
        onChunk(chunkText) {
          pendingMsg.text += chunkText;
          messages.value = [...messages.value]; // 触发响应式
          scrollToBottom();
        },
        onDone() {
          pendingMsg.streaming = false;
          if (!pendingMsg.text.trim()) {
            pendingMsg.text = "暂时无法连接知识库，请检查网络后重试。";
          }
          messages.value = [...messages.value];
          scrollToBottom();
        },
        onError(err) {
          pendingMsg.streaming = false;
          if (!pendingMsg.text.trim()) {
            pendingMsg.text = `连接失败：${err.message}`;
          }
          messages.value = [...messages.value];
          scrollToBottom();
        },
      });
    } else {
      // Mock 模式（非流式）
      const answer = text.includes("奖学金")
      ? "奖学金通常综合考察学业成绩、综合素质与志愿服务。不同奖项条件不同，建议先查看学院本学年评审通知。我可以继续帮你整理申请材料清单。"
        : "我已经记录你的问题。当前为 Mock 知识库模式，建议以学校教务处或学院最新通知为准。需要的话，我可以帮你把相关步骤整理成待办。";
      pendingMsg.text = answer;
      pendingMsg.streaming = false;
      messages.value = [...messages.value];
      scrollToBottom();
    }
  } catch {
    pendingMsg.streaming = false;
    if (!pendingMsg.text.trim()) {
      pendingMsg.text = "暂时无法连接知识库，请检查网络后重试。";
    }
    messages.value = [...messages.value];
    scrollToBottom();
  } finally {
    sending.value = false;
  }
}
function scrollToBottom() {
  setTimeout(() => {
    const el = chatAreaEl.value;
    if (el) el.scrollTop = el.scrollHeight;
  }, 10);
}
function toggleTimer() { timerRunning.value=!timerRunning.value; if(timerRunning.value) timer=setInterval(()=>{ if(seconds.value>0) seconds.value--; else toggleTimer(); },1000); else clearInterval(timer); }
function resetTimer() { clearInterval(timer); timerRunning.value=false; seconds.value=25*60; }
onBeforeUnmount(()=>clearInterval(timer));
</script>

<template>
  <TasksView v-if="section === 'tasks'" />
  <main v-else class="feature-page page-enter">
    <div class="page-title"><div><h1>{{ titleMap[section] || "校园服务" }}</h1><p>{{ section === "counselor" ? "基于校园知识库的事务问答，当前能力会明确标注 Mock。" : "集中处理与当前模块相关的校园事务。" }}</p></div><span class="mode-badge"><i></i>{{ store.mockMode ? "Mock 模式" : "真实后端" }}</span></div>

    <section v-if="section === 'tasks'" class="feature-split">
      <div class="data-panel"><div class="section-head"><h2>我的待办</h2><span>{{ store.pendingCount }} 项未完成</span></div><div class="rows"><label v-for="task in store.tasks" :key="task.id" class="task-row" :class="{done:task.done}"><input type="checkbox" :checked="task.done" @change="store.toggleTask(task.id)" /><span><strong>{{ task.title }}</strong><small>{{ task.due }} · {{ task.course }}</small></span><button class="icon-button" @click.prevent="store.deleteTask(task.id)" aria-label="删除"><UiIcon name="PhTrash" /></button></label><div v-if="!store.tasks.length" class="empty-state"><UiIcon name="PhCheckCircle" :size="36" />暂时没有待办，去给今天安排一个小目标吧。</div></div></div>
      <form class="side-form surface" @submit.prevent="addTask"><h2>新建待办</h2><label>任务名称<input v-model="newTask" placeholder="例如：完成数据结构实验报告" /></label><label>截止时间<input v-model="deadline" type="datetime-local" /></label><button class="primary-button" :disabled="!newTask.trim()">添加任务</button></form>
    </section>

    <section v-else-if="section === 'notifications'" class="feature-split">
      <div class="surface extraction-box"><h2>粘贴校园通知</h2><p>系统会尝试提取标题、来源、截止时间与待办。结果需要你确认后保存。</p><textarea v-model="noticeText" rows="12"></textarea><button class="primary-button" @click="runExtract" :disabled="extracting">{{ extracting ? "正在智能提取…" : "开始提取" }}<UiIcon name="PhSparkle" /></button></div>
      <div class="surface extraction-result"><h2>提取结果</h2><div v-if="!extracted" class="empty-state"><UiIcon name="PhClipboardText" :size="42" />提取结果会显示在这里</div><div v-else-if="extracted.error" class="alert error">{{ extracted.error }}</div><div v-else class="result-fields"><label>标题<input v-model="extracted.title" /></label><label>来源<input v-model="extracted.source" /></label><label>截止时间<input v-model="extracted.deadline" /></label><div><strong>识别出的事项</strong><p v-for="task in extracted.tasks" :key="task">• {{ task }}</p></div><small>置信度 {{ Math.round(extracted.confidence*100) }}%，结果仅供确认。</small><button class="primary-button" @click="saveExtracted" :disabled="extracted.saved">{{ extracted.saved ? "已保存到待办" : "确认并保存" }}</button></div></div>
    </section>

    <section v-else-if="section === 'counselor'" class="chat-layout">
      <div class="chat-main surface"><div class="chat-head"><span class="robot-avatar"><UiIcon name="PhRobot" :size="28" /></span><div><h2>AI 导员小夏 <em>{{ store.mockMode ? 'Mock' : 'DeepSeek' }}</em></h2><p>校园事务问答 · 不替代学校正式通知</p></div></div><div class="messages" ref="chatAreaEl"><article v-for="(m,i) in messages" :key="i" :class="[m.role, { streaming: m.streaming }]"><div v-if="m.role === 'assistant' && m.text" class="md-content" v-html="renderMarkdown(m.text)"></div><p v-else-if="m.role === 'user'">{{ m.text }}</p><p v-else-if="m.role === 'assistant' && !m.text" class="blink-cursor">▌</p></article></div><form class="chat-input" @submit.prevent="send"><textarea v-model="message" rows="2" placeholder="输入你的校园事务问题…"></textarea><button class="primary-button" :disabled="sending || !message.trim()" aria-label="发送"><UiIcon name="PhPaperPlaneTilt" /></button></form></div>
      <aside class="surface suggestions"><h2>可以这样问</h2><button v-for="q in ['奖学金申请条件有哪些？','如何办理课程重修？','校园卡挂失后怎么补办？','图书馆期末开放到几点？']" :key="q" @click="message=q">{{ q }}<UiIcon name="PhCaretRight" /></button><div class="safe-note"><UiIcon name="PhShieldCheck" /><p>回答仅提供校园事务辅助，不进行心理或疾病诊断。</p></div></aside>
    </section>

    <section v-else-if="section === 'study'" class="study-layout">
      <div class="focus-timer surface"><p>本次专注</p><strong>{{ timerText }}</strong><div><button class="primary-button" @click="toggleTimer"><UiIcon :name="timerRunning ? 'PhPause' : 'PhPlay'" weight="fill" />{{ timerRunning ? "暂停" : "开始专注" }}</button><button class="secondary-button" @click="resetTimer"><UiIcon name="PhArrowCounterClockwise" />重置</button></div></div>
      <div class="data-panel expression-panel"><div class="section-head"><h2>表情识别辅助</h2><em>Mock CNN</em></div><div class="expression-state"><span class="soft-icon large"><UiIcon name="PhSmiley" :size="34" /></span><div><strong>当前表情可能偏中性</strong><p>识别结果仅供辅助参考，不代表心理状态或医学判断。</p></div></div><div class="alert info">低置信度时会显示“暂时无法稳定判断当前表情”，且不会触发情绪安慰。</div></div>
      <div class="data-panel"><div class="section-head"><h2>本周学习记录</h2></div><div class="history-bars"><span v-for="(h,i) in [32,56,45,80,62,90,40]" :key="i"><i :style="{height:h+'%'}"></i><small>{{ ['一','二','三','四','五','六','日'][i] }}</small></span></div></div>
    </section>

    <section v-else-if="section === 'courses'" class="course-gallery"><article v-for="(c,i) in courses" :key="c" class="course-card"><span class="course-code">{{ ['DS','CO','MA','EN','OS','CN'][i] }}</span><div><small>{{ i%2 ? "专业基础课" : "专业必修课" }}</small><h2>{{ c }}</h2><p>{{ ['张明远','刘文静','王建国'][i%3] }}老师 · 教学楼 {{ 2+i }}-30{{ i }}</p></div><button class="secondary-button">进入课程<UiIcon name="PhArrowRight" /></button></article></section>

    <section v-else-if="section === 'profile'" class="profile-grid">
      <div class="surface profile-card"><div class="avatar large-avatar">{{ store.session?.name?.slice(0,1) }}</div><h2>{{ store.session?.name }}</h2><p>{{ store.session?.detail }}</p><dl><div><dt>账号角色</dt><dd>{{ store.session?.role }}</dd></div><div><dt>服务状态</dt><dd>{{ store.backendOnline ? "已连接" : "离线可用" }}</dd></div></dl></div>
      <div class="surface settings"><h2>偏好设置</h2><label class="switch-row"><span><strong>减少动态效果</strong><small>减少页面切换与卡片进入动画</small></span><input type="checkbox" :checked="store.reduceMotion" @change="store.setReduceMotion($event.target.checked)" /></label><label class="switch-row"><span><strong>截止提醒</strong><small>Web 端使用站内提醒</small></span><input type="checkbox" checked /></label></div>
    </section>

    <section v-else-if="section === 'users'" class="data-panel"><div class="section-head"><h2>平台用户</h2><button class="primary-button"><UiIcon name="PhPlus" />创建用户</button></div><div class="table"><div class="table-head"><span>姓名</span><span>学号 / 工号</span><span>角色</span><span>状态</span><span>操作</span></div><div v-for="u in users" :key="u.id" class="table-row"><strong>{{ u.name }}</strong><span>{{ u.id }}</span><span>{{ u.role }}</span><span class="success-text">{{ u.status }}</span><button>查看</button></div></div></section>

    <section v-else class="generic-grid">
      <article v-for="(item,i) in ['关键指标概览','近期活动','待处理事项','运行状态']" :key="item" class="data-panel"><div class="section-head"><h2>{{ item }}</h2><UiIcon :name="['PhChartBar','PhClockCounterClockwise','PhClipboardText','PhPulse'][i]" /></div><div class="empty-state compact"><strong>{{ [96,24,6,'正常'][i] }}</strong><span>{{ section === 'system' ? '系统服务数据' : section === 'stats' ? '教学数据' : '当前模块数据' }}</span></div></article>
    </section>
  </main>
</template>

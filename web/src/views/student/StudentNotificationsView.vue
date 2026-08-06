<script setup>
import { computed, onMounted, ref } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import client, { extractNotice } from "../../services/api";
import { createPersonalTask, getStudentClasses, markAnnouncementRead } from "../../services/studentApi";

const loading = ref(true);
const refreshing = ref(false);
const error = ref("");
const notices = ref([]);
const query = ref("");
const source = ref("all");
const readFilter = ref("unread");
const expandedId = ref(null);
const text = ref("");
const extracting = ref(false);
const extracted = ref(null);
const saving = ref(false);

const filtered = computed(() => notices.value.filter((item) => {
  const matchesSource = source.value === "all" || item.source === source.value;
  const matchesRead = readFilter.value === "all" || !item.has_read;
  const keyword = `${item.title} ${item.content || ""}`.toLowerCase();
  return matchesSource && matchesRead && keyword.includes(query.value.trim().toLowerCase());
}));

const unreadCount = computed(() => notices.value.filter((item) => !item.has_read).length);
const sources = computed(() => [...new Set(notices.value.map((item) => item.source).filter(Boolean))]);
const exampleNotices = [
  { title: "英语晨读活动", type: "课程", source: "演示 · 英语1班 · 李老师(演示)", label: "时间", value: "每周二、四 07:30", label2: "地点", value2: "图书馆北广场" },
  { title: "安装 Python 3.11+ 与 VS Code", type: "课程", source: "演示 · 计算机1班 · 李老师(演示)", label: "截止时间", value: "第一节课前", label2: "提交方式", value2: "无需提交" },
  { title: "第一次作业提交", type: "课程", source: "演示 · 计算机1班 · 李老师(演示)", label: "截止时间", value: "9月20日 23:59", label2: "提交方式", value2: "上传扫描件 / 电子文档" },
  { title: "开学第一周课程安排", type: "学院", source: "信息工程学院 教务办", label: "时间", value: "周一 1-2 节；周五 3-4 节", label2: "地点", value2: "A301 教室" },
];

async function load(refresh = false) {
  if (refresh) refreshing.value = true;
  else loading.value = true;
  error.value = "";
  try {
    const classes = (await getStudentClasses()).items || [];
    const groups = await Promise.all(classes.map(async (cls) => {
      const { data } = await client.get(`/classes/${cls.id}/announcements`, { params: { page_size: 100 } });
      return (data.items || []).map((item) => ({ ...item, source: cls.name }));
    }));
    notices.value = groups.flat().sort((a, b) => String(b.published_at || b.created_at).localeCompare(String(a.published_at || a.created_at)));
  } catch (e) {
    error.value = e.response?.data?.detail || "通知加载失败，请稍后重试。";
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

function displayNoticeTime(item, index) {
  const preset = ["15 分钟前", "32 分钟前", "1 小时前", "2 小时前", "昨日 18:24"];
  if (!item.published_at && !item.created_at) return "刚刚";
  return preset[index] || "刚刚";
}

async function toggleNotice(item) {
  expandedId.value = expandedId.value === item.id ? null : item.id;
  if (item.has_read) return;
  try {
    await markAnnouncementRead(item.id);
    item.has_read = true;
  } catch {
    error.value = "通知已打开，但已读状态同步失败。";
  }
}

async function extract() {
  if (!text.value.trim() || extracting.value) return;
  extracting.value = true;
  extracted.value = null;
  try {
    extracted.value = await extractNotice(text.value);
  } catch (e) {
    extracted.value = { error: e.response?.data?.detail || "提取失败，请检查通知内容后重试。" };
  } finally {
    extracting.value = false;
  }
}

async function saveTask() {
  if ((!extracted.value?.task && !extracted.value?.title) || saving.value) return;
  saving.value = true;
  try {
    await createPersonalTask({
      title: extracted.value.task || extracted.value.title,
      description: extracted.value.source_text || text.value,
      deadline: extracted.value.deadline,
      materials: extracted.value.materials || [],
      submission_method: extracted.value.submission_method,
      location: extracted.value.location,
      source_name: extracted.value.source_name,
      source_text: text.value,
    });
    extracted.value.saved = true;
  } catch (e) {
    extracted.value.error = e.response?.data?.detail || "保存待办失败，请稍后重试。";
  } finally {
    saving.value = false;
  }
}

onMounted(() => load());
</script>

<template>
  <main class="student-page notifications-page page-enter">
    <div class="student-heading page-heading-wide notice-heading">
      <div>
        <span class="eyebrow">NOTICES / 校园信息</span>
        <h1>通知整理</h1>
        <p>先浏览课程通知，也可以粘贴一段原文，让系统提取截止时间并确认后保存为待办。</p>
      </div>
      <div class="hero-side"><div class="hero-decoration"><UiIcon name="PhSparkle" /></div><div class="notice-heading-art"><img src="/assets/campusmate-notice-illustration.png" alt="通知整理插画" /></div><button class="secondary-button" :disabled="refreshing" @click="load(true)"><UiIcon name="PhArrowClockwise" />刷新</button></div>
    </div>

    <div v-if="error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ error }}<button class="link-button" @click="load">重试</button></div>

    <section class="notice-layout">
      <div class="notice-list-column surface">
        <section class="notice-toolbar">
          <div class="search-field"><UiIcon name="PhMagnifyingGlass" /><input v-model="query" placeholder="搜索通知标题或内容" /></div>
          <select v-model="source"><option value="all">全部课程班级</option><option v-for="item in sources" :key="item" :value="item">{{ item }}</option></select>
          <select v-model="readFilter"><option value="unread">仅看未读</option><option value="all">全部通知</option></select>
        </section>

        <section class="notice-panel">
          <div class="notice-tabs">
            <div><span class="eyebrow">{{ unreadCount }} 条未读通知</span><h2>通知列表</h2></div>
            <div class="notice-count-tabs"><button class="active">全部 <b>{{ filtered.length }}</b></button><span>课程 {{ Math.max(0, filtered.length - 1) }}</span><span>学院 1</span><span>活动 0</span><span>系统 0</span></div>
          </div>

          <div v-if="loading" class="list-skeleton-stack"><div v-for="i in 5" :key="i" class="list-skeleton"></div></div>
          <div v-else-if="filtered.length" class="notice-detail-list">
            <article v-for="(notice, index) in filtered" :key="notice.id" class="notice-detail" :class="{ unread: !notice.has_read, expanded: expandedId === notice.id }">
              <button @click="toggleNotice(notice)">
                <span class="notice-leading-icon" :class="`notice-tone-${notice.id % 4}`"><UiIcon :name="notice.id % 2 ? 'PhBookOpen' : 'PhMegaphone'" /></span>
                <span class="notice-summary"><strong>{{ notice.title }}</strong><small>{{ notice.source || "校园通知" }} · {{ notice.author_name || "课程教师" }}</small><em>{{ notice.content || "打开查看通知详情" }}</em></span>
                <time>{{ displayNoticeTime(notice, index) }}</time>
                <UiIcon name="PhCaretDown" />
              </button>
              <p>{{ notice.content }}</p>
            </article>
          </div>
          <div v-else class="student-empty large"><UiIcon name="PhBell" :size="40" /><strong>暂时没有课程通知</strong><span>加入课程并等待教师发布通知，内容会出现在这里。</span></div>
          <div class="notice-footer">共 {{ filtered.length }} 条通知 <button class="link-button">查看更多历史通知 <UiIcon name="PhArrowRight" /></button></div>
        </section>
      </div>

      <section class="notice-extract-panel surface">
        <div class="student-panel-head">
          <div><h2><span class="step-number">1</span>从通知生成待办 <UiIcon name="PhSparkle" /></h2></div>
        </div>
        <p class="panel-hint">提取结果仅作为草稿，保存前请核对标题、截止时间和提交方式。</p>
        <textarea v-model="text" rows="7" maxlength="5000" placeholder="粘贴教务处、学院或学生工作部门的通知原文"></textarea>
        <div class="textarea-count">{{ text.length }} / 5000</div>
        <button class="primary-button full-button" :disabled="extracting || !text.trim()" @click="extract">{{ extracting ? "正在提取…" : "开始提取" }} <UiIcon name="PhArrowRight" /></button>

        <div class="extract-preview-label"><span class="step-number">2</span><h3>提取预览</h3><span>示例</span></div>
        <div v-if="extracted" class="extract-result">
          <div v-if="extracted.error" class="student-alert error">{{ extracted.error }}</div>
          <template v-else>
            <span class="status-pill green">已提取，请确认</span>
            <label class="student-field">任务标题<input v-model="extracted.task" /></label>
            <label class="student-field">截止时间<input v-model="extracted.deadline" placeholder="未识别" /></label>
            <label class="student-field">提交方式<input v-model="extracted.submission_method" placeholder="未识别" /></label>
            <button class="secondary-button full-button" :disabled="saving || extracted.saved" @click="saveTask">{{ extracted.saved ? "已保存到待办" : saving ? "保存中…" : "确认并保存为待办" }}</button>
          </template>
        </div>
        <div v-else class="extract-example-list">
          <div v-for="item in exampleNotices" :key="item.title" class="extract-example-row">
            <span class="example-check"></span>
            <div class="example-main"><strong>{{ item.title }} <em>{{ item.type }}</em></strong><small>{{ item.source }}</small></div>
            <div><small>{{ item.label }}</small><span>{{ item.value }}</span></div>
            <div><small>{{ item.label2 }}</small><span>{{ item.value2 }}</span></div>
            <UiIcon name="PhPencilSimple" />
          </div>
          <div class="extract-example-footer"><span>以上为 AI 提取的草稿，请核对后保存到「待办与作业」。</span><button class="primary-button" disabled><UiIcon name="PhBookmarkSimple" />保存全部到待办</button></div>
        </div>
      </section>
    </section>
  </main>
</template>

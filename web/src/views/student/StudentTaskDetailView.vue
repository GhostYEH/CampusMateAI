<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import {
  completePersonalTask,
  deletePersonalTask,
  getAssignment,
  getMySubmission,
  getPersonalTask,
  saveMySubmission,
} from "../../services/studentApi";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const error = ref("");
const item = ref(null);
const submission = ref(null);
const text = ref("");
const saving = ref(false);
const submitting = ref(false);

const assignmentMode = computed(() => route.params.kind === "assignment");

const itemStatus = computed(() => {
  if (!item.value) return "";
  if (!assignmentMode.value) return item.value.status === "completed" ? "已完成" : "待完成";
  const status = item.value.status;
  if (status === "closed") return "已结束";
  const submissionStatus = submission.value?.status;
  if (submissionStatus === "graded") return "已评分";
  if (submissionStatus === "submitted") return "已提交";
  if (submissionStatus === "late") return "已提交（逾期）";
  if (submissionStatus === "resubmitted") return "已重新提交";
  if (submissionStatus === "draft") return "草稿";
  return "待完成";
});

const isCompleted = computed(() => {
  if (!item.value) return false;
  return assignmentMode.value
    ? ["submitted", "graded", "late", "resubmitted"].includes(submission.value?.status)
    : item.value.status === "completed";
});

const deadlineMs = computed(() => {
  const value = item.value?.deadline;
  if (!value) return null;
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? null : time;
});

const isOverdue = computed(() => {
  if (!deadlineMs.value || isCompleted.value) return false;
  return deadlineMs.value < Date.now();
});

const daysLeft = computed(() => {
  if (!deadlineMs.value || isCompleted.value) return null;
  return Math.max(0, Math.ceil((deadlineMs.value - Date.now()) / 86400000));
});

const deadlineDate = computed(() => {
  const value = item.value?.deadline;
  if (!value) return "未设置";
  const d = new Date(value);
  if (Number.isNaN(d.valueOf())) return String(value);
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
});

const dueState = computed(() => {
  if (!item.value?.deadline) return "未设置截止时间";
  if (isCompleted.value) return assignmentMode.value ? "已提交" : "已完成";
  if (isOverdue.value) return "已逾期";
  if (daysLeft.value === 0) return "今天截止";
  return `还剩 ${daysLeft.value} 天`;
});

const submissionLabel = computed(
  () =>
    ({
      draft: "草稿",
      submitted: "已提交",
      late: "已提交（逾期）",
      resubmitted: "已重新提交",
      graded: "已评分",
    }[submission.value?.status] || "尚未提交")
);

const priorityLabel = computed(
  () => ({ high: "高优先级", medium: "中优先级", low: "低优先级" }[item.value?.priority] || "中优先级")
);

const reminderText = computed(() => {
  const minutes = item.value?.reminder_minutes;
  if (minutes == null) return "未设置提醒";
  if (minutes === 0) return "截止时提醒";
  if (minutes % 1440 === 0) return `提前 ${minutes / 1440} 天提醒`;
  if (minutes % 60 === 0) return `提前 ${minutes / 60} 小时提醒`;
  return `提前 ${minutes} 分钟提醒`;
});

const heroContext = computed(() => {
  if (!item.value) return "";
  const main = assignmentMode.value
    ? item.value.course_name || item.value.class_name || "课程作业"
    : item.value.source_name || "个人安排";
  return `${main} · ${itemStatus.value}`;
});

const heroDescription = computed(() => {
  const raw = item.value?.description || (!assignmentMode.value ? item.value?.source_text || "" : "");
  return raw ? String(raw).replace(/\s+/g, " ").trim() : "";
});

const descriptionText = computed(() => {
  if (item.value?.description) return item.value.description;
  if (!assignmentMode.value && item.value?.source_text) return item.value.source_text;
  return assignmentMode.value ? "教师暂未补充作业说明。" : "暂未补充说明。";
});

const infoRows = computed(() => {
  if (!item.value) return [];
  const rows = [];
  if (assignmentMode.value) {
    rows.push({ label: "截止时间", value: dateText(item.value.deadline), icon: "PhCalendarBlank", tone: "blue" });
    rows.push({ label: "发布教师", value: item.value.author_name || "—", icon: "PhUser", tone: "indigo" });
    rows.push({ label: "提交方式", value: item.value.submission_types?.join("、") || "在线文本", icon: "PhPaperclip", tone: "green" });
    rows.push({ label: "最高分", value: item.value.max_score != null ? `${item.value.max_score} 分` : "未设置", icon: "PhChartBar", tone: "amber" });
  } else {
    rows.push({ label: "截止时间", value: dateText(item.value.deadline), icon: "PhCalendarBlank", tone: "blue" });
    rows.push({ label: "来源", value: item.value.source_name || "个人安排", icon: "PhBookOpen", tone: "indigo" });
    rows.push({ label: "优先级", value: priorityLabel.value, icon: "PhFlag", tone: "amber" });
    rows.push({ label: "提醒", value: reminderText.value, icon: "PhBell", tone: "green" });
    if (item.value.location) rows.push({ label: "地点", value: item.value.location, icon: "PhMapPin", tone: "blue" });
    if (item.value.submission_method) rows.push({ label: "提交方式", value: item.value.submission_method, icon: "PhPaperclip", tone: "green" });
    if (item.value.created_at) rows.push({ label: "创建时间", value: dateText(item.value.created_at), icon: "PhNotePencil", tone: "indigo" });
  }
  return rows;
});

const submissionState = computed(() => {
  const status = submission.value?.status;
  if (status === "graded") {
    return {
      icon: "PhSealCheck",
      title: "教师已评分",
      text: submission.value?.submitted_at ? `提交于 ${dateText(submission.value.submitted_at)}` : "评分结果已经同步到课程成绩。",
    };
  }
  if (status === "submitted" || status === "late" || status === "resubmitted") {
    return {
      icon: "PhPaperPlaneTilt",
      title: "内容已提交",
      text: submission.value?.submitted_at ? `提交于 ${dateText(submission.value.submitted_at)}` : "内容已发送给教师。",
    };
  }
  if (status === "draft") {
    return {
      icon: "PhPencilSimpleLine",
      title: "草稿已保存",
      text: submission.value?.updated_at ? `最近保存于 ${dateText(submission.value.updated_at)}` : "内容只会在你主动保存后发送",
    };
  }
  return { icon: "PhPencilSimpleLine", title: "从草稿开始", text: "内容只会在你主动保存后发送" };
});

const nextStepTitle = computed(() => {
  if (!assignmentMode.value) return item.value?.status === "completed" ? "这件事已经完成" : "完成后记得更新状态";
  if (submission.value?.status === "graded") return "查看教师反馈";
  if (item.value?.status === "closed") return "作业已结束";
  if (submission.value?.status === "submitted" || submission.value?.status === "late" || submission.value?.status === "resubmitted") return "等待教师评分";
  return "完成并提交作业";
});

const nextStepText = computed(() => {
  if (!assignmentMode.value) {
    return item.value?.status === "completed"
      ? "完成状态已同步到待办列表和首页摘要。"
      : "点击右侧按钮标记完成，或继续编辑这条待办。";
  }
  if (submission.value?.status === "graded") return "教师已经为这次提交留下评分和评语。";
  if (item.value?.status === "closed") return "截止时间已过，无法继续提交。";
  if (submission.value?.status === "submitted" || submission.value?.status === "late" || submission.value?.status === "resubmitted") {
    return "内容已发送给教师，评分结果会出现在右侧。";
  }
  return "先保存草稿，再确认内容无误后正式提交。";
});

const stateTone = computed(() => {
  if (isCompleted.value) return "green";
  if (isOverdue.value) return "red";
  if (assignmentMode.value && submission.value?.status === "draft") return "amber";
  return assignmentMode.value ? "blue" : "indigo";
});

const dueTone = computed(() => {
  if (isCompleted.value) return "green";
  if (isOverdue.value) return "red";
  return assignmentMode.value ? "blue" : "indigo";
});

const submissionTone = computed(() => {
  const status = submission.value?.status;
  if (status === "graded") return "green";
  if (status === "submitted" || status === "late" || status === "resubmitted") return "blue";
  if (status === "draft") return "amber";
  return "indigo";
});

const nextTone = computed(() => (isCompleted.value ? "green" : "amber"));

const createdLabel = computed(() => (item.value?.created_at ? dateText(item.value.created_at) : "—"));
const scoreLabel = computed(() => (item.value?.max_score != null ? `${item.value.max_score} 分` : "未设置"));

const submitButtonLabel = computed(() => {
  if (submission.value?.status === "submitted" || submission.value?.status === "late" || submission.value?.status === "resubmitted") {
    return "重新提交";
  }
  return "正式提交";
});

function dateText(value) {
  if (!value) return "未设置截止时间";
  const d = new Date(value);
  return Number.isNaN(d.valueOf()) ? String(value) : d.toLocaleString("zh-CN");
}

function formatSize(bytes) {
  const value = Number(bytes);
  if (!Number.isFinite(value) || value < 0) return "";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

async function load() {
  loading.value = true;
  error.value = "";
  text.value = "";
  try {
    if (assignmentMode.value) {
      item.value = await getAssignment(route.params.id);
      submission.value = await getMySubmission(route.params.id);
      text.value = submission.value?.text_content || "";
    } else {
      item.value = await getPersonalTask(route.params.id);
    }
  } catch (e) {
    error.value = e.response?.data?.detail || "事项详情加载失败。";
  } finally {
    loading.value = false;
  }
}

async function saveDraft(shouldSubmit = false) {
  if (!text.value.trim() || saving.value || submitting.value) return;
  if (shouldSubmit) submitting.value = true;
  else saving.value = true;
  try {
    submission.value = await saveMySubmission(route.params.id, {
      text_content: text.value,
      submit: shouldSubmit,
    });
  } catch (e) {
    error.value = e.response?.data?.detail || "提交失败，请重试。";
  } finally {
    saving.value = false;
    submitting.value = false;
  }
}

async function togglePersonal() {
  try {
    item.value = await completePersonalTask(item.value.id, item.value.status !== "completed");
  } catch (e) {
    error.value = e.response?.data?.detail || "更新待办状态失败。";
  }
}

async function removePersonal() {
  if (!window.confirm("确认删除这条待办吗？")) return;
  try {
    await deletePersonalTask(item.value.id);
    router.replace("/tasks");
  } catch (e) {
    error.value = e.response?.data?.detail || "删除失败，请重试。";
  }
}

watch(
  () => [route.params.kind, route.params.id],
  () => {
    if (route.params.id) load();
  }
);

onMounted(load);
</script>

<template>
  <main class="student-page page-enter task-detail-redesign">
    <button class="cd-back-link" type="button" @click="router.push('/tasks')">
      <UiIcon name="PhArrowLeft" />返回待办
    </button>

    <div v-if="loading" class="td-loading" aria-label="任务详情加载中">
      <div class="td-loading-hero"></div>
      <div class="td-loading-grid"><span></span><span></span></div>
    </div>

    <div v-else-if="error" class="student-alert error">
      <UiIcon name="PhWarningCircle" />{{ error }}
      <button class="link-button" type="button" @click="load">重试</button>
    </div>

    <template v-else-if="item">
      <header class="td-hero" :class="assignmentMode ? 'tone-blue' : 'tone-indigo'">
        <div class="td-hero-main">
          <div class="td-hero-head">
            <span class="td-kind" :class="assignmentMode ? 'blue' : 'indigo'">
              <UiIcon :name="assignmentMode ? 'PhFileText' : 'PhCheckSquare'" :size="15" />
              {{ assignmentMode ? '课程作业' : '个人待办' }}
            </span>
            <span class="td-state" :class="stateTone">{{ itemStatus }}</span>
          </div>
          <h1 class="td-title">
            {{ item.title }}<UiIcon name="PhSparkle" class="td-sparkle" :size="22" />
          </h1>
          <p class="td-context">{{ heroContext }}</p>
          <p v-if="heroDescription" class="td-desc">{{ heroDescription }}</p>
        </div>

        <aside class="td-focus" :class="dueTone">
          <div class="td-focus-head">
            <span class="td-focus-icon"><UiIcon :name="assignmentMode ? 'PhClock' : 'PhCalendarBlank'" :size="18" /></span>
            <span>截止时间</span>
          </div>
          <strong class="td-focus-date">{{ deadlineDate }}</strong>
          <span class="td-focus-state">{{ dueState }}</span>
          <div class="td-focus-divider"></div>
          <div class="td-focus-meta">
            <span>
              <small>当前状态</small>
              <strong>{{ itemStatus }}</strong>
            </span>
            <span>
              <small>{{ assignmentMode ? '提交状态' : '优先级' }}</small>
              <strong>{{ assignmentMode ? submissionLabel : priorityLabel }}</strong>
            </span>
          </div>
        </aside>
      </header>

      <section class="td-stats" aria-label="任务概况">
        <div class="td-stat">
          <span class="td-stat-icon blue"><UiIcon name="PhHourglass" /></span>
          <span>
            <small>当前状态</small>
            <strong>{{ itemStatus }}</strong>
          </span>
        </div>
        <div class="td-stat">
          <span class="td-stat-icon indigo"><UiIcon :name="assignmentMode ? 'PhPaperPlaneTilt' : 'PhFlag'" /></span>
          <span>
            <small>{{ assignmentMode ? '提交状态' : '优先级' }}</small>
            <strong>{{ assignmentMode ? submissionLabel : priorityLabel }}</strong>
          </span>
        </div>
        <div class="td-stat">
          <span class="td-stat-icon amber"><UiIcon :name="assignmentMode ? 'PhPaperclip' : 'PhBell'" /></span>
          <span>
            <small>{{ assignmentMode ? '附件' : '提醒' }}</small>
            <strong>{{ assignmentMode ? `${item.attachments?.length || 0} 个附件` : reminderText }}</strong>
          </span>
        </div>
        <div class="td-stat">
          <span class="td-stat-icon green"><UiIcon name="PhCalendarBlank" /></span>
          <span>
            <small>{{ assignmentMode ? '满分' : '创建时间' }}</small>
            <strong>{{ assignmentMode ? scoreLabel : createdLabel }}</strong>
          </span>
        </div>
      </section>

      <section class="td-layout">
        <div class="td-main">
          <article class="cd-panel td-panel">
            <div class="cd-panel-head td-panel-head">
              <div>
                <span class="cd-eyebrow">TASK BRIEF</span>
                <h2>事项说明</h2>
              </div>
              <span class="cd-count">{{ assignmentMode ? '课程作业' : '个人待办' }}</span>
            </div>

            <p class="td-description">{{ descriptionText }}</p>

            <div class="td-info-grid">
              <div v-for="row in infoRows" :key="row.label" class="td-info-item">
                <span class="td-info-icon" :class="row.tone"><UiIcon :name="row.icon" :size="16" /></span>
                <span class="td-info-main">
                  <small>{{ row.label }}</small>
                  <strong>{{ row.value }}</strong>
                </span>
              </div>
            </div>

            <div v-if="!assignmentMode && item.materials?.length" class="td-block">
              <div class="td-block-head"><UiIcon name="PhFiles" />所需材料</div>
              <div class="td-chip-list">
                <span v-for="(material, index) in item.materials" :key="index" class="td-chip">
                  <UiIcon name="PhPaperclip" :size="13" />{{ material }}
                </span>
              </div>
            </div>

            <div v-if="assignmentMode && item.attachments?.length" class="td-block">
              <div class="td-block-head"><UiIcon name="PhPaperclip" />作业附件</div>
              <div class="td-file-list">
                <a
                  v-for="file in item.attachments"
                  :key="file.id"
                  class="td-file-item"
                  :href="`/api/v1/assignments/${item.id}/attachments/${file.id}`"
                  target="_blank"
                  rel="noopener"
                >
                  <span class="td-file-icon"><UiIcon name="PhFileText" /></span>
                  <span>
                    <strong>{{ file.original_filename }}</strong>
                    <small>{{ file.size_bytes != null ? formatSize(file.size_bytes) : '附件' }}</small>
                  </span>
                  <UiIcon name="PhDownloadSimple" />
                </a>
              </div>
            </div>
          </article>

          <article class="cd-panel td-next-panel">
            <span class="td-next-icon" :class="nextTone"><UiIcon name="PhLightbulb" /></span>
            <div class="td-next-main">
              <span class="cd-eyebrow">NEXT STEP</span>
              <h2>{{ nextStepTitle }}</h2>
              <p>{{ nextStepText }}</p>
            </div>
            <UiIcon name="PhArrowRight" class="td-next-arrow" />
          </article>
        </div>

        <aside class="td-side">
          <template v-if="assignmentMode">
            <article class="cd-panel td-submit-card">
              <div class="cd-panel-head td-panel-head">
                <div>
                  <span class="cd-eyebrow">MY SUBMISSION</span>
                  <h2>我的提交</h2>
                </div>
                <span class="td-status-pill" :class="submissionTone">{{ submissionLabel }}</span>
              </div>

              <div class="td-submit-state">
                <span class="td-submit-icon" :class="submissionTone"><UiIcon :name="submissionState.icon" /></span>
                <span>
                  <strong>{{ submissionState.title }}</strong>
                  <small>{{ submissionState.text }}</small>
                </span>
              </div>

              <textarea
                v-model="text"
                name="assignment-submission"
                rows="9"
                :disabled="item.status === 'closed' || submission?.status === 'graded'"
                placeholder="写下你的作业内容，先保存草稿，再提交给教师"
              ></textarea>

              <div v-if="submission?.score != null" class="td-grade">
                <span class="td-grade-score"><strong>{{ submission.score }}</strong><small>分</small></span>
                <span class="td-grade-main">
                  <span class="cd-eyebrow">教师反馈</span>
                  <strong>{{ submission.teacher_comment ? '已收到评语' : '已评分，暂未留下评语' }}</strong>
                  <p>{{ submission.teacher_comment || '教师暂未留下评语。' }}</p>
                </span>
              </div>

              <div class="td-submit-actions">
                <button class="cd-enter-btn" type="button" :disabled="saving || !text.trim()" @click="saveDraft(false)">
                  {{ saving ? '保存中…' : '保存草稿' }}
                </button>
                <button
                  class="cd-primary-btn"
                  type="button"
                  :disabled="submitting || !text.trim() || item.status === 'closed' || submission?.status === 'graded'"
                  @click="saveDraft(true)"
                >
                  {{ submitting ? '提交中…' : submitButtonLabel }}
                </button>
              </div>

              <p class="td-hint"><UiIcon name="PhInfo" />提交前请确认内容完整，正式提交后状态由教师端返回。</p>
            </article>
          </template>

          <template v-else>
            <article class="cd-panel td-action-card">
              <div class="cd-panel-head td-panel-head">
                <div>
                  <span class="cd-eyebrow">PERSONAL TASK</span>
                  <h2>我的安排</h2>
                </div>
                <span class="td-status-pill" :class="item.status === 'completed' ? 'green' : 'amber'">{{ itemStatus }}</span>
              </div>

              <div class="td-action-state">
                <span class="td-submit-icon" :class="item.status === 'completed' ? 'green' : 'indigo'"><UiIcon name="PhCheckCircle" /></span>
                <span>
                  <strong>{{ item.status === 'completed' ? '这件事已经完成' : '还差最后一步' }}</strong>
                  <small>{{ item.status === 'completed' ? `完成于 ${dateText(item.completed_at)}` : reminderText }}</small>
                </span>
              </div>

              <div class="td-reminder-list">
                <div>
                  <span><UiIcon name="PhFlag" /></span>
                  <small>优先级</small>
                  <strong>{{ priorityLabel }}</strong>
                </div>
                <div>
                  <span><UiIcon name="PhBell" /></span>
                  <small>提醒</small>
                  <strong>{{ reminderText }}</strong>
                </div>
                <div v-if="item.location">
                  <span><UiIcon name="PhMapPin" /></span>
                  <small>地点</small>
                  <strong>{{ item.location }}</strong>
                </div>
                <div v-if="item.submission_method">
                  <span><UiIcon name="PhPaperclip" /></span>
                  <small>提交方式</small>
                  <strong>{{ item.submission_method }}</strong>
                </div>
              </div>

              <div class="td-action-buttons">
                <button class="cd-primary-btn" type="button" @click="togglePersonal">
                  <UiIcon name="PhCheck" />{{ item.status === 'completed' ? '标记未完成' : '标记已完成' }}
                </button>
                <button class="td-danger-btn" type="button" @click="removePersonal">
                  <UiIcon name="PhTrash" />删除待办
                </button>
              </div>

              <p class="td-hint"><UiIcon name="PhInfo" />完成、恢复或删除操作都会直接同步到个人待办数据。</p>
            </article>
          </template>
        </aside>
      </section>
    </template>
  </main>
</template>

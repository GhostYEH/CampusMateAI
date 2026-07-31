<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import PageHeader from "../../components/teacher/PageHeader.vue";
import Skeleton from "../../components/teacher/Skeleton.vue";
import ErrorState from "../../components/teacher/ErrorState.vue";
import EmptyState from "../../components/teacher/EmptyState.vue";
import StatusTag from "../../components/teacher/StatusTag.vue";
import StatCard from "../../components/teacher/StatCard.vue";
import UiIcon from "../../components/UiIcon.vue";
import { useToast, extractErrorMessage } from "../../composables/useToast";
import { useConfirm } from "../../composables/useConfirm";
import {
  getAssignment, updateAssignment, publishAssignment, closeAssignment, archiveAssignment,
  getAssignmentStats, getStudentStatus, listAssignmentAttachments, buildAttachmentDownloadUrl,
} from "../../services/teacher/assignments";
import { formatDate, formatDateTime, formatFileSize, daysUntil, isOverdue } from "../../composables/useFormat";

const route = useRoute();
const router = useRouter();
const toast = useToast();
const { confirm } = useConfirm();

const assignmentId = computed(() => route.params.assignmentId);
const loading = ref(true);
const error = ref("");
const assignment = ref(null);
const stats = ref(null);
const students = ref([]);
const attachments = ref([]);
const tab = ref("overview");

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [a, s] = await Promise.all([
      getAssignment(assignmentId.value),
      getAssignmentStats(assignmentId.value).catch(() => null),
    ]);
    assignment.value = a;
    stats.value = s;
    if (a.status !== "draft") {
      const ss = await getStudentStatus(assignmentId.value).catch(() => ({ items: [] }));
      students.value = ss.items || [];
    } else {
      students.value = [];
    }
    const atts = await listAssignmentAttachments(assignmentId.value).catch(() => []);
    attachments.value = Array.isArray(atts) ? atts : (atts.items || []);
  } catch (err) {
    error.value = extractErrorMessage(err, "作业详情加载失败");
  } finally {
    loading.value = false;
  }
}

async function publish() {
  const ok = await confirm({
    title: "发布作业",
    message: `发布后「${assignment.value.title}」将立即对学生可见。确定发布?`,
    confirmText: "发布",
  });
  if (!ok) return;
  try {
    await publishAssignment(assignment.value.id);
    toast.success("作业已发布");
    await load();
  } catch (err) {
    toast.error(extractErrorMessage(err, "发布失败"));
  }
}

async function close() {
  const ok = await confirm({
    title: "结束作业",
    message: `结束后学生将不能再提交。确定结束?`,
    confirmText: "结束",
  });
  if (!ok) return;
  try {
    await closeAssignment(assignment.value.id);
    toast.success("作业已结束");
    await load();
  } catch (err) {
    toast.error(extractErrorMessage(err, "结束失败"));
  }
}

async function archive() {
  const ok = await confirm({
    title: "归档作业", message: `归档后作业将不再出现在学生列表。确定归档?`, confirmText: "归档",
  });
  if (!ok) return;
  try {
    await archiveAssignment(assignment.value.id);
    toast.success("作业已归档");
    await load();
  } catch (err) {
    toast.error(extractErrorMessage(err, "归档失败"));
  }
}

const breadcrumbs = computed(() => [
  { label: "作业管理", to: "/teacher/assignments" },
  { label: assignment.value?.title || "作业详情" },
]);

const submitRate = computed(() => {
  if (!stats.value || !stats.value.total_students) return null;
  return Math.round((stats.value.submitted_count / stats.value.total_students) * 100);
});

const gradedRate = computed(() => {
  if (!stats.value || !stats.value.submitted_count) return null;
  return Math.round((stats.value.graded_count / stats.value.submitted_count) * 100);
});

const avgScore = computed(() => {
  if (!stats.value || !stats.value.graded_count) return null;
  return Math.round((stats.value.total_score / stats.value.graded_count) * 10) / 10;
});

const deadlineHint = computed(() => {
  if (!assignment.value?.deadline) return "无截止";
  if (isOverdue(assignment.value.deadline)) return "已截止";
  const d = daysUntil(assignment.value.deadline);
  if (d === 0) return "今日截止";
  if (d === 1) return "明日截止";
  return `${d} 天后截止`;
});

const tabs = [
  { key: "overview", label: "概览", icon: "PhInfo" },
  { key: "students", label: "学生提交", icon: "PhStudent" },
  { key: "attachments", label: "附件", icon: "PhPaperclip" },
];

onMounted(load);
watch(assignmentId, load);
</script>

<template>
  <main class="tch-page page-enter">
    <PageHeader
      kicker="作业详情"
      :title="assignment?.title || '加载中…'"
      :subtitle="assignment?.description || ''"
      :breadcrumbs="breadcrumbs"
      @breadcrumb-click="(c) => c.to && router.push(c.to)"
    >
      <template #actions>
        <button class="secondary-button" @click="router.push('/teacher/assignments')"><UiIcon name="PhArrowLeft" :size="16" />返回列表</button>
        <button v-if="assignment?.status === 'draft'" class="primary-button" @click="publish"><UiIcon name="PhPaperPlaneTilt" :size="16" />发布</button>
        <button v-if="assignment?.status === 'published'" class="secondary-button" @click="close"><UiIcon name="PhLock" :size="16" />结束</button>
        <button v-if="assignment?.status === 'closed' || assignment?.status === 'published'" class="secondary-button" @click="archive"><UiIcon name="PhArchive" :size="16" />归档</button>
      </template>
    </PageHeader>

    <Skeleton v-if="loading" :rows="4" layout="grid" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />
    <template v-else-if="assignment">
      <nav class="tch-tabs">
        <button v-for="t in tabs" :key="t.key" :class="{ active: tab === t.key }" @click="tab = t.key">
          <UiIcon :name="t.icon" :size="16" /><span>{{ t.label }}</span>
        </button>
      </nav>

      <section v-show="tab === 'overview'" class="tch-tab-panel">
        <section v-if="stats" class="tch-stat-strip">
          <StatCard label="应交人数" :value="stats.total_students" icon="PhUsers" />
          <StatCard label="已提交" :value="stats.submitted_count" :hint="submitRate !== null ? `${submitRate}%` : ''" icon="PhCheckCircle" tone="info" />
          <StatCard label="已批改" :value="stats.graded_count" :hint="gradedRate !== null ? `${gradedRate}%` : ''" icon="PhPencilSimpleLine" tone="primary" />
          <StatCard label="平均分" :value="avgScore ?? '—'" :hint="assignment.full_score ? `满分 ${assignment.full_score}` : ''" icon="PhChartLine" tone="primary" />
          <StatCard label="未提交" :value="stats.total_students - stats.submitted_count" icon="PhClock" tone="warning" />
        </section>

        <div class="tch-overview-grid">
          <div class="tch-panel">
            <h2>作业信息</h2>
            <dl class="tch-info-list">
              <div><dt>状态</dt><dd><StatusTag :status="assignment.status" type="assignment" /></dd></div>
              <div><dt>截止时间</dt><dd>{{ formatDateTime(assignment.deadline) }} <em class="tch-deadline-hint">{{ deadlineHint }}</em></dd></div>
              <div><dt>满分分值</dt><dd>{{ assignment.full_score ?? '—' }}</dd></div>
              <div><dt>允许迟交</dt><dd>{{ assignment.allow_late ? '是' : '否' }}</dd></div>
              <div><dt>创建时间</dt><dd>{{ formatDateTime(assignment.created_at) }}</dd></div>
            </dl>
          </div>
          <div class="tch-panel">
            <h2>作业描述</h2>
            <article class="tch-detail-content">{{ assignment.description || '暂无描述' }}</article>
            <button class="secondary-button" @click="router.push('/teacher/assignments')"><UiIcon name="PhPencil" :size="16" />在列表页编辑</button>
          </div>
        </div>

        <section v-if="assignment.status !== 'draft'" class="tch-panel">
          <div class="tch-panel-head">
            <h2>提交情况</h2>
            <button class="primary-button" @click="router.push('/teacher/grading')"><UiIcon name="PhPencilSimpleLine" :size="16" />前往批改</button>
          </div>
          <p class="tch-hint">已提交 {{ stats?.submitted_count ?? 0 }} / 应交 {{ stats?.total_students ?? 0 }}，已批改 {{ stats?.graded_count ?? 0 }} 份。</p>
        </section>
      </section>

      <section v-show="tab === 'students'" class="tch-tab-panel">
        <div class="tch-panel-head-row"><h2>学生提交情况</h2></div>
        <EmptyState v-if="assignment.status === 'draft'" icon="PhFileText" title="作业尚未发布" description="发布后可查看学生提交情况。" />
        <EmptyState v-else-if="!students.length" icon="PhStudent" title="暂无学生" />
        <section v-else class="tch-panel">
          <div class="tch-table-wrap">
            <div class="tch-table-scroll" style="min-width: 760px">
              <table class="tch-table">
                <thead>
                  <tr>
                    <th>学号</th><th>姓名</th><th>提交状态</th><th>提交时间</th><th>成绩</th><th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="s in students" :key="s.user_id || s.student_id">
                    <td>{{ s.student_number || s.username || '—' }}</td>
                    <td>{{ s.display_name || s.username || '—' }}</td>
                    <td><StatusTag :status="s.submission_status || s.status || 'unread'" type="submission" /></td>
                    <td><small>{{ s.submitted_at ? formatDateTime(s.submitted_at) : '—' }}</small></td>
                    <td>{{ s.score ?? '—' }}<small v-if="s.score !== null && s.score !== undefined && assignment.full_score"> / {{ assignment.full_score }}</small></td>
                    <td>
                      <div class="tch-row-actions">
                        <button v-if="s.submission_id" class="tch-link" @click="router.push(`/teacher/grading?assignment_id=${assignment.id}&submission_id=${s.submission_id}`)">批改</button>
                        <span v-else class="muted">—</span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </section>

      <section v-show="tab === 'attachments'" class="tch-tab-panel">
        <div class="tch-panel-head-row"><h2>作业附件</h2></div>
        <section class="tch-panel">
          <p class="tch-hint">附件对学生可见。可在作业列表页管理附件。</p>
          <EmptyState v-if="!attachments.length" icon="PhPaperclip" title="暂无附件" />
          <ul v-else class="tch-attach-list">
            <li v-for="att in attachments" :key="att.id">
              <UiIcon name="PhFile" :size="18" />
              <div class="tch-attach-info">
                <strong>{{ att.filename || att.name }}</strong>
                <small>{{ formatFileSize(att.size || att.file_size) }} · {{ formatDateTime(att.created_at) }}</small>
              </div>
              <a class="tch-link" :href="buildAttachmentDownloadUrl(assignment.id, att.id)" target="_blank" rel="noopener">
                <UiIcon name="PhDownloadSimple" :size="14" />下载
              </a>
            </li>
          </ul>
          <button class="primary-button" @click="router.push('/teacher/assignments')"><UiIcon name="PhPencil" :size="16" />管理附件</button>
        </section>
      </section>
    </template>
  </main>
</template>
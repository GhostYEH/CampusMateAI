<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import PageHeader from "../../components/teacher/PageHeader.vue";
import FilterBar from "../../components/teacher/FilterBar.vue";
import Skeleton from "../../components/teacher/Skeleton.vue";
import ErrorState from "../../components/teacher/ErrorState.vue";
import EmptyState from "../../components/teacher/EmptyState.vue";
import StatusTag from "../../components/teacher/StatusTag.vue";
import StatCard from "../../components/teacher/StatCard.vue";
import UiIcon from "../../components/UiIcon.vue";
import { useTeacherStore } from "../../stores/teacher";
import { useToast, extractErrorMessage } from "../../composables/useToast";
import { getTeacherAnalytics } from "../../services/teacher/analytics";
import { formatDate } from "../../composables/useFormat";

const router = useRouter();
const teacherStore = useTeacherStore();
const toast = useToast();

const loading = ref(true);
const error = ref("");
const data = ref(null);
const classFilter = ref("");
const courseFilter = ref("");
const tab = ref("overview");

const classOptions = computed(() => teacherStore.classOptionsWithCourse());

const filterConfig = computed(() => [
  {
    key: "course", label: "课程", value: courseFilter.value,
    options: teacherStore.courses.map((c) => ({ value: c.id, label: c.name })),
  },
  {
    key: "class", label: "班级", value: classFilter.value,
    options: classOptions.value.map((c) => ({ value: c.id, label: `${c.course?.name || ""} / ${c.name}` })),
  },
]);

function onFiltersChange(next) {
  next.forEach((f) => {
    if (f.key === "course") courseFilter.value = f.value;
    if (f.key === "class") classFilter.value = f.value;
  });
  load();
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    await teacherStore.loadAll().catch(() => null);
    const params = {};
    if (classFilter.value) params.class_id = classFilter.value;
    if (courseFilter.value) params.course_id = courseFilter.value;
    data.value = await getTeacherAnalytics(params);
  } catch (err) {
    error.value = extractErrorMessage(err, "学情数据加载失败");
  } finally {
    loading.value = false;
  }
}

const submissionRatePct = computed(() => {
  if (!data.value || !data.value.total_expected_submissions) return null;
  return Math.round((data.value.total_submitted / data.value.total_expected_submissions) * 100);
});
const gradingRatePct = computed(() => {
  if (!data.value || !data.value.total_submitted) return null;
  return Math.round((data.value.total_graded / data.value.total_submitted) * 100);
});

const scoreBars = computed(() => {
  if (!data.value?.score_distribution) return [];
  const entries = Object.entries(data.value.score_distribution);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  return entries.map(([label, count]) => ({ label, count, pct: Math.round((count / max) * 100) }));
});

const assignmentBars = computed(() => {
  if (!data.value?.assignments) return [];
  return data.value.assignments.map((a) => ({
    ...a,
    submissionPct: a.submission_rate ?? (a.total_students ? Math.round((a.submitted / a.total_students) * 100) : 0),
    gradingPct: a.grading_rate ?? (a.submitted ? Math.round((a.graded / a.submitted) * 100) : 0),
  }));
});

const sortedStudents = computed(() => {
  if (!data.value?.students) return [];
  return [...data.value.students].sort((a, b) => (a.completion_rate ?? 0) - (b.completion_rate ?? 0));
});

const tabs = [
  { key: "overview", label: "总体概览", icon: "PhChartBar" },
  { key: "assignments", label: "作业完成", icon: "PhFileText" },
  { key: "students", label: "学生完成率", icon: "PhStudent" },
  { key: "attention", label: "需关注", icon: "PhFlag" },
];

onMounted(load);
</script>

<template>
  <main class="tch-page page-enter">
    <PageHeader kicker="学情分析" title="教学数据看板" subtitle="基于真实提交与批改数据生成的客观统计，不进行主观判断。">
      <template #actions>
        <button class="secondary-button" @click="load"><UiIcon name="PhArrowClockwise" :size="16" />刷新</button>
      </template>
    </PageHeader>

    <FilterBar :filters="filterConfig" :searchable="false" @update:filters="onFiltersChange" />

    <Skeleton v-if="loading" :rows="5" layout="grid" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />
    <EmptyState v-else-if="!data || !data.total_assignments" icon="PhChartBar" title="暂无数据" description="发布作业并收到学生提交后，这里会显示学情统计。" />
    <template v-else>
      <nav class="tch-tabs">
        <button v-for="t in tabs" :key="t.key" :class="{ active: tab === t.key }" @click="tab = t.key">
          <UiIcon :name="t.icon" :size="16" /><span>{{ t.label }}</span>
        </button>
      </nav>

      <section v-show="tab === 'overview'" class="tch-tab-panel">
        <section class="tch-stat-strip">
          <StatCard label="作业总数" :value="data.total_assignments" icon="PhFileText" />
          <StatCard label="应交提交" :value="data.total_expected_submissions" icon="PhUsers" />
          <StatCard label="已提交" :value="data.total_submitted" :hint="submissionRatePct !== null ? `${submissionRatePct}%` : ''" icon="PhCheckCircle" tone="info" />
          <StatCard label="待批改" :value="data.total_pending_grading" icon="PhPencilSimpleLine" tone="warning" />
          <StatCard label="已批改" :value="data.total_graded" :hint="gradingRatePct !== null ? `${gradingRatePct}%` : ''" icon="PhCheckSquare" tone="primary" />
          <StatCard label="迟交份数" :value="data.total_late" icon="PhClock" tone="warning" />
        </section>

        <div class="tch-overview-grid">
          <section class="tch-panel">
            <h2>分数分布</h2>
            <EmptyState v-if="!scoreBars.length" icon="PhChartBar" title="暂无分数数据" compact />
            <div v-else class="tch-bar-chart">
              <div v-for="bar in scoreBars" :key="bar.label" class="tch-bar-col">
                <div class="tch-bar-track">
                  <div class="tch-bar-fill" :style="{ height: bar.pct + '%' }">
                    <span class="tch-bar-value">{{ bar.count }}</span>
                  </div>
                </div>
                <span class="tch-bar-label">{{ bar.label }}</span>
              </div>
            </div>
          </section>

          <section class="tch-panel">
            <h2>分数概览</h2>
            <dl class="tch-info-list">
              <div><dt>平均分</dt><dd>{{ data.overall_avg_score ?? '—' }}</dd></div>
              <div><dt>最高分</dt><dd>{{ data.overall_max_score ?? '—' }}</dd></div>
              <div><dt>最低分</dt><dd>{{ data.overall_min_score ?? '—' }}</dd></div>
              <div><dt>提交率</dt><dd>{{ submissionRatePct ?? '—' }}%</dd></div>
              <div><dt>批改率</dt><dd>{{ gradingRatePct ?? '—' }}%</dd></div>
            </dl>
            <p class="tch-hint">以上统计仅反映提交与成绩分布，不构成对学生学习状态的主观判断。</p>
          </section>
        </div>
      </section>

      <section v-show="tab === 'assignments'" class="tch-tab-panel">
        <div class="tch-panel-head-row"><h2>各作业完成情况</h2></div>
        <EmptyState v-if="!assignmentBars.length" icon="PhFileText" title="暂无作业数据" />
        <section v-else class="tch-panel">
          <div class="tch-table-wrap">
            <div class="tch-table-scroll" style="min-width: 980px">
              <table class="tch-table">
                <thead>
                  <tr>
                    <th>作业</th><th>课程 / 班级</th><th>状态</th><th>截止</th><th>应交</th><th>已交</th><th>提交率</th><th>已批改</th><th>平均分</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="a in assignmentBars" :key="a.assignment_id">
                    <td>
                      <button class="tch-link strong" @click="router.push(`/teacher/assignments/${a.assignment_id}`)">{{ a.title }}</button>
                    </td>
                    <td><small>{{ a.course_name }} / {{ a.class_name }}</small></td>
                    <td><StatusTag :status="a.status" type="assignment" /></td>
                    <td><small>{{ formatDate(a.deadline) }}</small></td>
                    <td>{{ a.total_students }}</td>
                    <td>{{ a.submitted }}</td>
                    <td>
                      <div class="tch-mini-bar">
                        <div class="tch-mini-bar-fill" :style="{ width: a.submissionPct + '%' }"></div>
                        <span>{{ a.submissionPct }}%</span>
                      </div>
                    </td>
                    <td>{{ a.graded }} / {{ a.submitted }}</td>
                    <td>{{ a.avg_score ?? '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </section>

      <section v-show="tab === 'students'" class="tch-tab-panel">
        <div class="tch-panel-head-row"><h2>学生完成率</h2></div>
        <EmptyState v-if="!sortedStudents.length" icon="PhStudent" title="暂无学生数据" />
        <section v-else class="tch-panel">
          <p class="tch-hint">按完成率从低到高排列，便于了解整体分布。完成率仅反映提交比例，不代表学习能力。</p>
          <div class="tch-table-wrap">
            <div class="tch-table-scroll" style="min-width: 880px">
              <table class="tch-table">
                <thead>
                  <tr>
                    <th>学号</th><th>姓名</th><th>课程 / 班级</th><th>应交</th><th>已交</th><th>未交</th><th>已批改</th><th>完成率</th><th>平均分</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="s in sortedStudents" :key="s.student_id">
                    <td>{{ s.student_number || '—' }}</td>
                    <td>{{ s.student_name || '—' }}</td>
                    <td><small>{{ s.course_name }} / {{ s.class_name }}</small></td>
                    <td>{{ s.total_assignments }}</td>
                    <td>{{ s.submitted_assignments }}</td>
                    <td>{{ s.unsubmitted_assignments }}</td>
                    <td>{{ s.graded_assignments }}</td>
                    <td>
                      <div class="tch-mini-bar">
                        <div class="tch-mini-bar-fill" :style="{ width: (s.completion_rate ?? 0) + '%' }"></div>
                        <span>{{ Math.round(s.completion_rate ?? 0) }}%</span>
                      </div>
                    </td>
                    <td>{{ s.avg_score ?? '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </section>

      <section v-show="tab === 'attention'" class="tch-tab-panel">
        <div class="tch-panel-head-row"><h2>连续未提交学生</h2></div>
        <p class="tch-hint">以下学生存在多次未提交记录，建议结合实际情况沟通了解原因，不预设主观判断。</p>
        <EmptyState v-if="!data.frequent_unsubmitted_students?.length" icon="PhCheckCircle" title="暂无连续未提交学生" description="所有学生提交情况良好。" />
        <section v-else class="tch-panel">
          <div class="tch-table-wrap">
            <div class="tch-table-scroll" style="min-width: 720px">
              <table class="tch-table">
                <thead>
                  <tr>
                    <th>学号</th><th>姓名</th><th>课程 / 班级</th><th>未交次数</th><th>应交总数</th><th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="s in data.frequent_unsubmitted_students" :key="s.student_id">
                    <td>{{ s.student_number || '—' }}</td>
                    <td>{{ s.student_name || '—' }}</td>
                    <td><small>{{ s.course_name }} / {{ s.class_name }}</small></td>
                    <td><strong class="warm">{{ s.unsubmitted_count }}</strong></td>
                    <td>{{ s.total_assignments }}</td>
                    <td>
                      <button class="tch-link" @click="router.push('/teacher/ai-assistant')"><UiIcon name="PhChatCircleText" :size="14" />沟通建议</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </section>
    </template>
  </main>
</template>
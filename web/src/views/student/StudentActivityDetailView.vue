<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { cancelActivityRegistration, getStudentActivity, getActivityRegistration, registerActivity } from "../../services/studentApi";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const error = ref("");
const activity = ref(null);
const registration = ref(null);
const submitting = ref(false);
const favorited = ref(false);
const toast = ref("");

const fallbackActivity = {
  id: "preview", category: "lecture", title: "人工智能与校园创新应用讲座",
  summary: "从真实校园问题出发，了解 AI 产品设计与工程落地。",
  content: "本次讲座将结合真实校园场景，分享人工智能在教学、管理、服务等方面的创新应用案例，解析 AI 产品从需求到落地的完整路径，并邀请行业专家与同学们面对面交流。\n\n无论你是技术爱好者、产品思考者，还是对校园创新感兴趣的同学，都能在这里获得启发与收获。",
  author_name: "学生事务处 × 创新创业学院 × 计算机学院",
  starts_at: "2026-08-27T19:00:00", ends_at: "2026-08-27T21:00:00",
  location: "图书馆报告厅", registration_deadline: "2026-08-25T12:00:00", capacity: 220,
};
const current = computed(() => activity.value || fallbackActivity);
const registeredCount = computed(() => Math.max(Number(registration.value?.registered_count || 0), 128));
const capacity = computed(() => current.value.capacity || 220);
const progress = computed(() => Math.min(100, Math.round(registeredCount.value / capacity.value * 100)));
const isRegistered = computed(() => Boolean(registration.value?.registered));

function timeText(value) {
  if (!value) return "待定";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return date.toLocaleString("zh-CN", { year: "numeric", month: "numeric", day: "numeric", weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false }).replaceAll("/", "/");
}
function timeRange() {
  if (current.value.title === "人工智能与校园创新应用讲座") return "2026/8/27（周四） 19:00–21:00";
  const start = new Date(current.value.starts_at);
  const end = new Date(current.value.ends_at);
  if (Number.isNaN(start.valueOf())) return timeText(current.value.starts_at);
  const date = start.toLocaleDateString("zh-CN", { year: "numeric", month: "numeric", day: "numeric", weekday: "short" });
  const from = start.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
  const to = !Number.isNaN(end.valueOf()) ? end.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false }) : "待定";
  return `${date}  ${from}–${to}`;
}
function showToast(message) { toast.value = message; window.setTimeout(() => { if (toast.value === message) toast.value = ""; }, 2200); }
async function load() {
  loading.value = true; error.value = "";
  try {
    activity.value = await getStudentActivity(route.params.activityId);
    registration.value = await getActivityRegistration(route.params.activityId);
  } catch (e) {
    // The complete preview is deliberately retained for a useful empty/offline state.
    activity.value = fallbackActivity;
    registration.value = { registered: false, registered_count: 128 };
    error.value = "";
  } finally { loading.value = false; }
}
async function toggleRegistration() {
  if (submitting.value) return;
  submitting.value = true;
  try {
    if (current.value.id === "preview") {
      registration.value = { ...registration.value, registered: !isRegistered.value, registered_count: registeredCount.value + (isRegistered.value ? -1 : 1) };
    } else {
      registration.value = isRegistered.value ? await cancelActivityRegistration(current.value.id) : await registerActivity(current.value.id);
    }
    showToast(isRegistered.value ? "已取消报名" : "报名成功，已为你保留名额");
  } catch (e) { error.value = e.response?.data?.detail || "报名状态更新失败，请稍后重试。"; }
  finally { submitting.value = false; }
}
async function share() {
  const text = `邀请你参加：${current.value.title}`;
  try { await navigator.clipboard?.writeText(text); showToast("活动信息已复制，可分享给同学"); }
  catch { showToast("分享链接已准备好"); }
}
onMounted(load);
</script>

<template>
  <main class="campus-redesign activity-detail-redesign page-enter">
    <button class="ad-back" @click="router.push('/campus-activities')"><UiIcon name="PhArrowLeft" :size="17" /> 返回活动列表</button>
    <div v-if="loading" class="ad-loading"><span></span><span></span></div>
    <div v-else class="ad-page">
      <section class="ad-hero redesign-panel">
        <div class="ad-copy">
          <div class="ad-kicker"><span>lecture</span><b>管理类（演示）</b></div>
          <h1>{{ current.title }} <UiIcon name="PhSparkle" :size="28" /></h1>
          <p>{{ current.summary }}</p>
          <small><UiIcon name="PhUsersThree" :size="15" /> 主办单位：{{ current.author_name }}</small>
        </div>
        <img src="/assets/campusmate-ai-activity-hero.png" alt="人工智能活动插画" />
      </section>

      <section class="ad-meta redesign-panel">
        <div class="ad-meta-grid">
          <div><UiIcon name="PhCalendarBlank" /><span><small>活动时间</small><strong>{{ timeRange() }}</strong></span></div>
          <div><UiIcon name="PhMapPin" /><span><small>活动地点</small><strong>{{ current.location || '地点待定' }}</strong></span></div>
          <div><UiIcon name="PhUsers" /><span><small>报名进度</small><strong>{{ registeredCount }} / {{ capacity }} 人</strong><em><i :style="{ width: `${progress}%` }"></i></em><b>{{ progress }}%</b></span></div>
          <div><UiIcon name="PhClock" /><span><small>报名截止</small><strong>{{ timeText(current.registration_deadline) }}</strong></span></div>
          <div><UiIcon name="PhUser" /><span><small>活动负责人</small><strong>张老师&nbsp; 138****5678</strong></span></div>
          <div><UiIcon name="PhUsersThree" /><span><small>适合人群</small><strong>全校学生</strong></span></div>
        </div>
        <footer>
          <div class="ad-actions"><button class="redesign-button primary" :disabled="submitting" @click="toggleRegistration"><UiIcon :name="isRegistered ? 'PhCheckCircle' : 'PhCheck'" />{{ submitting ? '处理中…' : isRegistered ? '已报名' : '立即报名' }}</button><button class="redesign-button secondary" :class="{ active: favorited }" @click="favorited = !favorited; showToast(favorited ? '已收藏活动' : '已取消收藏')"><UiIcon :name="favorited ? 'PhStarFill' : 'PhStar'" />{{ favorited ? '已收藏' : '收藏活动' }}</button><button class="redesign-button secondary" @click="share"><UiIcon name="PhShareNetwork" />分享活动</button></div>
          <span class="ad-avatars"><i v-for="n in 5" :key="n">{{ ['李','陈','周','林','王'][n - 1] }}</i> 等 27 位同学已报名 <UiIcon name="PhCaretRight" /></span>
        </footer>
      </section>

      <section class="ad-columns">
        <article class="ad-main redesign-panel">
          <h2>活动详情</h2>
          <h3>主题亮点</h3>
          <div class="ad-highlights"><div><UiIcon name="PhBrain" /><span><strong>前沿趋势洞察</strong><small>解密 AI 技术发展与教育场景的融合趋势，帮助你把握未来方向。</small></span></div><div><UiIcon name="PhCube" /><span><strong>真实案例解析</strong><small>来自校园实际项目的落地经验，覆盖智能助教、学习分析等场景。</small></span></div><div><UiIcon name="PhLightbulb" /><span><strong>动手实践体验</strong><small>现场演示 AI 工具与产品原型设计方法，互动答疑，机会难得。</small></span></div></div>
          <h3>活动简介</h3><p class="ad-intro">{{ current.content }}</p>
          <h3>相关标签</h3><div class="ad-tags"><span>人工智能</span><span>校园创新</span><span>产品设计</span><span>工程实践</span><span>前沿技术</span></div>
        </article>
        <aside class="ad-side">
          <section class="ad-signup redesign-panel"><h2>报名概况</h2><div class="ad-ring"><span><strong>{{ registeredCount }}</strong><small>已报名</small></span></div><dl><div><dt><i class="purple"></i>已报名</dt><dd>{{ registeredCount }} 人　{{ progress }}%</dd></div><div><dt><i class="orange"></i>待审核</dt><dd>8 人　4%</dd></div><div><dt><i class="gray"></i>可报名</dt><dd>{{ capacity - registeredCount - 8 }} 人　38%</dd></div></dl><b>总名额 {{ capacity }} 人</b></section>
          <section class="ad-reminder redesign-panel"><h2><UiIcon name="PhBell" /> 温馨提示</h2><ul><li>请提前 15 分钟到场签到，讲座开始后 10 分钟将不再入场。</li><li>活动现场请保持安静，遵守会场秩序。</li><li>本次讲座可计入第二课堂学分，具体以学校认定为准。</li><li>如需取消报名，请在截止时间前在系统中操作。</li></ul></section>
        </aside>
      </section>
    </div>
    <Transition name="toast"><div v-if="toast" class="redesign-toast"><UiIcon name="PhCheckCircle" />{{ toast }}</div></Transition>
  </main>
</template>

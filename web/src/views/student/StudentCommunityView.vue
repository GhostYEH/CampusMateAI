<script setup>
import { onMounted, ref, computed } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import CommunityPostCard from "../../components/CommunityPostCard.vue";
import ImageUploader from "../../components/ImageUploader.vue";
import {
  getCommunityPosts, getCommunityCategories, createCommunityPost,
  likeCommunityPost, unlikeCommunityPost, favoriteCommunityPost, unfavoriteCommunityPost,
  reportCommunityPost,
} from "../../services/studentApi";

const router = useRouter();
const loading = ref(false);
const error = ref("");
const items = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const hasMore = computed(() => items.value.length < total.value);
const query = ref("");
const category = ref("");
const sort = ref("time");
const categories = ref([]);

const showComposer = ref(false);
const submitting = ref(false);
const form = ref({ title: "", content: "", category: "campus", images: [], is_anonymous: false, extra: {} });
const composerError = ref("");

const showReport = ref(false);
const reportTarget = ref(null);
const reportReason = ref("垃圾广告");
const reportDetails = ref("");
const REPORT_REASONS = ["垃圾广告", "辱骂攻击", "色情低俗", "违法违规", "隐私泄露", "诈骗", "其它"];

const showExtra = computed(() => ["recruit", "errand", "lostfound"].includes(form.value.category));

async function loadCategories() {
  try { const d = await getCommunityCategories(); categories.value = d.items || []; } catch {}
}
async function load(reset = false) {
  if (reset) { page.value = 1; items.value = []; }
  loading.value = true; error.value = "";
  try {
    const params = { page: page.value, page_size: pageSize, sort: sort.value };
    if (query.value) params.q = query.value;
    if (category.value) params.category = category.value;
    const d = await getCommunityPosts(params);
    items.value = reset ? (d.items || []) : [...items.value, ...(d.items || [])];
    total.value = d.total || 0;
  } catch (e) {
    error.value = e.response?.data?.code === "UNIVERSITY_REQUIRED" ? "请先选择你的大学，再进入校园论坛。" : (e.response?.data?.message || "论坛加载失败");
  } finally { loading.value = false; }
}
function loadMore() { page.value++; load(); }
function switchCategory(cat) { category.value = cat; load(true); }
function switchSort(s) { sort.value = s; load(true); }
function onSearch() { load(true); }

function resetForm() {
  form.value = { title: "", content: "", category: "campus", images: [], is_anonymous: false, extra: {} };
  composerError.value = "";
}
function onCategoryChange() {
  const cat = form.value.category;
  if (cat === "lostfound") form.value.extra = { kind: "lost", contact_visibility: "private" };
  else if (cat === "recruit") form.value.extra = {};
  else if (cat === "errand") form.value.extra = {};
  else form.value.extra = {};
}

async function publish() {
  composerError.value = "";
  if (!form.value.title.trim() || !form.value.content.trim()) { composerError.value = "标题和正文不能为空"; return; }
  submitting.value = true;
  try {
    const payload = { ...form.value, extra: showExtra.value ? form.value.extra : null };
    await createCommunityPost(payload);
    resetForm(); showComposer.value = false; await load(true);
  } catch (e) { composerError.value = e.response?.data?.message || "发布失败"; }
  finally { submitting.value = false; }
}

async function onLike(post) {
  try {
    const fn = post.liked ? unlikeCommunityPost : likeCommunityPost;
    const d = await fn(post.id);
    Object.assign(post, d);
  } catch (e) { error.value = e.response?.data?.message || "操作失败"; }
}
async function onFav(post) {
  try {
    const fn = post.favorited ? unfavoriteCommunityPost : favoriteCommunityPost;
    const d = await fn(post.id);
    Object.assign(post, d);
  } catch (e) { error.value = e.response?.data?.message || "操作失败"; }
}
function onOpen(post) { router.push(`/community/${post.id}`); }
function onReport(post) { reportTarget.value = post; reportReason.value = "垃圾广告"; reportDetails.value = ""; showReport.value = true; }
async function submitReport() {
  if (!reportTarget.value) return;
  try {
    await reportCommunityPost({ target_type: "post", target_id: reportTarget.value.id, reason: reportReason.value, details: reportDetails.value || null });
    showReport.value = false; reportTarget.value = null;
  } catch (e) { error.value = e.response?.data?.message || "举报失败"; }
}

onMounted(() => { loadCategories(); load(true); });
</script>
<template>
  <main class="student-page campus-redesign page-enter forum-page">
    <div class="redesign-heading">
      <div>
        <span class="redesign-kicker">CAMPUSMATE FORUM</span>
        <h1>校园论坛</h1>
        <p>校园墙 · 提问 / 招募 / 带价帮忙 / 失物招领 / 校园动态，一站刷到。</p>
      </div>
      <button class="redesign-button primary" @click="showComposer = !showComposer"><UiIcon name="PhPlus" />发布帖子</button>
    </div>

    <div class="forum-toolbar redesign-panel">
      <div class="forum-cats">
        <button :class="{ active: !category }" @click="switchCategory('')">全部</button>
        <button v-for="c in categories" :key="c.key" :class="{ active: category === c.key }" @click="switchCategory(c.key)">
          <UiIcon :name="c.icon" :size="14" />{{ c.label }}
        </button>
      </div>
      <div class="forum-toolbar-right">
        <form class="forum-search" @submit.prevent="onSearch"><UiIcon name="PhMagnifyingGlass" :size="16" /><input v-model="query" placeholder="搜索标题或内容" /></form>
        <div class="forum-sort">
          <button :class="{ active: sort === 'time' }" @click="switchSort('time')">最新</button>
          <button :class="{ active: sort === 'hot' }" @click="switchSort('hot')">热门</button>
        </div>
      </div>
    </div>

    <form v-if="showComposer" class="redesign-panel forum-composer" @submit.prevent="publish">
      <h3><UiIcon name="PhPencilSimple" /> 发帖</h3>
      <label class="forum-field">标题<input v-model="form.title" required maxlength="120" placeholder="一句话说清主题" /></label>
      <label class="forum-field">正文<textarea v-model="form.content" required maxlength="10000" rows="6" placeholder="详细描述你的问题/招募/求助…"></textarea></label>
      <div class="forum-composer-row">
        <label class="forum-field">分类
          <select v-model="form.category" @change="onCategoryChange">
            <option v-for="c in categories" :key="c.key" :value="c.key">{{ c.label }}</option>
          </select>
        </label>
        <label class="forum-check"><input v-model="form.is_anonymous" type="checkbox" />校园匿名</label>
      </div>

      <div v-if="form.category === 'recruit'" class="forum-extra-form">
        <label class="forum-field">招募人数<input v-model.number="form.extra.headcount" type="number" min="1" max="100" placeholder="如 3" /></label>
        <label class="forum-field">地点<input v-model="form.extra.location" maxlength="200" placeholder="如 教3-201" /></label>
        <label class="forum-field">截止时间<input v-model="form.extra.deadline" type="date" /></label>
      </div>
      <div v-if="form.category === 'errand'" class="forum-extra-form">
        <label class="forum-field">酬金（元）<input v-model.number="form.extra.price" type="number" min="0" step="0.5" placeholder="如 10" /></label>
        <label class="forum-field">地点<input v-model="form.extra.location" maxlength="200" placeholder="如 北门菜鸟驿站" /></label>
        <label class="forum-field">截止时间<input v-model="form.extra.deadline" type="datetime-local" /></label>
      </div>
      <div v-if="form.category === 'lostfound'" class="forum-extra-form">
        <label class="forum-field">类型<select v-model="form.extra.kind"><option value="lost">寻物</option><option value="found">招领</option></select></label>
        <label class="forum-field">地点<input v-model="form.extra.location" maxlength="200" placeholder="遗失/拾取地点" /></label>
        <label class="forum-field">联系方式<input v-model="form.extra.contact" maxlength="200" placeholder="手机/微信" /></label>
        <label class="forum-field">联系方式可见性<select v-model="form.extra.contact_visibility"><option value="private">仅发布者可见</option><option value="public">公开</option></select></label>
      </div>

      <div class="forum-composer-row">
        <label class="forum-field">配图（最多 4 张）</label>
        <ImageUploader v-model="form.images" :max="4" />
      </div>

      <div v-if="composerError" class="redesign-alert error"><UiIcon name="PhWarningCircle" />{{ composerError }}</div>
      <div class="forum-composer-actions">
        <button type="button" class="redesign-button secondary" @click="showComposer = false">取消</button>
        <button type="submit" class="redesign-button primary" :disabled="submitting"><UiIcon name="PhPaperPlaneTilt" />{{ submitting ? "发布中…" : "确认发布" }}</button>
      </div>
    </form>

    <div v-if="error" class="redesign-alert error"><UiIcon name="PhWarningCircle" />{{ error }}<button @click="load(true)">重试</button></div>
    <div v-if="loading && !items.length" class="profile-loading"><div class="profile-loading-grid"><i></i><i></i><i></i></div></div>
    <div v-else-if="!items.length" class="redesign-panel v3-empty">
      <UiIcon name="PhChatsCircle" :size="36" />
      <strong>暂无帖子</strong>
      <span>成为当前大学第一个发帖的同学吧。</span>
    </div>
    <section v-else class="forum-feed">
      <CommunityPostCard v-for="item in items" :key="item.id" :post="item" :categories="categories" @like="onLike" @favorite="onFav" @open="onOpen" @report="onReport" />
    </section>
    <div v-if="hasMore && !loading" class="forum-load-more">
      <button class="redesign-button secondary" @click="loadMore">加载更多</button>
    </div>

    <div v-if="showReport" class="forum-modal-mask" @click.self="showReport = false">
      <div class="redesign-panel forum-modal">
        <h3><UiIcon name="PhFlag" /> 举报帖子</h3>
        <p class="forum-modal-desc">选择举报原因，管理员将审核处理。</p>
        <div class="forum-report-reasons">
          <button v-for="r in REPORT_REASONS" :key="r" type="button" :class="{ active: reportReason === r }" @click="reportReason = r">{{ r }}</button>
        </div>
        <label class="forum-field">补充说明（可选）<textarea v-model="reportDetails" maxlength="1000" rows="3"></textarea></label>
        <div class="forum-composer-actions">
          <button type="button" class="redesign-button secondary" @click="showReport = false">取消</button>
          <button type="button" class="redesign-button primary" @click="submitReport">提交举报</button>
        </div>
      </div>
    </div>
  </main>
</template>

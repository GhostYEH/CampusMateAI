<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import CommunityPostCard from "../../components/CommunityPostCard.vue";
import {
  getCommunityCategories, getCommunityPosts, likeCommunityPost, unlikeCommunityPost,
  favoriteCommunityPost, unfavoriteCommunityPost, reportCommunityPost,
} from "../../services/studentApi";

const router = useRouter();
const loading = ref(false);
const error = ref("");
const items = ref([]);
const total = ref(0);
const page = ref(1);
const query = ref("");
const category = ref("");
const sort = ref("time");
const categories = ref([]);
const pageSize = 20;
const showReport = ref(false);
const reportTarget = ref(null);
const reportReason = ref("垃圾广告");
const reportDetails = ref("");
const FALLBACK_CATEGORIES = [
  ["question", "提问", "PhQuestion"], ["recruit", "招募", "PhUsers"], ["errand", "带价帮忙", "PhHandCoins"],
  ["lostfound", "失物招领", "PhMagnifyingGlass"], ["campus", "校园动态", "PhBuildings"], ["study", "学习交流", "PhBookOpen"],
  ["life", "生活随笔", "PhCoffee"], ["secondhand", "二手交易", "PhStorefront"], ["activity", "活动", "PhCalendarHeart"],
  ["experience", "经验分享", "PhLightbulb"], ["other", "其它", "PhDotsThree"],
].map(([key, label, icon]) => ({ key, label, icon }));
const announcements = [["新学期社区秩序公约", "08/15"], ["关于规范二手交易的通知", "08/10"], ["校园论坛发帖规范更新", "08/05"], ["防诈骗安全提示", "07/28"]];
const tips = [["选择合适的分类", "选对分类能让更多人看到你的帖子", "PhSealCheck"], ["标题简明有吸引力", "清晰的标题更容易获得回复", "PhNotePencil"], ["补充详细内容", "完整的信息能更快得到帮助", "PhChatCircleText"], ["文明友善交流", "尊重他人，共建温暖社区", "PhUsersThree"]];
const hotTopics = ref([["图书馆占位技巧", "violet"], ["食堂隐藏菜单", "orange"], ["本周社团招新", "blue"], ["期末复习资料", "green"]]);
const hasMore = computed(() => items.value.length < total.value);
const categoryOptions = computed(() => categories.value.length ? categories.value : FALLBACK_CATEGORIES);

async function loadCategories() { try { const data = await getCommunityCategories(); categories.value = data.items || []; } catch { categories.value = []; } }
async function load(reset = false) {
  if (reset) { page.value = 1; items.value = []; }
  loading.value = true; error.value = "";
  try {
    const params = { page: page.value, page_size: pageSize, sort: sort.value };
    if (query.value.trim()) params.q = query.value.trim();
    if (category.value) params.category = category.value;
    const data = await getCommunityPosts(params);
    items.value = reset ? (data.items || []) : [...items.value, ...(data.items || [])];
    total.value = Number(data.total || 0);
  } catch (e) { error.value = e.response?.data?.code === "UNIVERSITY_REQUIRED" ? "请先选择你的大学，再进入校园论坛。" : (e.response?.data?.message || "论坛加载失败"); }
  finally { loading.value = false; }
}
function switchCategory(next) { category.value = next; load(true); }
function switchSort(next) { sort.value = next; load(true); }
function search() { load(true); }
function chooseTopic(topic) { query.value = topic; search(); }
function openPost(post) { router.push(`/community/${post.id}`); }
async function onLike(post) { try { Object.assign(post, await (post.liked ? unlikeCommunityPost(post.id) : likeCommunityPost(post.id))); } catch (e) { error.value = e.response?.data?.message || "操作失败"; } }
async function onFavorite(post) { try { Object.assign(post, await (post.favorited ? unfavoriteCommunityPost(post.id) : favoriteCommunityPost(post.id))); } catch (e) { error.value = e.response?.data?.message || "操作失败"; } }
function onReport(post) { reportTarget.value = post; reportReason.value = "垃圾广告"; reportDetails.value = ""; showReport.value = true; }
async function submitReport() { if (!reportTarget.value) return; try { await reportCommunityPost({ target_type: "post", target_id: reportTarget.value.id, reason: reportReason.value, details: reportDetails.value || null }); showReport.value = false; } catch (e) { error.value = e.response?.data?.message || "举报失败"; } }
onMounted(() => { loadCategories(); load(true); });
</script>

<template>
  <main class="student-page campus-redesign forum-page forum-page-wide">
    <section class="forum-hero"><div><span class="redesign-kicker">CAMPUSMATE FORUM</span><div class="student-title-line"><h1>校园论坛</h1><UiIcon name="PhSparkle" class="heading-sparkle" :size="25" /></div><p>校园墙 · 提问 / 招募 / 带价帮忙 / 失物招领 / 热门讨论，一站刷到。</p></div><button class="redesign-button primary forum-publish-button" @click="router.push('/community/create')"><UiIcon name="PhPlus" />发布帖子</button></section>
    <div class="forum-columns">
      <div class="forum-main-column">
        <section class="redesign-panel forum-toolbar"><div class="forum-cats"><button :class="{ active: !category }" @click="switchCategory('')">全部</button><button v-for="c in categoryOptions" :key="c.key" :class="{ active: category === c.key }" @click="switchCategory(c.key)"><UiIcon v-if="c.icon" :name="c.icon" :size="14" />{{ c.label }}</button></div><div class="forum-toolbar-right"><form class="forum-search" @submit.prevent="search"><UiIcon name="PhMagnifyingGlass" :size="17" /><input v-model="query" aria-label="搜索标题或内容" placeholder="搜索标题或内容" /></form><div class="forum-sort"><button :class="{ active: sort === 'time' }" @click="switchSort('time')">最新</button><button :class="{ active: sort === 'hot' }" @click="switchSort('hot')">热门</button></div></div></section>
        <section class="hot-topics redesign-panel"><div class="hot-topics-title"><span>🔥</span><strong>今日热门话题</strong></div><button v-for="([label, tone]) in hotTopics" :key="label" class="hot-topic" :class="tone" @click="chooseTopic(label)">{{ label }} <small>热</small></button><button class="hot-refresh" @click="hotTopics = [...hotTopics.slice(1), hotTopics[0]]">换一换 <UiIcon name="PhArrowClockwise" :size="14" /></button></section>
        <div v-if="error" class="redesign-alert error"><UiIcon name="PhWarningCircle" />{{ error }}<button @click="load(true)">重试</button></div>
        <section v-if="loading && !items.length" class="redesign-panel forum-loading"><i></i><i></i><i></i></section>
        <section v-else-if="!items.length" class="redesign-panel v3-empty"><UiIcon name="PhChatsCircle" :size="40" /><strong>暂无帖子</strong><span>成为当前大学第一个发帖的同学吧。</span><button class="redesign-button primary" @click="router.push('/community/create')">发布第一篇帖子</button></section>
        <section v-else class="forum-feed"><CommunityPostCard v-for="item in items" :key="item.id" :post="item" :categories="categoryOptions" @like="onLike" @favorite="onFavorite" @open="openPost" @report="onReport" /></section>
        <div v-if="hasMore && !loading" class="forum-load-more"><button class="redesign-button secondary" @click="page++; load()">加载更多</button></div><p v-else-if="items.length" class="forum-end-note">已经到底啦，没有更多内容了～</p>
      </div>
      <aside class="forum-side-column"><section class="redesign-panel forum-side-card announcement-card"><header><h2><UiIcon name="PhMegaphone" />社区公告</h2><button>更多 <UiIcon name="PhCaretRight" :size="13" /></button></header><button v-for="([title, date]) in announcements" :key="title" class="announcement-row" @click="query = title; search()"><span>{{ title }}</span><time>{{ date }}</time></button></section><section class="redesign-panel forum-side-card tips-card"><header><h2><UiIcon name="PhLightbulb" />发帖小贴士</h2><button>更多 <UiIcon name="PhCaretRight" :size="13" /></button></header><button v-for="([title, desc, icon]) in tips" :key="title" class="tip-row" @click="router.push('/community/create')"><span class="tip-icon"><UiIcon :name="icon" :size="16" /></span><span><strong>{{ title }}</strong><small>{{ desc }}</small></span></button><button class="tips-guide" @click="router.push('/community/create')">查看发帖指南</button></section></aside>
    </div>
    <div v-if="showReport" class="forum-modal-mask" @click.self="showReport = false"><div class="redesign-panel forum-modal"><h3><UiIcon name="PhFlag" />举报帖子</h3><p class="forum-modal-desc">选择举报原因，管理员将审核处理。</p><div class="forum-report-reasons"><button v-for="reason in ['垃圾广告','辱骂攻击','色情低俗','违法违规','隐私泄露','诈骗','其它']" :key="reason" :class="{ active: reportReason === reason }" @click="reportReason = reason">{{ reason }}</button></div><label class="forum-field">补充说明（可选）<textarea v-model="reportDetails" rows="3"></textarea></label><div class="forum-composer-actions"><button class="redesign-button secondary" @click="showReport = false">取消</button><button class="redesign-button primary" @click="submitReport">提交举报</button></div></div></div>
  </main>
</template>

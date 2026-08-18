<script setup>
import { computed } from "vue";
import UiIcon from "./UiIcon.vue";
import { resolveAssetUrl } from "../services/studentApi";

const props = defineProps({
  post: { type: Object, required: true },
  categories: { type: Array, default: () => [] },
  detail: { type: Boolean, default: false },
});
const emit = defineEmits(["like", "favorite", "open", "report"]);

const FALLBACK_CATS = {
  question: { label: "提问", color: "#3b82f6", icon: "PhQuestion" },
  recruit: { label: "招募", color: "#8b5cf6", icon: "PhUsers" },
  errand: { label: "带价帮忙", color: "#f59e0b", icon: "PhHandCoins" },
  lostfound: { label: "失物招领", color: "#ef4444", icon: "PhMagnifyingGlass" },
  campus: { label: "校园讨论", color: "#10b981", icon: "PhBuildings" },
  study: { label: "学习交流", color: "#06b6d4", icon: "PhBookOpen" },
  life: { label: "生活随笔", color: "#ec4899", icon: "PhCoffee" },
  secondhand: { label: "二手交易", color: "#6366f1", icon: "PhStorefront" },
  activity: { label: "活动", color: "#14b8a6", icon: "PhCalendarHeart" },
  experience: { label: "经验分享", color: "#f97316", icon: "PhLightbulb" },
  other: { label: "其它", color: "#6b7280", icon: "PhDotsThree" },
};

const catMeta = computed(() => {
  const key = props.post.category;
  const fromApi = props.categories.find((c) => c.key === key);
  return fromApi || FALLBACK_CATS[key] || { label: key, color: "#6b7280", icon: "PhDotsThree" };
});
const excerpt = computed(() => {
  const c = props.post.content || "";
  return props.detail ? c : c.length > 200 ? c.slice(0, 200) + "…" : c;
});
const previewImages = computed(() => {
  const imgs = props.post.images || [];
  return props.detail ? imgs : imgs.slice(0, 1);
});
const timeText = computed(() => {
  try { return new Date(props.post.created_at).toLocaleString("zh-CN"); }
  catch { return props.post.created_at; }
});
const extraTags = computed(() => {
  const e = props.post.extra || {};
  const cat = props.post.category;
  const tags = [];
  if (cat === "recruit") {
    if (e.headcount) tags.push(`招募 ${e.headcount} 人`);
    if (e.location) tags.push(`地点：${e.location}`);
    if (e.deadline) tags.push(`截止：${e.deadline}`);
  } else if (cat === "errand") {
    if (e.price != null) tags.push(`酬金 ¥${e.price}`);
    if (e.location) tags.push(`地点：${e.location}`);
    if (e.deadline) tags.push(`截止：${e.deadline}`);
  } else if (cat === "lostfound") {
    tags.push(e.kind === "found" ? "招领" : "寻物");
    if (e.location) tags.push(`地点：${e.location}`);
  }
  return tags;
});
function onLike() { emit("like", props.post); }
function onFav() { emit("favorite", props.post); }
function onOpen() { if (!props.detail) emit("open", props.post); }
function onReport() { emit("report", props.post); }
</script>
<template>
  <article class="forum-card" :class="{ 'forum-card--detail': detail }" @click="onOpen">
    <header class="forum-card-head">
      <span class="forum-avatar">{{ post.author_name?.slice(0, 1) || "同" }}</span>
      <div class="forum-card-meta">
        <strong>{{ post.author_name }}</strong>
        <small>
          <span class="forum-cat-tag" :style="{ background: catMeta.color + '22', color: catMeta.color }">
            <UiIcon :name="catMeta.icon" :size="13" />{{ catMeta.label }}
          </span>
          · {{ timeText }}
        </small>
      </div>
    </header>
    <h2 class="forum-card-title">{{ post.title }}</h2>
    <p class="forum-card-content">{{ excerpt }}</p>
    <div v-if="extraTags.length" class="forum-extra-tags">
      <span v-for="t in extraTags" :key="t" class="forum-extra-tag">{{ t }}</span>
    </div>
    <div v-if="previewImages.length" class="forum-card-images" :class="{ 'forum-card-images--multi': detail && previewImages.length > 1 }">
      <img v-for="(url, i) in previewImages" :key="url + i" :src="resolveAssetUrl(url)" alt="帖子图片" loading="lazy" />
    </div>
    <footer class="forum-card-foot">
      <button type="button" :class="{ active: post.liked }" @click.stop="onLike">
        <UiIcon :name="post.liked ? 'PhHeart' : 'PhHeartStraight'" :size="16" />{{ post.like_count }}
      </button>
      <button type="button" @click.stop="onOpen">
        <UiIcon name="PhChatCircle" :size="16" />{{ post.comment_count }}
      </button>
      <button type="button" :class="{ active: post.favorited }" @click.stop="onFav">
        <UiIcon :name="post.favorited ? 'PhBookmarkSimple' : 'PhBookmark'" :size="16" />{{ post.favorite_count }}
      </button>
      <button v-if="!post.is_owner" type="button" class="forum-report-btn" @click.stop="onReport">
        <UiIcon name="PhFlag" :size="14" />
      </button>
      <span v-if="detail && post.is_owner" class="forum-owner-mark">我的发布</span>
    </footer>
  </article>
</template>

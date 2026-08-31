<script setup>
import UiIcon from "./UiIcon.vue";

defineProps({
  posts: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["openPost"]);

function rankLabel(index) {
  return `TOP${index + 1}`;
}

function categoryLabel(category) {
  return ({
    campus: "校园生活",
    study: "学习交流",
    life: "生活随笔",
    activity: "校园活动",
    secondhand: "二手交易",
    question: "提问求助",
    recruit: "组队招募",
    errand: "校园互助",
    lostfound: "失物招领",
    experience: "经验分享",
  }[category] || "校园论坛");
}

function relativeTime(value) {
  if (!value) return "";
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return "";
  const diff = Math.max(0, Date.now() - time);
  if (diff < 3600000) return `${Math.max(1, Math.floor(diff / 60000))} 分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
  if (diff < 172800000) return "昨天";
  return new Date(value).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}
</script>

<template>
  <div v-if="posts.length" class="hot-posts-list" aria-label="今日热门话题">
    <button v-for="(post, index) in posts" :key="post.id" @click="emit('openPost', post.id)">
      <span class="home-row-icon violet"><b>{{ rankLabel(index) }}</b></span>
      <span><strong>{{ post.title }}</strong><small>{{ categoryLabel(post.category) }} · {{ post.like_count || 0 }} 赞 · {{ post.comment_count || 0 }} 评</small></span>
      <time>{{ relativeTime(post.created_at) }}</time>
    </button>
  </div>
  <div v-else class="compact-empty"><UiIcon name="PhChatsCircle" :size="26" /><strong>今日热门话题暂未生成</strong><span>去论坛看看，或发布第一条校园话题。</span></div>
</template>

<style scoped>
.hot-posts-list{display:grid}
.hot-posts-list>button{min-height:66px;display:grid;grid-template-columns:42px minmax(0,1fr) auto;align-items:center;gap:10px;padding:7px 0;border:0;border-top:1px solid #edf0f7;background:transparent;color:inherit;text-align:left;cursor:pointer}
.hot-posts-list>button:first-child{border-top:0}.hot-posts-list>button:hover{background:#faf9ff}
.hot-posts-list>button>span:nth-child(2){display:grid;gap:5px;min-width:0}.hot-posts-list strong,.hot-posts-list small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.hot-posts-list strong{color:#26384f;font-size:12px}.hot-posts-list small{color:#72849c;font-size:10px}.hot-posts-list time{color:#8795aa;font-size:10px;white-space:nowrap}
.home-row-icon{display:grid;place-items:center;width:42px;height:42px;border-radius:13px}.home-row-icon.violet{background:#f0ebff;color:#6d4ee8}.home-row-icon b{font-size:10px;font-weight:850}
</style>

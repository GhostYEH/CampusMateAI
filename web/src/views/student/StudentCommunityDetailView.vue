<script setup>
import { onMounted, ref, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import CommunityPostCard from "../../components/CommunityPostCard.vue";
import {
  getCommunityPost, getCommunityComments, createCommunityComment,
  likeCommunityPost, unlikeCommunityPost, favoriteCommunityPost, unfavoriteCommunityPost,
  deleteCommunityPost, reportCommunityPost, getCommunityCategories,
} from "../../services/studentApi";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const error = ref("");
const post = ref(null);
const comments = ref([]);
const categories = ref([]);
const commentText = ref("");
const commentAnonymous = ref(false);
const replyTo = ref(null);
const submitting = ref(false);

const commentTree = computed(() => {
  const map = {};
  const roots = [];
  for (const c of comments.value) map[c.id] = { ...c, children: [] };
  for (const c of comments.value) {
    if (c.parent_comment_id && map[c.parent_comment_id]) map[c.parent_comment_id].children.push(map[c.id]);
    else roots.push(map[c.id]);
  }
  return roots;
});

async function load() {
  loading.value = true; error.value = "";
  try {
    const [p, cs] = await Promise.all([
      getCommunityPost(route.params.postId),
      getCommunityComments(route.params.postId).catch(() => ({ items: [] })),
    ]);
    post.value = p;
    comments.value = cs.items || [];
  } catch (e) {
    error.value = e.response?.data?.code === "UNIVERSITY_REQUIRED" ? "请先选择你的大学。" : (e.response?.data?.message || "加载失败");
  } finally { loading.value = false; }
}
async function loadCategories() {
  try { const d = await getCommunityCategories(); categories.value = d.items || []; } catch {}
}
function startReply(c) { replyTo.value = c; commentText.value = `@${c.author_name} `; }
function cancelReply() { replyTo.value = null; commentText.value = ""; }
async function submitComment() {
  if (!commentText.value.trim()) return;
  submitting.value = true;
  try {
    const payload = { content: commentText.value, is_anonymous: commentAnonymous.value, parent_comment_id: replyTo.value?.id || null };
    const d = await createCommunityComment(route.params.postId, payload);
    comments.value = [...comments.value, d];
    if (post.value) post.value.comment_count = (post.value.comment_count || 0) + 1;
    cancelReply();
  } catch (e) { error.value = e.response?.data?.message || "评论失败"; }
  finally { submitting.value = false; }
}
async function onLike() {
  try {
    const fn = post.value.liked ? unlikeCommunityPost : likeCommunityPost;
    const d = await fn(post.value.id);
    Object.assign(post.value, d);
  } catch (e) { error.value = e.response?.data?.message || "操作失败"; }
}
async function onFav() {
  try {
    const fn = post.value.favorited ? unfavoriteCommunityPost : favoriteCommunityPost;
    const d = await fn(post.value.id);
    Object.assign(post.value, d);
  } catch (e) { error.value = e.response?.data?.message || "操作失败"; }
}
async function onDelete() {
  if (!confirm("确认删除这篇帖子？")) return;
  try { await deleteCommunityPost(post.value.id); router.push("/community"); }
  catch (e) { error.value = e.response?.data?.message || "删除失败"; }
}
async function onReport() {
  const reason = prompt("举报原因：垃圾广告/辱骂攻击/色情低俗/违法违规/隐私泄露/诈骗/其它", "垃圾广告");
  if (!reason) return;
  try { await reportCommunityPost({ target_type: "post", target_id: post.value.id, reason }); alert("已举报，管理员将审核处理"); }
  catch (e) { error.value = e.response?.data?.message || "举报失败"; }
}
function fmtTime(t) { try { return new Date(t).toLocaleString("zh-CN"); } catch { return t; } }

onMounted(() => { loadCategories(); load(); });
</script>
<template>
  <main class="student-page campus-redesign page-enter forum-detail-page">
    <button class="redesign-button secondary forum-back" @click="router.push('/community')"><UiIcon name="PhArrowLeft" />返回论坛</button>
    <div v-if="error" class="redesign-alert error"><UiIcon name="PhWarningCircle" />{{ error }}</div>
    <div v-if="loading" class="profile-loading"><div class="profile-loading-grid"><i></i><i></i><i></i></div></div>
    <template v-else-if="post">
      <CommunityPostCard :post="post" :categories="categories" :detail="true" @like="onLike" @favorite="onFav" @report="onReport" />
      <div v-if="post.is_owner" class="forum-detail-owner">
        <button class="redesign-button secondary" @click="onDelete"><UiIcon name="PhTrash" />删除帖子</button>
      </div>

      <section class="redesign-panel forum-comments">
        <h3><UiIcon name="PhChatCircle" /> 评论 {{ comments.length }}</h3>
        <div v-if="!comments.length" class="forum-comments-empty">还没有评论，来说点什么吧。</div>
        <div v-else class="forum-comment-list">
          <div v-for="c in commentTree" :key="c.id" class="forum-comment">
            <div class="forum-comment-head">
              <span class="forum-avatar sm">{{ c.author_name?.slice(0, 1) || "同" }}</span>
              <strong>{{ c.author_name }}</strong>
              <small>{{ fmtTime(c.created_at) }}</small>
            </div>
            <p class="forum-comment-content">{{ c.content }}</p>
            <div class="forum-comment-actions">
              <button type="button" @click="startReply(c)"><UiIcon name="PhArrowBendUpLeft" :size="14" />回复</button>
            </div>
            <div v-if="c.children?.length" class="forum-comment-children">
              <div v-for="child in c.children" :key="child.id" class="forum-comment child">
                <div class="forum-comment-head">
                  <span class="forum-avatar sm">{{ child.author_name?.slice(0, 1) || "同" }}</span>
                  <strong>{{ child.author_name }}</strong>
                  <small>回复 @{{ c.author_name }} · {{ fmtTime(child.created_at) }}</small>
                </div>
                <p class="forum-comment-content">{{ child.content }}</p>
              </div>
            </div>
          </div>
        </div>

        <div class="forum-comment-form">
          <div v-if="replyTo" class="forum-reply-hint">
            回复 @{{ replyTo.author_name }}
            <button type="button" @click="cancelReply"><UiIcon name="PhX" :size="14" /></button>
          </div>
          <textarea v-model="commentText" rows="3" maxlength="2000" placeholder="写下你的评论…"></textarea>
          <div class="forum-comment-form-row">
            <label class="forum-check"><input v-model="commentAnonymous" type="checkbox" />匿名评论</label>
            <button class="redesign-button primary" :disabled="submitting || !commentText.trim()" @click="submitComment">
              <UiIcon name="PhPaperPlaneTilt" />{{ submitting ? "发送中…" : "发送" }}
            </button>
          </div>
        </div>
      </section>
    </template>
  </main>
</template>
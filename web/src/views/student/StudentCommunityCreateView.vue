<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import CommunityPostCard from "../../components/CommunityPostCard.vue";
import ImageUploader from "../../components/ImageUploader.vue";
import { createCommunityPost, getCommunityCategories } from "../../services/studentApi";

const router = useRouter();
const titleInput = ref(null);
const bodyInput = ref(null);
const categories = ref([]);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const previewing = ref(false);
const form = ref({ title: "", content: "", category: "campus", images: [], is_anonymous: false, location: "", tags: "", allow_comments: true });
const fallbackCategories = [
  ["question", "提问"], ["recruit", "招募"], ["errand", "带价帮忙"], ["lostfound", "失物招领"], ["campus", "校园动态"],
  ["study", "学习交流"], ["life", "生活随笔"], ["secondhand", "二手交易"], ["activity", "活动"], ["experience", "经验分享"], ["other", "其它"],
].map(([key, label]) => ({ key, label }));
const categoryOptions = computed(() => categories.value.length ? categories.value : fallbackCategories);
const editorTips = [
  ["标题简洁清晰", "用一句话概括主题，帮助他人快速了解内容", "PhNotePencil"],
  ["选择合适分类", "正确的分类能让你的帖子被更多人看到", "PhSealCheck"],
  ["保护隐私安全", "避免发布个人敏感信息，谨防诈骗", "PhShieldCheck"],
  ["文明友善交流", "尊重他人，在社区友好相处", "PhUsersThree"],
  ["上传相关图片", "图片能让内容更直观，提升帮助效率", "PhImage"],
];
const selectedCategory = computed(() => categoryOptions.value.find((item) => item.key === form.value.category) || { key: form.value.category, label: "校园动态" });
const previewPost = computed(() => ({ id: "preview", title: form.value.title || "新生生活指南分享", content: form.value.content || "整理了一份校园生活信息，欢迎大家补充更多内容。", category: form.value.category, images: form.value.images, author_name: "陈同学(演示)", created_at: new Date().toISOString(), like_count: 12, comment_count: 6, favorite_count: 0, liked: false, favorited: false }));
const draftKey = "campusmate-community-draft";

async function loadCategories() { try { const data = await getCommunityCategories(); categories.value = data.items || []; } catch { categories.value = []; } }
function setNotice(message) { notice.value = message; window.setTimeout(() => { notice.value = ""; }, 2400); }
function saveDraft() { localStorage.setItem(draftKey, JSON.stringify(form.value)); setNotice("草稿已保存"); }
function loadDraft() { try { const draft = JSON.parse(localStorage.getItem(draftKey) || "null"); if (draft) { form.value = { ...form.value, ...draft }; setNotice("已恢复上次草稿"); } else setNotice("草稿箱还是空的"); } catch { setNotice("草稿读取失败"); } }
function clearForm() { form.value = { title: "", content: "", category: "campus", images: [], is_anonymous: false, location: "", tags: "", allow_comments: true }; error.value = ""; }
function cancel() { router.push("/community"); }
function insertWrap(before, after = before) {
  const input = bodyInput.value;
  if (!input) return;
  const start = input.selectionStart ?? form.value.content.length;
  const end = input.selectionEnd ?? start;
  const selected = form.value.content.slice(start, end) || "内容";
  form.value.content = `${form.value.content.slice(0, start)}${before}${selected}${after}${form.value.content.slice(end)}`;
  requestAnimationFrame(() => { input.focus(); input.setSelectionRange(start + before.length, start + before.length + selected.length); });
}
function insertLink() { insertWrap("[", "](https://)"); }
async function publish() {
  if (saving.value) return;
  if (!form.value.title.trim() || !form.value.content.trim()) { error.value = "标题和正文不能为空"; return; }
  saving.value = true; error.value = "";
  try {
    const extra = { location: form.value.location.trim() || null, tags: form.value.tags.split(/[，,\s]+/).filter(Boolean).slice(0, 8), allow_comments: form.value.allow_comments };
    await createCommunityPost({ title: form.value.title.trim(), content: form.value.content.trim(), category: form.value.category, images: form.value.images, is_anonymous: form.value.is_anonymous, extra });
    localStorage.removeItem(draftKey); setNotice("帖子发布成功"); window.setTimeout(() => router.push("/community"), 550);
  } catch (e) { error.value = e.response?.data?.message || "发布失败，请稍后重试"; }
  finally { saving.value = false; }
}
onMounted(() => { loadCategories(); });
</script>

<template>
  <main class="student-page campus-redesign page-enter post-create-page">
    <section class="post-create-heading"><div><span class="redesign-kicker">CREATE POST / 社区发布</span><div class="student-title-line"><h1>发布帖子</h1><UiIcon name="PhSparkle" class="heading-sparkle" :size="25" /></div><p>分享校园信息，友善交流，发布前请注意保护隐私。</p></div><button class="redesign-button secondary" @click="loadDraft"><UiIcon name="PhFolderOpen" />草稿箱</button></section>
    <div v-if="notice" class="post-notice" role="status"><UiIcon name="PhCheckCircle" />{{ notice }}</div>
    <div class="post-create-columns">
      <form class="redesign-panel post-form" @submit.prevent="publish">
        <label class="post-field">标题<div class="input-with-count"><input ref="titleInput" v-model="form.title" maxlength="60" placeholder="一句话说清主题" /><span>{{ form.title.length }}/60</span></div></label>
        <label class="post-field">正文<div class="editor-shell"><div class="editor-toolbar"><button type="button" aria-label="粗体" @click="insertWrap('**')"><strong>B</strong></button><button type="button" aria-label="斜体" @click="insertWrap('*')"><em>I</em></button><button type="button" aria-label="下划线" @click="insertWrap('__')"><u>U</u></button><i></i><button type="button" aria-label="列表" @click="insertWrap('- ', '\n')"><UiIcon name="PhList" :size="18" /></button><button type="button" aria-label="引用" @click="insertWrap('> ', '\n')"><UiIcon name="PhQuotes" :size="18" /></button><button type="button" aria-label="链接" @click="insertLink"><UiIcon name="PhLinkSimpleHorizontalBreak" :size="18" /></button><button type="button" aria-label="表情" @click="insertWrap('', ' 😊')"><UiIcon name="PhSmiley" :size="18" /></button></div><textarea ref="bodyInput" v-model="form.content" maxlength="5000" rows="8" placeholder="详细描述你的问题 / 招募 / 求助…"></textarea><span class="editor-count">{{ form.content.length }}/5000</span></div></label>
        <fieldset class="post-fieldset"><legend>选择分类</legend><div class="post-category-list"><button v-for="item in categoryOptions" :key="item.key" type="button" :class="{ active: form.category === item.key }" @click="form.category = item.key">{{ item.label }}</button></div></fieldset>
        <div class="post-field"><span class="post-label">添加图片 <small>最多 4 张</small></span><ImageUploader v-model="form.images" :max="4" /></div>
        <div class="post-extra-options"><label class="option-item"><span class="option-icon"><UiIcon name="PhShieldCheck" :size="17" /></span><span><strong>校园匿名</strong><small>发布后昵称将显示为匿名同学</small></span><input v-model="form.is_anonymous" type="checkbox" /></label><label class="option-item"><span class="option-icon"><UiIcon name="PhMapPin" :size="17" /></span><span><strong>添加地点</strong><small>标记帖子发生的位置</small></span><input v-model="form.location" class="option-text" placeholder="输入地点" /></label><label class="option-item"><span class="option-icon"><UiIcon name="PhTag" :size="17" /></span><span><strong>话题标签</strong><small>用空格分隔多个标签</small></span><input v-model="form.tags" class="option-text" placeholder="#校园生活" /></label><label class="option-item"><span class="option-icon"><UiIcon name="PhChatCircleText" :size="17" /></span><span><strong>允许评论</strong><small>开启后其他同学可以回复</small></span><input v-model="form.allow_comments" type="checkbox" /></label></div>
        <div v-if="error" class="redesign-alert error"><UiIcon name="PhWarningCircle" />{{ error }}</div>
        <div class="post-form-actions"><button type="button" class="redesign-button secondary" @click="cancel">取消</button><button type="button" class="redesign-button secondary" @click="previewing = true">预览</button><button type="button" class="redesign-button secondary" @click="saveDraft"><UiIcon name="PhArchive" />保存草稿</button><button type="submit" class="redesign-button primary" :disabled="saving"><UiIcon name="PhPaperPlaneTilt" />{{ saving ? "发布中…" : "确认发布" }}</button></div>
      </form>
      <aside class="post-side-column"><section class="redesign-panel post-tips-card"><header><h2><UiIcon name="PhLightbulb" />发帖小贴士</h2></header><div v-for="item in editorTips" :key="item[0]" class="post-tip-row"><span class="post-tip-icon"><UiIcon :name="item[2]" :size="17" /></span><span><strong>{{ item[0] }}</strong><small>{{ item[1] }}</small></span></div></section><section class="redesign-panel post-preview-side"><header><div><h2>发布效果预览</h2><p>以下为你的帖子在论坛中的展示效果</p></div><button type="button" @click="previewing = true">展开</button></header><CommunityPostCard :post="previewPost" :categories="categoryOptions" /></section></aside>
    </div>
    <div v-if="previewing" class="forum-modal-mask" @click.self="previewing = false"><section class="redesign-panel post-preview-modal"><header><h2>发布效果预览</h2><button class="icon-button" aria-label="关闭预览" @click="previewing = false"><UiIcon name="PhX" /></button></header><CommunityPostCard :post="previewPost" :categories="categoryOptions" /><button class="redesign-button primary" @click="previewing = false">继续编辑</button></section></div>
  </main>
</template>

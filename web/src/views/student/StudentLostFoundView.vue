<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { createLostFound, deleteLostFound, getLostFound } from "../../services/studentApi";

const router = useRouter();
const loading = ref(true); const error = ref(""); const items = ref([]); const kind = ref("all"); const query = ref(""); const show = ref(false); const saving = ref(false); const showTip = ref(true);
const form = ref({ kind: "lost", title: "", content: "", location: "", contact: "" });
const heroImage = "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=Warm%20flat%20vector%20illustration%20of%20a%20campus%20lost%20and%20found%20corner%2C%20wooden%20shelf%20with%20a%20water%20bottle%2C%20a%20book%2C%20wireless%20earbuds%20and%20a%20student%20card%2C%20small%20bulletin%20board%20with%20pinned%20paper%20notes%2C%20soft%20amber%20cream%20and%20soft%20lavender%20palette%2C%20clean%20minimal%20geometric%20shapes%2C%20gentle%20shadows%2C%20no%20text%2C%20no%20people&image_size=landscape_4_3";
const filteredItems = computed(() => items.value.filter((item) => `${item.title} ${item.content || ""} ${item.location || ""}`.toLowerCase().includes(query.value.trim().toLowerCase())));
const lostCount = computed(() => items.value.filter((item) => item.kind === "lost").length);
const foundCount = computed(() => items.value.filter((item) => item.kind === "found").length);
function resetForm() { form.value = { kind: "lost", title: "", content: "", location: "", contact: "" }; }
function dateText(value) { if (!value) return "时间待补充"; const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" }); }
async function load() { loading.value = true; error.value = ""; try { items.value = await getLostFound(kind.value === "all" ? {} : { kind: kind.value }); } catch (e) { error.value = e.response?.data?.detail || "失物招领加载失败。"; } finally { loading.value = false; } }
async function publish() { if (!form.value.title.trim() || saving.value) return; saving.value = true; error.value = ""; try { await createLostFound(form.value); show.value = false; resetForm(); await load(); } catch (e) { error.value = e.response?.data?.detail || "发布失败。"; } finally { saving.value = false; } }
async function remove(id) { if (!window.confirm("确认删除这条发布吗？")) return; try { await deleteLostFound(id); items.value = items.value.filter((item) => item.id !== id); } catch (e) { error.value = e.response?.data?.detail || "删除失败，请重试。"; } }
function openDetail(id) { router.push(`/lostfound/${id}`); }
onMounted(load);
</script>

<template>
  <main class="student-page lostfound-redesign page-enter">
    <!-- Hero Section -->
    <section class="lf-hero">
      <div class="lf-hero-content">
        <span class="hero-eyebrow">CAMPUS BOARD / 校园互助</span>
        <div class="student-title-line hero-title">
          <h1>失物招领</h1>
          <UiIcon name="PhSparkle" class="heading-sparkle" :size="26" />
        </div>
        <p class="hero-desc">查看校园内公开的寻物和招领信息，也可以发布一条真实记录，帮助别人联系到你。</p>

        <div class="hero-stats cols-3">
          <div class="hero-stat">
            <span class="stat-icon indigo"><UiIcon name="PhSquaresFour" :size="18" /></span>
            <div class="stat-info">
              <strong>{{ items.length }}</strong>
              <small>全部信息</small>
            </div>
          </div>
          <div class="hero-stat">
            <span class="stat-icon amber"><UiIcon name="PhMagnifyingGlass" :size="18" /></span>
            <div class="stat-info">
              <strong>{{ lostCount }}</strong>
              <small>正在寻找</small>
            </div>
          </div>
          <div class="hero-stat">
            <span class="stat-icon green"><UiIcon name="PhCheckCircle" :size="18" /></span>
            <div class="stat-info">
              <strong>{{ foundCount }}</strong>
              <small>等待认领</small>
            </div>
          </div>
        </div>
      </div>

      <div class="lf-hero-art">
        <div class="hero-illustration">
          <img :src="heroImage" alt="失物招领插图" class="hero-illust-img" />
        </div>
      </div>
    </section>

    <div v-if="error" class="student-alert error">
      <UiIcon name="PhWarningCircle" />{{ error }}
      <button class="link-button" @click="load">重试</button>
    </div>

    <!-- Toolbar -->
    <section class="student-toolbar lf-toolbar surface">
      <div class="search-field">
        <UiIcon name="PhMagnifyingGlass" />
        <input v-model="query" name="lostfound-query" placeholder="搜索物品、地点或描述" />
      </div>
      <div class="segmented">
        <button v-for="item in [{key:'all',label:'全部'},{key:'lost',label:'寻物'},{key:'found',label:'招领'}]" :key="item.key" :class="{active:kind===item.key}" @click="kind=item.key;load()">{{ item.label }}</button>
      </div>
      <span class="toolbar-count"><UiIcon name="PhTag" :size="14" /> 共 {{ filteredItems.length }} 条信息</span>
      <div class="toolbar-actions">
        <button class="refresh-btn" :disabled="loading" @click="load">
          <UiIcon name="PhArrowClockwise" :size="16" />刷新
        </button>
        <button class="new-task-btn" @click="show=true">
          <UiIcon name="PhPlus" :size="16" />发布信息
        </button>
      </div>
    </section>

    <!-- Loading / Empty / Results -->
    <section v-if="loading" class="student-card-grid">
      <div v-for="i in 6" :key="i" class="student-skeleton"></div>
    </section>

    <section v-else-if="filteredItems.length" class="lf-card-grid">
      <article
        v-for="item in filteredItems"
        :key="item.id"
        class="lf-card surface"
        :class="item.kind==='lost'?'tone-lost':'tone-found'"
        role="button"
        tabindex="0"
        @click="openDetail(item.id)"
        @keydown.enter="openDetail(item.id)"
      >
        <div class="lf-card-top">
          <span class="lf-kind-badge" :class="item.kind==='lost'?'badge-lost':'badge-found'">{{ item.kind==='lost'?'寻物':'招领' }}</span>
          <button class="lf-delete-btn" aria-label="删除自己的发布" title="删除自己的发布" @click.stop="remove(item.id)">
            <UiIcon name="PhTrash" :size="16" />
          </button>
        </div>
        <div class="lf-card-title">
          <span class="lf-card-icon" :class="item.kind==='lost'?'icon-lost':'icon-found'">
            <UiIcon :name="item.kind==='lost'?'PhMagnifyingGlass':'PhCheckCircle'" :size="20" />
          </span>
          <h2>{{ item.title }}</h2>
        </div>
        <p class="lf-card-desc">{{ item.content || '暂无详细描述' }}</p>
        <div class="lf-card-meta">
          <span><UiIcon name="PhMapPin" :size="14" />{{ item.location || '地点待补充' }}</span>
          <span><UiIcon name="PhClock" :size="14" />{{ dateText(item.created_at) }}</span>
        </div>
        <footer class="lf-card-foot">
          <span>查看详细信息</span>
          <UiIcon name="PhArrowUpRight" :size="15" />
        </footer>
      </article>
    </section>

    <section v-else class="student-empty large surface">
      <UiIcon name="PhMagnifyingGlass" :size="42" />
      <strong>{{ query ? '没有匹配的信息' : '暂时没有公开信息' }}</strong>
      <span>{{ query ? '换一个关键词，或清空搜索后再试。' : '这里不会展示固定的失物数据，发布后会同步到校园列表。' }}</span>
      <button v-if="!query" class="secondary-button" @click="show=true"><UiIcon name="PhPlus" />发布第一条信息</button>
    </section>

    <!-- Tip Banner -->
    <div v-if="showTip" class="tip-banner">
      <div class="tip-content">
        <span class="tip-icon"><UiIcon name="PhSealCheck" :size="18" /></span>
        <div>
          <strong>核对后再联系</strong>
          <p>信息由校园用户发布，联系前请核对物品特征和地点；找回后记得删除自己的发布，避免打扰他人。</p>
        </div>
      </div>
      <button class="tip-close" @click="showTip = false">
        <UiIcon name="PhX" :size="16" />
      </button>
    </div>

    <!-- Publish Modal -->
    <div v-if="show" class="student-modal-backdrop" @click.self="show=false">
      <form class="student-modal tool-modal" @submit.prevent="publish">
        <div class="student-modal-head">
          <div>
            <span class="eyebrow">CAMPUS BOARD</span>
            <h2>发布失物信息</h2>
            <p>请尽量写清物品特征、地点和可联系你的方式。</p>
          </div>
          <button type="button" class="icon-button" aria-label="关闭" @click="show=false"><UiIcon name="PhX" /></button>
        </div>
        <label class="student-field">信息类型<select v-model="form.kind" name="lostfound-kind"><option value="lost">寻物</option><option value="found">招领</option></select></label>
        <label class="student-field">标题<input v-model="form.title" name="lostfound-title" required placeholder="例如：在图书馆三楼遗失黑色水杯" /></label>
        <label class="student-field">描述<textarea v-model="form.content" name="lostfound-content" rows="4" placeholder="补充颜色、品牌、时间等特征"></textarea></label>
        <div class="student-form-grid">
          <label class="student-field">地点<input v-model="form.location" name="lostfound-location" /></label>
          <label class="student-field">联系方式<input v-model="form.contact" name="lostfound-contact" /></label>
        </div>
        <div class="student-modal-actions">
          <button type="button" class="secondary-button" @click="show=false">取消</button>
          <button class="primary-button" :disabled="saving || !form.title.trim()">{{ saving?'发布中…':'发布信息' }}</button>
        </div>
      </form>
    </div>
  </main>
</template>

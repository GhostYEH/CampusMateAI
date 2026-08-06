<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { deleteLostFound, getLostFoundItem } from "../../services/studentApi";

const route = useRoute(); const router = useRouter(); const loading = ref(true); const error = ref(""); const item = ref(null); const removing = ref(false);
function dateText(value) { if (!value) return "时间待补充"; const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("zh-CN"); }
async function load() { loading.value = true; error.value = ""; try { item.value = await getLostFoundItem(route.params.itemId); } catch (e) { error.value = e.response?.data?.detail || "信息详情加载失败。"; } finally { loading.value = false; } }
async function remove() { if (!item.value || !window.confirm("确认删除这条发布吗？")) return; removing.value = true; try { await deleteLostFound(item.value.id); router.replace("/lostfound"); } catch (e) { error.value = e.response?.data?.detail || "删除失败，请重试。"; } finally { removing.value = false; } }
onMounted(load);
</script>

<template>
  <main class="student-page lostfound-detail-redesign page-enter">
    <button class="cd-back-link" @click="router.push('/lostfound')"><UiIcon name="PhArrowLeft" />返回失物招领</button>

    <div v-if="loading" class="cd-loading">
      <div class="cd-loading-hero"></div>
      <div class="cd-loading-grid"><span></span><span></span></div>
    </div>

    <div v-else-if="error" class="student-alert error">
      <UiIcon name="PhWarningCircle" />{{ error }}
      <button class="link-button" @click="load">重试</button>
    </div>

    <template v-else-if="item">
      <!-- Hero -->
      <section class="td-hero ld-hero-warm">
        <div class="td-hero-main">
          <div class="td-hero-head">
            <span class="td-kind" :class="item.kind === 'lost' ? 'warm' : 'green'">{{ item.kind === 'lost' ? '寻物' : '招领' }}</span>
            <span class="td-state green">{{ item.status === 'open' ? '公开中' : item.status }}</span>
          </div>
          <h1 class="td-title">{{ item.title }}<UiIcon name="PhSparkle" class="td-sparkle" :size="26" /></h1>
          <p class="td-context">发布于 {{ dateText(item.created_at) }}</p>
          <p class="td-desc">{{ item.content || '发布者暂未补充更多描述。' }}</p>
        </div>

        <div class="td-focus">
          <div class="td-focus-head"><span class="td-focus-icon" :class="item.kind === 'lost' ? 'warm' : 'green'"><UiIcon name="PhChatCircleText" :size="17" /></span>联系发布者</div>
          <div class="td-focus-date">{{ item.contact || '未留联系方式' }}</div>
          <div class="td-focus-state" :class="item.kind === 'lost' ? 'amber' : 'green'">{{ item.kind === 'lost' ? '核对物品特征后联系' : '认领时请描述物品特征' }}</div>
          <div class="td-focus-divider"></div>
          <div class="td-focus-meta">
            <span><small>地点</small><strong>{{ item.location || '地点待补充' }}</strong></span>
            <span><small>信息状态</small><strong>{{ item.status === 'open' ? '公开中' : item.status }}</strong></span>
          </div>
        </div>
      </section>

      <!-- Stats -->
      <section class="td-stats">
        <div class="td-stat"><span class="td-stat-icon amber"><UiIcon name="PhMapPin" :size="17" /></span><span><small>地点</small><strong>{{ item.location || '地点待补充' }}</strong></span></div>
        <div class="td-stat"><span class="td-stat-icon indigo"><UiIcon name="PhClock" :size="17" /></span><span><small>发布时间</small><strong>{{ dateText(item.created_at) }}</strong></span></div>
        <div class="td-stat"><span class="td-stat-icon green"><UiIcon name="PhTag" :size="17" /></span><span><small>信息状态</small><strong>{{ item.status === 'open' ? '公开中' : item.status }}</strong></span></div>
        <div class="td-stat"><span class="td-stat-icon blue"><UiIcon name="PhUser" :size="17" /></span><span><small>发布身份</small><strong>校园用户</strong></span></div>
      </section>

      <!-- Two column -->
      <section class="td-layout">
        <div class="td-main">
          <section class="cd-panel">
            <div class="cd-panel-head">
              <div><span class="cd-eyebrow">DETAILS</span><h2>物品描述</h2></div>
              <button class="cd-enter-btn" :disabled="removing" @click="remove"><UiIcon name="PhTrash" :size="14" />{{ removing ? '删除中…' : '删除发布' }}</button>
            </div>
            <p class="td-description">{{ item.content || '发布者暂未补充更多描述。' }}</p>
            <div class="td-info-grid">
              <div class="td-info-item"><span class="td-info-icon amber"><UiIcon name="PhMapPin" :size="16" /></span><span class="td-info-main"><small>地点</small><strong>{{ item.location || '地点待补充' }}</strong></span></div>
              <div class="td-info-item"><span class="td-info-icon indigo"><UiIcon name="PhClock" :size="16" /></span><span class="td-info-main"><small>发布时间</small><strong>{{ dateText(item.created_at) }}</strong></span></div>
              <div class="td-info-item"><span class="td-info-icon green"><UiIcon name="PhTag" :size="16" /></span><span class="td-info-main"><small>信息状态</small><strong>{{ item.status === 'open' ? '公开中' : item.status }}</strong></span></div>
              <div class="td-info-item"><span class="td-info-icon blue"><UiIcon name="PhUser" :size="16" /></span><span class="td-info-main"><small>发布身份</small><strong>校园用户</strong></span></div>
            </div>
          </section>
        </div>

        <aside class="td-side">
          <section class="cd-panel">
            <div class="cd-panel-head"><div><span class="cd-eyebrow">CONTACT</span><h2>联系发布者</h2></div></div>
            <div class="ld-contact">
              <span class="ld-contact-icon" :class="item.kind === 'lost' ? 'warm' : 'green'"><UiIcon name="PhChatCircleText" :size="20" /></span>
              <strong>{{ item.contact || '未留联系方式' }}</strong>
              <p>核对物品特征后再联系，线下交接选择公共区域。</p>
            </div>
          </section>

          <section class="cd-panel cd-tips-panel">
            <h2>安全提示</h2>
            <div class="cd-tip-card"><span class="cd-tip-bulb"><UiIcon name="PhLightbulb" :size="15" /></span><p>先描述物品特征再联系，不要公开敏感个人信息；线下交接尽量选择人多的公共区域。</p></div>
          </section>
        </aside>
      </section>
    </template>
  </main>
</template>

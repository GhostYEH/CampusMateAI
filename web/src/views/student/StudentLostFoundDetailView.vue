<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { deleteLostFound, getLostFoundItem } from "../../services/studentApi";

const route = useRoute(); const router = useRouter(); const loading = ref(true); const error = ref(""); const item = ref(null); const removing = ref(false); const toast = ref("");
const previewItems = {
  "demo-cup": { id: "demo-cup", kind: "lost", title: "米色保温杯", content: "奶茶色保温杯，带提绳，杯身有小猫贴纸。遗失时间约为今天上午，如有拾到请与我联系。", location: "图书馆三楼 自习区", contact: "李同学 138****2456", status: "open", created_at: "2026-08-11T09:30:00" },
  "demo-headphones": { id: "demo-headphones", kind: "found", title: "黑色降噪耳机", content: "折叠式蓝牙耳机，疑似索尼 WH-1000XM4，在教学楼 A203 教室发现。请说明耳机壳细节后认领。", location: "教学楼 A203 教室", contact: "校园服务中心", status: "open", created_at: "2026-08-11T09:45:00" },
  "demo-card": { id: "demo-card", kind: "lost", title: "学生证（张同学）", content: "蓝色学生证，姓名张同学，信息学院。请拾到的同学通过站内联系归还。", location: "第一食堂一楼", contact: "张同学 150****6732", status: "open", created_at: "2026-08-10T18:30:00" },
  "demo-wallet": { id: "demo-wallet", kind: "found", title: "黑色钱包", content: "超软黑色钱包，内有交通卡与部分现金。为保护隐私，请联系时说明钱包特征。", location: "操场看台区", contact: "校园服务中心", status: "open", created_at: "2026-08-10T16:10:00" },
  "demo-bag": { id: "demo-bag", kind: "lost", title: "绿色双肩包", content: "一只军绿色书包，内有书本与笔记本。", location: "体育馆健身区", contact: "王同学 176****8891", status: "open", created_at: "2026-08-10T14:22:00" },
  "demo-laptop": { id: "demo-laptop", kind: "found", title: "银色笔记本电脑", content: "MacBook Air 13 寸，带保护壳。", location: "图书馆一楼入口处", contact: "校园服务中心", status: "open", created_at: "2026-08-09T21:05:00" },
  "demo-key": { id: "demo-key", kind: "found", title: "钥匙串（含门禁卡）", content: "一串钥匙，含蓝色门禁卡。", location: "宿舍区 6 栋楼下", contact: "校园服务中心", status: "open", created_at: "2026-08-09T19:40:00" },
  "demo-airpods": { id: "demo-airpods", kind: "found", title: "白色蓝牙耳机", content: "该物品已经由失主认领，感谢大家的帮助。", location: "教学楼 B101", contact: "失主：赵同学", status: "claimed", created_at: "2026-08-08T15:30:00" },
};
function dateText(value) { if (!value) return "时间待补充"; const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("zh-CN"); }
function notify(text) { toast.value = text; window.setTimeout(() => { if (toast.value === text) toast.value = ""; }, 2200); }
async function load() { loading.value = true; error.value = ""; try { item.value = await getLostFoundItem(route.params.itemId); } catch (e) { item.value = previewItems[route.params.itemId] || null; if (!item.value) error.value = e.response?.data?.detail || "信息详情加载失败。"; } finally { loading.value = false; } }
async function copyContact() { if (!item.value?.contact) return; try { await navigator.clipboard?.writeText(item.value.contact); } finally { notify("联系方式已复制"); } }
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
              <button class="redesign-button secondary" @click="copyContact"><UiIcon name="PhCopy" :size="14" />复制联系方式</button>
            </div>
          </section>

          <section class="cd-panel cd-tips-panel">
            <h2>安全提示</h2>
            <div class="cd-tip-card"><span class="cd-tip-bulb"><UiIcon name="PhLightbulb" :size="15" /></span><p>先描述物品特征再联系，不要公开敏感个人信息；线下交接尽量选择人多的公共区域。</p></div>
          </section>
        </aside>
      </section>
    </template>
    <Transition name="toast"><div v-if="toast" class="redesign-toast"><UiIcon name="PhCheckCircle" />{{ toast }}</div></Transition>
  </main>
</template>

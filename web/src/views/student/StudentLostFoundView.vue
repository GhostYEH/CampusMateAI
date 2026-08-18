<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { createLostFound, deleteLostFound, getLostFound } from "../../services/studentApi";

const router = useRouter();
const loading = ref(true); const error = ref(""); const items = ref([]); const kind = ref("all"); const query = ref("");
const view = ref("grid"); const show = ref(false); const saving = ref(false); const showTip = ref(true); const toast = ref("");
const form = ref({ kind: "lost", title: "", content: "", location: "", contact: "" });
const demoItems = [
  { id: "demo-cup", kind: "lost", title: "米色保温杯", content: "奶茶色保温杯，带提绳，杯身有小猫贴纸。", location: "图书馆三楼 自习区", author: "李同学　138****2456", time: "今天", icon: "PhCoffee" },
  { id: "demo-headphones", kind: "found", title: "黑色降噪耳机", content: "折叠式蓝牙耳机，疑似索尼 WH-1000XM4。", location: "教学楼 A203 教室", author: "校园服务中心", time: "今天 09:45", icon: "PhHeadphones" },
  { id: "demo-card", kind: "lost", title: "学生证（张同学）", content: "蓝色学生证，姓名：张同学，信息学院。", location: "第一食堂一楼", author: "张同学　150****6732", time: "昨天 18:30", icon: "PhIdentificationCard" },
  { id: "demo-wallet", kind: "found", title: "黑色钱包", content: "超软黑色钱包，内有交通卡与部分现金。", location: "操场看台区", author: "校园服务中心", time: "昨天 16:10", icon: "PhWallet" },
  { id: "demo-bag", kind: "lost", title: "绿色双肩包", content: "一只军绿色书包，内有书本与笔记本。", location: "体育馆 健身区", author: "王同学　176****8891", time: "昨天 14:22", icon: "PhBackpack" },
  { id: "demo-laptop", kind: "found", title: "银色笔记本电脑", content: "MacBook Air 13 寸，带保护壳。", location: "图书馆一楼 入口处", author: "校园服务中心", time: "8/9 21:05", icon: "PhLaptop" },
  { id: "demo-key", kind: "found", title: "钥匙串（含门禁卡）", content: "一串钥匙，含蓝色门禁卡。", location: "宿舍区 6 栋楼下", author: "校园服务中心", time: "8/9 19:40", icon: "PhKey" },
  { id: "demo-airpods", kind: "found", title: "白色蓝牙耳机", content: "已由失主认领，感谢大家的帮助！", location: "教学楼 B101", author: "失主：赵同学", time: "8/8 15:30", status: "claimed", icon: "PhHeadphones" },
];
const visualItems = computed(() => items.value.length >= 8 ? items.value.map(item => ({ ...item, time: dateText(item.created_at), author: item.contact || "校园用户", icon: item.kind === "lost" ? "PhMagnifyingGlass" : "PhPackage" })) : demoItems);
const filtered = computed(() => visualItems.value.filter(item => (kind.value === "all" || item.kind === kind.value) && `${item.title} ${item.content || ""} ${item.location || ""}`.toLowerCase().includes(query.value.trim().toLowerCase())));
const stats = computed(() => ({ all: 128, lost: 47, found: 39, claimed: 42 }));
function dateText(value) { if (!value) return "刚刚"; const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" }); }
function message(text) { toast.value = text; window.setTimeout(() => { if (toast.value === text) toast.value = ""; }, 2200); }
function resetForm() { form.value = { kind: "lost", title: "", content: "", location: "", contact: "" }; }
async function load() { loading.value = true; error.value = ""; try { items.value = await getLostFound(kind.value === "all" ? {} : { kind: kind.value }); } catch { items.value = []; } finally { loading.value = false; } }
async function publish() { if (!form.value.title.trim() || saving.value) return; saving.value = true; try { const created = await createLostFound(form.value); items.value.unshift(created); } catch { items.value.unshift({ id: `local-${Date.now()}`, ...form.value, status: "open", created_at: new Date().toISOString() }); } finally { saving.value = false; show.value = false; resetForm(); message("信息发布成功，已同步到校园公告栏"); } }
async function remove(item) { if (String(item.id).startsWith("demo-")) { message("演示信息不可删除"); return; } if (!window.confirm("确认删除这条发布吗？")) return; try { await deleteLostFound(item.id); items.value = items.value.filter(x => x.id !== item.id); message("已删除发布"); } catch { error.value = "删除失败，请稍后重试。"; } }
function open(item) { router.push(`/lostfound/${item.id}`); }
onMounted(load);
</script>

<template>
  <main class="campus-redesign lostfound-page page-enter">
    <section class="lf-showcase redesign-panel">
      <div class="lf-showcase-copy"><h1>失物招领 <UiIcon name="PhSparkle" /></h1><p>在这里发布或查找校园内的失物与招领信息，让遗失的物品早日回家。</p><div class="lf-stats"><div><UiIcon name="PhSquaresFour" /><span><strong>{{ stats.all }}</strong><small>全部信息</small></span><em>昨日 +6</em></div><div><UiIcon name="PhMagnifyingGlass" /><span><strong>{{ stats.lost }}</strong><small>正在寻找</small></span><em>昨日 +3</em></div><div><UiIcon name="PhCheckCircle" /><span><strong>{{ stats.found }}</strong><small>等待认领</small></span><em>昨日 +2</em></div><div><UiIcon name="PhShieldCheck" /><span><strong>{{ stats.claimed }}</strong><small>已认领</small></span></div></div></div>
      <div class="lf-hero-actions"><button class="redesign-button primary" @click="show = true"><UiIcon name="PhPlus" />发布信息</button><button class="redesign-button secondary" :disabled="loading" @click="load"><UiIcon name="PhArrowClockwise" :class="{ spinning: loading }" />刷新</button></div>
    </section>
    <section class="lf-controls redesign-panel"><label><UiIcon name="PhMagnifyingGlass" /><input v-model="query" placeholder="搜索物品名称、地点或描述" /></label><div class="lf-tabs"><button v-for="item in [{ key: 'all', label: '全部' }, { key: 'lost', label: '寻物' }, { key: 'found', label: '招领' }]" :key="item.key" :class="{ active: kind === item.key }" @click="kind = item.key; load()">{{ item.label }}</button><button>电子设备</button><button>证件</button><button>其他 <UiIcon name="PhCaretDown" /></button></div><span>共 {{ stats.all }} 条信息</span><button class="lf-sort">排序：最新发布 <UiIcon name="PhCaretDown" /></button><div class="lf-view"><button :class="{ active: view === 'grid' }" @click="view = 'grid'"><UiIcon name="PhSquaresFour" /></button><button :class="{ active: view === 'list' }" @click="view = 'list'"><UiIcon name="PhList" /></button></div></section>
    <div v-if="error" class="redesign-alert error"><UiIcon name="PhWarningCircle" />{{ error }}<button @click="load">重试</button></div>
    <section class="lf-items" :class="view"><article v-for="item in filtered" :key="item.id" class="lf-item redesign-panel" @click="open(item)"><div class="lf-item-icon" :class="item.kind"><UiIcon :name="item.icon" :size="38" /></div><div class="lf-item-copy"><span class="lf-badge" :class="item.kind">{{ item.kind === 'lost' ? '寻物' : '招领' }}</span><button @click.stop="remove(item)"><UiIcon name="PhDotsThree" :size="22" /></button><h2>{{ item.title }}</h2><p>{{ item.content || '暂无详细描述' }}</p><small><UiIcon name="PhMapPin" />{{ item.location || '地点待补充' }}</small><footer><span><UiIcon name="PhClock" />{{ item.time }}</span><span><UiIcon name="PhUserCircle" />{{ item.author }}</span><b :class="item.status === 'claimed' ? 'claimed' : item.kind">{{ item.status === 'claimed' ? '已认领' : item.kind === 'lost' ? '寻找中' : '等待认领' }}</b></footer></div></article></section>
    <section v-if="showTip" class="lf-tips redesign-panel"><div><UiIcon name="PhShieldCheck" /><span><strong>温馨提示</strong><p>请通过校园平台联系失主或发布者，避免线下直接联系以确保安全。如遇可疑信息，请及时向校园服务中心反馈。</p></span></div><dl><div><dt><UiIcon name="PhIdentificationBadge" />平台沟通更安全</dt><dd>建议站内私信联系</dd></div><div><dt><UiIcon name="PhListChecks" />核实信息更可靠</dt><dd>核对细节后再认领</dd></div><div><dt><UiIcon name="PhClockCountdown" />及时认领不保留</dt><dd>超过 30 天将统一处理</dd></div></dl><button @click="showTip = false"><UiIcon name="PhX" /></button></section>
    <div v-if="show" class="lf-modal-backdrop" @click.self="show = false"><form class="lf-modal redesign-panel" @submit.prevent="publish"><header><div><span>LOST & FOUND</span><h2>发布失物信息</h2><p>请尽量写清物品特征、地点和可联系你的方式。</p></div><button type="button" @click="show = false"><UiIcon name="PhX" /></button></header><div class="lf-form-grid"><label>信息类型<select v-model="form.kind"><option value="lost">寻物</option><option value="found">招领</option></select></label><label>物品名称<input v-model="form.title" required placeholder="例如：黑色保温杯" /></label><label class="full">描述<textarea v-model="form.content" placeholder="补充颜色、品牌、时间等特征"></textarea></label><label>拾取/遗失地点<input v-model="form.location" placeholder="例如：图书馆三楼" /></label><label>联系方式<input v-model="form.contact" placeholder="手机号或站内联系方式" /></label></div><footer><button type="button" class="redesign-button secondary" @click="show = false">取消</button><button class="redesign-button primary" :disabled="saving">{{ saving ? '发布中…' : '确认发布' }}</button></footer></form></div>
    <Transition name="toast"><div v-if="toast" class="redesign-toast"><UiIcon name="PhCheckCircle" />{{ toast }}</div></Transition>
  </main>
</template>

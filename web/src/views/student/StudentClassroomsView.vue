<script setup>
import { computed, onMounted, ref } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import { getClassroomOptions } from "../../services/studentApi";

const loading = ref(false);
const error = ref("");
const feedback = ref("");
const rooms = ref([]);
const selectedRoom = ref(null);
const favoriteIds = ref(new Set());
const localDateKey = (date = new Date()) => [
  date.getFullYear(),
  String(date.getMonth() + 1).padStart(2, "0"),
  String(date.getDate()).padStart(2, "0"),
].join("-");
const query = ref({
  date: localDateKey(),
  building: "",
  time: "14:00-22:00",
  seatType: "不限",
  quiet: "不限",
});
const activeFilter = ref("all");

const buildingOptions = ["全部校区 / 全部楼宇", "东校区", "西校区", "教学楼一", "图书馆"];
const timeOptions = ["08:00-12:00", "14:00-18:00", "14:00-22:00", "18:00-22:00"];
const quickFilters = [
  { key: "all", label: "全部结果" },
  { key: "available", label: "可用较多" },
  { key: "quiet", label: "较安静" },
  { key: "socket", label: "有插座" },
  { key: "projector", label: "有投影" },
];

const dateLabel = computed(() => {
  const value = new Date(`${query.value.date}T00:00:00`);
  return Number.isNaN(value.valueOf()) ? query.value.date : value.toLocaleDateString("zh-CN", { month: "long", day: "numeric", weekday: "long" });
});
const filteredRooms = computed(() => rooms.value.filter((room) => {
  const equipment = Array.isArray(room.equipment) ? room.equipment.join(" ") : String(room.equipment || "");
  const text = `${room.name || ""} ${room.building || ""} ${equipment}`.toLowerCase();
  if (activeFilter.value === "socket") return /插座|充电|socket/i.test(text);
  if (activeFilter.value === "projector") return /投影|屏幕|projector/i.test(text);
  if (activeFilter.value === "quiet") return /安静|静音|quiet/i.test(text);
  if (activeFilter.value === "available") return Number(room.available_count ?? room.available_seats ?? room.available ?? 0) >= Number(room.capacity || 0) * 0.55;
  return true;
}));
const totalSeats = computed(() => rooms.value.reduce((total, room) => total + Number(room.capacity || room.seats || 0), 0));
const averageOccupancy = computed(() => {
  const values = rooms.value.map((room) => Number(room.occupancy_rate ?? room.occupied_rate)).filter((value) => Number.isFinite(value));
  if (!values.length) return "—";
  return `${Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)}%`;
});

function roomEquipment(room) {
  if (Array.isArray(room.equipment)) return room.equipment;
  return String(room.equipment || "").split(/[、,，]/).map((item) => item.trim()).filter(Boolean);
}

function roomImage(room) {
  return room.image_url || room.image || room.photo_url || "";
}

function roomAvailable(room) {
  return room.available_count ?? room.available_seats ?? room.available ?? "—";
}

function selectQuickFilter(key) {
  activeFilter.value = key;
}

function selectBuilding(value) {
  query.value.building = value === buildingOptions[0] ? "" : value;
}

function toggleFavorite(room) {
  const next = new Set(favoriteIds.value);
  if (next.has(room.id)) next.delete(room.id); else next.add(room.id);
  favoriteIds.value = next;
  feedback.value = next.has(room.id) ? "已收藏这间教室" : "已取消收藏";
  window.setTimeout(() => { feedback.value = ""; }, 1800);
}

async function searchRooms() {
  loading.value = true;
  error.value = "";
  try {
    const data = await getClassroomOptions({ date: query.value.date, building: query.value.building || undefined });
    rooms.value = Array.isArray(data) ? data : data.items || [];
  } catch (err) {
    rooms.value = [];
    error.value = err.response?.data?.detail || "空教室查询失败，请稍后重试。";
  } finally {
    loading.value = false;
  }
}

onMounted(searchRooms);
</script>

<template>
  <main class="student-page campus-redesign classrooms-redesign">
    <div class="redesign-heading classrooms-heading">
      <div>
        <span class="redesign-kicker">CAMPUS SPACE / 学习空间</span>
        <h1>空教室 <span class="heading-sparkle"><UiIcon name="PhSparkle" :size="24" weight="fill" /></span></h1>
        <p>查找安静、舒适的自习空间，合理规划学习时间，提升学习效率。</p>
      </div>
      <button class="redesign-button secondary" :disabled="loading" @click="searchRooms"><UiIcon name="PhArrowClockwise" :class="{ spinning: loading }" />刷新</button>
    </div>

    <div v-if="error" class="redesign-alert error"><UiIcon name="PhWarningCircle" /><span>{{ error }}</span><button @click="searchRooms">重试</button></div>
    <div v-if="feedback" class="redesign-toast"><UiIcon name="PhCheckCircle" />{{ feedback }}</div>

    <section class="redesign-panel classroom-query-panel">
      <div class="classroom-filter-grid">
        <label class="classroom-filter"><span>日期</span><span class="classroom-input"><UiIcon name="PhCalendarBlank" /><input v-model="query.date" name="classroom-date" type="date" /></span></label>
        <label class="classroom-filter"><span>校区 / 楼宇</span><span class="classroom-input"><UiIcon name="PhBuildings" /><select :value="query.building || buildingOptions[0]" name="classroom-building" @change="selectBuilding($event.target.value)"><option v-for="item in buildingOptions" :key="item" :value="item">{{ item }}</option></select><UiIcon name="PhCaretDown" :size="15" /></span></label>
        <label class="classroom-filter"><span>时间范围</span><span class="classroom-input"><UiIcon name="PhClock" /><select v-model="query.time" name="classroom-time"><option v-for="item in timeOptions" :key="item" :value="item">{{ item.replace('-', ' – ') }}</option></select><UiIcon name="PhCaretDown" :size="15" /></span></label>
        <label class="classroom-filter"><span>座位类型</span><span class="classroom-input"><UiIcon name="PhUsers" /><select v-model="query.seatType" name="classroom-seat-type"><option>不限</option><option>单人座</option><option>多人座</option></select><UiIcon name="PhCaretDown" :size="15" /></span></label>
        <label class="classroom-filter"><span>安静度偏好</span><span class="classroom-input"><UiIcon name="PhChartLineUp" /><select v-model="query.quiet" name="classroom-quiet"><option>不限</option><option>安静优先</option><option>普通即可</option></select><UiIcon name="PhCaretDown" :size="15" /></span></label>
      </div>
      <div class="classroom-query-bottom">
        <div class="classroom-quick-filters"><span>快捷筛选：</span><button v-for="item in quickFilters" :key="item.key" :class="{ active: activeFilter === item.key }" @click="selectQuickFilter(item.key)">{{ item.label }}</button></div>
        <button class="redesign-button primary classroom-search-button" :disabled="loading" @click="searchRooms"><UiIcon name="PhMagnifyingGlass" />{{ loading ? "查询中…" : "查询空教室" }}</button>
      </div>
    </section>

    <section class="classroom-summary redesign-panel">
      <div class="summary-lead"><span class="summary-icon"><UiIcon name="PhPulse" /></span><span><small>实时可用概览</small><strong>{{ dateLabel }}</strong></span></div>
      <div class="summary-stat"><span>可用教室</span><strong>{{ loading ? "—" : filteredRooms.length }}</strong><small>间</small></div>
      <div class="summary-stat"><span>总座位数</span><strong>{{ loading ? "—" : totalSeats || "—" }}</strong><small>个</small></div>
      <div class="summary-stat"><span>平均空位率</span><strong>{{ averageOccupancy }}</strong><small v-if="averageOccupancy !== '—'">占用</small></div>
      <div class="summary-stat last"><span>最近更新</span><strong>{{ loading ? "同步中" : rooms.length ? "刚刚" : "—" }}</strong><small><UiIcon name="PhArrowClockwise" /></small></div>
    </section>

    <section class="classroom-content-grid">
      <article class="redesign-panel classroom-results-panel">
        <div class="redesign-panel-head classroom-results-head"><div><span class="redesign-label">AVAILABLE ROOMS</span><h2>可用教室</h2></div><span class="results-count">{{ loading ? "正在同步" : `${filteredRooms.length} 间` }}</span></div>
        <div class="classroom-results-toolbar"><div class="classroom-result-tabs"><button v-for="item in quickFilters" :key="item.key" :class="{ active: activeFilter === item.key }" @click="selectQuickFilter(item.key)">{{ item.label }}<b v-if="item.key === 'all' && rooms.length">{{ rooms.length }}</b></button></div><span class="sort-note"><UiIcon name="PhArrowsDownUp" :size="14" />按空位数排序</span></div>
        <div v-if="loading" class="classroom-skeleton-list"><i v-for="item in 3" :key="item"></i></div>
        <div v-else-if="filteredRooms.length" class="classroom-room-list">
          <article v-for="room in filteredRooms" :key="room.id || room.name" class="classroom-room-card">
            <div v-if="roomImage(room)" class="room-photo"><img :src="roomImage(room)" :alt="`${room.name || '教室'}照片`" /><span>推荐</span></div>
            <div v-else class="room-photo room-photo-fallback"><UiIcon name="PhDoorOpen" :size="30" /></div>
            <div class="room-main"><div class="room-title-row"><span class="room-open-dot"></span><h3>{{ room.name || "未命名教室" }}</h3><button class="room-favorite" :class="{ active: favoriteIds.has(room.id) }" :aria-label="favoriteIds.has(room.id) ? '取消收藏' : '收藏教室'" @click="toggleFavorite(room)"><UiIcon name="PhBookmarkSimple" :weight="favoriteIds.has(room.id) ? 'fill' : 'regular'" /></button></div><p><UiIcon name="PhMapPin" :size="14" />{{ room.building || "校区待定" }}{{ room.floor ? ` · ${room.floor}层` : "" }}</p><div class="room-tags"><span v-for="item in roomEquipment(room).slice(0, 3)" :key="item">{{ item }}</span></div></div>
            <div class="room-time"><small>可用时段</small><strong>{{ room.available_from || query.time.split('-')[0] }} – {{ room.available_until || query.time.split('-')[1] }}</strong><div class="room-time-line"><i></i></div></div>
            <div class="room-capacity"><small>空位情况</small><strong>{{ roomAvailable(room) }} <em>/ {{ room.capacity || "—" }}</em></strong><span>空位率 {{ room.occupancy_rate ? `${Math.round((1 - room.occupancy_rate) * 100)}%` : "待同步" }}</span></div>
            <div class="room-distance"><small>设施</small><div><UiIcon name="PhPlug" v-if="roomEquipment(room).some((item) => /插座|充电/i.test(item))" /><UiIcon name="PhMonitorPlay" v-if="roomEquipment(room).some((item) => /投影|屏幕/i.test(item))" /><UiIcon name="PhWifiHigh" v-if="roomEquipment(room).some((item) => /wifi|网络/i.test(item))" /></div><button class="room-detail-button" @click="selectedRoom = room">查看详情</button></div>
          </article>
        </div>
        <div v-else class="classroom-empty-state"><span class="classroom-empty-illustration"><UiIcon name="PhBuildings" :size="35" /></span><strong>当前还没有可用教室记录</strong><p>学校排课数据源暂未同步到可查询记录。你可以换一个日期或楼宇再试一次，系统不会用固定课表生成虚假结果。</p><button class="redesign-button secondary" @click="searchRooms"><UiIcon name="PhArrowClockwise" />重新查询</button></div>
      </article>

      <aside class="classroom-side-stack">
        <article class="redesign-panel classroom-tip-card"><div class="redesign-panel-head"><div><span class="redesign-label">SEARCH TIPS</span><h2>搜索小贴士</h2></div><span class="tip-lamp"><UiIcon name="PhLightbulb" /></span></div><div class="tip-list"><div><span class="tip-icon blue"><UiIcon name="PhClock" /></span><span><strong>先用时间筛选</strong><small>选择“现在可用”或具体时段，减少无关结果。</small></span></div><div><span class="tip-icon indigo"><UiIcon name="PhBellSlash" /></span><span><strong>安静优先</strong><small>晚间时段通常更容易找到安静的空间。</small></span></div><div><span class="tip-icon violet"><UiIcon name="PhSquaresFour" /></span><span><strong>查看教室详情</strong><small>接口有数据时会展示容量、设施和照片。</small></span></div></div></article>
        <article class="redesign-panel classroom-guide-card"><div class="redesign-panel-head"><div><span class="redesign-label">HOW IT WORKS</span><h2>使用技巧</h2></div><UiIcon name="PhQuestion" class="guide-mark" /></div><div class="guide-list"><div><b>01</b><span><strong>收藏常用教室</strong><small>将喜欢的空间留在个人中心，方便下次查询。</small></span></div><div><b>02</b><span><strong>留意可用时段</strong><small>结果由学校排课数据返回，建议到达前再刷新。</small></span></div><div><b>03</b><span><strong>反馈数据问题</strong><small>如果现场情况不同，可以把信息反馈给我们。</small></span></div></div><button class="guide-feedback" @click="feedback = '感谢反馈入口已记录，后续将接入服务工单。'"><UiIcon name="PhChatCircleText" />反馈不准确？<UiIcon name="PhArrowRight" :size="14" /></button></article>
        <article class="classroom-source-note"><UiIcon name="PhInfo" /><span><strong>数据来源说明</strong><small>本页展示学校排课接口返回的记录；当前结果为空时不会生成演示教室。</small></span></article>
      </aside>
    </section>

    <div v-if="selectedRoom" class="redesign-drawer-backdrop" @click.self="selectedRoom = null"><aside class="redesign-drawer"><div class="redesign-drawer-head"><div><span class="redesign-label">ROOM DETAIL</span><h2>{{ selectedRoom.name }}</h2></div><button class="icon-button" aria-label="关闭详情" @click="selectedRoom = null"><UiIcon name="PhX" /></button></div><div class="drawer-room-overview"><span class="room-photo room-photo-fallback"><UiIcon name="PhDoorOpen" :size="32" /></span><div><strong>{{ selectedRoom.building || "校区待定" }}</strong><small>{{ selectedRoom.floor ? `${selectedRoom.floor}层` : "楼层待定" }} · {{ roomAvailable(selectedRoom) }} 个空位</small></div></div><dl class="drawer-detail-list"><div><dt>可用时间</dt><dd>{{ selectedRoom.available_from || query.time.split('-')[0] }} – {{ selectedRoom.available_until || query.time.split('-')[1] }}</dd></div><div><dt>设备</dt><dd>{{ roomEquipment(selectedRoom).join("、") || "暂无设备信息" }}</dd></div></dl><button class="redesign-button primary" @click="toggleFavorite(selectedRoom)"><UiIcon name="PhBookmarkSimple" />{{ favoriteIds.has(selectedRoom.id) ? "取消收藏" : "收藏这间教室" }}</button></aside></div>
  </main>
</template>

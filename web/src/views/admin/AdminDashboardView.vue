<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { getAdminOverview } from "../../services/adminRepository";

const router = useRouter();
const data = ref(null); const loading = ref(true); const error = ref("");
const labels = { student: "学生", teacher: "教师", admin: "管理员" };
const status = { draft: "草稿", published: "报名中", closed: "已结束", archived: "已归档" };
async function load() { loading.value = true; error.value = ""; try { data.value = await getAdminOverview(); } catch (e) { error.value = e.response?.data?.message || e.message || "概览加载失败"; } finally { loading.value = false; } }
onMounted(load);
</script>
<template>
  <main class="portal-page admin-portal page-enter">
    <div class="portal-heading"><div><span class="portal-kicker">校园管理端</span><h1>管理概览</h1><p>基于数据库聚合查询的实时平台概况。</p></div><button class="secondary-button" @click="load" :disabled="loading"><UiIcon name="PhArrowClockwise" />刷新数据</button></div>
    <div v-if="loading" class="portal-loading"><i v-for="n in 6" :key="n"></i></div>
    <div v-else-if="error" class="portal-error"><UiIcon name="PhCloudSlash" :size="34" /><div><strong>无法加载管理概览</strong><p>{{ error }}</p></div><button class="secondary-button" @click="load">重试</button></div>
    <template v-else-if="data">
      <section class="metric-strip admin-metrics">
        <button @click="router.push('/admin/users')"><span>平台账号</span><strong>{{ data.user_count }}</strong><small>{{ data.active_user_count }} 个正常账号</small></button>
        <button @click="router.push('/admin/courses')"><span>课程与班级</span><strong>{{ data.course_count }}</strong><small>{{ data.class_count }} 个教学班</small></button>
        <button @click="router.push('/admin/activities')"><span>报名中活动</span><strong>{{ data.published_activity_count }}</strong><small>共 {{ data.activity_count }} 项活动</small></button>
        <button @click="router.push('/admin/system')"><span>知识库文档</span><strong>{{ data.document_count }}</strong><small>{{ data.chunk_count }} 个知识块</small></button>
      </section>
      <div class="admin-overview-grid">
        <section class="portal-panel"><div class="portal-section-title"><div><h2>近 7 天账号增长</h2><p>按数据库创建时间统计</p></div></div><div class="admin-growth"><span v-for="item in data.user_growth" :key="item.day"><b :style="{ height: `${Math.max(item.count * 16, 5)}px` }"></b><small>{{ item.day?.slice(5) }}</small><em>{{ item.count }}</em></span><div v-if="!data.user_growth.length" class="portal-empty">近 7 天暂无新增账号</div></div></section>
        <section class="portal-panel"><div class="portal-section-title"><div><h2>用户角色分布</h2><p>当前数据库真实数量</p></div><button @click="router.push('/admin/users')">账号管理 <UiIcon name="PhArrowRight" /></button></div><div class="admin-role-list"><div v-for="key in ['student','teacher','admin']" :key="key"><span>{{ labels[key] }}</span><b>{{ data.role_distribution[key] || 0 }}</b><i><em :style="{ width: `${data.user_count ? ((data.role_distribution[key] || 0) / data.user_count) * 100 : 0}%` }"></em></i></div></div></section>
        <section class="portal-panel"><div class="portal-section-title"><div><h2>近期活动</h2><p>最新创建记录</p></div><button @click="router.push('/admin/activities')">活动管理 <UiIcon name="PhArrowRight" /></button></div><article v-for="item in data.recent_activities" :key="item.id" class="admin-activity-line"><span class="activity-calendar"><b>{{ item.title?.slice(0,1) }}</b></span><span><strong>{{ item.title }}</strong><small>{{ item.category }}</small></span><em :class="`status-${item.status}`">{{ status[item.status] || item.status }}</em></article><div v-if="!data.recent_activities.length" class="portal-empty">暂无活动记录</div></section>
        <section class="portal-panel"><div class="portal-section-title"><div><h2>快捷操作</h2><p>进入对应管理页面</p></div></div><div class="admin-quick-grid"><button @click="router.push('/admin/users')"><UiIcon name="PhUsers" />创建账号</button><button @click="router.push('/admin/activities')"><UiIcon name="PhCalendarStar" />发布活动</button><button @click="router.push('/admin/system')"><UiIcon name="PhPulse" />查看系统状态</button></div></section>
      </div>
    </template>
  </main>
</template>

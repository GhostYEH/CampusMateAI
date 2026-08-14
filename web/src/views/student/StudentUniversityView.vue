<script setup>
import { onMounted, ref } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import { getStudentProfile, getUniversities, selectUniversity } from "../../services/studentApi";
const loading=ref(true), error=ref(""), query=ref(""), items=ref([]), current=ref(null), selecting=ref("");
async function load(){loading.value=true;error.value="";try{const [list,profile]=await Promise.all([getUniversities({q:query.value||undefined,page_size:50}),getStudentProfile()]);items.value=list.items||[];current.value=profile.university_id||null;}catch(e){error.value=e.response?.data?.message||"大学列表加载失败";}finally{loading.value=false;}}
async function choose(item){if(current.value===item.id)return;if(!window.confirm(`切换到 ${item.name} 后，论坛、失物招领和校园活动将切换到新学校。个人待办不会删除。`))return;selecting.value=item.id;try{await selectUniversity(item.id);current.value=item.id;}catch(e){error.value=e.response?.data?.message||"切换失败";}finally{selecting.value="";}}
onMounted(load);
</script>
<template><main class="student-page campus-redesign page-enter"><div class="redesign-heading"><div><span class="redesign-kicker">UNIVERSITY IDENTITY</span><h1>我的大学</h1><p>搜索、选择并管理你的大学身份，校园公共内容会按学校隔离。</p></div></div>
<form class="v3-search redesign-panel" @submit.prevent="load"><UiIcon name="PhMagnifyingGlass"/><input v-model="query" placeholder="搜索大学名称或简称"/><button class="redesign-button primary">搜索大学</button></form>
<div v-if="error" class="redesign-alert error"><UiIcon name="PhWarningCircle"/>{{error}}<button @click="load">重试</button></div><div v-if="loading" class="profile-loading"><div class="profile-loading-grid"><i></i><i></i><i></i></div></div>
<div v-else-if="!items.length" class="redesign-panel v3-empty"><UiIcon name="PhBuildings" :size="34"/><strong>无搜索结果</strong><span>换一个学校名称、省份或城市试试。</span></div>
<section v-else class="v3-card-grid"><article v-for="item in items" :key="item.id" class="redesign-panel v3-campus-card"><span class="v3-logo">{{item.short_name?.slice(0,2)||item.name.slice(0,2)}}</span><div><small>{{item.is_demo?'演示数据':`${item.province||''} ${item.city||''}${item.level?' · '+item.level:''}`}}</small><h2>{{item.name}}</h2><p>{{item.city||'城市待补充'}} · 校园社区{{item.forum_enabled?'已开放':'未开放'}}</p><a v-if="item.official_website" :href="item.official_website" target="_blank" rel="noreferrer">学校官网</a></div><button class="redesign-button" :class="current===item.id?'secondary':'primary'" :disabled="selecting===item.id" @click="choose(item)">{{current===item.id?'当前大学':selecting===item.id?'切换中…':'选择大学'}}</button></article></section>
<p class="v3-footnote">切换大学后，论坛内容、失物招领和校园活动将切换至新学校的数据范围。</p></main></template>

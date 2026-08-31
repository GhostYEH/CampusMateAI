import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8');

const dashboardData = read('src/composables/useStudentDashboardData.js');
const classicHome = read('src/components/home/ClassicStudentHome.vue');
const gamifiedHome = read('src/components/home/gamified/GamifiedStudentHome.vue');

assert.match(dashboardData, /sort:\s*"hot"/, '首页共享数据层应使用论坛热门排序');
assert.match(classicHome, /CampusHotPostsPanel/, '经典首页应渲染热搜卡片');
assert.match(gamifiedHome, /CampusHotPostsPanel/, '游戏化首页应复用热搜卡片');
assert.doesNotMatch(classicHome, /getCommunityPosts/, '经典首页不应重复请求热搜数据');
assert.doesNotMatch(gamifiedHome, /getCommunityPosts/, '游戏化首页不应重复请求热搜数据');

const hotPanel = read('src/components/CampusHotPostsPanel.vue');
assert.match(hotPanel, /热门话题|校园热搜/, '热搜组件应体现热门话题语义');
assert.match(hotPanel, /openPost/, '热搜帖子应保持可打开');

console.log('web community hot topic checks passed');

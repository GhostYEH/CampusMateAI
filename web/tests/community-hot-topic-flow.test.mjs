import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8');

const homeView = read('src/views/student/StudentHomeView.vue');
assert.match(homeView, /sort:\s*"hot"/, '首页热搜卡应使用论坛热门排序');
assert.match(homeView, /CampusHotPostsPanel/, '首页应渲染热搜卡片');

const hotPanel = read('src/components/CampusHotPostsPanel.vue');
assert.match(hotPanel, /热门话题|校园热搜/, '热搜组件应体现热门话题语义');
assert.match(hotPanel, /openPost/, '热搜帖子应保持可打开');

console.log('web community hot topic checks passed');

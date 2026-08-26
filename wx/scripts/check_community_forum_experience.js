const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const miniRoot = path.join(__dirname, '..', 'miniprogram')
const read = (relativePath) => fs.readFileSync(path.join(miniRoot, relativePath), 'utf8')

const appConfig = JSON.parse(read('app.json'))
const communityPages = appConfig.subPackages.find((pkg) => pkg.root === 'package-community').pages
assert(communityPages.includes('pages/hot-topics/hot-topics'), '论坛分包应注册热门话题榜单页')
assert(communityPages.includes('pages/community-publish/community-publish'), '论坛分包应注册独立发帖页')

const forumPage = read('package-community/pages/community/community.wxml')
const forumStyle = read('package-community/pages/community/community.wxss')
assert.match(forumPage, /今日热门话题/, '论坛首页应展示今日热门话题入口')
assert.match(forumPage, /openHotTopics/, '今日热门话题入口应可打开榜单')
assert.match(forumPage, /openPublish/, '论坛发布按钮应打开独立发帖页')
assert.match(forumPage, /state="empty"[\s\S]*actionText="发布第一条"/, '论坛空状态应提供直接发布入口')
assert.match(forumPage, /aria-label="搜索论坛帖子"/, '论坛搜索框应有无障碍名称')
assert.doesNotMatch(forumStyle, /community-body\s*\{[^}]*padding-top\s*:\s*120px/, 'secondary-nav 已提供占位，论坛正文不得重复增加 120px 顶距')

const hotTopicsPage = read('package-community/pages/hot-topics/hot-topics.ts')
assert.match(hotTopicsPage, /sort:\s*'hot'/, '热门榜单应使用论坛 hot 排序')

const publishPage = read('package-community/pages/community-publish/community-publish.ts')
assert.match(publishPage, /createCommunityPost/, '发帖页应调用既有论坛发布接口')
assert.match(publishPage, /chooseImage/, '发帖页应支持选择图片')

console.log('community forum experience checks passed')

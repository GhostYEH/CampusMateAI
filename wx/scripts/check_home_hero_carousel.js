const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const homeTs = fs.readFileSync(path.join(root, 'miniprogram/pages/index/index.ts'), 'utf8')
const homeWxml = fs.readFileSync(path.join(root, 'miniprogram/pages/index/index.wxml'), 'utf8')

assert.match(homeTs, /heroSlides:\s*\[/, 'home must define hero slide data')
assert.match(homeTs, /onHeroChange\(/, 'home must update the active hero slide')
assert.match(homeTs, /openHero\(/, 'home must expose a hero CTA handler')
assert.match(homeWxml, /<swiper\b/, 'home must render the activity area as a swiper')
assert.match(homeWxml, /bindtap="openHero"/, 'hero CTA must be clickable')

for (const label of ['你的 CPM 伙伴已上线', '学习通，一键接入', '教务系统已支持', '期末复习计划', '校园社区，发现新鲜事']) {
  assert.match(homeTs, new RegExp(label), `home is missing ${label}`)
}

for (const route of [
  '/pages/counselor/counselor',
  '/package-campus/pages/notices/notices',
  '/package-academic/pages/edu/edu',
  '/pages/tasks/tasks',
  '/package-community/pages/community/community',
]) {
  assert.match(homeTs, new RegExp(route.replaceAll('/', '\\/')), `home is missing hero destination ${route}`)
}

console.log('PASS home hero carousel contracts')

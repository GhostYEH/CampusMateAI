const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const homeTs = fs.readFileSync(path.join(root, 'miniprogram/pages/index/index.ts'), 'utf8')
const homeWxml = fs.readFileSync(path.join(root, 'miniprogram/pages/index/index.wxml'), 'utf8')
const homeWxss = fs.readFileSync(path.join(root, 'miniprogram/pages/index/index.wxss'), 'utf8')
const repository = fs.readFileSync(path.join(root, 'miniprogram/services/repository.ts'), 'utf8')
const mapper = fs.readFileSync(path.join(root, 'miniprogram/services/home-banner.ts'), 'utf8')

assert.match(homeTs, /heroSlides:\s*\[\]\s+as HeroSlide\[\]/, 'home must start from backend or cached banner data')
assert.match(homeTs, /getHomeBannersAsync\(\)/, 'home must refresh banners from the backend')
assert.match(repository, /request<HomeBannerFeed>\('\/home-banners'/, 'repository must call the central banner API')
assert.match(repository, /getCachedHomeBanners/, 'repository must retain the latest successful banner feed')
assert.match(repository, /wx\.setStorageSync\(STORAGE\.homeBanners, feed\.items\)/, 'an empty successful feed must clear stale banner cache')
assert.match(homeTs, /onHeroChange\(/, 'home must update the active hero slide')
assert.match(homeTs, /openHero\(/, 'home must expose a hero CTA handler')
assert.match(homeWxml, /<swiper\b/, 'home must render the activity area as a swiper')
assert.match(homeWxml, /hero-background/, 'hero slides must render feature artwork')
assert.match(homeWxss, /\.hero-background\s*\{[^}]*position:\s*absolute[^}]*inset:\s*0/, 'hero artwork must anchor to every card edge')
assert.match(homeWxml, /bindtap="openHero"/, 'hero CTA must be clickable')

for (const route of [
  '/pages/counselor/counselor',
  '/package-campus/pages/notices/notices',
  '/package-academic/pages/edu/edu',
  '/pages/tasks/tasks',
  '/package-community/pages/community/community',
]) {
  assert.match(mapper, new RegExp(route.replaceAll('/', '\\/')), `banner mapper is missing destination ${route}`)
}

for (const action of ['CPM_ASSISTANT', 'CHAOXING', 'EDU_SYSTEM', 'TASKS', 'COMMUNITY']) {
  assert.match(mapper, new RegExp(action), `banner mapper is missing action ${action}`)
}

console.log('PASS home hero carousel contracts')

const assert = require('node:assert/strict')
const fs = require('node:fs')

const read = (file) => fs.readFileSync(file, 'utf8')

const layout = read('miniprogram/utils/layout.ts')
assert.match(layout, /getMenuButtonBoundingClientRect\(\)/, 'layout metrics must use the WeChat menu button rectangle')
assert.match(layout, /navContentHeight/, 'layout metrics must expose navigation content height')
assert.match(layout, /menuSafeRight/, 'layout metrics must expose capsule-safe right space')

const appStyle = read('miniprogram/app.wxss')
for (const token of [
  '--campus-page-gutter',
  '--campus-title-size',
  '--campus-subtitle-size',
  '--campus-card-radius-lg',
  '--campus-card-padding',
  '--campus-section-gap',
  '--campus-tab-reserve',
]) {
  assert.ok(appStyle.includes(token), `missing shared layout token ${token}`)
}

for (const file of [
  'miniprogram/components/campus-header/campus-header.ts',
  'miniprogram/components/secondary-nav/secondary-nav.ts',
]) {
  const source = read(file)
  assert.match(source, /getMiniProgramLayoutMetrics/, `${file} must consume shared layout metrics`)
}

console.log('PASS shared layout tokens and menu-safe navigation contracts')

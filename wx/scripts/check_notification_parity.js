const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..', 'miniprogram', 'package-campus', 'pages', 'notices')
const ts = fs.readFileSync(path.join(root, 'notices.ts'), 'utf8')
const wxml = fs.readFileSync(path.join(root, 'notices.wxml'), 'utf8')

for (const behavior of ['importClipboard', 'selectSource', 'openLocalNotice', 'deleteLocalNotice', 'clearLocalNotices', 'updateResultField']) {
  assert.match(ts, new RegExp(`${behavior}\\s*\\(`), `missing notification behavior ${behavior}`)
}
for (const surface of ['通知来源', '平台能力说明', '读取剪贴板', '手动整理', '最近导入', '校园通知']) {
  assert.ok(wxml.includes(surface), `missing notification surface ${surface}`)
}
assert.match(wxml, /wx:for="\{\{sourceFilters\}\}"/, 'missing source filter controls')
assert.match(wxml, /bindtap="openLocalNotice"/, 'local inbox rows must open details')
console.log('PASS notification parity contracts')

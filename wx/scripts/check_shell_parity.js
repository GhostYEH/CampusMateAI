const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
for (const component of ['secondary-nav', 'state-view']) {
  for (const extension of ['json', 'ts', 'wxml', 'wxss']) {
    assert.ok(
      fs.existsSync(path.join(root, `miniprogram/components/${component}/${component}.${extension}`)),
      `missing ${component}.${extension}`,
    )
  }
}

const appStyle = fs.readFileSync(path.join(root, 'miniprogram/app.wxss'), 'utf8')
assert.match(appStyle, /--campus-primary:\s*#5B68F2/i)
assert.match(appStyle, /--campus-page-gutter:\s*16px/i)
assert.match(appStyle, /--campus-enter-duration:\s*300ms/i)

const appConfig = JSON.parse(fs.readFileSync(path.join(root, 'miniprogram/app.json'), 'utf8'))
assert.equal(appConfig.usingComponents['secondary-nav'], '/components/secondary-nav/secondary-nav')
assert.equal(appConfig.usingComponents['state-view'], '/components/state-view/state-view')

console.log('PASS shared Android-parity shell contracts')

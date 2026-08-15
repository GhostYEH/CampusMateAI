const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')

const config = JSON.parse(fs.readFileSync(path.join(root, 'project.config.json'), 'utf8'))
assert.equal(
  config.setting && config.setting.es6,
  true,
  'DevTools ES6 transform must be enabled for TypeScript output such as class fields',
)

console.log('PASS DevTools syntax compatibility contracts')

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const sourcePath = path.resolve(__dirname, '../miniprogram/services/home-banner.ts')
assert.ok(fs.existsSync(sourcePath), 'home banner mapper must exist')
const source = fs.readFileSync(sourcePath, 'utf8')
const output = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText
const moduleValue = { exports: {} }
vm.runInNewContext(output, { module: moduleValue, exports: moduleValue.exports }, { filename: sourcePath })

const { mapHomeBanner } = moduleValue.exports
const base = {
  id: 'banner-1', eyebrow: 'UPDATE', title: 'Feature', subtitle: 'Description',
  cta_label: 'Try', image_url: '/static/banner-images/feature.png', theme_key: 'INDIGO',
  sort_order: 10, status: 'PUBLISHED', starts_at: null, ends_at: null,
  created_at: '2026-08-26T00:00:00Z', updated_at: '2026-08-26T00:00:00Z',
}
const resolveImage = (url) => `https://api.example.test${url}`

const expected = {
  CPM_ASSISTANT: ['/pages/counselor/counselor', true, 'cpm'],
  CHAOXING: ['/package-campus/pages/notices/notices', false, 'learning'],
  EDU_SYSTEM: ['/package-academic/pages/edu/edu', false, 'academic'],
  TASKS: ['/pages/tasks/tasks', true, 'study'],
  COMMUNITY: ['/package-community/pages/community/community', false, 'community'],
}

for (const [actionKey, [route, tab, theme]] of Object.entries(expected)) {
  const slide = mapHomeBanner({ ...base, action_key: actionKey }, resolveImage)
  assert.equal(slide.route, route)
  assert.equal(slide.tab, tab)
  assert.equal(slide.theme, theme)
  assert.equal(slide.image, 'https://api.example.test/static/banner-images/feature.png')
  assert.equal(slide.button, 'Try')
}

const unknown = mapHomeBanner({ ...base, action_key: 'REMOVED_MODULE' }, resolveImage)
assert.equal(unknown.route, '')
assert.equal(unknown.tab, false)

console.log('PASS home banner mapping')

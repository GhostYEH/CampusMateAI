const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const matrix = JSON.parse(fs.readFileSync(path.join(root, 'parity/feature-matrix.json'), 'utf8'))
const allowed = new Set(['ALIGNED', 'PARTIAL', 'MISSING', 'PLATFORM_LIMITED', 'BLOCKED'])
assert.ok(Array.isArray(matrix.features) && matrix.features.length >= 30, 'parity matrix must cover the native student surface')
const ids = new Set()
for (const feature of matrix.features) {
  assert.ok(feature.id && !ids.has(feature.id), `duplicate or empty feature id ${feature.id}`)
  assert.ok(allowed.has(feature.status), `invalid status for ${feature.id}`)
  if (feature.status !== 'ALIGNED') assert.ok(feature.gap || feature.fallback, `${feature.id} needs a gap or fallback`)
  ids.add(feature.id)
}
for (const required of ['notifications', 'system-notification-listener', 'counselor-chat', 'local-expression', 'local-study-state', 'tasks', 'edu-system', 'community', 'qr-login']) {
  assert.ok(ids.has(required), `missing parity feature ${required}`)
}
console.log(`PASS full parity matrix: ${matrix.features.length} features`)

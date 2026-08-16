const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const repository = fs.readFileSync(path.join(root, 'miniprogram/services/repository.ts'), 'utf8')

for (const endpoint of [
  '/student/exams',
  '/student/classrooms',
  '/community/posts',
  '/student/lost-found',
  '/activities',
  '/personal-hub/files',
  '/personal-hub/favorites',
  '/universities',
  '/student/service-requests',
]) {
  assert.match(repository, new RegExp(endpoint.replaceAll('/', '\\/')), `missing real backend endpoint ${endpoint}`)
}

console.log('PASS student tool backend contracts')

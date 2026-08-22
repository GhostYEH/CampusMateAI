const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const appConfig = JSON.parse(fs.readFileSync(path.join(root, 'miniprogram/app.json'), 'utf8'))
const home = [
  'miniprogram/pages/index/index.wxml',
  'miniprogram/pages/index/index.ts',
].map((file) => fs.readFileSync(path.join(root, file), 'utf8')).join('\n')

for (const route of [
  'package-campus/pages/exams/exams',
  'package-campus/pages/classrooms/classrooms',
  'package-community/pages/community/community',
  'package-study/pages/study/study',
  'package-community/pages/lostfound/lostfound',
]) {
  const configured = appConfig.subPackages
    .flatMap(({ root, pages }) => pages.map((page) => `${root}/${page}`))
  assert.ok(configured.includes(route), `missing Android home destination ${route}`)
}

for (const label of ['考试安排', '空教室', '校园社区', '专注自习', '失物招领']) {
  assert.match(home, new RegExp(label), `home is missing ${label}`)
}

console.log('PASS primary Android route contracts')

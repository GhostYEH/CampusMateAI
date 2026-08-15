const fs = require('fs')
const path = require('path')

const root = path.resolve(__dirname, '..')
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')
const repository = read('miniprogram/services/repository.ts')
const noticesPage = read('miniprogram/pages/notices/notices.ts')
const indexPage = read('miniprogram/pages/index/index.ts')
const coursesPage = read('miniprogram/pages/courses/courses.ts')
const tabBar = read('miniprogram/custom-tab-bar/index.ts')
const studyPage = read('miniprogram/pages/study/study.ts')
const tasksPage = read('miniprogram/pages/tasks/tasks.ts')
const noticesMarkup = read('miniprogram/pages/notices/notices.wxml')
const loginStyle = read('miniprogram/pages/login/login.wxss')

const checks = [
  ['personal tasks use backend /tasks route', repository.includes("'/tasks'")],
  ['notice extraction sends content', /extract-multi[\s\S]*\{\s*content/.test(repository)],
  ['notice extraction maps multi-task response', repository.includes('response.tasks.map')],
  ['counselor uses conversation_id', repository.includes('conversation_id')],
  ['counselor explicitly requests non-stream response', /stream:\s*false/.test(repository)],
  ['refresh token is persisted', repository.includes('refreshToken')],
  ['401 can refresh access token', repository.includes("'/auth/refresh'")],
  ['courses expose an async real-data method', repository.includes('getCoursesAsync')],
  ['notices expose an async real-data method', repository.includes('getNoticesAsync')],
  ['notice save waits for backend completion', /async saveTask[\s\S]*await repository/.test(noticesPage)],
  ['home loads remote-capable tasks', indexPage.includes('getTasksAsync')],
  ['courses page loads remote-capable courses', coursesPage.includes('getCoursesAsync')],
  ['tab badge loads remote-capable tasks', tabBar.includes('getTasksAsync')],
  ['student app defaults to remote backend mode', /mockMode:\s*false/.test(repository)],
  ['student app defaults to active LAN backend', repository.includes("apiBaseUrl: 'http://192.168.1.14:8000'")],
  ['repository exposes current connection state', repository.includes('getConnectionState()')],
  ['repository exposes a real backend probe', repository.includes('probeRealBackend()')],
  ['repository can test backend health', repository.includes('checkBackendHealth')],
  ['repository supports real study sessions', repository.includes('startStudySession')
    && repository.includes('pauseStudySession')
    && repository.includes('finishStudySession')],
  ['study page uses backend sessions', studyPage.includes('startStudySession')],
  ['study page restores backend active session', studyPage.includes('getActiveStudySession')],
  ['study page exposes failed finish retry state', studyPage.includes("status: 'finishError'")],
  ['logout does not depend on current mock setting', !repository.includes('!this.getSettings().mockMode && refreshToken')],
  ['logout does not rotate an expired token', /\/auth\/logout[\s\S]*retryAfterRefresh:\s*false/.test(repository)],
  ['logout revokes a freshly rotated token', /async logout[\s\S]*refreshAccessToken[\s\S]*latestRefreshToken/.test(repository)],
  ['invalid manual deadlines are rejected', repository.includes('无法识别截止时间')],
  ['real course filters are derived from returned data', coursesPage.includes("filters: ['全部', ...courseTypes]" )],
  ['task load errors expose backend message', /catch \(error\)[\s\S]*error instanceof Error/.test(tasksPage)],
  ['notice page renders a dedicated error state', noticesMarkup.includes('wx:elif="{{error}}"')],
  ['home tolerates partial backend failures', indexPage.includes('Promise.allSettled')],
  ['login uses WeChat-compatible viewport sizing', loginStyle.includes('height:100vh')
    && !loginStyle.includes('100dvh')],
]

const failed = checks.filter(([, passed]) => !passed)
if (failed.length) {
  for (const [name] of failed) console.error(`FAIL ${name}`)
  process.exit(1)
}

console.log(`PASS ${checks.length} backend integration contracts`)

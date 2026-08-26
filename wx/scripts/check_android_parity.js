const fs = require('fs')
const path = require('path')

const root = path.resolve(__dirname, '..', 'miniprogram')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')

const contracts = [
  ['app.wxss', '--primary: #5b68f2', '全局主色必须与安卓端一致'],
  ['app.wxss', '--primary-soft: #eff0ff', '全局柔和主色必须与安卓端一致'],
  ['custom-tab-bar/index.wxss', 'border-radius: 60rpx', '底栏必须使用安卓式胶囊外形'],
  ['pages/index/index.wxml', 'class="quick-card', '首页必须包含五项快捷服务区'],
  ['pages/index/index.wxml', 'class="today-card', '首页必须包含安卓式今日课程卡'],
  ['pages/courses/courses.wxml', 'class="next-course-card', '课程页必须包含下一节课主卡'],
  ['pages/tasks/tasks.wxml', 'class="task-summary', '待办页必须包含汇总卡'],
  ['pages/counselor/counselor.wxml', 'class="cpm-stage', '助手页必须包含 CPM 数字人舞台'],
  ['pages/profile/profile.wxml', 'class="profile-hero', '我的页面必须包含紫色身份头图区'],
  ['pages/login/login.wxml', 'src="/assets/campus-login.jpg"', '登录页必须使用随包校园视觉资源'],
]

const failures = contracts.filter(([file, token]) => !read(file).toLowerCase().includes(token))

if (failures.length) {
  for (const [file, , message] of failures) {
    console.error(`FAIL ${file}: ${message}`)
  }
  process.exit(1)
}

console.log(`PASS ${contracts.length} Android parity contracts`)

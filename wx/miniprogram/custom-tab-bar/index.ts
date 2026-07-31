import { repository } from '../services/repository'

interface TabItem {
  pagePath: string
  text: string
  icon: string
}

Component({
  data: {
    selected: 0,
    darkMode: false,
    taskCount: 0,
    list: [
      { pagePath: '/pages/index/index', text: '首页', icon: 'home' },
      { pagePath: '/pages/courses/courses', text: '课程', icon: 'courses' },
      { pagePath: '/pages/tasks/tasks', text: '待办', icon: 'tasks' },
      { pagePath: '/pages/counselor/counselor', text: 'AI 导员', icon: 'counselor' },
      { pagePath: '/pages/profile/profile', text: '我的', icon: 'profile' },
    ] as TabItem[],
  },
  lifetimes: {
    attached() {
      this.sync()
    },
  },
  pageLifetimes: {
    show() {
      this.sync()
    },
  },
  methods: {
    sync() {
      const pages = getCurrentPages()
      const currentRoute = pages.length ? `/${pages[pages.length - 1].route}` : ''
      const selected = this.data.list.findIndex((item) => item.pagePath === currentRoute)
      this.setData({
        selected: selected < 0 ? 0 : selected,
        darkMode: repository.getSettings().darkMode,
        taskCount: repository.getTasks().filter((task) => !task.done).length,
      })
    },
    switchTab(event: WechatMiniprogram.TouchEvent) {
      const pagePath = event.currentTarget.dataset.path as string
      if (!pagePath) return
      wx.switchTab({ url: pagePath })
    },
  },
})

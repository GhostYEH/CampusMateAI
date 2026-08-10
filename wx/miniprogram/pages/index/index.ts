import { repository } from '../../services/repository'
import { CampusTask, Course, User } from '../../services/types'

interface QuickAction {
  label: string
  detail: string
  route: string
  tab: boolean
  tone: string
  icon: string
}

interface DeadlineTask extends CampusTask {
  icon: string
  tone: string
}

Page({
  data: {
    statusBarHeight: 24,
    user: null as User | null,
    todayLabel: '',
    deadlineTasks: [] as DeadlineTask[],
    courses: [] as Course[],
    pendingCount: 0,
    completedCount: 0,
    weekProgress: 0,
    reduceMotion: false,
    darkMode: false,
    quickActions: [
      {
        label: '课程表',
        detail: '查看本周安排',
        route: '/pages/courses/courses',
        tab: true,
        tone: 'blue',
        icon: 'quick-calendar',
      },
      {
        label: '校园通知',
        detail: '整理长通知',
        route: '/pages/notices/notices',
        tab: false,
        tone: 'teal',
        icon: 'quick-notice',
      },
      {
        label: '学习陪伴',
        detail: '开始一段专注',
        route: '/pages/study/study',
        tab: false,
        tone: 'orange',
        icon: 'quick-study',
      },
      {
        label: 'AI 校园助手',
        detail: '问问校园里的事',
        route: '/pages/counselor/counselor',
        tab: true,
        tone: 'navy',
        icon: 'quick-counselor',
      },
    ] as QuickAction[],
  },
  onLoad() {
    this.setData({
      statusBarHeight: wx.getWindowInfo().statusBarHeight || 24,
      todayLabel: this.formatToday(),
    })
  },
  onShow() {
    const user = repository.getSession()
    if (!user) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }

    const tasks = repository.getTasks()
    const pendingTasks = tasks.filter((task) => !task.done)
    const settings = repository.getSettings()
    const courses = repository.getCourses().slice(0, 2)
    const completedCount = tasks.length - pendingTasks.length
    const deadlineTasks = pendingTasks.slice(0, 3).map((task, index) => ({
      ...task,
      icon: index === 0 ? 'deadline-blue' : 'deadline-orange',
      tone: index === 0 ? 'blue' : 'orange',
    }))

    this.setData({
      user,
      courses,
      deadlineTasks,
      pendingCount: pendingTasks.length,
      completedCount,
      weekProgress: tasks.length ? Math.round((completedCount / tasks.length) * 100) : 0,
      reduceMotion: settings.reduceMotion,
      darkMode: settings.darkMode,
    })
    wx.nextTick(() => {
      const tabBar = this.getTabBar()
      if (tabBar) tabBar.sync()
    })
  },
  openProfile() {
    wx.switchTab({ url: '/pages/profile/profile' })
  },
  openNotice() {
    wx.navigateTo({ url: '/pages/notices/notices' })
  },
  openAction(event: WechatMiniprogram.TouchEvent) {
    const route = event.currentTarget.dataset.route as string
    const tab = event.currentTarget.dataset.tab as boolean
    if (!route) return
    if (tab) {
      wx.switchTab({ url: route })
    } else {
      wx.navigateTo({ url: route })
    }
  },
  openTasks() {
    wx.switchTab({ url: '/pages/tasks/tasks' })
  },
  openCourses() {
    wx.switchTab({ url: '/pages/courses/courses' })
  },
  formatToday(): string {
    const date = new Date()
    const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    return `${date.getMonth() + 1}月${date.getDate()}日 · ${weekDays[date.getDay()]}`
  },
})

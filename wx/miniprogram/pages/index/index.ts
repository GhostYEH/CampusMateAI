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
        label: '考试安排', detail: '', route: '/pages/exams/exams', tab: false, tone: 'indigo',
        icon: 'quick-calendar',
      },
      {
        label: '空教室', detail: '', route: '/pages/classrooms/classrooms', tab: false, tone: 'blue', icon: 'quick-classroom',
      },
      {
        label: '校园社区', detail: '', route: '/pages/community/community', tab: false, tone: 'teal', icon: 'quick-community',
      },
      {
        label: '专注自习', detail: '', route: '/pages/study/study', tab: false, tone: 'orange', icon: 'quick-study',
      },
      { label: '失物招领', detail: '', route: '/pages/lostfound/lostfound', tab: false, tone: 'violet', icon: 'quick-lost' },
    ] as QuickAction[],
  },
  onLoad() {
    this.setData({
      statusBarHeight: wx.getWindowInfo().statusBarHeight || 24,
      todayLabel: this.formatToday(),
    })
  },
  async onShow() {
    const user = repository.getSession()
    if (!user) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }

    const settings = repository.getSettings()
    try {
      const [tasksResult, coursesResult] = await Promise.allSettled([
        repository.getTasksAsync(),
        repository.getCoursesAsync(),
      ])
      if (tasksResult.status === 'rejected' && coursesResult.status === 'rejected') {
        throw tasksResult.reason
      }
      const tasks = tasksResult.status === 'fulfilled' ? tasksResult.value : []
      const allCourses = coursesResult.status === 'fulfilled' ? coursesResult.value : []
      const pendingTasks = tasks.filter((task) => !task.done)
      const courses = allCourses.slice(0, 2)
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
      if (tasksResult.status === 'rejected' || coursesResult.status === 'rejected') {
        wx.showToast({ title: '部分校园数据暂未加载', icon: 'none' })
      }
    } catch (error) {
      this.setData({
        user,
        courses: [],
        deadlineTasks: [],
        pendingCount: 0,
        completedCount: 0,
        weekProgress: 0,
        reduceMotion: settings.reduceMotion,
        darkMode: settings.darkMode,
      })
      wx.showToast({
        title: error instanceof Error ? error.message : '首页数据加载失败',
        icon: 'none',
      })
    }
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
    if (!route) {
      wx.showToast({ title: '该功能正在接入小程序', icon: 'none' })
      return
    }
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

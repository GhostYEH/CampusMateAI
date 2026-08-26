import { repository } from '../../services/repository'
import { CampusTask, Course, User } from '../../services/types'
import { HeroSlide, mapHomeBanner } from '../../services/home-banner'

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
    heroCurrent: 0,
    heroSlides: [] as HeroSlide[],
    quickActions: [
      {
        label: '考试安排', detail: '', route: '/package-campus/pages/exams/exams', tab: false, tone: 'indigo',
        icon: 'quick-calendar',
      },
      {
        label: '空教室', detail: '', route: '/package-campus/pages/classrooms/classrooms', tab: false, tone: 'blue', icon: 'quick-classroom',
      },
      {
        label: '校园社区', detail: '', route: '/package-community/pages/community/community', tab: false, tone: 'teal', icon: 'quick-community',
      },
      {
        label: '专注自习', detail: '', route: '/package-study/pages/study/study', tab: false, tone: 'orange', icon: 'quick-study',
      },
      { label: '失物招领', detail: '', route: '/package-community/pages/lostfound/lostfound', tab: false, tone: 'violet', icon: 'quick-lost' },
    ] as QuickAction[],
  },
  onLoad() {
    const cachedBanners = repository.getCachedHomeBanners()
    this.setData({
      statusBarHeight: wx.getWindowInfo().statusBarHeight || 24,
      todayLabel: this.formatToday(),
      heroSlides: cachedBanners.map((item) => mapHomeBanner(item, (url) => repository.resolveAssetUrl(url))),
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
      const [tasksResult, coursesResult, bannersResult] = await Promise.allSettled([
        repository.getTasksAsync(),
        repository.getCoursesAsync(),
        repository.getHomeBannersAsync(),
      ])
      if (tasksResult.status === 'rejected' && coursesResult.status === 'rejected') {
        throw tasksResult.reason
      }
      const tasks = tasksResult.status === 'fulfilled' ? tasksResult.value : []
      const allCourses = coursesResult.status === 'fulfilled' ? coursesResult.value : []
      const heroSlides = bannersResult.status === 'fulfilled'
        ? bannersResult.value.map((item) => mapHomeBanner(item, (url) => repository.resolveAssetUrl(url)))
        : this.data.heroSlides
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
      heroSlides,
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
      heroSlides: this.data.heroSlides,
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
    wx.navigateTo({ url: '/package-campus/pages/notices/notices' })
  },
  onHeroChange(event: WechatMiniprogram.CustomEvent<{ current: number }>) {
    this.setData({ heroCurrent: Number(event.detail.current) })
  },
  selectHero(event: WechatMiniprogram.TouchEvent) {
    const index = Number(event.currentTarget.dataset.index)
    if (!Number.isInteger(index) || index < 0 || index >= this.data.heroSlides.length) return
    this.setData({ heroCurrent: index })
  },
  openHero(event: WechatMiniprogram.TouchEvent) {
    this.openAction(event)
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

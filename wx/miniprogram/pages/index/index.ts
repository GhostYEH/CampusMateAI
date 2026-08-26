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

interface HeroSlide {
  id: string
  eyebrow: string
  title: string
  subtitle: string
  button: string
  route: string
  tab: boolean
  theme: 'cpm' | 'learning' | 'academic' | 'study' | 'community'
  art?: string
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
    heroSlides: [
      {
        id: 'cpm', eyebrow: '新功能上线', title: '你的 CPM 伙伴已上线',
        subtitle: '小灵随时陪你聊课程、校园服务和学习计划', button: '和小灵聊聊',
        route: '/pages/counselor/counselor', tab: true, theme: 'cpm', art: '/assets/secondary/ai-robot.png',
      },
      {
        id: 'learning', eyebrow: '学习通接入', title: '学习通，一键接入',
        subtitle: '学习通课程、作业与通知，及时同步到你的校园首页', button: '查看学习通',
        route: '/package-campus/pages/notices/notices', tab: false, theme: 'learning',
      },
      {
        id: 'academic', eyebrow: '教务系统接入', title: '教务系统已支持',
        subtitle: '连接学校教务系统，课表和成绩都能在这里查看', button: '连接教务系统',
        route: '/package-academic/pages/edu/edu', tab: false, theme: 'academic',
      },
      {
        id: 'study', eyebrow: '专注学习', title: '期末复习计划',
        subtitle: '待办、复习与专注时段，帮你稳稳推进每一步', button: '打开学习计划',
        route: '/pages/tasks/tasks', tab: true, theme: 'study',
      },
      {
        id: 'community', eyebrow: '校园社区', title: '校园社区，发现新鲜事',
        subtitle: '校园动态、经验分享和新鲜话题，等你一起加入', button: '逛逛校园社区',
        route: '/package-community/pages/community/community', tab: false, theme: 'community',
      },
    ] as HeroSlide[],
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

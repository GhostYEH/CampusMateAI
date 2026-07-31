import { repository } from '../../services/repository'
import { CampusTask, User } from '../../services/types'

interface QuickAction {
  label: string
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
    deadlineTasks: [] as DeadlineTask[],
    pendingCount: 0,
    weekProgress: 72,
    reduceMotion: false,
    darkMode: false,
    quickActions: [
      { label: '课程表', route: '/pages/courses/courses', tab: true, tone: 'purple', icon: 'quick-calendar' },
      { label: '待办任务', route: '/pages/tasks/tasks', tab: true, tone: 'blue', icon: 'quick-task' },
      { label: '校园通知', route: '/pages/notices/notices', tab: false, tone: 'teal', icon: 'quick-notice' },
      { label: '学习陪伴', route: '/pages/study/study', tab: false, tone: 'orange', icon: 'quick-study' },
      { label: 'AI 导员', route: '/pages/counselor/counselor', tab: true, tone: 'purple', icon: 'quick-counselor' },
    ] as QuickAction[],
  },
  onLoad() {
    this.setData({ statusBarHeight: wx.getWindowInfo().statusBarHeight || 24 })
  },
  onReady() {
    this.drawProgress()
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
    const deadlineTasks = pendingTasks.slice(0, 2).map((task, index) => ({
      ...task,
      icon: index === 0 ? 'deadline-blue' : 'deadline-orange',
      tone: index === 0 ? 'blue' : 'orange',
    }))
    this.setData({
      user,
      deadlineTasks,
      pendingCount: pendingTasks.length,
      reduceMotion: settings.reduceMotion,
      darkMode: settings.darkMode,
    })
    wx.nextTick(() => {
      this.drawProgress()
      const tabBar = this.getTabBar()
      if (tabBar) tabBar.sync()
    })
  },
  openProfile() {
    wx.switchTab({ url: '/pages/profile/profile' })
  },
  openAction(event: WechatMiniprogram.TouchEvent) {
    const route = event.currentTarget.dataset.route as string
    const tab = event.currentTarget.dataset.tab as boolean
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
  drawProgress() {
    const query = wx.createSelectorQuery()
    query.select('#progressCanvas').fields({ node: true, size: true }).exec((results) => {
      const result = results[0] as unknown as {
        node?: {
          width: number
          height: number
          getContext: (kind: string) => WechatMiniprogram.CanvasContext
        }
        width?: number
        height?: number
      }
      if (!result || !result.node || !result.width || !result.height) return
      const canvas = result.node
      const context = canvas.getContext('2d') as unknown as {
        scale: (x: number, y: number) => void
        clearRect: (x: number, y: number, width: number, height: number) => void
        beginPath: () => void
        arc: (x: number, y: number, radius: number, start: number, end: number) => void
        stroke: () => void
        fillRect: (x: number, y: number, width: number, height: number) => void
        lineWidth: number
        lineCap: string
        strokeStyle: string
        fillStyle: string
      }
      const pixelRatio = wx.getWindowInfo().pixelRatio || 1
      const width = result.width
      const height = result.height
      canvas.width = width * pixelRatio
      canvas.height = height * pixelRatio
      context.scale(pixelRatio, pixelRatio)
      context.clearRect(0, 0, width, height)

      const centerX = width / 2
      const centerY = height / 2
      const radius = Math.min(width, height) / 2 - 6
      context.lineWidth = 6
      context.lineCap = 'round'
      context.strokeStyle = this.data.darkMode ? '#203F50' : '#E6EEF4'
      context.beginPath()
      context.arc(centerX, centerY, radius, 0, Math.PI * 2)
      context.stroke()

      context.strokeStyle = this.data.darkMode ? '#7182FF' : '#5268EB'
      context.beginPath()
      context.arc(
        centerX,
        centerY,
        radius,
        -Math.PI / 2,
        -Math.PI / 2 + Math.PI * 2 * (this.data.weekProgress / 100),
      )
      context.stroke()

      context.fillStyle = this.data.darkMode ? '#7182FF' : '#5268EB'
      const barWidth = 5
      const gap = 3
      const baseY = centerY + 16
      context.fillRect(centerX - barWidth - gap, baseY - 18, barWidth, 18)
      context.fillRect(centerX, baseY - 32, barWidth, 32)
      context.fillRect(centerX + barWidth + gap, baseY - 24, barWidth, 24)
    })
  },
})

import { repository } from '../../services/repository'
import { Course } from '../../services/types'

Page({
  data: {
    courses: [] as Course[],
    filtered: [] as Course[],
    filter: '全部',
    filters: ['全部', '专业必修', '专业核心', '学科基础', '公共基础'],
    loading: true,
    error: '',
    mockMode: true,
    reduceMotion: false,
    darkMode: false,
  },
  onShow() {
    this.load()
    wx.nextTick(() => {
      const tabBar = this.getTabBar()
      if (tabBar) tabBar.sync()
    })
  },
  load() {
    const settings = repository.getSettings()
    this.setData({
      loading: true,
      error: '',
      mockMode: settings.mockMode,
      reduceMotion: settings.reduceMotion,
      darkMode: settings.darkMode,
    })
    setTimeout(() => {
      try {
        const courses = repository.getCourses()
        this.setData({ courses, filtered: courses, loading: false })
      } catch {
        this.setData({ loading: false, error: '课程暂时加载失败' })
      }
    }, settings.reduceMotion ? 0 : 180)
  },
  chooseFilter(event: WechatMiniprogram.TouchEvent) {
    const filter = event.currentTarget.dataset.filter as string
    const filtered = filter === '全部'
      ? this.data.courses
      : this.data.courses.filter((course) => course.type === filter)
    this.setData({ filter, filtered })
  },
  scrollToCourses() {
    wx.pageScrollTo({ scrollTop: 0, duration: 180 })
  },
  openDetail() {
    const course = this.data.courses[0]
    if (!course) return
    wx.showModal({
      title: course.name,
      content: `${course.code}\n${course.teacher} · ${course.location}\n${course.weekday} ${course.time}`,
      showCancel: false,
      confirmText: '知道了',
    })
  },
})

import { repository } from '../../services/repository'
import { Course } from '../../services/types'
import { buildCurrentWeek } from '../../services/date-utils'

Page({
  data: {
    courses: [] as Course[],
    filtered: [] as Course[],
    courseTypeCount: 0,
    filter: '全部',
    filters: ['全部', '今日课程', '专业课', '公共课', '实验课'],
    loading: true,
    error: '',
    mockMode: true,
    reduceMotion: false,
    darkMode: false,
    weekDays: buildCurrentWeek(),
  },
  onShow() {
    this.load()
    wx.nextTick(() => {
      const tabBar = this.getTabBar()
      if (tabBar) tabBar.sync()
    })
  },
  async load() {
    const settings = repository.getSettings()
    this.setData({
      loading: true,
      error: '',
      mockMode: settings.mockMode,
      reduceMotion: settings.reduceMotion,
      darkMode: settings.darkMode,
    })
    try {
      if (!settings.reduceMotion) await new Promise((resolve) => setTimeout(resolve, 180))
      const courses = await repository.getCoursesAsync()
      const courseTypes = Array.from(new Set(courses.map((course) => course.type)))
        this.setData({
          courses,
          filtered: courses,
          filters: ['全部', '今日课程', '专业课', '公共课', '实验课'],
          filter: '全部',
          courseTypeCount: courseTypes.length,
          loading: false,
        })
    } catch (error) {
      this.setData({
        loading: false,
        courses: [],
        filtered: [],
        error: error instanceof Error ? error.message : '课程暂时加载失败',
      })
    }
  },
  chooseFilter(event: WechatMiniprogram.TouchEvent) {
    const filter = event.currentTarget.dataset.filter as string
    const weekday = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][new Date().getDay()]
    const filtered = this.data.courses.filter((course) => {
      const text = `${course.name} ${course.type} ${course.location}`
      if (filter === '全部') return true
      if (filter === '今日课程') return course.weekday.includes(weekday)
      if (filter === '公共课') return /英语|体育|思政|公共|通识/.test(text)
      if (filter === '实验课') return /实验|实训/.test(text)
      if (filter === '专业课') return !/英语|体育|思政|公共|通识/.test(text)
      return course.type === filter
    })
    this.setData({ filter, filtered })
  },
  scrollToCourses() {
    wx.pageScrollTo({ scrollTop: 0, duration: 180 })
  },
  openDetail(event?: WechatMiniprogram.TouchEvent) {
    const code = event
      ? event.currentTarget.dataset.code as string | undefined
      : undefined
    const course = this.data.courses.find((item) => item.code === code) || this.data.courses[0]
    if (!course) return
    wx.showModal({
      title: course.name,
      content: `${course.code}\n${course.teacher} · ${course.location}\n${course.weekday} ${course.time}`,
      showCancel: false,
      confirmText: '知道了',
    })
  },
})

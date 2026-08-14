import { repository } from '../../services/repository'
import { Course } from '../../services/types'
import { buildCurrentWeek } from '../../services/date-utils'

Page({
  data: {
    courses: [] as Course[],
    filtered: [] as Course[],
    courseTypeCount: 0,
    filter: '全部',
    filters: ['全部', '专业必修', '专业核心', '学科基础', '公共基础'],
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
          filters: ['全部', ...courseTypes],
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
    const filtered = filter === '全部'
      ? this.data.courses
      : this.data.courses.filter((course) => course.type === filter)
    this.setData({ filter, filtered })
  },
  scrollToCourses() {
    wx.pageScrollTo({ scrollTop: 0, duration: 180 })
  },
  openDetail(event?: WechatMiniprogram.TouchEvent) {
    const code = event?.currentTarget.dataset.code as string | undefined
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

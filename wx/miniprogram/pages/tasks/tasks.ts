import { repository } from '../../services/repository'
import { CampusTask } from '../../services/types'

Page({
  data: {
    tasks: [] as CampusTask[],
    filtered: [] as CampusTask[],
    filter: '待完成',
    filters: ['待完成', '已完成', '全部'],
    pendingCount: 0,
    progress: 0,
    loading: true,
    showAdd: false,
    titleInput: '',
    dueInput: '',
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
      mockMode: settings.mockMode,
      reduceMotion: settings.reduceMotion,
      darkMode: settings.darkMode,
    })
    setTimeout(() => {
      this.refresh(repository.getTasks(), this.data.filter)
      this.setData({ loading: false })
    }, settings.reduceMotion ? 0 : 160)
  },
  refresh(tasks: CampusTask[], filter: string) {
    const pendingCount = tasks.filter((task) => !task.done).length
    const filtered = tasks.filter((task) => {
      if (filter === '已完成') return task.done
      if (filter === '全部') return true
      return !task.done
    })
    this.setData({
      tasks,
      filtered,
      filter,
      pendingCount,
      progress: tasks.length ? Math.round(((tasks.length - pendingCount) / tasks.length) * 100) : 0,
    })
    wx.nextTick(() => {
      const tabBar = this.getTabBar()
      if (tabBar) tabBar.sync()
    })
  },
  chooseFilter(event: WechatMiniprogram.TouchEvent) {
    this.refresh(this.data.tasks, event.currentTarget.dataset.filter as string)
  },
  toggleTask(event: WechatMiniprogram.TouchEvent) {
    const tasks = repository.toggleTask(Number(event.currentTarget.dataset.id))
    this.refresh(tasks, this.data.filter)
    wx.showToast({ title: '状态已更新', icon: 'success' })
  },
  deleteTask(event: WechatMiniprogram.TouchEvent) {
    const id = Number(event.currentTarget.dataset.id)
    wx.showModal({
      title: '删除这项待办？',
      content: '删除后无法恢复。',
      confirmText: '删除',
      confirmColor: '#C25450',
      success: (result) => {
        if (!result.confirm) return
        this.refresh(repository.deleteTask(id), this.data.filter)
        wx.showToast({ title: '已删除', icon: 'success' })
      },
    })
  },
  openAdd() {
    this.setData({ showAdd: true, titleInput: '', dueInput: '' })
  },
  closeAdd() {
    this.setData({ showAdd: false })
  },
  stopPropagation() {
    return
  },
  onTitleInput(event: WechatMiniprogram.Input) {
    this.setData({ titleInput: event.detail.value })
  },
  onDueInput(event: WechatMiniprogram.Input) {
    this.setData({ dueInput: event.detail.value })
  },
  addTask() {
    const title = this.data.titleInput.trim()
    if (!title) return
    const tasks = repository.addTask(title, this.data.dueInput.trim() || '待设置')
    this.refresh(tasks, this.data.filter)
    this.setData({ showAdd: false })
    wx.showToast({ title: '已添加待办', icon: 'success' })
  },
})

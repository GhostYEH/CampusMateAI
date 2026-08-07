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
  async load() {
    const settings = repository.getSettings()
    this.setData({
      loading: true,
      mockMode: settings.mockMode,
      reduceMotion: settings.reduceMotion,
      darkMode: settings.darkMode,
    })
    try {
      const tasks = await repository.getTasksAsync()
      this.refresh(tasks, this.data.filter)
    } catch (e) {
      wx.showToast({ title: '加载失败', icon: 'none' })
      this.refresh([], this.data.filter)
    } finally {
      this.setData({ loading: false })
    }
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
  async toggleTask(event: WechatMiniprogram.TouchEvent) {
    const id = event.currentTarget.dataset.id
    try {
      wx.showLoading({ title: '处理中' })
      const tasks = await repository.toggleTask(id)
      this.refresh(tasks, this.data.filter)
      wx.showToast({ title: '状态已更新', icon: 'success' })
    } catch (e) {
      wx.showToast({ title: '更新失败', icon: 'none' })
    }
  },
  deleteTask(event: WechatMiniprogram.TouchEvent) {
    const id = event.currentTarget.dataset.id
    wx.showModal({
      title: '删除这项待办？',
      content: '删除后无法恢复。',
      confirmText: '删除',
      confirmColor: '#C25450',
      success: async (result) => {
        if (!result.confirm) return
        try {
          wx.showLoading({ title: '处理中' })
          const tasks = await repository.deleteTask(id)
          this.refresh(tasks, this.data.filter)
          wx.showToast({ title: '已删除', icon: 'success' })
        } catch (e) {
          wx.showToast({ title: '删除失败', icon: 'none' })
        }
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
  async addTask() {
    const title = this.data.titleInput.trim()
    if (!title) return
    try {
      wx.showLoading({ title: '处理中' })
      const tasks = await repository.addTask(title, this.data.dueInput.trim() || '待设置')
      this.refresh(tasks, this.data.filter)
      this.setData({ showAdd: false })
      wx.showToast({ title: '已添加待办', icon: 'success' })
    } catch (e) {
      wx.showToast({ title: '添加失败', icon: 'none' })
    }
  },
})

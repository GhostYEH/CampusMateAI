import { repository } from '../../services/repository'

interface HubItem {
  id: string
  title: string
  subtitle: string
  meta: string
  icon: string
}

const CONFIG: Record<string, { title: string; subtitle: string; icon: string }> = {
  files: { title: '我的文件', subtitle: '校园材料与常用文档', icon: '/assets/icons/quick-notice.svg' },
  activities: { title: '校园活动', subtitle: '发现并参与校园生活', icon: '/assets/icons/quick-calendar.svg' },
  favorites: { title: '我的收藏', subtitle: '集中查看收藏的校园内容', icon: '/assets/icons/quick-counselor.svg' },
  help: { title: '帮助与反馈', subtitle: '提交问题并跟踪处理进度', icon: '/assets/icons/quick-task.svg' },
  university: { title: '我的大学', subtitle: '查看已连接的学校信息', icon: '/assets/icons/quick-counselor.svg' },
  academic: { title: '教务系统', subtitle: '查看已同步的课程与教务数据', icon: '/assets/icons/tab-courses-active-light.svg' },
}

Page({
  data: {
    kind: 'files',
    title: '我的大学',
    subtitle: '',
    icon: '/assets/icons/quick-notice.svg',
    loading: true,
    error: '',
    items: [] as HubItem[],
    showComposer: false,
    requestTitle: '',
    requestContent: '',
    sending: false,
    currentUniversityId: '',
    selectingUniversityId: '',
  },
  onLoad(query: Record<string, string | undefined>) {
    const kind = query.kind && CONFIG[query.kind] ? query.kind : 'files'
    const config = CONFIG[kind]
    this.setData({ kind, ...config })
    this.load()
  },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      let items: HubItem[] = []
      if (this.data.kind === 'files') {
        items = (await repository.getPersonalFilesAsync()).map((item) => ({ id: item.id, title: item.name, subtitle: item.category, meta: item.size_label || item.updated_at, icon: CONFIG.files.icon }))
      } else if (this.data.kind === 'activities') {
        items = (await repository.getActivitiesAsync()).map((item) => ({ id: item.id, title: item.title, subtitle: item.summary || item.location || '校园活动', meta: item.start_time || item.registration_deadline || '', icon: CONFIG.activities.icon }))
      } else if (this.data.kind === 'favorites') {
        items = (await repository.getFavoritesAsync()).map((item) => ({ id: item.id, title: item.title, subtitle: item.subtitle || item.type, meta: item.saved_at, icon: CONFIG.favorites.icon }))
      } else if (this.data.kind === 'university') {
        const session = repository.getSession()
        this.setData({ currentUniversityId: session?.universityId || '' })
        items = (await repository.getUniversitiesAsync()).map((item) => ({ id: item.id, title: item.name, subtitle: [item.province, item.city].filter(Boolean).join(' · ') || '学校信息', meta: '校园后端', icon: CONFIG.university.icon }))
      } else if (this.data.kind === 'academic') {
        items = (await repository.getCoursesAsync()).map((item) => ({ id: item.code, title: item.name, subtitle: `${item.teacher} · ${item.location}`, meta: `${item.weekday} ${item.time}`, icon: CONFIG.academic.icon }))
      } else {
        items = (await repository.getServiceRequestsAsync()).map((item) => ({ id: item.id, title: item.title, subtitle: item.content || item.kind, meta: item.status, icon: CONFIG.help.icon }))
      }
      this.setData({ items, loading: false })
    } catch (error) {
      this.setData({ loading: false, error: error instanceof Error ? error.message : '内容加载失败' })
    }
  },
  async onSelectUniversity(event: WechatMiniprogram.BaseEvent) {
    const id = event.currentTarget.dataset.id as string
    const name = event.currentTarget.dataset.name as string
    if (!id || id === this.data.currentUniversityId) return
    const confirm = await new Promise<boolean>((resolve) => {
      wx.showModal({
        title: '切换大学',
        content: `切换到 ${name} 后，论坛、失物招领和校园活动将切换到新学校。`,
        confirmText: '确认切换',
        success: (res) => resolve(res.confirm),
      })
    })
    if (!confirm) return
    this.setData({ selectingUniversityId: id })
    try {
      const result = await repository.selectUniversityAsync(id)
      this.setData({ currentUniversityId: result.university_id })
      wx.showToast({ title: '大学已切换', icon: 'success' })
    } catch (error) {
      wx.showToast({ title: error instanceof Error ? error.message : '切换失败', icon: 'none' })
    } finally {
      this.setData({ selectingUniversityId: '' })
    }
  },
  toggleComposer() {
    this.setData({ showComposer: !this.data.showComposer })
  },
  onRequestTitle(event: WechatMiniprogram.Input) {
    this.setData({ requestTitle: event.detail.value })
  },
  onRequestContent(event: WechatMiniprogram.Input) {
    this.setData({ requestContent: event.detail.value })
  },
  async submitRequest() {
    const title = this.data.requestTitle.trim()
    if (!title) {
      wx.showToast({ title: '请填写问题标题', icon: 'none' })
      return
    }
    this.setData({ sending: true })
    try {
      await repository.createServiceRequest('feedback', title, this.data.requestContent.trim())
      this.setData({ showComposer: false, requestTitle: '', requestContent: '' })
      await this.load()
      wx.showToast({ title: '已提交', icon: 'success' })
    } catch (error) {
      wx.showToast({ title: error instanceof Error ? error.message : '提交失败', icon: 'none' })
    } finally {
      this.setData({ sending: false })
    }
  },
})

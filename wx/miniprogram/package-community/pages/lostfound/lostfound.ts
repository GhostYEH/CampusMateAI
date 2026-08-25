import { repository } from '../../../services/repository'
import { LostFoundItem } from '../../../services/types'
import { getMiniProgramLayoutMetrics } from '../../../utils/layout'

interface LostFoundViewItem extends LostFoundItem {
  categoryLabel: string
  dateLabel: string
  image: string
}

Page({
  data: {
    statusBarHeight: 24,
    navContentHeight: 52,
    menuSafeRight: 12,
    actionTop: 78,
    loading: true,
    error: '',
    activeKind: 'lost',
    activeCategory: '全部',
    categories: ['全部', '证件卡片', '电子产品', '书籍资料', '生活用品', '其他'],
    activeLocation: '全部地点',
    locations: ['全部地点', '图书馆', '教学楼', '宿舍区', '食堂', '运动场'],
    activeSort: '最新优先',
    sorts: ['最新优先', '最早优先'],
    query: '',
    mineOnly: false,
    items: [] as LostFoundItem[],
    filtered: [] as LostFoundViewItem[],
    showPublish: false,
    publishing: false,
    publishKind: 'lost',
    publishTitle: '',
    publishContent: '',
    publishLocation: '',
    publishContact: '',
    needsUniversity: false,
  },

  onLoad() {
    const metrics = getMiniProgramLayoutMetrics()
    this.setData({
      statusBarHeight: metrics.statusBarHeight,
      navContentHeight: Math.max(52, metrics.navContentHeight),
      menuSafeRight: metrics.menuSafeRight,
      actionTop: metrics.statusBarHeight + metrics.navContentHeight + 6,
    })
  },

  onShow() {
    this.load()
  },

  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const items = await repository.getLostFoundAsync(this.data.mineOnly)
      this.setData({ items, loading: false })
      this.applyFilter()
    } catch (error) {
      const message = error instanceof Error ? error.message : '失物招领加载失败'
      const needsUniversity = message.includes('409') || message.includes('学校') || message.includes('UNIVERSITY_REQUIRED')
      this.setData({
        loading: false,
        error: needsUniversity
          ? '当前账号尚未关联学校，关联后即可查看全校失物信息'
          : message,
        needsUniversity,
        filtered: [],
      })
    }
  },

  goSelectUniversity() {
    wx.navigateTo({ url: '/pages/hub/hub?kind=university' })
  },

  goBack() {
    wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/index/index' }) })
  },

  toggleMine() {
    this.setData({ mineOnly: !this.data.mineOnly }, () => this.load())
  },

  chooseKind(event: WechatMiniprogram.TouchEvent) {
    this.setData({ activeKind: event.currentTarget.dataset.kind as 'lost' | 'found' })
    this.applyFilter()
  },

  chooseCategory(event: WechatMiniprogram.TouchEvent) {
    this.setData({ activeCategory: event.currentTarget.dataset.category as string })
    this.applyFilter()
  },

  chooseLocation(event: WechatMiniprogram.PickerChange) {
    this.setData({ activeLocation: this.data.locations[Number(event.detail.value)] })
    this.applyFilter()
  },

  chooseSort(event: WechatMiniprogram.PickerChange) {
    this.setData({ activeSort: this.data.sorts[Number(event.detail.value)] })
    this.applyFilter()
  },

  onQuery(event: WechatMiniprogram.Input) {
    this.setData({ query: event.detail.value })
    this.applyFilter()
  },

  applyFilter() {
    const query = this.data.query.trim().toLowerCase()
    const filtered = this.data.items
      .filter((item) => {
        const haystack = `${item.title} ${item.content || ''} ${item.location || ''}`.toLowerCase()
        const categoryLabel = this.categoryFor(item)
        const kindMatched = item.kind === this.data.activeKind
        const queryMatched = !query || haystack.includes(query)
        const categoryMatched = this.data.activeCategory === '全部' || categoryLabel === this.data.activeCategory
        const locationMatched = this.data.activeLocation === '全部地点' || haystack.includes(this.data.activeLocation)
        return kindMatched && queryMatched && categoryMatched && locationMatched
      })
      .sort((a, b) => {
        const delta = new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        return this.data.activeSort === '最新优先' ? delta : -delta
      })
      .map((item, index) => ({
        ...item,
        categoryLabel: this.categoryFor(item),
        dateLabel: this.formatDate(item.created_at),
        image: this.imageFor(item, index),
      }))
    this.setData({ filtered })
  },

  openPublish() {
    this.setData({ showPublish: true })
  },

  closePublish() {
    if (!this.data.publishing) this.setData({ showPublish: false })
  },

  stopPropagation() {},

  choosePublishKind(event: WechatMiniprogram.TouchEvent) {
    this.setData({ publishKind: event.currentTarget.dataset.kind as 'lost' | 'found' })
  },

  onPublishTitle(event: WechatMiniprogram.Input) {
    this.setData({ publishTitle: event.detail.value })
  },

  onPublishContent(event: WechatMiniprogram.TextareaInput) {
    this.setData({ publishContent: event.detail.value })
  },

  onPublishLocation(event: WechatMiniprogram.Input) {
    this.setData({ publishLocation: event.detail.value })
  },

  onPublishContact(event: WechatMiniprogram.Input) {
    this.setData({ publishContact: event.detail.value })
  },

  async submitPublish() {
    if (!this.data.publishTitle.trim() || !this.data.publishLocation.trim() || !this.data.publishContact.trim()) {
      wx.showToast({ title: '请填写物品、地点和联系方式', icon: 'none' })
      return
    }
    this.setData({ publishing: true })
    try {
      await repository.createLostFound({
        kind: this.data.publishKind as 'lost' | 'found',
        title: this.data.publishTitle.trim(),
        content: this.data.publishContent.trim(),
        location: this.data.publishLocation.trim(),
        contact: this.data.publishContact.trim(),
        contact_visibility: 'private',
      })
      this.setData({
        showPublish: false,
        publishing: false,
        publishTitle: '',
        publishContent: '',
        publishLocation: '',
        publishContact: '',
      })
      wx.showToast({ title: '发布成功', icon: 'success' })
      await this.load()
    } catch (error) {
      this.setData({ publishing: false })
      wx.showToast({ title: error instanceof Error ? error.message : '发布失败', icon: 'none' })
    }
  },

  showDetail(event: WechatMiniprogram.TouchEvent) {
    const item = this.data.filtered.find((candidate) => candidate.id === event.currentTarget.dataset.id)
    if (!item) return
    wx.showModal({
      title: item.title,
      content: `${item.content || '暂无补充说明'}\n\n地点：${item.location || '待补充'}\n时间：${item.dateLabel}`,
      showCancel: false,
    })
  },

  categoryFor(item: LostFoundItem): string {
    const text = `${item.title} ${item.content || ''}`.toLowerCase()
    if (/卡|证|校园卡|身份证/.test(text)) return '证件卡片'
    if (/手机|耳机|电脑|充电|数码|电子/.test(text)) return '电子产品'
    if (/书|教材|资料|笔记/.test(text)) return '书籍资料'
    if (/伞|水杯|衣|钥匙|生活/.test(text)) return '生活用品'
    return '其他'
  },

  imageFor(item: LostFoundItem, index: number): string {
    const category = this.categoryFor(item)
    if (category === '电子产品') return '/package-community/assets/lost-power-bank.jpg'
    if (category === '书籍资料') return '/package-community/assets/lost-book.jpg'
    return index % 2 === 0 ? '/package-community/assets/lost-power-bank.jpg' : '/package-community/assets/lost-book.jpg'
  },

  formatDate(value: string): string {
    const date = new Date(value)
    const now = new Date()
    const dayDelta = Math.floor((now.getTime() - date.getTime()) / 86400000)
    const time = `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
    if (dayDelta <= 0) return `今天 ${time}`
    if (dayDelta === 1) return `昨天 ${time}`
    return `${date.getMonth() + 1}月${date.getDate()}日 ${time}`
  },
})

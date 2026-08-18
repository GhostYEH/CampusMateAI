import { repository } from '../../../services/repository'
import { CommunityPost, CategoryMeta } from '../../../services/types'

const CATEGORY_LABELS: Record<string, string> = {
  question: '提问', recruit: '招募', errand: '带价帮忙', lostfound: '失物招领',
  campus: '校园动态', study: '学习交流', life: '生活随笔', secondhand: '二手交易',
  activity: '活动', experience: '经验分享', other: '其它',
}

interface PostView extends CommunityPost {
  avatar: string
  catLabel: string
  timeText: string
  excerpt: string
  previewImage: string
  extraTags: string[]
}

Page({
  data: {
    loading: true,
    error: '',
    posts: [] as PostView[],
    total: 0,
    page: 1,
    pageSize: 20,
    query: '',
    category: '',
    sort: 'time',
    categories: [] as CategoryMeta[],
    hotPosts: [] as PostView[],
    showComposer: false,
    sending: false,
    composerError: '',
    title: '',
    content: '',
    formCategory: 'campus',
    formCategoryLabel: '校园动态',
    isAnonymous: false,
    images: [] as string[],
    imageUrls: [] as string[],
    showExtra: false,
    extraHeadcount: '' as string | number,
    extraLocation: '',
    extraDeadline: '',
    extraPrice: '' as string | number,
    extraKind: 'lost',
    extraContact: '',
    extraContactVisibility: 'private',
  },
  onShow() {
    this.loadCategories()
    this.load(true)
    this.loadHotTopics()
  },
  async loadHotTopics() {
    try {
      const { items } = await repository.getCommunityPostsAsync({ sort: 'hot', page: 1, page_size: 3 })
      this.setData({ hotPosts: items.map((item) => this.toView(item)) })
    } catch {}
  },
  async loadCategories() {
    try {
      const cats = await repository.getCommunityCategoriesAsync()
      const cat = this.data.formCategory
      const label = (cats.find((c) => c.key === cat) || {}).label || cat
      this.setData({ categories: cats, formCategoryLabel: label })
    } catch {}
  },
  async load(reset = false) {
    this.setData({ loading: true, error: '' })
    if (reset) this.setData({ page: 1 })
    try {
      const { items, total } = await repository.getCommunityPostsAsync({
        q: this.data.query || undefined,
        category: this.data.category || undefined,
        sort: this.data.sort,
        page: this.data.page,
        page_size: this.data.pageSize,
      })
      const views = items.map((item) => this.toView(item))
      const merged = reset ? views : [...this.data.posts, ...views]
      this.setData({ posts: merged, total, loading: false })
    } catch (error) {
      this.setData({ loading: false, error: error instanceof Error ? error.message : '论坛加载失败' })
    }
  },
  toView(item: CommunityPost): PostView {
    const cat = item.category || 'other'
    const content = item.content || ''
    const imgs = item.images || []
    const e = (item.extra || {}) as Record<string, unknown>
    const extraTags: string[] = []
    if (cat === 'recruit') {
      if (e.headcount) extraTags.push(`招募 ${e.headcount} 人`)
      if (e.location) extraTags.push(`地点：${e.location}`)
      if (e.deadline) extraTags.push(`截止：${e.deadline}`)
    } else if (cat === 'errand') {
      if (e.price != null) extraTags.push(`酬金 ¥${e.price}`)
      if (e.location) extraTags.push(`地点：${e.location}`)
      if (e.deadline) extraTags.push(`截止：${e.deadline}`)
    } else if (cat === 'lostfound') {
      extraTags.push(e.kind === 'found' ? '招领' : '寻物')
      if (e.location) extraTags.push(`地点：${e.location}`)
    }
    let timeText = item.created_at
    try { timeText = new Date(item.created_at).toLocaleString('zh-CN') } catch {}
    return {
      ...item,
      avatar: (item.author_name || '同').slice(0, 1),
      catLabel: CATEGORY_LABELS[cat] || cat,
      timeText,
      excerpt: content.length > 200 ? content.slice(0, 200) + '…' : content,
      previewImage: imgs.length ? repository.resolveAssetUrl(imgs[0]) : '',
      extraTags,
    }
  },
  switchCategory(e: WechatMiniprogram.TouchEvent) {
    this.setData({ category: e.currentTarget.dataset.cat as string })
    this.load(true)
  },
  switchSort(e: WechatMiniprogram.TouchEvent) {
    this.setData({ sort: e.currentTarget.dataset.sort as string })
    this.load(true)
  },
  onQuery(e: WechatMiniprogram.Input) {
    this.setData({ query: e.detail.value })
  },
  onSearch() { this.load(true) },
  loadMore() { this.setData({ page: this.data.page + 1 }); this.load() },
  toggleComposer() {
    this.openPublish()
  },
  openPublish() {
    wx.navigateTo({ url: '/package-community/pages/community-publish/community-publish' })
  },
  openHotTopics() {
    wx.navigateTo({ url: '/package-community/pages/hot-topics/hot-topics' })
  },
  onTitle(e: WechatMiniprogram.Input) { this.setData({ title: e.detail.value }) },
  onContent(e: WechatMiniprogram.Input) { this.setData({ content: e.detail.value }) },
  onFormCategory(e: WechatMiniprogram.PickerChange) {
    const idx = Number(e.detail.value)
    const cat = (this.data.categories[idx] && this.data.categories[idx].key) || 'campus'
    const label = (this.data.categories[idx] && this.data.categories[idx].label) || cat
    this.setData({ formCategory: cat, formCategoryLabel: label, showExtra: ['recruit', 'errand', 'lostfound'].includes(cat), extraHeadcount: '', extraLocation: '', extraDeadline: '', extraPrice: '', extraKind: 'lost', extraContact: '', extraContactVisibility: 'private' })
  },
  onAnonymous(e: WechatMiniprogram.SwitchChange) { this.setData({ isAnonymous: e.detail.value }) },
  onExtraHeadcount(e: WechatMiniprogram.Input) { this.setData({ extraHeadcount: e.detail.value }) },
  onExtraLocation(e: WechatMiniprogram.Input) { this.setData({ extraLocation: e.detail.value }) },
  onExtraDeadline(e: WechatMiniprogram.Input) { this.setData({ extraDeadline: e.detail.value }) },
  onExtraPrice(e: WechatMiniprogram.Input) { this.setData({ extraPrice: e.detail.value }) },
  onExtraKind(e: WechatMiniprogram.PickerChange) { this.setData({ extraKind: Number(e.detail.value) === 1 ? 'found' : 'lost' }) },
  onExtraContact(e: WechatMiniprogram.Input) { this.setData({ extraContact: e.detail.value }) },
  onExtraVisibility(e: WechatMiniprogram.PickerChange) { this.setData({ extraContactVisibility: Number(e.detail.value) === 1 ? 'public' : 'private' }) },
  async chooseImage() {
    const remain = 4 - this.data.images.length
    if (remain <= 0) { wx.showToast({ title: '最多 4 张', icon: 'none' }); return }
    try {
      const res = await new Promise<WechatMiniprogram.ChooseImageSuccessCallbackResult>((resolve, reject) => {
        wx.chooseImage({ count: remain, success: resolve, fail: reject })
      })
      wx.showLoading({ title: '上传中…' })
      const urls: string[] = []
      const previews: string[] = []
      for (const path of res.tempFilePaths) {
        const url = await repository.uploadCommunityImageAsync(path)
        urls.push(url)
        previews.push(repository.resolveAssetUrl(url))
      }
      this.setData({ images: [...this.data.images, ...urls], imageUrls: [...this.data.imageUrls, ...previews] })
    } catch (error) {
      wx.showToast({ title: error instanceof Error ? error.message : '上传失败', icon: 'none' })
    } finally { wx.hideLoading() }
  },
  removeImage(e: WechatMiniprogram.TouchEvent) {
    const idx = e.currentTarget.dataset.idx as number
    const next = [...this.data.images]; next.splice(idx, 1)
    const nextUrls = [...this.data.imageUrls]; nextUrls.splice(idx, 1)
    this.setData({ images: next, imageUrls: nextUrls })
  },
  buildExtra(): Record<string, unknown> | undefined {
    const cat = this.data.formCategory
    if (cat === 'recruit') {
      const e: Record<string, unknown> = {}
      if (this.data.extraHeadcount) e.headcount = Number(this.data.extraHeadcount)
      if (this.data.extraLocation) e.location = this.data.extraLocation
      if (this.data.extraDeadline) e.deadline = this.data.extraDeadline
      return Object.keys(e).length ? e : undefined
    }
    if (cat === 'errand') {
      const e: Record<string, unknown> = {}
      if (this.data.extraPrice !== '') e.price = Number(this.data.extraPrice)
      if (this.data.extraLocation) e.location = this.data.extraLocation
      if (this.data.extraDeadline) e.deadline = this.data.extraDeadline
      return Object.keys(e).length ? e : undefined
    }
    if (cat === 'lostfound') {
      const e: Record<string, unknown> = { kind: this.data.extraKind, contact_visibility: this.data.extraContactVisibility }
      if (this.data.extraLocation) e.location = this.data.extraLocation
      if (this.data.extraContact) e.contact = this.data.extraContact
      return e
    }
    return undefined
  },
  async publish() {
    const title = this.data.title.trim()
    const content = this.data.content.trim()
    if (!title || !content) { this.setData({ composerError: '请填写标题和正文' }); return }
    this.setData({ sending: true, composerError: '' })
    try {
      await repository.createCommunityPost({
        title, content, category: this.data.formCategory,
        images: this.data.images, is_anonymous: this.data.isAnonymous,
        extra: this.buildExtra(),
      })
      this.setData({ showComposer: false, title: '', content: '', formCategory: 'campus', isAnonymous: false, images: [], imageUrls: [], showExtra: false })
      await this.load(true)
      wx.showToast({ title: '发布成功', icon: 'success' })
    } catch (error) {
      this.setData({ composerError: error instanceof Error ? error.message : '发布失败' })
    } finally { this.setData({ sending: false }) }
  },
  async onLike(e: WechatMiniprogram.TouchEvent) {
    const idx = e.currentTarget.dataset.idx as number
    const post = this.data.posts[idx]
    try {
      const fn = post.liked ? repository.unlikeCommunityPost.bind(repository) : repository.likeCommunityPost.bind(repository)
      const updated = await fn(post.id)
      const posts = [...this.data.posts]; posts[idx] = this.toView(updated)
      this.setData({ posts })
    } catch (error) { wx.showToast({ title: error instanceof Error ? error.message : '操作失败', icon: 'none' }) }
  },
  async onFav(e: WechatMiniprogram.TouchEvent) {
    const idx = e.currentTarget.dataset.idx as number
    const post = this.data.posts[idx]
    try {
      const fn = post.favorited ? repository.unfavoriteCommunityPost.bind(repository) : repository.favoriteCommunityPost.bind(repository)
      const updated = await fn(post.id)
      const posts = [...this.data.posts]; posts[idx] = this.toView(updated)
      this.setData({ posts })
    } catch (error) { wx.showToast({ title: error instanceof Error ? error.message : '操作失败', icon: 'none' }) }
  },
  onOpen(e: WechatMiniprogram.TouchEvent) {
    const id = e.currentTarget.dataset.id as string
    wx.navigateTo({ url: `/package-community/pages/community-detail/community-detail?id=${id}` })
  },
})

import { repository } from '../../services/repository'
import { CommunityPost, CommunityComment } from '../../services/types'

const CATEGORY_LABELS: Record<string, string> = {
  question: '提问', recruit: '招募', errand: '带价帮忙', lostfound: '失物招领',
  campus: '校园动态', study: '学习交流', life: '生活随笔', secondhand: '二手交易',
  activity: '活动', experience: '经验分享', other: '其它',
}

interface CommentView extends CommunityComment {
  avatar: string
  timeText: string
  children: CommentView[]
}

Page({
  data: {
    id: '',
    loading: true,
    error: '',
    post: null as CommunityPost | null,
    catLabel: '',
    timeText: '',
    previewImages: [] as string[],
    extraTags: [] as string[],
    comments: [] as CommentView[],
    commentText: '',
    commentAnonymous: false,
    replyTo: null as CommunityComment | null,
    replyName: '',
    sending: false,
    isOwner: false,
  },
  onLoad(options: { id?: string }) {
    if (options.id) {
      this.setData({ id: options.id })
      this.load()
    }
  },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const [post, comments] = await Promise.all([
        repository.getCommunityPostAsync(this.data.id),
        repository.getCommunityCommentsAsync(this.data.id).catch(() => [] as CommunityComment[]),
      ])
      const cat = post.category || 'other'
      const imgs = (post.images || []).map((u) => repository.resolveAssetUrl(u))
      const e = (post.extra || {}) as Record<string, unknown>
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
      let timeText = post.created_at
      try { timeText = new Date(post.created_at).toLocaleString('zh-CN') } catch {}
      this.setData({
        post, catLabel: CATEGORY_LABELS[cat] || cat, timeText,
        previewImages: imgs, extraTags,
        comments: this.buildTree(comments),
        isOwner: !!post.is_owner, loading: false,
      })
    } catch (error) {
      this.setData({ loading: false, error: error instanceof Error ? error.message : '加载失败' })
    }
  },
  buildTree(list: CommunityComment[]): CommentView[] {
    const map: Record<string, CommentView> = {}
    const roots: CommentView[] = []
    for (const c of list) {
      let timeText = c.created_at
      try { timeText = new Date(c.created_at).toLocaleString('zh-CN') } catch {}
      map[c.id] = { ...c, avatar: (c.author_name || '同').slice(0, 1), timeText, children: [] }
    }
    for (const c of list) {
      if (c.parent_comment_id && map[c.parent_comment_id]) map[c.parent_comment_id].children.push(map[c.id])
      else roots.push(map[c.id])
    }
    return roots
  },
  onComment(e: WechatMiniprogram.Input) { this.setData({ commentText: e.detail.value }) },
  onCommentAnonymous(e: WechatMiniprogram.SwitchChange) { this.setData({ commentAnonymous: e.detail.value }) },
  startReply(e: WechatMiniprogram.TouchEvent) {
    const id = e.currentTarget.dataset.id as string
    const name = e.currentTarget.dataset.name as string
    const comment = this.data.comments.flatMap((c) => [c, ...c.children]).find((c) => c.id === id)
    this.setData({ replyTo: comment || null, replyName: name, commentText: `@${name} ` })
  },
  cancelReply() { this.setData({ replyTo: null, replyName: '', commentText: '' }) },
  async submitComment() {
    if (!this.data.commentText.trim()) return
    this.setData({ sending: true })
    try {
      const d = await repository.createCommunityCommentAsync(this.data.id, {
        content: this.data.commentText,
        is_anonymous: this.data.commentAnonymous,
        parent_comment_id: this.data.replyTo?.id || undefined,
      })
      const flat = [...this.data.comments.flatMap((c) => [c, ...c.children]), d]
      this.setData({ comments: this.buildTree(flat), commentText: '', replyTo: null, replyName: '' })
      if (this.data.post) this.setData({ post: { ...this.data.post, comment_count: (this.data.post.comment_count || 0) + 1 } })
    } catch (error) {
      wx.showToast({ title: error instanceof Error ? error.message : '评论失败', icon: 'none' })
    } finally { this.setData({ sending: false }) }
  },
  async onLike() {
    if (!this.data.post) return
    try {
      const fn = this.data.post.liked ? repository.unlikeCommunityPost.bind(repository) : repository.likeCommunityPost.bind(repository)
      const updated = await fn(this.data.post.id)
      this.setData({ post: updated })
    } catch (error) { wx.showToast({ title: error instanceof Error ? error.message : '操作失败', icon: 'none' }) }
  },
  async onFav() {
    if (!this.data.post) return
    try {
      const fn = this.data.post.favorited ? repository.unfavoriteCommunityPost.bind(repository) : repository.favoriteCommunityPost.bind(repository)
      const updated = await fn(this.data.post.id)
      this.setData({ post: updated })
    } catch (error) { wx.showToast({ title: error instanceof Error ? error.message : '操作失败', icon: 'none' }) }
  },
  async onDelete() {
    if (!this.data.post) return
    wx.showModal({
      title: '确认删除',
      content: '确认删除这篇帖子？',
      success: async (res) => {
        if (!res.confirm) return
        try { await repository.deleteCommunityPost(this.data.post!.id); wx.navigateBack() }
        catch (error) { wx.showToast({ title: error instanceof Error ? error.message : '删除失败', icon: 'none' }) }
      },
    })
  },
  previewImage(e: WechatMiniprogram.TouchEvent) {
    const idx = e.currentTarget.dataset.idx as number
    wx.previewImage({ current: this.data.previewImages[idx], urls: this.data.previewImages })
  },
})
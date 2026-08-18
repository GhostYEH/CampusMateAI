import { repository } from '../../../services/repository'
import { CommunityPost } from '../../../services/types'

interface HotPost extends CommunityPost {
  rank: number
  timeText: string
  excerpt: string
}

Page({
  data: { loading: true, error: '', posts: [] as HotPost[] },
  onShow() { this.load() },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const { items } = await repository.getCommunityPostsAsync({ sort: 'hot', page: 1, page_size: 50 })
      const posts = items.map((item, index) => ({
        ...item,
        rank: index + 1,
        timeText: this.relativeTime(item.created_at),
        excerpt: (item.content || '').slice(0, 86),
      }))
      this.setData({ posts, loading: false })
    } catch (error) {
      this.setData({ loading: false, error: error instanceof Error ? error.message : '热门话题加载失败' })
    }
  },
  relativeTime(value: string) {
    const time = new Date(value).getTime()
    if (Number.isNaN(time)) return value
    const diff = Math.max(0, Date.now() - time)
    if (diff < 3600000) return `${Math.max(1, Math.floor(diff / 60000))} 分钟前`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
    return new Date(value).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
  },
  openPost(e: WechatMiniprogram.TouchEvent) {
    wx.navigateTo({ url: `/package-community/pages/community-detail/community-detail?id=${e.currentTarget.dataset.id as string}` })
  },
  openPublish() { wx.navigateTo({ url: '/package-community/pages/community-publish/community-publish' }) },
})

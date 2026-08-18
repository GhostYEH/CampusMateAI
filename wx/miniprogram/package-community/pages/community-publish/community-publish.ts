import { repository } from '../../../services/repository'
import { CategoryMeta } from '../../../services/types'

Page({
  data: {
    categories: [] as CategoryMeta[], title: '', content: '', category: 'campus', images: [] as string[], imageUrls: [] as string[],
    isAnonymous: false, allowComments: true, location: '', tags: '', sending: false, error: '',
  },
  onLoad() { this.loadCategories() },
  async loadCategories() {
    try { this.setData({ categories: await repository.getCommunityCategoriesAsync() }) } catch (error) { this.setData({ error: error instanceof Error ? error.message : '分类加载失败' }) }
  },
  onTitle(e: WechatMiniprogram.Input) { this.setData({ title: e.detail.value }) },
  onContent(e: WechatMiniprogram.Input) { this.setData({ content: e.detail.value }) },
  onCategory(e: WechatMiniprogram.TouchEvent) { this.setData({ category: e.currentTarget.dataset.key as string }) },
  onAnonymous(e: WechatMiniprogram.SwitchChange) { this.setData({ isAnonymous: e.detail.value }) },
  onAllowComments(e: WechatMiniprogram.SwitchChange) { this.setData({ allowComments: e.detail.value }) },
  onLocation(e: WechatMiniprogram.Input) { this.setData({ location: e.detail.value }) },
  onTags(e: WechatMiniprogram.Input) { this.setData({ tags: e.detail.value }) },
  async chooseImage() {
    const count = 9 - this.data.images.length
    if (count <= 0) { wx.showToast({ title: '最多 9 张图片', icon: 'none' }); return }
    try {
      const res = await new Promise<WechatMiniprogram.ChooseImageSuccessCallbackResult>((resolve, reject) => wx.chooseImage({ count, success: resolve, fail: reject }))
      wx.showLoading({ title: '上传图片' })
      const uploaded = await Promise.all(res.tempFilePaths.map((path) => repository.uploadCommunityImageAsync(path)))
      this.setData({ images: [...this.data.images, ...uploaded], imageUrls: [...this.data.imageUrls, ...uploaded.map((url) => repository.resolveAssetUrl(url))] })
    } catch (error) { wx.showToast({ title: error instanceof Error ? error.message : '图片上传失败', icon: 'none' }) } finally { wx.hideLoading() }
  },
  removeImage(e: WechatMiniprogram.TouchEvent) {
    const index = Number(e.currentTarget.dataset.index); const images = [...this.data.images]; const imageUrls = [...this.data.imageUrls]
    images.splice(index, 1); imageUrls.splice(index, 1); this.setData({ images, imageUrls })
  },
  async publish() {
    const title = this.data.title.trim(); const content = this.data.content.trim()
    if (!title || !content) { this.setData({ error: '请填写标题和正文' }); return }
    this.setData({ sending: true, error: '' })
    try {
      await repository.createCommunityPost({ title, content, category: this.data.category, images: this.data.images, is_anonymous: this.data.isAnonymous, extra: { location: this.data.location.trim() || undefined, tags: this.data.tags.split(/[，,]/).map((tag) => tag.trim()).filter(Boolean), allow_comments: this.data.allowComments } })
      wx.showToast({ title: '发布成功', icon: 'success' }); setTimeout(() => wx.navigateBack(), 450)
    } catch (error) { this.setData({ error: error instanceof Error ? error.message : '发布失败' }) } finally { this.setData({ sending: false }) }
  },
})

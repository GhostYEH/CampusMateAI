import { AcademicStatusItem, CommunityPostExtra, CommunityPostItem, UniversityItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';

@Component
export struct V3CorePage {
  @Prop route: string = 'university';
  @Prop darkMode: boolean = false;
  @Prop loading: boolean = false;
  @Prop selectedUniversityId: string = '';
  @Prop universities: UniversityItem[] = [];
  @Prop posts: CommunityPostItem[] = [];
  @Prop hotPosts: CommunityPostItem[] = [];
  @Prop academicStatus: AcademicStatusItem = { status: 'unsupported', provider: 'unsupported' };
  onBack: () => void = () => {};
  onRefresh: () => void = () => {};
  onSelectUniversity: (id: string) => void = () => {};
  onPublish: (title: string, content: string, anonymous: boolean, category: string, extra?: CommunityPostExtra) => void = () => {};
  onLike: (id: string) => void = () => {};
  onOpenHot: () => void = () => {};
  onOpenPublish: () => void = () => {};
  @State titleInput: string = '';
  @State contentInput: string = '';
  @State anonymous: boolean = false;
  @State categoryInput: string = 'campus';
  @State locationInput: string = '';
  @State tagInput: string = '';
  @State allowComments: boolean = true;
  @State composing: boolean = false;

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  title(): string { return this.route === 'university' ? '我的大学' : this.route === 'community_hot' ? '热门话题' : this.route === 'community_publish' ? '发布帖子' : this.route === 'community' ? '校园论坛' : '教务系统'; }
  subtitle(): string {
    if (this.route === 'university') return '选择后，社区、失物招领和教务能力将按大学隔离';
    if (this.route === 'community') return '提问 / 招募 / 带价帮忙 / 失物招领';
    if (this.route === 'community_hot') return '按点赞和讨论热度排行';
    if (this.route === 'community_publish') return '分享校园信息，友善交流，注意保护隐私';
    return '连接学生自己的教务账号，同步课程、课表、成绩和考试';
  }

  @Builder EmptyState(text: string) {
    Row({ space: 10 }) {
      SymbolGlyph($r('sys.symbol.info_circle')).fontSize(24).fontColor([this.palette().primary])
      Text(text).fontSize(13).fontColor(this.palette().muted).layoutWeight(1)
    }.width('100%').padding(18).backgroundColor(this.palette().surface).borderRadius(22)
  }

  @Builder UniversityContent() {
    if (!this.loading && this.universities.length === 0) { this.EmptyState('未找到可选择的大学') }
    ForEach(this.universities, (item: UniversityItem) => {
      Row({ space: 13 }) {
        Stack({ alignContent: Alignment.Center }) { SymbolGlyph($r('sys.symbol.school')).fontSize(25).fontColor([this.palette().primary]) }
          .width(46).height(46).backgroundColor(this.palette().soft).borderRadius(15)
        Column({ space: 4 }) {
          Text(item.name).fontSize(16).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
          Text(`${item.province ?? '中国'} · ${item.city ?? '校园'}`).fontSize(11).fontColor(this.palette().muted)
          Text(item.academic_provider === 'unsupported' ? '暂未支持自动教务同步' : '支持教务同步').fontSize(10).fontColor(this.palette().muted)
        }.layoutWeight(1).alignItems(HorizontalAlign.Start)
        Button(this.selectedUniversityId === item.id ? '当前大学' : '选择').enabled(this.selectedUniversityId !== item.id)
          .onClick(() => this.onSelectUniversity(item.id))
      }.width('100%').padding(17).backgroundColor(this.palette().surface).borderRadius(22)
    }, (item: UniversityItem) => item.id)
  }

  @Builder CommunityContent() {
    Button('＋ 发布').width('100%').onClick(() => this.onOpenPublish())
    Row() { Text('🔥 今日热门话题').fontSize(18).fontWeight(FontWeight.Bold).fontColor(this.palette().text); Blank(); Text('更多 ›').fontSize(13).fontColor(this.palette().primary).onClick(() => this.onOpenHot()) }
      .width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(20)
    ForEach(this.hotPosts.slice(0, 3), (post: CommunityPostItem, index: number) => { Text(`TOP${index + 1}  ${post.title}`).fontColor(this.palette().text).fontSize(13).maxLines(1) }, (post: CommunityPostItem) => post.id)
    if (this.composing) {
      Column({ space: 10 }) {
        TextInput({ text: this.titleInput, placeholder: '帖子标题' }).onChange((value: string) => this.titleInput = value)
        TextArea({ text: this.contentInput, placeholder: '分享校园生活或提出问题' }).height(110).onChange((value: string) => this.contentInput = value)
        Row() { Toggle({ type: ToggleType.Checkbox, isOn: this.anonymous }).onChange((value: boolean) => this.anonymous = value); Text('校园匿名').fontColor(this.palette().muted).margin({ left: 7 }); Blank(); Button('确认发布').enabled(this.titleInput.trim().length > 0 && this.contentInput.trim().length > 0).onClick(() => { this.onPublish(this.titleInput.trim(), this.contentInput.trim(), this.anonymous, this.categoryInput); this.titleInput = ''; this.contentInput = ''; this.composing = false; }) }
      }.width('100%').padding(17).backgroundColor(this.palette().surface).borderRadius(22)
    }
    if (!this.loading && this.posts.length === 0) { this.EmptyState('暂无帖子，来发起第一场校园讨论吧') }
    ForEach(this.posts, (post: CommunityPostItem) => {
      Column({ space: 9 }) {
        Text(post.author_name).fontSize(12).fontColor(this.palette().primary)
        Text(post.title).fontSize(18).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
        Text(post.content).fontSize(13).fontColor(this.palette().muted).lineHeight(20)
        Row({ space: 18 }) { Text(`♡ ${post.like_count}`).fontColor(this.palette().muted).onClick(() => this.onLike(post.id)); Text(`评论 ${post.comment_count}`).fontColor(this.palette().muted); Text(`收藏 ${post.favorite_count}`).fontColor(this.palette().muted) }
      }.width('100%').alignItems(HorizontalAlign.Start).padding(18).backgroundColor(this.palette().surface).borderRadius(22)
    }, (post: CommunityPostItem) => post.id)
  }

  @Builder HotTopicsContent() {
    Text('🔥 今日热门话题').fontSize(24).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
    ForEach(this.posts, (post: CommunityPostItem, index: number) => {
      Row({ space: 12 }) { Text((index + 1).toString()).fontSize(20).fontWeight(FontWeight.Bold).fontColor(index < 3 ? '#FF6B5D' : this.palette().muted).width(28); Column({ space: 5 }) { Text(post.title).fontSize(16).fontWeight(FontWeight.Bold).fontColor(this.palette().text).maxLines(1); Text(post.content).fontSize(12).fontColor(this.palette().muted).maxLines(2) }.layoutWeight(1); Text(`🔥 ${post.like_count + post.comment_count * 2}`).fontSize(11).fontColor('#FF6B5D') }
        .width('100%').padding(17).backgroundColor(this.palette().surface).borderRadius(18)
    }, (post: CommunityPostItem) => post.id)
  }

  @Builder PublishContent() {
    Column({ space: 12 }) {
      Row({ space: 8 }) { Text('●').fontSize(20).fontColor(this.palette().primary); Text('分享校园信息，友善交流，注意保护隐私').fontSize(13).fontColor(this.palette().text) }
        .width('100%').padding(15).backgroundColor(this.palette().soft).borderRadius(18)
      Text(`● 标题  ${this.titleInput.length}/60`).fontSize(17).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
      TextInput({ text: this.titleInput, placeholder: '输入一个清晰的标题' }).maxLength(60).onChange((value: string) => this.titleInput = value).height(54).backgroundColor(this.palette().surface).borderRadius(18)
      Text(`● 正文  ${this.contentInput.length}/1000`).fontSize(17).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
      TextArea({ text: this.contentInput, placeholder: '写下你的内容、问题或需求…' }).maxLength(1000).height(160).onChange((value: string) => this.contentInput = value).backgroundColor(this.palette().surface).borderRadius(18)
      Text('● 选择分类').fontSize(17).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
      Row({ space: 8 }) {
        Button('提问').onClick(() => this.categoryInput = 'question').backgroundColor(this.categoryInput === 'question' ? this.palette().primary : this.palette().soft)
        Button('招募').onClick(() => this.categoryInput = 'recruit').backgroundColor(this.categoryInput === 'recruit' ? this.palette().primary : this.palette().soft)
        Button('带价帮忙').onClick(() => this.categoryInput = 'errand').backgroundColor(this.categoryInput === 'errand' ? this.palette().primary : this.palette().soft)
      }.width('100%')
      Row({ space: 8 }) {
        Button('失物招领').onClick(() => this.categoryInput = 'lostfound').backgroundColor(this.categoryInput === 'lostfound' ? this.palette().primary : this.palette().soft)
        Button('校园动态').onClick(() => this.categoryInput = 'campus').backgroundColor(this.categoryInput === 'campus' ? this.palette().primary : this.palette().soft)
        Button('学习资料').onClick(() => this.categoryInput = 'study').backgroundColor(this.categoryInput === 'study' ? this.palette().primary : this.palette().soft)
      }.width('100%')
      Text('● 添加图片（最多9张）').fontSize(17).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
      Button('＋ 添加图片').width(118).height(80).backgroundColor(this.palette().soft).fontColor(this.palette().primary)
      Row({ space: 8 }) { Toggle({ type: ToggleType.Switch, isOn: this.anonymous }).onChange((value: boolean) => this.anonymous = value); Column({ space: 2 }) { Text('校园匿名').fontColor(this.palette().text); Text('发布后将隐藏你的姓名和个人信息').fontSize(11).fontColor(this.palette().muted) }.alignItems(HorizontalAlign.Start) }
        .width('100%').padding(14).backgroundColor(this.palette().surface).borderRadius(18)
      Row({ space: 8 }) { Text('⌖ 添加地点').fontSize(15).fontColor(this.palette().text); TextInput({ text: this.locationInput, placeholder: '选择校内位置' }).layoutWeight(1).onChange((value: string) => this.locationInput = value) }.width('100%').padding(12).backgroundColor(this.palette().surface).borderRadius(18)
      Row({ space: 8 }) { Text('# 话题标签').fontSize(15).fontColor(this.palette().text); TextInput({ text: this.tagInput, placeholder: '添加标签' }).layoutWeight(1).onChange((value: string) => this.tagInput = value) }.width('100%').padding(12).backgroundColor(this.palette().surface).borderRadius(18)
      Row() { Toggle({ type: ToggleType.Switch, isOn: this.allowComments }).onChange((value: boolean) => this.allowComments = value); Text('允许评论').margin({ left: 8 }).fontColor(this.palette().text); Blank(); Button('立即发布').enabled(this.titleInput.trim().length > 0 && this.contentInput.trim().length > 0).onClick(() => { const extra: CommunityPostExtra = { location: this.locationInput, topic_tag: this.tagInput, allow_comments: this.allowComments }; this.onPublish(this.titleInput.trim(), this.contentInput.trim(), this.anonymous, this.categoryInput, extra); this.titleInput = ''; this.contentInput = ''; this.onBack(); }) }
    }.width('100%').padding(18).backgroundColor(this.palette().surface).borderRadius(20)
  }

  @Builder AcademicContent() {
    Column({ space: 7 }) {
      Text('当前连接状态').fontSize(11).fontColor(this.palette().muted)
      Text(this.academicStatus.status === 'unsupported' ? '暂未支持自动教务同步' : this.academicStatus.status).fontSize(19).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
      Text(`Provider: ${this.academicStatus.provider}`).fontSize(12).fontColor(this.palette().muted)
    }.width('100%').alignItems(HorizontalAlign.Start).padding(20).backgroundColor(this.palette().surface).borderRadius(22)
    Column({ space: 7 }) {
      Text('凭证安全').fontSize(16).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
      Text('教务密码仅通过 HTTPS 发送到 Backend 完成认证，不会保存在本机、API 响应或日志中。未验证的学校不会显示假绑定或假课程。').fontSize(13).fontColor(this.palette().muted).lineHeight(20)
    }.width('100%').alignItems(HorizontalAlign.Start).padding(18).backgroundColor(this.palette().soft).borderRadius(22)
  }

  build() {
    Column({ space: 12 }) {
      SecondaryHeader({ title: this.title(), subtitle: this.subtitle(), darkMode: this.darkMode, onBack: this.onBack })
      Scroll() {
        Column({ space: 13 }) {
          if (this.loading) { LoadingProgress().width(28).height(28).color(this.palette().primary) }
          if (this.route === 'university') { this.UniversityContent() }
          else if (this.route === 'community') { this.CommunityContent() }
          else if (this.route === 'community_hot') { this.HotTopicsContent() }
          else if (this.route === 'community_publish') { this.PublishContent() }
          else { this.AcademicContent() }
          Blank().height(30)
        }.width('100%').padding({ left: 16, right: 16, top: 6 })
      }.layoutWeight(1).scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

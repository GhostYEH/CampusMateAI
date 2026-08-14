import { AcademicStatusItem, CommunityPostItem, UniversityItem } from '../../data/Models';
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
  @Prop academicStatus: AcademicStatusItem = { status: 'unsupported', provider: 'unsupported' };
  onBack: () => void = () => {};
  onRefresh: () => void = () => {};
  onSelectUniversity: (id: string) => void = () => {};
  onPublish: (title: string, content: string, anonymous: boolean) => void = () => {};
  onLike: (id: string) => void = () => {};
  @State titleInput: string = '';
  @State contentInput: string = '';
  @State anonymous: boolean = false;
  @State composing: boolean = false;

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  title(): string { return this.route === 'university' ? '我的大学' : this.route === 'community' ? '校园社区' : '教务系统'; }
  subtitle(): string {
    if (this.route === 'university') return '选择后，社区、失物招领和教务能力将按大学隔离';
    if (this.route === 'community') return '只展示当前大学的公开讨论与同学互助';
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
    Button(this.composing ? '收起发布框' : '发布帖子').width('100%').onClick(() => this.composing = !this.composing)
    if (this.composing) {
      Column({ space: 10 }) {
        TextInput({ text: this.titleInput, placeholder: '帖子标题' }).onChange((value: string) => this.titleInput = value)
        TextArea({ text: this.contentInput, placeholder: '分享校园生活或提出问题' }).height(110).onChange((value: string) => this.contentInput = value)
        Row() { Toggle({ type: ToggleType.Checkbox, isOn: this.anonymous }).onChange((value: boolean) => this.anonymous = value); Text('校园匿名').fontColor(this.palette().muted).margin({ left: 7 }); Blank(); Button('确认发布').enabled(this.titleInput.trim().length > 0 && this.contentInput.trim().length > 0).onClick(() => { this.onPublish(this.titleInput.trim(), this.contentInput.trim(), this.anonymous); this.titleInput = ''; this.contentInput = ''; this.composing = false; }) }
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
          else { this.AcademicContent() }
          Blank().height(30)
        }.width('100%').padding({ left: 16, right: 16, top: 6 })
      }.layoutWeight(1).scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

import { AcademicStatusItem, CommunityComment, CommunityPostExtra, CommunityPostItem, UniversityItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { PinyinInitial } from '../../util/PinyinInitial';

interface UniversityGroup {
  letter: string;
  items: UniversityItem[];
}

interface UniFlatNode {
  key: string;
  isHeader: boolean;
  letter: string;
  item: UniversityItem | undefined;
}

@Component
export struct V3CorePage {
  @Prop route: string = 'university';
  @Prop darkMode: boolean = false;
  @Prop loading: boolean = false;
  @Prop selectedUniversityId: string = '';
  @Prop selectedUniversityName: string = '';
  @Prop @Watch('rebuildUniIndex') universities: UniversityItem[] = [];
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
  onOpenDetail: (id: string) => void = () => {};
  onDetailLike: () => void = () => {};
  onDetailFavorite: () => void = () => {};
  onDetailDelete: () => void = () => {};
  onDetailReport: () => void = () => {};
  onAddComment: (content: string, anonymous: boolean, parentId?: string) => void = () => {};
  onChooseImage: () => void = () => {};
  onRemoveImage: (url: string) => void = () => {};
  onDetailEdit: () => void = () => {};
  onEdit: (title: string, content: string, anonymous: boolean, category: string, extra?: CommunityPostExtra) => void = () => {};
  onCancelEdit: () => void = () => {};
  @Prop detailLoading: boolean = false;
  @Prop detailPost: CommunityPostItem | null = null;
  @Prop detailComments: Array<CommunityComment> = [];
  @Prop postImages: Array<string> = [];
  @Prop @Watch('onEditPostChange') editPost: CommunityPostItem | null = null;
  @Prop apiBaseUrl: string = '';
  @State titleInput: string = '';
  @State contentInput: string = '';
  @State anonymous: boolean = false;
  @State categoryInput: string = 'campus';
  @State locationInput: string = '';
  @State tagInput: string = '';
  @State allowComments: boolean = true;
  @State commentInput: string = '';
  @State commentAnonymous: boolean = false;
  @State replyToId: string = '';
  @State replyToName: string = '';
  @State extraHeadcount: string = '';
  @State extraDeadline: string = '';
  @State extraPrice: string = '';
  @State extraKind: string = 'lost';
  @State extraContact: string = '';
  @State uniSearch: string = '';
  @State uniNodes: UniFlatNode[] = [];
  @State uniLetters: string[] = [];
  @State uniLetterIndex: Record<string, number> = {};
  private uniScroller: Scroller = new Scroller();

  rebuildUniIndex(): void {
    const q: string = this.uniSearch.trim().toUpperCase();
    const filtered: UniversityItem[] = [];
    for (let i = 0; i < this.universities.length; i++) {
      const u: UniversityItem = this.universities[i];
      if (q.length === 0) {
        filtered.push(u);
      } else if (u.name.toUpperCase().indexOf(q) >= 0) {
        filtered.push(u);
      } else if (PinyinInitial.initials(u.name).indexOf(q) >= 0) {
        filtered.push(u);
      }
    }
    const groups: UniversityGroup[] = [];
    const indexMap: Record<string, number> = {};
    for (let i = 0; i < filtered.length; i++) {
      const u: UniversityItem = filtered[i];
      const letter: string = PinyinInitial.of(u.name);
      const idx: number | undefined = indexMap[letter];
      if (idx === undefined) {
        indexMap[letter] = groups.length;
        groups.push({ letter: letter, items: [u] });
      } else {
        groups[idx].items.push(u);
      }
    }
    groups.sort((a: UniversityGroup, b: UniversityGroup) => {
      if (a.letter === '#') return 1;
      if (b.letter === '#') return -1;
      return a.letter < b.letter ? -1 : (a.letter > b.letter ? 1 : 0);
    });
    const nodes: UniFlatNode[] = [];
    const letters: string[] = [];
    const letterIndex: Record<string, number> = {};
    for (let i = 0; i < groups.length; i++) {
      letters.push(groups[i].letter);
      letterIndex[groups[i].letter] = nodes.length;
      nodes.push({ key: 'h_' + groups[i].letter, isHeader: true, letter: groups[i].letter, item: undefined });
      const items: UniversityItem[] = groups[i].items;
      for (let j = 0; j < items.length; j++) {
        nodes.push({ key: 'i_' + items[j].id, isHeader: false, letter: groups[i].letter, item: items[j] });
      }
    }
    this.uniNodes = nodes;
    this.uniLetters = letters;
    this.uniLetterIndex = letterIndex;
  }

  onEditPostChange(): void {
    if (this.editPost !== null) {
      this.titleInput = this.editPost.title;
      this.contentInput = this.editPost.content;
      this.categoryInput = this.editPost.category;
      this.anonymous = this.editPost.is_anonymous;
      const extra: CommunityPostExtra | undefined = this.editPost.extra;
      if (extra !== undefined) {
        this.locationInput = extra.location ?? '';
        this.tagInput = extra.topic_tag ?? '';
        this.allowComments = extra.allow_comments ?? true;
        this.extraHeadcount = extra.headcount !== undefined ? String(extra.headcount) : '';
        this.extraDeadline = extra.deadline ?? '';
        this.extraPrice = extra.price !== undefined ? String(extra.price) : '';
        this.extraKind = extra.kind ?? 'lost';
        this.extraContact = extra.contact ?? '';
      }
    }
  }

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  title(): string { return this.route === 'university' ? '我的大学' : this.route === 'community_hot' ? '热门话题' : this.route === 'community_publish' ? '发布帖子' : this.route === 'community_detail' ? '帖子详情' : this.route === 'community_edit' ? '编辑帖子' : this.route === 'community' ? '校园论坛' : '教务系统'; }
  subtitle(): string {
    if (this.route === 'university') return '选择后，社区、失物招领和教务能力将按大学隔离';
    if (this.route === 'community') return '提问 / 招募 / 带价帮忙 / 失物招领';
    if (this.route === 'community_hot') return '按点赞和讨论热度排行';
    if (this.route === 'community_publish') return '分享校园信息，友善交流，注意保护隐私';
    if (this.route === 'community_detail') return '查看帖子详情与评论';
    if (this.route === 'community_edit') return '修改帖子内容后保存';
    return '连接学生自己的教务账号，同步课程、课表、成绩和考试';
  }

  @Builder EmptyState(text: string) {
    Row({ space: 10 }) {
      SymbolGlyph($r('sys.symbol.info_circle')).fontSize(24).fontColor([this.palette().primary])
      Text(text).fontSize(13).fontColor(this.palette().muted).layoutWeight(1)
    }.width('100%').padding(18).backgroundColor(this.palette().surface).borderRadius(22)
  }

  aboutToAppear(): void {
    this.rebuildUniIndex();
  }

  @Builder UniversityRow(item: UniversityItem) {
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
  }

  @Builder UniversityContent() {
    Column({ space: 10 }) {
      if (this.selectedUniversityId.length > 0 && this.selectedUniversityName.length > 0) {
        Row({ space: 10 }) {
          SymbolGlyph($r('sys.symbol.checkmark_circle')).fontSize(22).fontColor([this.palette().primary])
          Column({ space: 2 }) {
            Text('当前大学').fontSize(11).fontColor(this.palette().muted)
            Text(this.selectedUniversityName).fontSize(15).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
          }.layoutWeight(1).alignItems(HorizontalAlign.Start)
        }.width('100%').padding(16).backgroundColor(this.palette().soft).borderRadius(18)
      }
      Row({ space: 8 }) {
        SymbolGlyph($r('sys.symbol.magnifyingglass')).fontSize(18).fontColor([this.palette().muted])
        TextInput({ text: this.uniSearch, placeholder: '搜索大学名称或拼音首字母（如 BJDX）' })
          .layoutWeight(1).fontSize(14).fontColor(this.palette().text)
          .onChange((value: string) => { this.uniSearch = value; this.rebuildUniIndex(); })
      }.width('100%').padding({ left: 12, right: 12, top: 8, bottom: 8 }).backgroundColor(this.palette().surface).borderRadius(18)

      if (this.loading && this.universities.length === 0) {
        Column() { LoadingProgress().width(28).height(28).color(this.palette().primary) }.width('100%').layoutWeight(1).justifyContent(FlexAlign.Center)
      } else if (this.uniNodes.length === 0) {
        Column() { this.EmptyState(this.uniSearch.trim().length > 0 ? '未找到匹配的大学' : '未找到可选择的大学') }.width('100%').layoutWeight(1).justifyContent(FlexAlign.Start)
      } else {
        Row() {
          List({ scroller: this.uniScroller }) {
            ForEach(this.uniNodes, (node: UniFlatNode) => {
              if (node.isHeader) {
                ListItem() {
                  Text(node.letter).fontSize(13).fontWeight(FontWeight.Bold).fontColor(this.palette().muted).width('100%').padding({ left: 4, top: 12, bottom: 6 })
                }
              } else {
                ListItem() { this.UniversityRow(node.item!) }
              }
            }, (node: UniFlatNode) => node.key)
          }.layoutWeight(1).height('100%').scrollBar(BarState.Off).edgeEffect(EdgeEffect.Spring)

          Column() {
            ForEach(this.uniLetters, (letter: string) => {
              Text(letter).fontSize(10).fontWeight(FontWeight.Medium).fontColor(this.palette().primary)
                .width(18).height(16).textAlign(TextAlign.Center)
                .onClick(() => {
                  const idx: number | undefined = this.uniLetterIndex[letter];
                  if (idx !== undefined) this.uniScroller.scrollToIndex(idx);
                })
            }, (letter: string) => letter)
          }.width(22).justifyContent(FlexAlign.Center).padding({ top: 4, bottom: 4 }).backgroundColor(this.palette().surface).borderRadius(11)
        }.width('100%').layoutWeight(1).alignItems(VerticalAlign.Center)
      }
    }.width('100%').height('100%').padding({ left: 16, right: 8, top: 6, bottom: 6 })
  }

  @Builder CommunityContent() {
    Button('＋ 发布').width('100%').onClick(() => this.onOpenPublish())
    Row() { Text('🔥 今日热门话题').fontSize(18).fontWeight(FontWeight.Bold).fontColor(this.palette().text); Blank(); Text('更多 ›').fontSize(13).fontColor(this.palette().primary).onClick(() => this.onOpenHot()) }
      .width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(20)
    ForEach(this.hotPosts.slice(0, 3), (post: CommunityPostItem, index: number) => { Text(`TOP${index + 1}  ${post.title}`).fontColor(this.palette().text).fontSize(13).maxLines(1) }, (post: CommunityPostItem) => post.id)

    if (!this.loading && this.posts.length === 0) { this.EmptyState('暂无帖子，来发起第一场校园讨论吧') }
    ForEach(this.posts, (post: CommunityPostItem) => {
      Column({ space: 9 }) {
        Text(post.author_name).fontSize(12).fontColor(this.palette().primary)
        Text(post.title).fontSize(18).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
        Text(post.content).fontSize(13).fontColor(this.palette().muted).lineHeight(20).maxLines(3)
        Row({ space: 18 }) { Text(`♡ ${post.like_count}`).fontColor(this.palette().muted).onClick(() => this.onLike(post.id)); Text(`评论 ${post.comment_count}`).fontColor(this.palette().muted); Text(`收藏 ${post.favorite_count}`).fontColor(this.palette().muted) }
      }.width('100%').alignItems(HorizontalAlign.Start).padding(18).backgroundColor(this.palette().surface).borderRadius(22).onClick(() => this.onOpenDetail(post.id))
    }, (post: CommunityPostItem) => post.id)
  }

  @Builder HotTopicsContent() {
    Text('🔥 今日热门话题').fontSize(24).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
    if (!this.loading && this.hotPosts.length === 0) { this.EmptyState('暂无热门话题，快来发起讨论吧') }
    ForEach(this.hotPosts, (post: CommunityPostItem, index: number) => {
      Row({ space: 12 }) { Text((index + 1).toString()).fontSize(20).fontWeight(FontWeight.Bold).fontColor(index < 3 ? '#FF6B5D' : this.palette().muted).width(28); Column({ space: 5 }) { Text(post.title).fontSize(16).fontWeight(FontWeight.Bold).fontColor(this.palette().text).maxLines(1); Text(post.content).fontSize(12).fontColor(this.palette().muted).maxLines(2) }.layoutWeight(1); Text(`🔥 ${post.like_count + post.comment_count * 2}`).fontSize(11).fontColor('#FF6B5D') }
        .width('100%').padding(17).backgroundColor(this.palette().surface).borderRadius(18)
    }, (post: CommunityPostItem) => post.id)
  }

  @Builder CommunityDetailContent() {
    if (this.detailLoading) { LoadingProgress().width(28).height(28).color(this.palette().primary) }
    else if (this.detailPost !== null) {
      Column({ space: 10 }) {
        Text(this.detailPost.author_name).fontSize(12).fontColor(this.palette().primary)
        Text(this.detailPost.title).fontSize(20).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
        Text(this.detailPost.content).fontSize(14).fontColor(this.palette().text).lineHeight(22)
        if (this.detailPost.images && this.detailPost.images.length > 0) {
          Flex({ wrap: FlexWrap.Wrap }) {
            ForEach(this.detailPost.images, (img: string) => {
              Image(`${this.apiBaseUrl}${img}`).width(100).height(100).borderRadius(10).margin({ right: 6, bottom: 6 }).objectFit(ImageFit.Cover)
            }, (img: string) => img)
          }.width('100%')
        }
        Row({ space: 16 }) {
          Text(`${this.detailPost.liked ? '♥' : '♡'} ${this.detailPost.like_count}`).fontColor(this.detailPost.liked ? '#FF6B5D' : this.palette().muted).onClick(() => this.onDetailLike())
          Text(`★ ${this.detailPost.favorite_count}`).fontColor(this.detailPost.favorited ? this.palette().primary : this.palette().muted).onClick(() => this.onDetailFavorite())
          if (this.detailPost.is_owner) { Text('编辑').fontColor(this.palette().primary).onClick(() => this.onDetailEdit()); Text('删除').fontColor('#FF6B5D').onClick(() => this.onDetailDelete()) }
          Text('举报').fontColor(this.palette().muted).onClick(() => this.onDetailReport())
        }
      }.width('100%').alignItems(HorizontalAlign.Start).padding(18).backgroundColor(this.palette().surface).borderRadius(22)
      Text(`评论 ${this.detailComments.length}`).fontSize(15).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
      if (this.detailComments.length === 0) { Text('还没有评论，来说点什么吧。').fontSize(13).fontColor(this.palette().muted) }
      ForEach(this.detailComments, (c: CommunityComment) => {
        Column({ space: 4 }) {
          Row() { Text(c.author_name).fontSize(12).fontColor(this.palette().primary).layoutWeight(1); Text(c.created_at).fontSize(10).fontColor(this.palette().muted) }
          Text(c.content).fontSize(13).fontColor(this.palette().text)
          Text('回复').fontSize(11).fontColor(this.palette().muted).onClick(() => { this.replyToId = c.id; this.replyToName = c.author_name; this.commentInput = `@${c.author_name} `; })
        }.width('100%').alignItems(HorizontalAlign.Start).padding(14).backgroundColor(this.palette().surface).borderRadius(16)
      }, (c: CommunityComment) => c.id)
      Column({ space: 8 }) {
        if (this.replyToId.length > 0) { Row() { Text(`回复 @${this.replyToName}`).fontSize(12).fontColor(this.palette().primary); Blank(); Text('取消').fontSize(12).fontColor(this.palette().muted).onClick(() => { this.replyToId = ''; this.replyToName = ''; this.commentInput = ''; }) } }
        TextArea({ text: this.commentInput, placeholder: '写下你的评论…' }).height(80).onChange((value: string) => this.commentInput = value)
        Row() { Toggle({ type: ToggleType.Checkbox, isOn: this.commentAnonymous }).onChange((value: boolean) => this.commentAnonymous = value); Text('匿名').fontSize(12).fontColor(this.palette().muted).margin({ left: 6 }); Blank(); Button('发送').enabled(this.commentInput.trim().length > 0).onClick(() => { this.onAddComment(this.commentInput.trim(), this.commentAnonymous, this.replyToId.length > 0 ? this.replyToId : undefined); this.commentInput = ''; this.replyToId = ''; this.replyToName = ''; }) }
      }.width('100%').padding(14).backgroundColor(this.palette().surface).borderRadius(18)
    }
  }

  @Builder PostFormContent(isEdit: boolean) {
    Column({ space: 12 }) {
      Row({ space: 8 }) { Text('●').fontSize(20).fontColor(this.palette().primary); Text(isEdit ? '修改帖子内容，保存后即时生效' : '分享校园信息，友善交流，注意保护隐私').fontSize(13).fontColor(this.palette().text) }
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
      if (this.categoryInput === 'recruit') {
        Row({ space: 8 }) { Text('招募人数').fontSize(14).fontColor(this.palette().text).width(70); TextInput({ text: this.extraHeadcount, placeholder: '如 5' }).layoutWeight(1).onChange((v: string) => this.extraHeadcount = v) }.width('100%').padding(10).backgroundColor(this.palette().surface).borderRadius(14)
        Row({ space: 8 }) { Text('截止时间').fontSize(14).fontColor(this.palette().text).width(70); TextInput({ text: this.extraDeadline, placeholder: '如 2026-12-31' }).layoutWeight(1).onChange((v: string) => this.extraDeadline = v) }.width('100%').padding(10).backgroundColor(this.palette().surface).borderRadius(14)
      }
      if (this.categoryInput === 'errand') {
        Row({ space: 8 }) { Text('酬金(元)').fontSize(14).fontColor(this.palette().text).width(70); TextInput({ text: this.extraPrice, placeholder: '如 10' }).layoutWeight(1).onChange((v: string) => this.extraPrice = v) }.width('100%').padding(10).backgroundColor(this.palette().surface).borderRadius(14)
        Row({ space: 8 }) { Text('截止时间').fontSize(14).fontColor(this.palette().text).width(70); TextInput({ text: this.extraDeadline, placeholder: '如 2026-12-31' }).layoutWeight(1).onChange((v: string) => this.extraDeadline = v) }.width('100%').padding(10).backgroundColor(this.palette().surface).borderRadius(14)
      }
      if (this.categoryInput === 'lostfound') {
        Row({ space: 8 }) { Text('类型').fontSize(14).fontColor(this.palette().text).width(70); Button('寻物').backgroundColor(this.extraKind === 'lost' ? this.palette().primary : this.palette().soft).onClick(() => this.extraKind = 'lost'); Button('招领').backgroundColor(this.extraKind === 'found' ? this.palette().primary : this.palette().soft).onClick(() => this.extraKind = 'found') }.width('100%').padding(10).backgroundColor(this.palette().surface).borderRadius(14)
        Row({ space: 8 }) { Text('联系方式').fontSize(14).fontColor(this.palette().text).width(70); TextInput({ text: this.extraContact, placeholder: '可选' }).layoutWeight(1).onChange((v: string) => this.extraContact = v) }.width('100%').padding(10).backgroundColor(this.palette().surface).borderRadius(14)
      }
      Text(`● 添加图片（${this.postImages.length}/9）`).fontSize(17).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
      Flex({ wrap: FlexWrap.Wrap }) {
        ForEach(this.postImages, (img: string) => {
          Stack({ alignContent: Alignment.TopEnd }) {
            Image(`${this.apiBaseUrl}${img}`).width(80).height(80).borderRadius(10).objectFit(ImageFit.Cover)
            Text('×').fontSize(16).fontColor('#ffffff').backgroundColor('#dc2626').width(20).height(20).borderRadius(10).textAlign(TextAlign.Center).onClick(() => this.onRemoveImage(img))
          }.margin({ right: 6, bottom: 6 })
        }, (img: string) => img)
        if (this.postImages.length < 9) {
          Button('＋').width(80).height(80).backgroundColor(this.palette().soft).fontColor(this.palette().primary).onClick(() => this.onChooseImage())
        }
      }.width('100%')
      Row({ space: 8 }) { Toggle({ type: ToggleType.Switch, isOn: this.anonymous }).onChange((value: boolean) => this.anonymous = value); Column({ space: 2 }) { Text('校园匿名').fontColor(this.palette().text); Text('发布后将隐藏你的姓名和个人信息').fontSize(11).fontColor(this.palette().muted) }.alignItems(HorizontalAlign.Start) }
        .width('100%').padding(14).backgroundColor(this.palette().surface).borderRadius(18)
      Row({ space: 8 }) { Text('⌖ 添加地点').fontSize(15).fontColor(this.palette().text); TextInput({ text: this.locationInput, placeholder: '选择校内位置' }).layoutWeight(1).onChange((value: string) => this.locationInput = value) }.width('100%').padding(12).backgroundColor(this.palette().surface).borderRadius(18)
      Row({ space: 8 }) { Text('# 话题标签').fontSize(15).fontColor(this.palette().text); TextInput({ text: this.tagInput, placeholder: '添加标签' }).layoutWeight(1).onChange((value: string) => this.tagInput = value) }.width('100%').padding(12).backgroundColor(this.palette().surface).borderRadius(18)
      Row() { Toggle({ type: ToggleType.Switch, isOn: this.allowComments }).onChange((value: boolean) => this.allowComments = value); Text('允许评论').margin({ left: 8 }).fontColor(this.palette().text); Blank(); Button(isEdit ? '保存修改' : '立即发布').enabled(this.titleInput.trim().length > 0 && this.contentInput.trim().length > 0).onClick(() => { const extra: CommunityPostExtra = { location: this.locationInput, topic_tag: this.tagInput, allow_comments: this.allowComments }; if (this.categoryInput === 'recruit') { if (this.extraHeadcount) extra.headcount = Number(this.extraHeadcount); if (this.extraDeadline) extra.deadline = this.extraDeadline; } if (this.categoryInput === 'errand') { if (this.extraPrice) extra.price = Number(this.extraPrice); if (this.extraDeadline) extra.deadline = this.extraDeadline; } if (this.categoryInput === 'lostfound') { extra.kind = this.extraKind; if (this.extraContact) extra.contact = this.extraContact; extra.contact_visibility = 'private'; } if (isEdit) { this.onEdit(this.titleInput.trim(), this.contentInput.trim(), this.anonymous, this.categoryInput, extra); } else { this.onPublish(this.titleInput.trim(), this.contentInput.trim(), this.anonymous, this.categoryInput, extra); } this.titleInput = ''; this.contentInput = ''; this.onBack(); }) }
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
      if (this.route === 'university') {
        this.UniversityContent()
      } else {
        Scroll() {
          Column({ space: 13 }) {
            if (this.loading) { LoadingProgress().width(28).height(28).color(this.palette().primary) }
            if (this.route === 'community') { this.CommunityContent() }
            else if (this.route === 'community_hot') { this.HotTopicsContent() }
            else if (this.route === 'community_publish') { this.PostFormContent(false) }
            else if (this.route === 'community_detail') { this.CommunityDetailContent() }
            else if (this.route === 'community_edit') { this.PostFormContent(true) }
            else { this.AcademicContent() }
            Blank().height(30)
          }.width('100%').padding({ left: 16, right: 16, top: 6 })
        }.layoutWeight(1).align(Alignment.Top).scrollBar(BarState.Off)
      }
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

import { LostFoundItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';

@Component
export struct LostFoundPage {
  @Prop items: LostFoundItem[] = [];
  @Prop loading: boolean = false;
  @Prop submitting: boolean = false;
  @Prop darkMode: boolean = false;
  @State kind: string = 'lost';
  @State query: string = '';
  @State category: string = '全部';
  @State locationIndex: number = 0;
  @State newestFirst: boolean = true;
  @State showMine: boolean = false;
  @State showPublish: boolean = false;
  @State selectedId: string = '';
  @State title: string = '';
  @State content: string = '';
  @State location: string = '';
  @State contact: string = '';
  onBack: () => void = () => {};
  onFilter: (kind: string) => void = () => {};
  onSubmit: (kind: string, title: string, content: string, location: string, contact: string) => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  selectedItem(): LostFoundItem | undefined { return this.items.find((item: LostFoundItem) => item.id === this.selectedId); }

  imageFor(index: number): Resource {
    if (index % 4 === 0) return $r('app.media.lost_book');
    if (index % 4 === 1) return $r('app.media.lost_card');
    if (index % 4 === 2) return $r('app.media.lost_earbuds');
    return $r('app.media.lost_power_bank');
  }

  filteredItems(): LostFoundItem[] {
    const key = this.query.trim();
    const categoryKey = this.category === '全部' ? '' : this.category;
    const result = this.items.filter((item: LostFoundItem) => item.kind === this.kind && (key.length === 0 || (item.title ?? '').includes(key) || (item.location ?? '').includes(key)) && (categoryKey.length === 0 || (item.title ?? '').includes(categoryKey) || (item.content ?? '').includes(categoryKey)));
    return this.newestFirst ? result : result.reverse();
  }

  @Builder Tabs() {
    Row() {
      ForEach([['lost','失物'],['found','招领']], (entry: string[]) => {
        Column({ space: 5 }) {
          Text(entry[1]).fontColor(this.kind === entry[0] ? this.palette().primary : this.palette().muted).fontSize(14).fontWeight(FontWeight.Bold)
          Rect().width(32).height(3).fill(this.kind === entry[0] ? this.palette().primary : Color.Transparent).radius(2)
        }.layoutWeight(1).padding({ top: 8, bottom: 6 }).onClick(() => { this.kind = entry[0]; this.onFilter(entry[0]); })
      })
    }.width('100%').height(68).padding(5).backgroundColor(this.palette().surface).borderRadius(25).border({ width: 1, color: this.palette().line })
  }

  @Builder ItemCard(item: LostFoundItem, index: number) {
    Row({ space: 12 }) {
      Image(this.imageFor(index)).width(112).height(126).objectFit(ImageFit.Cover).borderRadius(20)
      Column({ space: 6 }) {
        Row() {
          Text(item.title).fontColor(this.palette().text).fontSize(19).fontWeight(FontWeight.Bold).maxLines(1).layoutWeight(1)
          Text(item.status === 'closed' ? '已解决' : '寻找中').fontColor(item.status === 'closed' ? this.palette().muted : '#FFF06B45').fontSize(11).fontWeight(FontWeight.Bold)
            .padding({ left: 9, right: 9, top: 6, bottom: 6 }).backgroundColor(item.status === 'closed' ? this.palette().soft : '#FFFFF0EA').borderRadius(14)
        }.width('100%')
        Row({ space: 7 }) {
          Text(item.kind === 'lost' ? '失物招领' : '招领物品').fontColor(item.kind === 'lost' ? '#FFF06B45' : this.palette().success).fontSize(10).fontWeight(FontWeight.Bold)
            .padding({ left: 8, right: 8, top: 5, bottom: 5 }).backgroundColor(item.kind === 'lost' ? '#FFFFEEE8' : '#FFEAF9F3').borderRadius(11)
          Text('电子产品').fontColor(this.palette().primary).fontSize(10).fontWeight(FontWeight.Bold)
            .padding({ left: 8, right: 8, top: 5, bottom: 5 }).backgroundColor(this.palette().soft).borderRadius(11)
        }
        Row({ space: 4 }) {
          SymbolGlyph($r('sys.symbol.location_up')).fontSize(12).fontColor([this.palette().muted])
          Text(item.location ?? '地点未填写').fontColor(this.palette().muted).fontSize(11).maxLines(1)
          Text(' | ').fontColor(this.palette().line).fontSize(11)
          SymbolGlyph($r('sys.symbol.clock')).fontSize(12).fontColor([this.palette().muted])
          Text((item.created_at ?? '刚刚').substring(0, Math.min(10, (item.created_at ?? '刚刚').length))).fontColor(this.palette().muted).fontSize(10).maxLines(1)
        }
        Text((item.content ?? '物品外观良好，如有线索请联系发布者。')).fontColor(this.palette().muted).fontSize(11).maxLines(2).lineHeight(18)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
    }.width('100%').padding(14).backgroundColor(this.palette().surface).borderRadius(27)
      .border({ width: 1, color: this.palette().line })
      .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: 20 })))
      .onClick(() => this.selectedId = item.id)
  }

  @Builder ItemDetail(item: LostFoundItem) {
    Scroll() {
      Column({ space: 13 }) {
        Column({ space: 8 }) {
          Text(item.title).fontColor(this.palette().text).fontSize(20).fontWeight(FontWeight.Bold).width('100%')
          Row({ space: 8 }) {
            Text(item.kind === 'lost' ? '失物' : '招领').fontColor(item.kind === 'lost' ? '#FFE35F42' : this.palette().success).fontSize(11).fontWeight(FontWeight.Bold)
              .padding({ left: 8, right: 8, top: 4, bottom: 4 }).backgroundColor(item.kind === 'lost' ? '#FFFFEFEA' : '#FFEAF9F3').borderRadius(10)
            Text(item.status === 'closed' ? '已解决' : '寻找中').fontColor(this.palette().muted).fontSize(11)
          }
        }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(18)
        Column() {
          this.DetailRow($r('sys.symbol.info_circle'), '类型', item.kind === 'lost' ? '失物' : '招领')
          Divider().color(this.palette().line)
          this.DetailRow($r('sys.symbol.location_up'), '地点', item.location ?? '地点未填写')
          Divider().color(this.palette().line)
          this.DetailRow($r('sys.symbol.clock'), '发布时间', item.created_at ?? '时间待记录')
          Divider().color(this.palette().line)
          this.DetailRow($r('sys.symbol.phone'), '联系方式', item.contact ?? '未提供')
          Divider().color(this.palette().line)
          this.DetailRow($r('sys.symbol.checkmark_circle'), '状态', item.status === 'closed' ? '已解决' : '寻找中')
        }.width('100%').padding({ left: 14, right: 14 }).backgroundColor(this.palette().surface).borderRadius(18)
        if ((item.content ?? '').length > 0) {
          Column({ space: 6 }) {
            Text('详细描述').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold)
            Text(item.content ?? '').fontColor(this.palette().muted).fontSize(12).lineHeight(20)
          }.width('100%').padding(14).backgroundColor(this.palette().surface).borderRadius(16)
        }
      }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
    }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
  }

  @Builder DetailRow(symbol: Resource, label: string, value: string) {
    Row({ space: 11 }) {
      SymbolGlyph(symbol).fontSize(19).fontColor([this.palette().primary])
      Text(label).fontColor(this.palette().muted).fontSize(11).width(74)
      Text(value).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Medium).layoutWeight(1)
    }.width('100%').padding({ top: 14, bottom: 14 })
  }

  @Builder BrowsePage() {
    Scroll() {
      Column({ space: 14 }) {
        Stack({ alignContent: Alignment.TopStart }) {
          Image($r('app.media.hero_lost_found_cutout')).width('100%').height(278).objectFit(ImageFit.Cover)
          Column({ space: 10 }) {
            Text('失物招领').fontColor('#FF102452').fontSize(36).fontWeight(FontWeight.Bold)
            Text('本地显示数据，接入后端后\n可全校同步').fontColor('#FF536888').fontSize(15).lineHeight(24)
          }.width('55%').padding({ left: 18, top: 104 }).alignItems(HorizontalAlign.Start)
          Row({ space: 10 }) {
            Text('我的发布').fontColor(this.palette().primary).fontSize(14).fontWeight(FontWeight.Bold).padding({ left: 16, right: 16, top: 11, bottom: 11 })
              .backgroundColor('#D9FFFFFF').border({ width: 1, color: '#CCFFFFFF' }).borderRadius(22).onClick(() => this.showMine = true)
            Stack({ alignContent: Alignment.Center }) { SymbolGlyph($r('sys.symbol.plus')).fontSize(27).fontColor(['#FFFFFFFF']) }
              .width(52).height(52).backgroundColor(this.palette().primary).borderRadius(26).shadow({ radius: 15, color: '#665B68F2', offsetY: 6 }).onClick(() => this.showPublish = true)
          }.padding({ top: 16, right: 16 }).align(Alignment.TopEnd)
        }.width('100%').height(278)
        this.Tabs()
        Row({ space: 9 }) {
          SymbolGlyph($r('sys.symbol.magnifyingglass')).fontSize(18).fontColor([this.palette().muted])
          TextInput({ placeholder: '搜索物品、地点', text: this.query }).layoutWeight(1).height(52)
            .fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(Color.Transparent)
            .onChange((value: string) => this.query = value)
        }.width('100%').height(62).padding({ left: 17, right: 14 }).backgroundColor(this.palette().surface)
          .border({ width: 1, color: this.palette().line }).borderRadius(23)
        Scroll() {
          Row({ space: 8 }) {
            ForEach(['全部', '证件卡片', '电子产品', '书籍资料', '生活用品', '其他'], (entry: string) => {
              Text(entry).fontColor(this.category === entry ? '#FFFFFFFF' : this.palette().text).fontSize(11).fontWeight(FontWeight.Medium)
                .padding({ left: 14, right: 14, top: 10, bottom: 10 }).backgroundColor(this.category === entry ? this.palette().primary : this.palette().surface)
                .border({ width: 1, color: this.category === entry ? this.palette().primary : this.palette().line }).borderRadius(13).onClick(() => this.category = entry)
            })
          }.width('max-content')
        }.width('100%').scrollBar(BarState.Off).scrollable(ScrollDirection.Horizontal)
        Row() {
          Row({ space: 8 }) {
            SymbolGlyph($r('sys.symbol.location_up')).fontSize(17).fontColor([this.palette().muted])
            Text(['全部地点', '图书馆', '教学楼', '宿舍区'][this.locationIndex]).fontColor(this.palette().text).fontSize(12).fontWeight(FontWeight.Medium)
            SymbolGlyph($r('sys.symbol.chevron_down')).fontSize(14).fontColor([this.palette().muted])
          }.padding({ left: 15, right: 13, top: 13, bottom: 13 }).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(17)
            .onClick(() => this.locationIndex = (this.locationIndex + 1) % 4)
          Blank()
          Row({ space: 8 }) {
            SymbolGlyph($r('sys.symbol.line_3_horizontal')).fontSize(17).fontColor([this.palette().muted])
            Text(this.newestFirst ? '最新优先' : '最早优先').fontColor(this.palette().text).fontSize(12).fontWeight(FontWeight.Medium)
            SymbolGlyph($r('sys.symbol.chevron_down')).fontSize(14).fontColor([this.palette().muted])
          }.padding({ left: 15, right: 13, top: 13, bottom: 13 }).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(17)
            .onClick(() => this.newestFirst = !this.newestFirst)
        }.width('100%')
        Row() {
          Text(this.kind === 'lost' ? '正在寻找' : '最新招领').fontColor(this.palette().text).fontSize(17).fontWeight(FontWeight.Bold)
          Blank(); Text(`${this.filteredItems().length} 条`).fontColor(this.palette().muted).fontSize(10)
        }.width('100%')
        if (this.loading) {
          LoadingProgress().width(34).height(34).color(this.palette().primary).margin({ top: 32 })
        } else if (this.filteredItems().length === 0) {
          Column({ space: 8 }) {
            SymbolGlyph($r('sys.symbol.magnifyingglass')).fontSize(32).fontColor([this.palette().muted])
            Text('没有找到匹配的失物信息').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
            Text('换个关键词或筛选条件试试').fontColor(this.palette().muted).fontSize(11)
          }.width('100%').padding({ top: 30, bottom: 30 })
        } else {
          ForEach(this.filteredItems(), (item: LostFoundItem, index: number) => { this.ItemCard(item, index) }, (item: LostFoundItem) => item.id)
        }
      }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
    }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
  }

  @Builder MinePage() {
    Scroll() {
      Column({ space: 13 }) {
        Text('我的发布').fontColor(this.palette().text).fontSize(22).fontWeight(FontWeight.Bold).width('100%')
        Text('查看我发布的失物与招领信息').fontColor(this.palette().muted).fontSize(12).width('100%')
        if (this.items.length === 0) {
          Text('暂时没有发布记录').fontColor(this.palette().muted).fontSize(12).padding(30)
        } else {
          ForEach(this.items, (item: LostFoundItem, index: number) => { this.ItemCard(item, index) }, (item: LostFoundItem) => item.id)
        }
      }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
    }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
  }

  @Builder PublishPage() {
    Scroll() {
      Column({ space: 13 }) {
        Row({ space: 7 }) {
          ForEach([['lost','我丢了物品'],['found','我捡到物品']], (entry: string[]) => {
            Text(entry[1]).layoutWeight(1).textAlign(TextAlign.Center).fontSize(11).padding({ top: 9, bottom: 9 })
              .fontColor(this.kind === entry[0] ? '#FFFFFFFF' : this.palette().muted)
              .backgroundColor(this.kind === entry[0] ? this.palette().primary : this.palette().surface)
              .border({ width: 1, color: this.kind === entry[0] ? this.palette().primary : this.palette().line }).borderRadius(18)
              .onClick(() => this.kind = entry[0])
          })
        }.width('100%')
        TextInput({ placeholder: '物品名称或信息标题', text: this.title }).height(50)
          .fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(this.palette().surface)
          .border({ width: 1, color: this.palette().line }).borderRadius(15).onChange((value: string) => this.title = value)
        TextArea({ placeholder: '描述物品特征、丢失或拾到的经过', text: this.content }).height(132)
          .fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(this.palette().surface)
          .border({ width: 1, color: this.palette().line }).borderRadius(15).onChange((value: string) => this.content = value)
        TextInput({ placeholder: '地点', text: this.location }).height(50).fontColor(this.palette().text).placeholderColor(this.palette().muted)
          .backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(15).onChange((value: string) => this.location = value)
        TextInput({ placeholder: '联系方式', text: this.contact }).height(50).fontColor(this.palette().text).placeholderColor(this.palette().muted)
          .backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(15).onChange((value: string) => this.contact = value)
        Button(this.submitting ? '发布中...' : '发布信息').width('100%').height(52).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF')
          .enabled(!this.submitting && this.title.trim().length > 0)
          .onClick(() => { this.onSubmit(this.kind, this.title.trim(), this.content.trim(), this.location.trim(), this.contact.trim()); this.showPublish = false; })
        Button('返回失物招领').width('100%').height(46).backgroundColor(this.palette().soft).fontColor(this.palette().primary).onClick(() => this.showPublish = false)
      }.width('100%').padding({ left: 17, right: 17, top: 6, bottom: 24 })
    }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
  }

  build() {
    Column() {
      SecondaryHeader({ title: this.showPublish ? '发布失物招领' : this.selectedId.length > 0 ? '详情' : this.showMine ? '我的发布' : '失物招领', subtitle: this.showPublish ? '请如实填写物品信息' : this.selectedId.length > 0 ? '查看失物招领详情' : this.showMine ? '管理我的发布记录' : '', darkMode: this.darkMode, onBack: () => { if (this.showPublish) { this.showPublish = false; } else if (this.selectedId.length > 0) { this.selectedId = ''; } else if (this.showMine) { this.showMine = false; } else { this.onBack(); } } })
      if (this.showPublish) { this.PublishPage() }
      else if (this.selectedItem() !== undefined) { this.ItemDetail(this.selectedItem()!) }
      else if (this.showMine) { this.MinePage() }
      else { this.BrowsePage() }
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

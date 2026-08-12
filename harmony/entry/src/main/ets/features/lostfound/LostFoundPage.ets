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
    return this.items.filter((item: LostFoundItem) => item.kind === this.kind && (key.length === 0 || (item.title ?? '').includes(key) || (item.location ?? '').includes(key)));
  }

  @Builder Tabs() {
    Row() {
      ForEach([['lost','失物'],['found','招领']], (entry: string[]) => {
        Column({ space: 5 }) {
          Text(entry[1]).fontColor(this.kind === entry[0] ? this.palette().primary : this.palette().muted).fontSize(14).fontWeight(FontWeight.Bold)
          Rect().width(32).height(3).fill(this.kind === entry[0] ? this.palette().primary : Color.Transparent).radius(2)
        }.layoutWeight(1).padding({ top: 8, bottom: 6 }).onClick(() => { this.kind = entry[0]; this.onFilter(entry[0]); })
      })
    }.width('100%').backgroundColor(this.palette().surface).borderRadius(16)
  }

  @Builder ItemCard(item: LostFoundItem, index: number) {
    Row({ space: 12 }) {
      Image(this.imageFor(index)).width(104).height(92).objectFit(ImageFit.Cover).borderRadius(14)
      Column({ space: 6 }) {
        Row() {
          Text(item.kind === 'lost' ? '失物' : '招领').fontColor(item.kind === 'lost' ? '#FFE35F42' : this.palette().success).fontSize(9).fontWeight(FontWeight.Bold)
            .padding({ left: 7, right: 7, top: 4, bottom: 4 }).backgroundColor(item.kind === 'lost' ? '#FFFFEFEA' : '#FFEAF9F3').borderRadius(9)
          Blank()
          Text(item.status === 'closed' ? '已解决' : '寻找中').fontColor(this.palette().muted).fontSize(9)
        }.width('100%')
        Text(item.title).fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold).maxLines(2)
        Row({ space: 4 }) {
          SymbolGlyph($r('sys.symbol.location_up')).fontSize(12).fontColor([this.palette().muted])
          Text(item.location ?? '地点未填写').fontColor(this.palette().muted).fontSize(10).maxLines(1)
        }
        Text((item.created_at ?? '').substring(0, Math.min(10, (item.created_at ?? '').length))).fontColor(this.palette().muted).fontSize(9)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
    }.width('100%').padding(11).backgroundColor(this.palette().surface).borderRadius(18)
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
      Column({ space: 12 }) {
        Stack({ alignContent: Alignment.BottomStart }) {
          Image($r('app.media.hero_lost_found')).width('100%').height(176).objectFit(ImageFit.Cover)
          Column({ space: 4 }) {
            Text('失物招领').fontColor('#FFFFFFFF').fontSize(27).fontWeight(FontWeight.Bold)
            Text('让每一件物品，都有机会回到主人身边').fontColor('#E6FFFFFF').fontSize(11)
          }.padding({ left: 16, bottom: 14 }).alignItems(HorizontalAlign.Start)
        }.width('100%').height(176).borderRadius(20).clip(true)
        this.Tabs()
        Row({ space: 9 }) {
          SymbolGlyph($r('sys.symbol.magnifyingglass')).fontSize(18).fontColor([this.palette().muted])
          TextInput({ placeholder: '搜索物品、地点', text: this.query }).layoutWeight(1).height(44)
            .fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(Color.Transparent)
            .onChange((value: string) => this.query = value)
          Stack({ alignContent: Alignment.Center }) {
            SymbolGlyph($r('sys.symbol.plus')).fontSize(18).fontColor(['#FFFFFFFF'])
          }.width(38).height(38).backgroundColor(this.palette().primary).borderRadius(19).onClick(() => this.showPublish = true)
        }.width('100%').height(52).padding({ left: 12, right: 7 }).backgroundColor(this.palette().surface)
          .border({ width: 1, color: this.palette().line }).borderRadius(17)
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
      SecondaryHeader({ title: this.showPublish ? '发布失物招领' : this.selectedId.length > 0 ? '详情' : '失物招领', subtitle: this.showPublish ? '请如实填写物品信息' : this.selectedId.length > 0 ? '查看失物招领详情' : '搜索、筛选并发布真实信息', darkMode: this.darkMode, onBack: () => { if (this.showPublish) { this.showPublish = false; } else if (this.selectedId.length > 0) { this.selectedId = ''; } else { this.onBack(); } } })
      if (this.showPublish) { this.PublishPage() }
      else if (this.selectedItem() !== undefined) { this.ItemDetail(this.selectedItem()!) }
      else { this.BrowsePage() }
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

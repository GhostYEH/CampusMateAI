import { ServiceRequestItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';

@Component
export struct ServicesPage {
  @Prop requests: ServiceRequestItem[] = [];
  @Prop loading: boolean = false;
  @Prop submitting: boolean = false;
  @Prop darkMode: boolean = false;
  @State showForm: boolean = false;
  @State formKind: string = 'leave';
  @State formTitle: string = '';
  @State formContent: string = '';
  @State selectedId: string = '';
  onBack: () => void = () => {};
  onRefresh: () => void = () => {};
  onSubmit: (kind: string, title: string, content: string) => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  selectedRequest(): ServiceRequestItem | undefined { return this.requests.find((item: ServiceRequestItem) => item.id === this.selectedId); }

  kindTitle(kind: string): string {
    if (kind === 'leave') return '请假申请';
    if (kind === 'repair') return '宿舍报修';
    if (kind === 'certificate') return '证明开具';
    return '意见反馈';
  }

  openForm(kind: string): void {
    this.formKind = kind;
    this.formTitle = '';
    this.formContent = '';
    this.showForm = true;
  }

  @Builder ServiceTile(kind: string, subtitle: string, symbol: Resource, color: string) {
    Column({ space: 8 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph(symbol).fontSize(23).fontColor([color])
      }.width(46).height(46).backgroundColor(this.palette().soft).borderRadius(14)
      Text(this.kindTitle(kind)).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
      Text(subtitle).fontColor(this.palette().muted).fontSize(9).maxLines(1)
    }.width('48%').padding({ top: 15, bottom: 15 }).backgroundColor(this.palette().surface).borderRadius(20)
      .onClick(() => this.openForm(kind))
      .scale({ x: 1, y: 1 })
      .animation({ duration: 200, curve: Curve.EaseInOut })
      .gesture(
        TapGesture({ count: 1 })
          .onAction(() => {
            animateTo({ duration: 150, curve: Curve.EaseInOut }, () => {
            })
          })
      )
  }

  @Builder RequestRow(item: ServiceRequestItem) {
    Row({ space: 10 }) {
      Stack({ alignContent: Alignment.Center }) {
        if (item.kind === 'repair') {
          SymbolGlyph($r('sys.symbol.wrench_and_screwdriver')).fontSize(19).fontColor([this.palette().primary])
        } else {
          SymbolGlyph($r('sys.symbol.doc_text')).fontSize(19).fontColor([this.palette().primary])
        }
      }.width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
      Column({ space: 4 }) {
        Text(item.title).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold).maxLines(1)
        Text(`申请时间：${item.created_at.substring(0, Math.min(10, item.created_at.length))}`).fontColor(this.palette().muted).fontSize(9)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      Text(item.status === 'completed' ? '已完成' : item.status === 'processing' ? '处理中' : '已提交')
        .fontColor(item.status === 'completed' ? this.palette().success : this.palette().primary).fontSize(10).fontWeight(FontWeight.Bold)
      SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(16).fontColor([this.palette().muted])
    }.width('100%').padding({ top: 11, bottom: 11 }).onClick(() => this.selectedId = item.id)
  }

  @Builder DetailPage(item: ServiceRequestItem) {
    Scroll() {
      Column({ space: 14 }) {
        Column({ space: 8 }) {
          Stack({ alignContent: Alignment.Center }) { SymbolGlyph($r('sys.symbol.doc_text')).fontSize(29).fontColor([this.palette().primary]) }
            .width(62).height(62).backgroundColor(this.palette().soft).borderRadius(20)
          Text(item.title).fontColor(this.palette().text).fontSize(21).fontWeight(FontWeight.Bold).textAlign(TextAlign.Center)
          Text(item.status === 'completed' ? '已完成' : item.status === 'processing' ? '处理中' : '已提交')
            .fontColor(item.status === 'completed' ? this.palette().success : this.palette().primary).fontSize(11).fontWeight(FontWeight.Bold)
        }.width('100%').padding({ top: 22, bottom: 20 }).backgroundColor(this.palette().surface).borderRadius(20)
        Text(item.content ?? '暂无详细说明').fontColor(this.palette().text).fontSize(13).lineHeight(21).width('100%').padding(15).backgroundColor(this.palette().surface).borderRadius(17)
        Column() {
          this.RequestMeta('业务类型', this.kindTitle(item.kind))
          Divider().color(this.palette().line)
          this.RequestMeta('申请时间', item.created_at)
          Divider().color(this.palette().line)
          this.RequestMeta('申请编号', item.id)
        }.width('100%').padding({ left: 14, right: 14 }).backgroundColor(this.palette().surface).borderRadius(17)
      }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
    }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
  }

  @Builder RequestMeta(label: string, value: string) {
    Row() { Text(label).fontColor(this.palette().muted).fontSize(11); Blank(); Text(value).fontColor(this.palette().text).fontSize(12).maxLines(1) }
      .width('100%').padding({ top: 14, bottom: 14 })
  }

  @Builder MainPage() {
    Scroll() {
      Column({ space: 13 }) {
        Stack({ alignContent: Alignment.BottomStart }) {
          Image($r('app.media.hero_services')).width('100%').height(178).objectFit(ImageFit.Cover)
          Column({ space: 5 }) {
            Text('办事大厅').fontColor('#FFFFFFFF').fontSize(28).fontWeight(FontWeight.Bold)
            Text('一站式校园服务中心，办事更轻松').fontColor('#E6FFFFFF').fontSize(12)
          }.padding({ left: 16, bottom: 15 }).alignItems(HorizontalAlign.Start)
        }.width('100%').height(178).borderRadius(20).clip(true)
        Row() {
          Column({ space: 2 }) {
            Text('高频服务 · 一键直达').fontColor(this.palette().text).fontSize(17).fontWeight(FontWeight.Bold)
            Text('快速处理常用事务，节省您的时间').fontColor(this.palette().muted).fontSize(10)
          }.alignItems(HorizontalAlign.Start)
          Blank()
          Text(`${this.requests.length} 条记录`).fontColor(this.palette().muted).fontSize(10)
        }.width('100%')
        Column({ space: 9 }) {
          Row() {
            this.ServiceTile('leave', '在线填写请假信息', $r('sys.symbol.calendar'), this.palette().primary)
            Blank()
            this.ServiceTile('repair', '提交设施维修申请', $r('sys.symbol.wrench_and_screwdriver'), '#FFF18C5C')
          }.width('100%')
          Row() {
            this.ServiceTile('certificate', '常用材料在线申请', $r('sys.symbol.doc_text'), '#FF4E8C6A')
            Blank()
            this.ServiceTile('feedback', '意见建议直达校园', $r('sys.symbol.message'), '#FF7A68D8')
          }.width('100%')
        }.width('100%')
        Row({ space: 8 }) {
          Rect().width(5).height(24).fill(this.palette().primary).radius(3)
          Text('最近申请').fontColor(this.palette().text).fontSize(17).fontWeight(FontWeight.Bold)
          Blank()
          Text('刷新').fontColor(this.palette().muted).fontSize(11).onClick(() => this.onRefresh())
        }.width('100%')
        Column() {
          if (this.loading) {
            LoadingProgress().width(34).height(34).color(this.palette().primary).margin(30)
          } else if (this.requests.length === 0) {
            Text('暂无申请记录').fontColor(this.palette().muted).fontSize(12).padding(30)
          } else {
            ForEach(this.requests, (item: ServiceRequestItem, index: number) => {
              this.RequestRow(item)
              if (index < this.requests.length - 1) { Divider().color(this.palette().line) }
            }, (item: ServiceRequestItem) => item.id)
          }
        }.width('100%').padding({ left: 14, right: 14 }).backgroundColor(this.palette().surface).borderRadius(20)
      }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
    }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
  }

  @Builder FormPage() {
    Column({ space: 15 }) {
      Text(this.kindTitle(this.formKind)).fontColor(this.palette().text).fontSize(22).fontWeight(FontWeight.Bold).width('100%')
      Text('填写申请信息，提交后可在最近申请中查看进度。').fontColor(this.palette().muted).fontSize(12).width('100%')
      TextInput({ placeholder: '请输入申请标题', text: this.formTitle })
        .height(52).fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(this.palette().surface)
        .border({ width: 1, color: this.palette().line }).borderRadius(15).onChange((value: string) => this.formTitle = value)
      TextArea({ placeholder: '请详细说明你的需求', text: this.formContent })
        .height(160).fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(this.palette().surface)
        .border({ width: 1, color: this.palette().line }).borderRadius(15).onChange((value: string) => this.formContent = value)
      Button(this.submitting ? '提交中...' : '提交申请').width('100%').height(52).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF')
        .enabled(!this.submitting && this.formTitle.trim().length > 0)
        .onClick(() => { this.onSubmit(this.formKind, this.formTitle.trim(), this.formContent.trim()); this.showForm = false; })
      Button('返回服务大厅').width('100%').height(46).backgroundColor(this.palette().soft).fontColor(this.palette().primary).onClick(() => this.showForm = false)
    }.width('100%').padding({ left: 18, right: 18, top: 12 })
  }

  build() {
    Column() {
      SecondaryHeader({ title: this.showForm ? this.kindTitle(this.formKind) : this.selectedId.length > 0 ? '申请详情' : '办事大厅', subtitle: this.showForm ? '在线提交校园事务' : this.selectedId.length > 0 ? '查看校园事务处理进度' : '一站式校园服务中心', darkMode: this.darkMode, onBack: () => this.showForm ? this.showForm = false : this.selectedId.length > 0 ? this.selectedId = '' : this.onBack() })
      if (this.showForm) { this.FormPage() }
      else if (this.selectedRequest() !== undefined) { this.DetailPage(this.selectedRequest()!) }
      else { this.MainPage() }
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

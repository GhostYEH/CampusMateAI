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
  @State showAllRequests: boolean = false;
  @State pressedKind: string = '';
  onBack: () => void = () => {};
  onRefresh: () => void = () => {};
  onSubmit: (kind: string, title: string, content: string) => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  selectedRequest(): ServiceRequestItem | undefined { return this.requests.find((item: ServiceRequestItem) => item.id === this.selectedId); }

  kindTitle(kind: string): string {
    if (kind === 'leave') return '请假申请';
    if (kind === 'repair') return '宿舍报修';
    if (kind === 'certificate') return '证明开具';
    if (kind === 'venue') return '场地申请';
    if (kind === 'mine') return '我的申请';
    return '意见反馈';
  }

  openForm(kind: string): void {
    if (kind === 'mine') {
      this.showAllRequests = true;
      return;
    }
    this.formKind = kind;
    this.formTitle = '';
    this.formContent = '';
    this.showForm = true;
  }

  @Builder ServiceTile(kind: string, subtitle: string, symbol: Resource, color: string) {
    Column({ space: 8 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph(symbol).fontSize(23).fontColor([color])
      }.width(48).height(48).backgroundColor(color + '1F').borderRadius(16)
      Text(this.kindTitle(kind)).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
      Text(subtitle).fontColor(this.palette().muted).fontSize(9).maxLines(1)
    }.width('31.5%').height(142).padding({ top: 15, bottom: 13, left: 4, right: 4 }).backgroundColor(this.palette().surface).borderRadius(22)
      .border({ width: 1, color: '#CCFFFFFF' })
      .scale({ x: this.pressedKind === kind ? 0.93 : 1.0, y: this.pressedKind === kind ? 0.93 : 1.0 })
      .animation({ duration: 160, curve: Curve.EaseOut })
      .onClick(() => { this.pressedKind = kind; setTimeout(() => { if (this.pressedKind === kind) this.pressedKind = ''; }, 160); this.openForm(kind); })

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
        Text(`申请时间：${(item.created_at ?? '').substring(0, Math.min(10, (item.created_at ?? '').length))}`).fontColor(this.palette().muted).fontSize(9)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      Text(item.status === 'completed' ? '已完成' : item.status === 'processing' ? '处理中' : '已提交')
        .fontColor(item.status === 'completed' ? this.palette().success : this.palette().primary).fontSize(10).fontWeight(FontWeight.Bold)
      SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(16).fontColor([this.palette().muted])
    }.width('100%').padding({ top: 11, bottom: 11 })
      .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: 12 })).animation({ duration: 280, curve: Curve.EaseOut }))
      .onClick(() => this.selectedId = item.id)
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
          this.RequestMeta('申请时间', item.created_at ?? '时间待记录')
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
      Column({ space: 16 }) {
        Stack({ alignContent: Alignment.TopStart }) {
          Image($r('app.media.hero_services_cutout')).width('100%').height(246).objectFit(ImageFit.Cover)
          Column({ space: 8 }) {
            Text('办事大厅').fontColor('#FF102452').fontSize(34).fontWeight(FontWeight.Bold)
            Text('一站式校园服务中心，办事更轻松').fontColor('#FF5D6D94').fontSize(14)
          }.width('56%').padding({ left: 18, top: 82 }).alignItems(HorizontalAlign.Start)
        }.width('100%').height(246)
        Column({ space: 13 }) {
          Row({ space: 11 }) {
            Stack({ alignContent: Alignment.Center }) { SymbolGlyph($r('sys.symbol.star_fill')).fontSize(23).fontColor([this.palette().primary]) }
              .width(48).height(48).backgroundColor(this.palette().soft).borderRadius(17)
            Column({ space: 4 }) {
              Text('高频服务，一键直达').fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold)
              Text('快速处理常用事务，节省您的时间').fontColor(this.palette().muted).fontSize(10)
            }.layoutWeight(1).alignItems(HorizontalAlign.Start)
            Text('查看全部  ›').fontColor(this.palette().primary).fontSize(11).fontWeight(FontWeight.Medium).onClick(() => this.showAllRequests = true)
          }.width('100%').alignItems(VerticalAlign.Center)
          Row({ space: 7 }) {
            this.MetricCard($r('sys.symbol.doc_text'), this.requests.filter((item: ServiceRequestItem) => item.status === 'processing').length.toString(), '处理中', this.palette().primary)
            this.MetricCard($r('sys.symbol.checkmark_circle'), this.requests.filter((item: ServiceRequestItem) => item.status === 'completed').length.toString(), '已完成', '#FF4F8BF4')
            this.MetricCard($r('sys.symbol.face_smiling'), '98%', '办结满意度', '#FF35BFA5')
          }.width('100%')
        }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(26).border({ width: 1, color: this.palette().line })
        Row({ space: 9 }) {
          Rect().width(5).height(25).fill(this.palette().primary).radius(3)
          Text('常用服务').fontColor(this.palette().text).fontSize(19).fontWeight(FontWeight.Bold)
          Text('校园事务，轻松办理').fontColor(this.palette().muted).fontSize(11)
          Blank()
          Text('全部服务  ›').fontColor(this.palette().muted).fontSize(11).onClick(() => this.showAllRequests = true)
        }.width('100%').alignItems(VerticalAlign.Center)
        Column({ space: 10 }) {
          Row() {
            this.ServiceTile('leave', '在线提交请假申请', $r('sys.symbol.calendar'), this.palette().primary)
            Blank()
            this.ServiceTile('repair', '报修维护更快捷', $r('sys.symbol.wrench_and_screwdriver'), '#FF45A276')
            Blank()
            this.ServiceTile('certificate', '各类证明在线开具', $r('sys.symbol.doc_text'), '#FFF08A4D')
          }.width('100%')
          Row() {
            this.ServiceTile('venue', '场地预约与申请', $r('sys.symbol.house'), '#FF4F8BF4')
            Blank()
            this.ServiceTile('feedback', '反馈问题与建议', $r('sys.symbol.message'), '#FF7A68D8')
            Blank()
            this.ServiceTile('mine', '查看申请进度', $r('sys.symbol.folder'), '#FF35BFA5')
          }.width('100%')
        }.width('100%')
        Row({ space: 8 }) {
          Rect().width(5).height(24).fill(this.palette().primary).radius(3)
          Text('最近申请').fontColor(this.palette().text).fontSize(17).fontWeight(FontWeight.Bold)
          Blank()
          Text('全部记录  ›').fontColor(this.palette().muted).fontSize(11).onClick(() => this.showAllRequests = true)
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

  @Builder MetricCard(symbol: Resource, value: string, label: string, color: string) {
    Row({ space: 6 }) {
      Stack({ alignContent: Alignment.Center }) { SymbolGlyph(symbol).fontSize(17).fontColor([color]) }
        .width(34).height(34).backgroundColor(color + '1C').borderRadius(12)
      Column({ space: 1 }) {
        Text(value).fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold)
        Text(label).fontColor(this.palette().muted).fontSize(8).maxLines(1)
      }.alignItems(HorizontalAlign.Start)
    }.layoutWeight(1).padding({ left: 7, right: 4, top: 10, bottom: 10 }).backgroundColor(color + '0D').borderRadius(15).alignItems(VerticalAlign.Center)
  }

  @Builder AllRequestsPage() {
    Scroll() {
      Column({ space: 12 }) {
        Text('全部申请记录').fontColor(this.palette().text).fontSize(22).fontWeight(FontWeight.Bold).width('100%')
        if (this.requests.length === 0) {
          Text('暂无申请记录').fontColor(this.palette().muted).fontSize(12).padding(30)
        } else {
          ForEach(this.requests, (item: ServiceRequestItem, index: number) => { this.RequestRow(item) }, (item: ServiceRequestItem) => item.id)
        }
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
      SecondaryHeader({ title: this.showForm ? this.kindTitle(this.formKind) : this.selectedId.length > 0 ? '申请详情' : this.showAllRequests ? '我的申请' : '办事大厅', subtitle: this.showForm ? '在线提交校园事务' : this.selectedId.length > 0 ? '查看校园事务处理进度' : this.showAllRequests ? '随时掌握办理进度' : '', darkMode: this.darkMode, onBack: () => this.showForm ? this.showForm = false : this.selectedId.length > 0 ? this.selectedId = '' : this.showAllRequests ? this.showAllRequests = false : this.onBack() })
      if (this.showForm) { this.FormPage() }
      else if (this.selectedRequest() !== undefined) { this.DetailPage(this.selectedRequest()!) }
      else if (this.showAllRequests) { this.AllRequestsPage() }
      else { this.MainPage() }
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

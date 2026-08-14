import { NoticeItem, LocalCapturedNotice, ExtractResult, TaskItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { NotificationIngestService } from '../../data/notification/NotificationIngestService';
import { NotificationCaptureCapability } from '../../data/notification/NotificationCaptureCapability';

@Component
export struct NotificationsPage {
  @Prop notices: NoticeItem[] = [];
  @Prop loading: boolean = false;
  @Prop darkMode: boolean = false;
  @Prop localNotices: LocalCapturedNotice[] = [];
  @Prop subscriberActive: boolean = false;
  @State unreadOnly: boolean = false;
  @State selectedId: string = '';
  @State manualText: string = '';
  @State extracting: boolean = false;
  @State hasExtractResult: boolean = false;
  @State resultError: string = '';
  @State resultTitle: string = '';
  @State resultSource: string = '';
  @State resultDeadline: string = '';
  @State resultConfidence: number = 0;
  @State resultTasks: string[] = [];
  @State editTitle: string = '';
  @State editDeadline: string = '';
  @State editSource: string = '';
  @State saving: boolean = false;
  @State saved: boolean = false;
  @State showLocal: boolean = true;
  ingestService: NotificationIngestService | null = null;
  onBack: () => void = () => {};
  onRefresh: () => void = () => {};
  onToggleSubscriber: () => void = () => {};
  onTaskSaved: () => void = () => {};
  onLocalNoticesChanged: () => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  captureCapability(): NotificationCaptureCapability { return NotificationCaptureCapability.ordinaryPhoneBuild(); }
  visible(): NoticeItem[] { return this.unreadOnly ? this.notices.filter((item: NoticeItem) => item.unread === true) : this.notices; }
  selectedNotice(): NoticeItem | undefined { return this.notices.find((item: NoticeItem) => item.id === this.selectedId); }

  async doExtract(text: string): Promise<void> {
    if (this.ingestService === null) {
      this.extracting = false;
      this.resultError = '通知服务未初始化';
      this.hasExtractResult = true;
      return;
    }
    try {
      const result: ExtractResult = await this.ingestService.extractNotice(text);
      this.resultError = result.error ?? '';
      this.resultTitle = result.title ?? '';
      this.resultSource = result.source ?? '';
      this.resultDeadline = result.deadline ?? '待设置';
      this.resultConfidence = result.confidence ?? 0;
      this.resultTasks = result.tasks ?? [];
      this.editTitle = result.title ?? '';
      this.editSource = result.source ?? '';
      this.editDeadline = result.deadline ?? '待设置';
      this.saved = false;
      this.hasExtractResult = true;
    } catch (e) {
      this.resultError = (e as Error).message;
      this.hasExtractResult = true;
    } finally {
      this.extracting = false;
    }
  }

  async doSaveTask(title: string, deadline: string, source: string): Promise<void> {
    if (this.ingestService === null) {
      this.saving = false;
      return;
    }
    try {
      const task: TaskItem | null = await this.ingestService.createTask(title, deadline, source, '');
      if (task !== null) {
        this.saved = true;
        this.onTaskSaved();
      }
    } catch { } finally { this.saving = false; }
  }

  @Builder SourceRow(symbol: Resource, title: string, subtitle: string, status: string) {
    Row({ space: 11 }) {
      Stack({ alignContent: Alignment.Center }) { SymbolGlyph(symbol).fontSize(20).fontColor([this.palette().primary]) }
        .width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
      Column({ space: 3 }) {
        Text(title).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
        Text(subtitle).fontColor(this.palette().muted).fontSize(10).maxLines(1)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      Text(status).fontColor(this.palette().success).fontSize(10).fontWeight(FontWeight.Medium)
    }.width('100%').padding({ top: 10, bottom: 10 })
  }

  @Builder NoticeRow(item: NoticeItem) {
    Row({ space: 11 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph($r('sys.symbol.bell')).fontSize(20).fontColor([this.palette().primary])
        if (item.unread === true) { Circle().width(7).height(7).fill('#FFE35F42').position({ x: 30, y: 4 }) }
      }.width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
      Column({ space: 4 }) {
        Text(item.title).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold).maxLines(1)
        Text(item.content ?? '暂无详细内容').fontColor(this.palette().muted).fontSize(10).maxLines(2)
        Text(`${item.source ?? '校园通知'} · ${(item.time ?? '').substring(0, Math.min(10, (item.time ?? '').length))}`).fontColor(this.palette().muted).fontSize(9)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
    }.width('100%').padding({ top: 12, bottom: 12 })
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: 20 })))
    .onClick(() => this.selectedId = item.id)
  }

  @Builder LocalNoticeRow(item: LocalCapturedNotice) {
    Row({ space: 11 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph($r('sys.symbol.info_circle')).fontSize(18).fontColor([this.palette().accent])
      }.width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
      Column({ space: 4 }) {
        Text(item.title).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold).maxLines(1)
        Text(item.content).fontColor(this.palette().muted).fontSize(10).maxLines(2)
        Text(`${item.source} · ${item.source_type} · ${item.time.substring(0, Math.min(10, item.time.length))}`).fontColor(this.palette().muted).fontSize(9)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
    }.width('100%').padding({ top: 12, bottom: 12 })
    .onClick(() => {
      this.manualText = item.content;
      this.hasExtractResult = false;
      this.saved = false;
    })
  }

  @Builder NoticeDetail(item: NoticeItem) {
    Scroll() {
      Column({ space: 13 }) {
        Column({ space: 8 }) {
          Text(item.title).fontColor(this.palette().text).fontSize(20).fontWeight(FontWeight.Bold).width('100%')
          Row({ space: 8 }) {
            SymbolGlyph($r('sys.symbol.clock')).fontSize(13).fontColor([this.palette().muted])
            Text(item.time ?? '时间待记录').fontColor(this.palette().muted).fontSize(11)
            Text('·').fontColor(this.palette().muted)
            Text(item.source ?? '校园通知').fontColor(this.palette().muted).fontSize(11)
          }
        }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(18)
        Column({ space: 6 }) {
          Text('通知正文').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold)
          Text(item.content ?? '暂无详细内容').fontColor(this.palette().muted).fontSize(13).lineHeight(22)
        }.width('100%').padding(14).backgroundColor(this.palette().surface).borderRadius(16)
      }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
    }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
  }

  @Builder ManualExtractCard() {
    Column({ space: 10 }) {
      Row({ space: 8 }) {
        SymbolGlyph($r('sys.symbol.bolt')).fontSize(18).fontColor([this.palette().primary])
        Text('手动整理').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold)
        Blank()
        Text('粘贴通知文本自动提取').fontColor(this.palette().muted).fontSize(10)
      }.width('100%')
      TextArea({ text: this.manualText, placeholder: '粘贴微信、QQ或学习通通知内容，自动提取事务并新建日程...' })
        .width('100%').height(90).fontSize(13).fontColor(this.palette().text)
        .backgroundColor(this.palette().background).borderRadius(12)
        .border({ width: 1, color: this.palette().line })
        .onChange((value: string) => { this.manualText = value; this.hasExtractResult = false; this.saved = false; })
      Button(this.extracting ? '提取中...' : '开始整理')
        .width('100%').height(44).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF')
        .borderRadius(12).enabled(this.manualText.trim().length > 0 && !this.extracting)
        .onClick(() => {
          if (this.manualText.trim().length === 0 || this.extracting) { return; }
          this.extracting = true;
          this.hasExtractResult = false;
          this.saved = false;
          this.doExtract(this.manualText.trim());
        })
    }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(18)
  }

  @Builder ExtractResultCard() {
    if (this.hasExtractResult) {
      if (this.resultError.length > 0) {
        Column({ space: 8 }) {
          Row({ space: 8 }) {
            SymbolGlyph($r('sys.symbol.exclamationmark_circle')).fontSize(18).fontColor([this.palette().danger])
            Text('提取失败').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold)
          }
          Text(this.resultError).fontColor(this.palette().muted).fontSize(12).lineHeight(20)
        }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(18)
      } else {
        Column({ space: 12 }) {
          Row({ space: 8 }) {
            SymbolGlyph($r('sys.symbol.checkmark_circle')).fontSize(18).fontColor([this.palette().success])
            Text('提取结果').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold)
            Blank()
            Text(`置信度 ${Math.round(this.resultConfidence * 100)}%`).fontColor(this.palette().muted).fontSize(10)
          }.width('100%')
          Column({ space: 6 }) {
            Text('标题').fontColor(this.palette().muted).fontSize(10)
            TextInput({ text: this.editTitle, placeholder: '事务标题' })
              .width('100%').height(42).fontSize(13).fontColor(this.palette().text)
              .backgroundColor(this.palette().background).borderRadius(10)
              .onChange((value: string) => { this.editTitle = value; })
          }.width('100%')
          Row({ space: 10 }) {
            Column({ space: 6 }) {
              Text('来源').fontColor(this.palette().muted).fontSize(10)
              TextInput({ text: this.editSource, placeholder: '来源' })
                .height(42).fontSize(13).fontColor(this.palette().text)
                .backgroundColor(this.palette().background).borderRadius(10)
                .onChange((value: string) => { this.editSource = value; })
            }.layoutWeight(1)
            Column({ space: 6 }) {
              Text('截止时间').fontColor(this.palette().muted).fontSize(10)
              TextInput({ text: this.editDeadline, placeholder: '待设置' })
                .height(42).fontSize(13).fontColor(this.palette().text)
                .backgroundColor(this.palette().background).borderRadius(10)
                .onChange((value: string) => { this.editDeadline = value; })
            }.layoutWeight(1)
          }.width('100%')
          if (this.resultTasks.length > 0) {
            Column({ space: 5 }) {
              Text('提取的待办项').fontColor(this.palette().muted).fontSize(10)
              ForEach(this.resultTasks, (task: string) => {
                Row({ space: 6 }) {
                  SymbolGlyph($r('sys.symbol.circle_fill')).fontSize(6).fontColor([this.palette().primary])
                  Text(task).fontColor(this.palette().text).fontSize(12).layoutWeight(1)
                }.width('100%')
              }, (task: string, index: number) => `${index}-${task}`)
            }.width('100%')
          }
          Button(this.saved ? '已保存到待办' : (this.saving ? '保存中...' : '确认并保存'))
            .width('100%').height(44)
            .backgroundColor(this.saved ? this.palette().success : this.palette().primary)
            .fontColor('#FFFFFFFF').borderRadius(12)
            .enabled(!this.saved && !this.saving && this.editTitle.trim().length > 0)
            .onClick(() => {
              if (this.saved || this.saving || this.editTitle.trim().length === 0) { return; }
              this.saving = true;
              this.doSaveTask(this.editTitle.trim(), this.editDeadline.trim(), this.editSource.trim());
            })
        }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(18)
      }
    }
  }

  build() {
    Column() {
      SecondaryHeader({ title: this.selectedId.length > 0 ? '通知详情' : '通知整理', subtitle: this.selectedId.length > 0 ? '查看通知完整内容' : '集中接收并整理校园通知', darkMode: this.darkMode, onBack: () => { if (this.selectedId.length > 0) { this.selectedId = ''; } else { this.onBack(); } } })
      if (this.selectedNotice() !== undefined) {
        this.NoticeDetail(this.selectedNotice()!)
      } else {
      Scroll() {
        Column({ space: 13 }) {
          Text('通知来源').fontColor(this.palette().text).fontSize(17).fontWeight(FontWeight.Bold).width('100%')
          Column() {
            this.SourceRow($r('sys.symbol.cloud'), '校园服务器', '公告、课程与截止事项', '已连接')
            Divider().color(this.palette().line)
            this.SourceRow($r('sys.symbol.book'), '学习通', '作为补充来源', '可设置')
            Divider().color(this.palette().line)
            Row({ space: 11 }) {
              Stack({ alignContent: Alignment.Center }) { SymbolGlyph($r('sys.symbol.shield_checkered')).fontSize(20).fontColor([this.palette().primary]) }
                .width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
              Column({ space: 3 }) {
                Text('系统通知监听').fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
                Text(this.captureCapability().detail).fontColor(this.palette().muted).fontSize(10).maxLines(2)
              }.layoutWeight(1).alignItems(HorizontalAlign.Start)
              Text(this.captureCapability().status).fontColor(this.palette().muted).fontSize(9).fontWeight(FontWeight.Medium)
            }.width('100%').padding({ top: 10, bottom: 10 })
          }.width('100%').padding({ left: 13, right: 13 }).backgroundColor(this.palette().surface).borderRadius(18)

          this.ManualExtractCard()
          this.ExtractResultCard()

          Row() {
            Text('最近收集').fontColor(this.palette().text).fontSize(17).fontWeight(FontWeight.Bold)
            Blank()
            if (this.localNotices.length > 0) {
              Text(this.showLocal ? '本地' : '后端').fontColor(this.palette().primary).fontSize(11).onClick(() => this.showLocal = !this.showLocal)
            }
            Text(this.unreadOnly ? '只看未读' : '全部').fontColor(this.palette().primary).fontSize(11).margin({ left: 14 }).onClick(() => this.unreadOnly = !this.unreadOnly)
            Text('刷新').fontColor(this.palette().muted).fontSize(11).margin({ left: 14 }).onClick(() => this.onRefresh())
          }.width('100%')
          Column() {
            if (this.loading) { LoadingProgress().width(34).height(34).color(this.palette().primary).margin(28) }
            else if (this.showLocal && this.localNotices.length > 0) {
              ForEach(this.localNotices, (item: LocalCapturedNotice, index: number) => { this.LocalNoticeRow(item); if (index < this.localNotices.length - 1) { Divider().color(this.palette().line) } }, (item: LocalCapturedNotice) => item.id)
            } else if (this.visible().length === 0) { Text('暂无校园通知').fontColor(this.palette().muted).fontSize(12).padding(30) }
            else {
              ForEach(this.visible(), (item: NoticeItem, index: number) => { this.NoticeRow(item); if (index < this.visible().length - 1) { Divider().color(this.palette().line) } }, (item: NoticeItem) => item.id)
            }
          }.width('100%').padding({ left: 13, right: 13 }).backgroundColor(this.palette().surface).borderRadius(18)
        }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
      }
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

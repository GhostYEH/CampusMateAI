import { ChatMessage } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';

@Component
export struct CounselorPage {
  @Prop messages: ChatMessage[] = [];
  @Prop sending: boolean = false;
  @Prop darkMode: boolean = false;
  @Link input: string;
  onSend: () => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  @Builder MessageBubble(message: ChatMessage) {
    Row() {
      if (message.role === 'assistant') {
        Stack({ alignContent: Alignment.Center }) {
          SymbolGlyph($r('sys.symbol.robot')).fontSize(17).fontColor([this.palette().primary])
        }.width(30).height(30).backgroundColor(this.palette().soft).borderRadius(10).margin({ right: 7 })
      } else { Blank().layoutWeight(1) }
      Text(message.content)
        .fontColor(message.role === 'user' ? '#FFFFFFFF' : this.palette().text).fontSize(13).lineHeight(20)
        .padding({ left: 14, right: 14, top: 12, bottom: 12 })
        .backgroundColor(message.role === 'user' ? this.palette().primary : this.palette().surface)
        .border({ width: message.role === 'user' ? 0 : 1, color: this.palette().line }).borderRadius(19)
        .constraintSize({ maxWidth: '78%' })
      if (message.role === 'assistant') { Blank().layoutWeight(1) }
    }.width('100%').alignItems(VerticalAlign.Bottom)
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: 20 })))
  }

  build() {
    Column() {
      Row() {
        Column({ space: 2 }) {
          Text('AI 校园助手').fontColor(this.palette().text).fontSize(25).fontWeight(FontWeight.Bold)
          Text('课程、通知与校园生活，随时问我').fontColor(this.palette().muted).fontSize(12)
        }.alignItems(HorizontalAlign.Start)
        Blank(); Text('REAL').fontColor(this.palette().success).fontSize(9).fontWeight(FontWeight.Bold)
      }.width('100%').padding({ left: 16, right: 16, top: 12, bottom: 12 })
      Scroll() {
        Column({ space: 12 }) {
          if (this.messages.length === 0) {
            this.MessageBubble({ id: 'welcome', role: 'assistant', content: '你好，我是 CampusMate AI。课程、考试、校园服务或学习安排，都可以问我。' })
          } else {
            ForEach(this.messages, (message: ChatMessage) => { this.MessageBubble(message) }, (message: ChatMessage) => message.id)
          }
          if (this.sending) { LoadingProgress().width(24).height(24).color(this.palette().primary) }
          Blank().height(12)
        }.width('100%').padding({ left: 14, right: 14, top: 8, bottom: 8 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
      Column({ space: 6 }) {
        Row({ space: 10 }) {
          TextInput({ placeholder: '输入你的校园事务问题…', text: this.input })
            .layoutWeight(1).height(48).fontSize(13).fontColor(this.palette().text)
            .placeholderColor(this.palette().muted).backgroundColor(this.palette().surface)
            .border({ width: 1, color: this.palette().line }).borderRadius(18)
            .onChange((value: string) => this.input = value).onSubmit(() => this.onSend())
          Stack({ alignContent: Alignment.Center }) {
            if (this.sending) { LoadingProgress().width(20).height(20).color('#FFFFFFFF') }
            else { SymbolGlyph($r('sys.symbol.arrow_up')).fontSize(20).fontColor(['#FFFFFFFF']) }
          }.width(48).height(48).backgroundColor(this.palette().primary).borderRadius(16).onClick(() => this.onSend())
        }.width('100%').alignItems(VerticalAlign.Center)
        Row({ space: 4 }) {
          SymbolGlyph($r('sys.symbol.shield_checkered')).fontSize(11).fontColor([this.palette().muted])
          Text('仅提供校园事务辅助，不替代学校正式通知或专业咨询')
            .fontColor(this.palette().muted).fontSize(10)
        }.width('100%')
      }.width('100%').padding({ left: 14, right: 14, top: 10, bottom: 104 }).backgroundColor(this.palette().surface)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

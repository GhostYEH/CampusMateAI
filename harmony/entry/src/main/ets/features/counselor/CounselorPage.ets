import { ChatMessage } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';

@Component
export struct CounselorPage {
  @Prop messages: ChatMessage[] = [];
  @Prop sending: boolean = false;
  @Prop darkMode: boolean = false;
  @Prop mockMode: boolean = false;
  @Link input: string;
  onSend: () => void = () => {};
  private scroller: Scroller = new Scroller();
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  sendQuestion(question: string): void {
    this.input = question;
    this.onSend();
  }

  @Builder MessageBubble(message: ChatMessage) {
    Row() {
      if (message.role === 'assistant') {
        Stack({ alignContent: Alignment.Center }) {
          SymbolGlyph($r('sys.symbol.robot')).fontSize(17).fontColor([this.palette().primary])
        }.width(30).height(30).backgroundColor(this.palette().soft).borderRadius(10).margin({ right: 7 })
      } else { Blank().layoutWeight(1) }
      Column() {
        Text(message.content)
          .fontColor(message.role === 'user' ? '#FFFFFFFF' : this.palette().text).fontSize(13).lineHeight(20)
        if (message.role === 'assistant') {
          Blank().height(7)
          Row({ space: 4 }) {
            SymbolGlyph($r('sys.symbol.book')).fontSize(12).fontColor([this.palette().muted])
            Text(this.mockMode ? 'Mock 校园知识库' : '校园知识库').fontColor(this.palette().muted).fontSize(9)
          }
        }
      }
        .padding({ left: 14, right: 14, top: 12, bottom: 12 })
        .backgroundColor(message.role === 'user' ? this.palette().primary : this.palette().surface)
        .border({ width: message.role === 'user' ? 0 : 1, color: this.palette().line })
        .borderRadius(message.role === 'user'
          ? { topLeft: 19, topRight: 19, bottomRight: 5, bottomLeft: 19 }
          : { topLeft: 19, topRight: 19, bottomRight: 19, bottomLeft: 5 })
        .constraintSize({ maxWidth: '78%' })
      if (message.role === 'assistant') { Blank().layoutWeight(1) }
    }.width('100%').alignItems(VerticalAlign.Bottom)
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: 20 })))
  }

  @Builder ModeBadge() {
    Text(this.mockMode ? 'MOCK' : 'REAL')
      .fontColor(this.mockMode ? this.palette().accent : this.palette().success)
      .fontSize(9)
      .fontWeight(FontWeight.Bold)
      .padding({ left: 6, right: 6, top: 2, bottom: 2 })
      .backgroundColor(this.mockMode ? '#1AE08A4E' : '#1A4E8C6A')
      .borderRadius(6)
  }

  @Builder HeroCard() {
    Stack({ alignContent: Alignment.BottomStart }) {
      Row({ space: 15 }) {
        Stack({ alignContent: Alignment.Center }) {
          SymbolGlyph($r('sys.symbol.person_2')).fontSize(30).fontColor([this.palette().primary])
        }.width(56).height(56).backgroundColor(this.palette().soft).borderRadius(18)

        Column({ space: 5 }) {
          Row({ space: 8 }) {
            Text('校园事务助手').fontColor(this.palette().text).fontSize(20).fontWeight(FontWeight.Bold)
            this.ModeBadge()
          }
          Text('帮你整理办事流程、材料和下一步').fontColor(this.palette().muted).fontSize(12)
          Row({ space: 5 }) {
            Stack() {}.width(7).height(7).borderRadius(3.5).backgroundColor(this.palette().success)
            Text(this.mockMode ? 'Mock 知识库在线 · 结果仅供演示' : '真实后端链路 · 模型由服务端配置')
              .fontColor(this.palette().muted).fontSize(10)
          }
        }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      }
      .width('100%')
      .height('100%')
      .padding(16)
      .alignItems(VerticalAlign.Center)

      Stack() {}.width(52).height(3).borderRadius(1.5).backgroundColor(this.palette().accent).margin({ left: 16, bottom: 0 })
    }
    .width('100%')
    .height(110)
    .backgroundColor(this.palette().surface)
    .border({ width: 1, color: this.palette().line })
    .borderRadius(24)
  }

  @Builder SuggestionChip(question: string) {
    Row({ space: 5 }) {
      SymbolGlyph($r('sys.symbol.checkmark_circle')).fontSize(14).fontColor([this.palette().primary])
      Text(question).fontColor(this.palette().text).fontSize(12).maxLines(1).textOverflow({ overflow: TextOverflow.Ellipsis })
    }
    .padding({ left: 10, right: 10, top: 7, bottom: 7 })
    .backgroundColor(this.palette().surface)
    .border({ width: 1, color: this.palette().line })
    .borderRadius(12)
    .onClick(() => this.sendQuestion(question))
  }

  build() {
    Column() {
      Row() {
        Column({ space: 2 }) {
          Text('AI 校园助手').fontColor(this.palette().text).fontSize(26).fontWeight(FontWeight.Bold)
          Text('校园问题，随时来聊一聊').fontColor(this.palette().muted).fontSize(13)
        }.alignItems(HorizontalAlign.Start)
        Blank()
        this.ModeBadge()
      }.width('100%').padding({ left: 16, right: 16, top: 12, bottom: 12 })

      Scroll(this.scroller) {
        Column({ space: 12 }) {
          this.HeroCard()

          Blank().height(4)

          Text('你可以这样问').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold)
          Scroll() {
            Row({ space: 8 }) {
              this.SuggestionChip('奖学金申请需要什么材料？')
              this.SuggestionChip('课程重修怎么办理？')
              this.SuggestionChip('校园卡丢了怎么补办？')
            }
          }.scrollable(ScrollDirection.Horizontal).scrollBar(BarState.Off)

          Blank().height(4)

          if (this.messages.length === 0) {
            this.MessageBubble({ id: 'welcome', role: 'assistant', content: this.mockMode ? '你好，我是 AI 校园助手小夏。课程流程、奖助政策、校园服务，都可以来问我。当前为 Mock 知识库演示模式。' : '你好，我是 AI 校园助手小夏。课程流程、奖助政策、校园服务，都可以来问我。回答会结合校园知识库与后端配置的模型。' })
          } else {
            ForEach(this.messages, (message: ChatMessage) => { this.MessageBubble(message) }, (message: ChatMessage) => message.id)
          }
          if (this.sending) {
            Row({ space: 9 }) {
              Stack({ alignContent: Alignment.Center }) {
                SymbolGlyph($r('sys.symbol.robot')).fontSize(17).fontColor([this.palette().primary])
              }.width(30).height(30).backgroundColor(this.palette().soft).borderRadius(10)
              Row({ space: 6 }) {
                LoadingProgress().width(14).height(14).color(this.palette().primary)
                Text('正在查找校园知识库').fontColor(this.palette().muted).fontSize(12)
              }
              .padding({ left: 14, right: 14, top: 13, bottom: 13 })
              .backgroundColor(this.palette().surface)
              .border({ width: 1, color: this.palette().line })
              .borderRadius(19)
            }.alignItems(VerticalAlign.Center)
          }
          Blank().height(12)
        }
        .width('100%')
        .constraintSize({ minHeight: '100%' })
        .padding({ left: 16, right: 16, top: 4, bottom: 8 })
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
        Row({ space: 5 }) {
          SymbolGlyph($r('sys.symbol.shield_checkered')).fontSize(12).fontColor([this.palette().success])
          Text('仅提供校园事务辅助，不替代学校正式通知或专业咨询')
            .fontColor(this.palette().muted).fontSize(10)
        }.width('100%')
      }
        .width('100%')
        .padding({ left: 14, right: 14, top: 10, bottom: 18 })
        .margin({ bottom: 96 })
        .backgroundColor(this.palette().surface)
        .border({ width: 1, color: this.palette().line })
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

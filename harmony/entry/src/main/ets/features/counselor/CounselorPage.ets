import { ChatMessage, MarkdownLine } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { MotionDuration, MotionSpec } from '../../ui/MotionSpec';
import { DigitalHumanStage } from './DigitalHumanStage';

interface QuickQuestion {
  label: string;
  prompt: string;
  symbol: Resource;
}

@Component
export struct CounselorPage {
  @Prop messages: ChatMessage[] = [];
  @Prop sending: boolean = false;
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @Prop mockMode: boolean = false;
  @Prop apiBaseUrl: string = '';
  @Prop authToken: string = '';
  @Prop speechText: string = '';
  @Prop speechRequestId: number = 0;
  @Link input: string;
  onSend: () => void = () => {};
  private scroller: Scroller = new Scroller();
  @State quickQuestions: QuickQuestion[] = [
    { label: '奖学金申请\n材料清单', prompt: '奖学金申请需要什么材料？', symbol: $r('sys.symbol.school') },
    { label: '课程重修\n办理流程', prompt: '课程重修怎么办理？', symbol: $r('sys.symbol.book') },
    { label: '校园卡丢失\n补办地点', prompt: '校园卡丢失去哪里补办？', symbol: $r('sys.symbol.creditcard') },
    { label: '请假流程\n怎么走', prompt: '请假流程怎么走？', symbol: $r('sys.symbol.calendar') }
  ];

  @State pressedPrompt: string = '';
  @State sendPressed: boolean = false;

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  ask(question: string): void {
    this.input = question;
    this.onSend();
  }
  triggerAsk(question: string): void {
    this.pressedPrompt = question;
    setTimeout(() => { if (this.pressedPrompt === question) this.pressedPrompt = ''; }, MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS));
    this.ask(question);
  }
  triggerSend(): void {
    if (this.sending || this.input.trim().length === 0) return;
    this.sendPressed = true;
    setTimeout(() => { this.sendPressed = false; }, MotionSpec.duration(this.reduceMotion, MotionDuration.STATE));
    this.onSend();
  }

  cleanMarkdown(value: string): string {
    return value.replace(/\*\*/g, '').replace(/`/g, '');
  }

  markdownLines(content: string): MarkdownLine[] {
    const rawLines: string[] = content.replace(/\r\n/g, '\n').split('\n');
    const result: MarkdownLine[] = [];
    for (let index: number = 0; index < rawLines.length; index++) {
      result.push({ id: index.toString(), text: rawLines[index].replace(/\s+$/, '') });
    }
    return result;
  }

  @Builder Robot(size: number) {
    Image($r('app.media.ai_campus_robot')).width(size).height(size).objectFit(ImageFit.Contain)
  }

  @Builder StatusBadge() {
    Row({ space: 5 }) {
      Circle().width(7).height(7).fill(this.mockMode ? this.palette().accent : '#FFFF9646')
      Text(this.mockMode ? '演示模式' : '真实后端').fontColor(this.palette().text).fontSize(12)
    }.alignItems(VerticalAlign.Center)
  }

  @Builder Header() {
    Row() {
      Column({ space: 3 }) {
        Row() {
          Text('AI 校园助手').fontColor(this.palette().text).fontSize(27).fontWeight(FontWeight.Bold)
          Text('✦').fontColor(this.palette().primary).fontSize(22).margin({ left: 4, top: -6 })
        }.alignItems(VerticalAlign.Top)
        Text('校园问题，随时来聊一聊').fontColor(this.palette().muted).fontSize(14)
      }.alignItems(HorizontalAlign.Start)
      Blank()
      this.StatusBadge()
    }.width('100%').padding({ left: 16, right: 16, top: 16, bottom: 14 }).alignItems(VerticalAlign.Top)
  }

  @Builder HeroCard() {
    Stack({ alignContent: Alignment.TopStart }) {
      this.Robot(124)
      Column({ space: 7 }) {
        Row({ space: 6 }) {
          Text('校园事务助手').fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold).maxLines(1)
          Circle().width(6).height(6).fill(this.mockMode ? this.palette().accent : '#FFFF9646')
          Text(this.mockMode ? '演示' : '真实后端').fontColor(this.palette().text).fontSize(10)
        }.alignItems(VerticalAlign.Center)
        Text('帮你整理流程、材料和下一步').fontColor(this.palette().muted).fontSize(12).maxLines(1)
        Row({ space: 4 }) {
          SymbolGlyph($r('sys.symbol.shield_checkered')).fontSize(13).fontColor([this.palette().primary])
          Text('覆盖奖助、课程、校园服务问答').fontColor(this.palette().primary).fontSize(9).maxLines(1)
        }.padding({ left: 7, right: 7, top: 5, bottom: 5 }).backgroundColor(this.palette().soft).borderRadius(15).alignItems(VerticalAlign.Center)
      }.width('100%').margin({ left: 125, right: 13, top: 25 }).alignItems(HorizontalAlign.Start)
    }
    .width('100%').height(144).backgroundColor(this.darkMode ? '#FF1B2436' : '#FFF6F7FF')
    .border({ width: 1, color: this.darkMode ? '#FF33405A' : '#FFE1E5FF' }).borderRadius(25)
  }

  @Builder QuestionCard(question: QuickQuestion) {
    Row({ space: 9 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph(question.symbol).fontSize(21).fontColor([this.palette().primary])
      }.width(40).height(40).backgroundColor(this.palette().soft).borderRadius(13)
      Text(question.label).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Medium).lineHeight(18).layoutWeight(1)
      SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(18).fontColor([this.palette().muted])
    }.width('100%').height(88).padding(11).backgroundColor(this.palette().surface)
      .border({ width: 1, color: this.palette().line }).borderRadius(18)
      .alignItems(VerticalAlign.Center)
      .scale({ x: this.pressedPrompt === question.prompt ? MotionSpec.scale(this.reduceMotion, 0.95) : 1.0, y: this.pressedPrompt === question.prompt ? MotionSpec.scale(this.reduceMotion, 0.95) : 1.0 })
      .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS), curve: Curve.EaseOut })
      .onClick(() => this.triggerAsk(question.prompt))
  }

  @Builder QuestionGrid() {
    Column({ space: 8 }) {
      Row({ space: 8 }) { this.QuestionCard(this.quickQuestions[0]); this.QuestionCard(this.quickQuestions[1]); }
      Row({ space: 8 }) { this.QuestionCard(this.quickQuestions[2]); this.QuestionCard(this.quickQuestions[3]); }
    }.width('100%')
  }

  @Builder MarkdownMessage(content: string, isUser: boolean) {
    Column({ space: 3 }) {
      ForEach(this.markdownLines(content), (entry: MarkdownLine) => {
        if (entry.text.startsWith('# ' ) || entry.text.startsWith('## ') || entry.text.startsWith('### ')) {
          Text(this.cleanMarkdown(entry.text.substring(entry.text.indexOf(' ') + 1))).fontColor(isUser ? '#FFFFFFFF' : this.palette().text).fontSize(16).fontWeight(FontWeight.Bold).lineHeight(22)
        } else if (entry.text.startsWith('- ') || entry.text.startsWith('* ')) {
          Row({ space: 6 }) {
            Text('•').fontColor(isUser ? '#FFFFFFFF' : this.palette().primary).fontSize(14)
            Text(this.cleanMarkdown(entry.text.substring(2))).fontColor(isUser ? '#FFFFFFFF' : this.palette().text).fontSize(14).lineHeight(21).layoutWeight(1)
          }.alignItems(VerticalAlign.Top)
        } else {
          Text(this.cleanMarkdown(entry.text)).fontColor(isUser ? '#FFFFFFFF' : this.palette().text).fontSize(14).lineHeight(21)
        }
      }, (entry: MarkdownLine) => entry.id)
    }
  }

  @Builder MessageBubble(message: ChatMessage) {
    Row() {
      if (message.role === 'assistant') { this.Robot(46) } else { Blank().layoutWeight(1) }
      Column({ space: 8 }) {
        this.MarkdownMessage(message.content, message.role === 'user')
        if (message.role === 'assistant' && message.content.length > 0) {
          Row({ space: 4 }) {
            SymbolGlyph($r('sys.symbol.book')).fontSize(13).fontColor([this.palette().muted])
            Text('校友知识库 · 流程同步').fontColor(this.palette().muted).fontSize(11)
          }.alignItems(VerticalAlign.Center)
        }
      }.padding(14).backgroundColor(message.role === 'assistant' ? this.palette().surface : this.palette().primary)
        .border({ width: message.role === 'assistant' ? 1 : 0, color: this.palette().line })
        .borderRadius(message.role === 'assistant' ? { topLeft: 22, topRight: 22, bottomRight: 22, bottomLeft: 5 } : { topLeft: 22, topRight: 22, bottomRight: 5, bottomLeft: 22 })
        .constraintSize({ maxWidth: '80%' })
      if (message.role === 'assistant') { Blank().layoutWeight(1) }
    }.width('100%').alignItems(VerticalAlign.Bottom)
      .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 14) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), curve: Curve.EaseOut }))
  }

  @Builder TypingBubble() {
    Row({ space: 6 }) {
      this.Robot(40)
      Row({ space: 7 }) {
        LoadingProgress().width(14).height(14).color(this.palette().primary)
        Text('正在查询校园知识库').fontColor(this.palette().muted).fontSize(12)
      }.padding(11).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(18).alignItems(VerticalAlign.Center)
    }.alignItems(VerticalAlign.Bottom)
      .transition(TransitionEffect.OPACITY.animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.STATE), curve: Curve.EaseInOut }))
  }

  @Builder Composer() {
    Column({ space: 7 }) {
      Row({ space: 8 }) {
        TextInput({ placeholder: '✦ 输入你的校园事务问题…', text: this.input })
          .layoutWeight(1).height(52).fontSize(14).fontColor(this.palette().text).placeholderColor(this.palette().muted)
          .backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().primary + '66' }).borderRadius(19)
          .onChange((value: string) => this.input = value).onSubmit(() => { if (!this.sending && this.input.trim().length > 0) this.onSend() })
        Stack({ alignContent: Alignment.Center }) {
          if (this.sending) { LoadingProgress().width(19).height(19).color('#FFFFFFFF') }
          else { SymbolGlyph($r('sys.symbol.paperplane_fill')).fontSize(21).fontColor(['#FFFFFFFF']) }
        }.width(52).height(52).backgroundColor(this.palette().primary).borderRadius(19)
          .scale({ x: this.sendPressed ? MotionSpec.scale(this.reduceMotion, 0.90) : 1.0, y: this.sendPressed ? MotionSpec.scale(this.reduceMotion, 0.90) : 1.0 })
          .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS), curve: Curve.EaseOut })
          .onClick(() => this.triggerSend())
      }.width('100%').alignItems(VerticalAlign.Center)
      Row({ space: 5 }) {
        SymbolGlyph($r('sys.symbol.shield_checkered')).fontSize(13).fontColor([this.palette().success])
        Text('仅提供校园事务辅助，不替代学校正式通知或专业咨询').fontColor(this.palette().muted).fontSize(10).maxLines(1)
      }.width('100%').alignItems(VerticalAlign.Center)
    }.width('100%').padding({ left: 11, right: 11, top: 11, bottom: 13 }).margin({ bottom: 88 })
      .backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line })
      .borderRadius({ topLeft: 24, topRight: 24 })
  }

  build() {
    Column() {
      this.Header()
      Scroll(this.scroller) {
        Column({ space: 13 }) {
          DigitalHumanStage({
            apiBaseUrl: this.apiBaseUrl,
            authToken: this.authToken,
            speechText: this.speechText,
            speechRequestId: this.speechRequestId,
            darkMode: this.darkMode
          })
          Text('你可以这样问').fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold)
          this.QuestionGrid()
          ForEach(this.messages, (message: ChatMessage) => { this.MessageBubble(message) }, (message: ChatMessage) => message.id)
          if (this.sending) this.TypingBubble()
          Blank().height(6)
        }.width('100%').padding({ left: 16, right: 16, bottom: 14 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
      this.Composer()
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

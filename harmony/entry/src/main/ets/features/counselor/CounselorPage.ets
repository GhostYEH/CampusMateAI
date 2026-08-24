import { pasteboard } from '@kit.BasicServicesKit';
import { MarkdownLine } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { MotionDuration, MotionSpec } from '../../ui/MotionSpec';
import { CpmChatDataSource, CpmChatMessage, CpmMessageStatus } from './CpmChatDataSource';
import { DigitalHumanStage } from './DigitalHumanStage';

interface QuickQuestion {
  id: string;
  label: string;
  prompt: string;
  symbol: Resource;
}

const CPM_QUESTIONS: QuickQuestion[] = [
  { id: 'freshman', label: '大一应该\n怎么规划', prompt: '大一应该怎么规划？', symbol: $r('sys.symbol.school') },
  { id: 'graduate', label: '我应该读研\n还是就业', prompt: '我应该读研还是就业？', symbol: $r('sys.symbol.briefcase') },
  { id: 'club', label: '社团应该\n怎么选', prompt: '社团应该怎么选？', symbol: $r('sys.symbol.person_2') },
  { id: 'balance', label: '怎么平衡\n学习和生活', prompt: '怎么平衡学习和生活？', symbol: $r('sys.symbol.calendar') },
  { id: 'internship', label: '大学期间如何\n准备实习', prompt: '大学期间应该如何准备实习？', symbol: $r('sys.symbol.briefcase') },
  { id: 'direction', label: '找不到方向\n怎么办', prompt: '大学里暂时找不到方向怎么办？', symbol: $r('sys.symbol.compass') },
  { id: 'friendship', label: '怎样建立健康的\n同学关系', prompt: '怎样建立健康的同学关系？', symbol: $r('sys.symbol.person_2') },
  { id: 'habits', label: '如何养成稳定的\n学习习惯', prompt: '如何养成稳定的学习习惯？', symbol: $r('sys.symbol.checkmark_circle') }
];

@Component
struct CpmMessageRow {
  @ObjectLink message: CpmChatMessage;
  @Prop darkMode: boolean = false;
  @Prop sending: boolean = false;
  onRetry: () => void = () => {};
  @State cursorOpacity: number = 1;
  private cursorTimer: number = -1;

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  aboutToAppear(): void {
    this.dataSource.onChanged = () => {
      setTimeout(() => this.scroller.scrollEdge(Edge.Bottom), 0);
    };
    this.cursorTimer = setInterval(() => {
      animateTo({ duration: 480, curve: Curve.EaseInOut }, () => {
        this.cursorOpacity = this.cursorOpacity > 0.5 ? 0.15 : 1;
      });
    }, 520);
  }

  aboutToDisappear(): void {
    this.dataSource.onChanged = () => {};
  }

  aboutToDisappear(): void {
    if (this.cursorTimer >= 0) clearInterval(this.cursorTimer);
  }

  cleanMarkdown(value: string): string {
    return value.replace(/\*\*/g, '').replace(/`/g, '');
  }

  markdownLines(content: string): MarkdownLine[] {
    return content.replace(/\r\n/g, '\n').split('\n').map((text: string, index: number) => {
      const line: MarkdownLine = { id: index.toString(), text: text.replace(/\s+$/, '') };
      return line;
    });
  }

  async copyText(): Promise<void> {
    try {
      const data = pasteboard.createData(pasteboard.MIMETYPE_TEXT_PLAIN, this.message.content);
      await pasteboard.getSystemPasteboard().setData(data);
    } catch (_) { /* clipboard unavailable */ }
  }

  @Builder Markdown() {
    Column({ space: 3 }) {
      ForEach(this.markdownLines(this.message.content), (entry: MarkdownLine) => {
        if (entry.text.startsWith('# ') || entry.text.startsWith('## ') || entry.text.startsWith('### ')) {
          Text(this.cleanMarkdown(entry.text.substring(entry.text.indexOf(' ') + 1)))
            .fontColor(this.message.role === 'user' ? '#FFFFFFFF' : this.palette().text).fontSize(16).fontWeight(FontWeight.Bold).lineHeight(22)
        } else if (entry.text.startsWith('- ') || entry.text.startsWith('* ')) {
          Row({ space: 6 }) {
            Text('•').fontColor(this.message.role === 'user' ? '#FFFFFFFF' : this.palette().primary).fontSize(14)
            Text(this.cleanMarkdown(entry.text.substring(2)))
              .fontColor(this.message.role === 'user' ? '#FFFFFFFF' : this.palette().text).fontSize(14).lineHeight(21).layoutWeight(1)
          }.alignItems(VerticalAlign.Top)
        } else {
          Text(this.cleanMarkdown(entry.text)).fontColor(this.message.role === 'user' ? '#FFFFFFFF' : this.palette().text).fontSize(14).lineHeight(21)
        }
      }, (entry: MarkdownLine) => entry.id)
    }.alignItems(HorizontalAlign.Start)
  }

  @Builder Actions() {
    Row({ space: 18 }) {
      Row({ space: 4 }) {
        SymbolGlyph($r('sys.symbol.doc')).fontSize(13).fontColor([this.palette().muted])
        Text('复制').fontSize(11).fontColor(this.palette().muted)
      }.onClick(() => this.copyText())
      Row({ space: 4 }) {
        SymbolGlyph($r('sys.symbol.arrow_counterclockwise')).fontSize(13).fontColor([this.palette().muted])
        Text('重新生成').fontSize(11).fontColor(this.palette().muted)
      }.opacity(this.sending ? 0.45 : 1).onClick(() => { if (!this.sending) this.onRetry(); })
    }.margin({ top: 8 })
  }

  build() {
    Row() {
      if (this.message.role === 'assistant') {
        Stack({ alignContent: Alignment.Center }) {
          Text('CPM').fontSize(8).fontWeight(FontWeight.Bold).fontColor(this.palette().primary)
        }.width(32).height(32).borderRadius(16).backgroundColor(this.palette().soft).margin({ right: 7 })
      } else {
        Blank().layoutWeight(1)
      }
      Column({ space: 2 }) {
        if (this.message.status === CpmMessageStatus.GENERATING && this.message.content.length === 0) {
          Row({ space: 7 }) {
            LoadingProgress().width(14).height(14).color(this.palette().primary)
            Text('正在思考...').fontColor(this.palette().muted).fontSize(13)
          }.alignItems(VerticalAlign.Center)
        } else {
          this.Markdown()
          if (this.message.status === CpmMessageStatus.GENERATING) {
            Text('▋').fontSize(13).fontColor(this.palette().primary).opacity(this.cursorOpacity)
          }
        }
        if (this.message.status === CpmMessageStatus.ERROR) {
          Text(this.message.errorMessage.length > 0 ? this.message.errorMessage : '生成中断')
            .fontColor('#FFE05555').fontSize(11).margin({ top: 6 })
          Text('重新生成').fontColor(this.palette().primary).fontSize(12).margin({ top: 5 }).onClick(() => this.onRetry())
        }
        if (this.message.status === CpmMessageStatus.COMPLETED && this.message.content.length > 0 && this.message.role === 'assistant') {
          this.Actions()
        }
      }
      .constraintSize({ maxWidth: '80%' })
      .padding(14)
      .backgroundColor(this.message.role === 'assistant' ? (this.darkMode ? '#F21B2436' : '#F8FFFFFF') : '#FF5262ED')
      .border({ width: this.message.role === 'assistant' ? 1 : 0, color: this.palette().line })
      .borderRadius(this.message.role === 'assistant'
        ? { topLeft: 22, topRight: 22, bottomRight: 22, bottomLeft: 6 }
        : { topLeft: 22, topRight: 22, bottomRight: 6, bottomLeft: 22 })
      .shadow({ radius: this.message.role === 'assistant' ? 9 : 0, color: '#12404E7D', offsetY: 4 })
      if (this.message.role === 'assistant') Blank().layoutWeight(1)
    }.width('100%').alignItems(VerticalAlign.Bottom)
  }
}

@Component
export struct CounselorPage {
  @Prop dataSource: CpmChatDataSource = new CpmChatDataSource();
  @Prop sending: boolean = false;
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @Prop apiBaseUrl: string = '';
  @Prop authToken: string = '';
  @Prop speechText: string = '';
  @Prop speechRequestId: number = 0;
  @Link input: string;
  onSend: (question: string) => void = () => {};
  onRetry: () => void = () => {};
  @State chatActive: boolean = false;
  @State suggestionOpacity: number = 1;
  @State recommendationOffset: number = 0;
  @State command: string = '';
  @State commandRequestId: number = 0;
  @State pressedPrompt: string = '';
  private scroller: Scroller = new Scroller();

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  aboutToAppear(): void {
    if (this.dataSource.totalCount() > 0) {
      this.chatActive = true;
      this.suggestionOpacity = 0;
    }
  }

  visibleQuestions(): QuickQuestion[] {
    const result: QuickQuestion[] = [];
    for (let index = 0; index < 4; index++) result.push(CPM_QUESTIONS[(this.recommendationOffset + index) % CPM_QUESTIONS.length]);
    return result;
  }

  issueCommand(command: string): void {
    this.command = command;
    this.commandRequestId += 1;
  }

  enterChat(question: string): void {
    const clean = question.trim();
    if (clean.length === 0 || this.sending) return;
    if (!this.chatActive) {
      animateTo({
        duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.STATE),
        curve: Curve.EaseOut,
        onFinish: () => { this.chatActive = true; }
      }, () => { this.suggestionOpacity = 0; });
    }
    this.onSend(clean);
  }

  @Builder Header() {
    Column({ space: 4 }) {
      Row() {
        Text('CPM').fontColor(this.palette().text).fontSize(38).fontWeight(FontWeight.Bold)
        Text('✦').fontColor(this.palette().primary).fontSize(24).margin({ left: 7, top: -3 })
      }.alignItems(VerticalAlign.Top)
      Text('校园问题，随时来聊一聊').fontColor(this.palette().muted).fontSize(16).fontWeight(FontWeight.Medium)
    }.width('100%').alignItems(HorizontalAlign.Start)
  }

  @Builder Avatar(size: number) {
    Stack({ alignContent: Alignment.Center }) {
      DigitalHumanStage({
        apiBaseUrl: this.apiBaseUrl,
        authToken: this.authToken,
        speechText: this.speechText,
        speechRequestId: this.speechRequestId,
        darkMode: this.darkMode,
        stageHeight: size,
        command: this.command,
        commandRequestId: this.commandRequestId
      })
    }.width(size).height(size).borderRadius(size / 2).clip(true).backgroundColor('#FFE7EAFF').border({ width: 2, color: '#FFFFFFFF' })
  }

  @Builder Control(symbol: Resource, label: string, command: string) {
    Column({ space: 5 }) {
      SymbolGlyph(symbol).fontSize(24).fontColor([this.palette().primary])
      Text(label).fontColor(this.palette().muted).fontSize(12)
    }.height(72).layoutWeight(1).justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
      .backgroundColor(this.darkMode ? '#661C2639' : '#A6FFFFFF').border({ width: 1, color: this.palette().line }).borderRadius(18)
      .onClick(() => this.issueCommand(command))
  }

  @Builder DigitalHumanCard() {
    if (this.chatActive) {
      Row({ space: 12 }) {
        this.Avatar(58)
        Column({ space: 3 }) {
          Text('你好，我是CPM').fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold)
          Text(this.sending ? '正在生成回答…' : '尽管提问！').fontColor(this.sending ? this.palette().primary : this.palette().muted).fontSize(12)
        }.layoutWeight(1).alignItems(HorizontalAlign.Start)
        SymbolGlyph($r('sys.symbol.speaker_slash')).fontSize(20).fontColor([this.palette().primary]).onClick(() => this.issueCommand('mute'))
        SymbolGlyph($r('sys.symbol.pause_circle')).fontSize(20).fontColor([this.palette().primary]).onClick(() => this.issueCommand('pause'))
      }.width('100%').height(78).padding(10).alignItems(VerticalAlign.Center)
        .backgroundColor(this.darkMode ? '#F21B2436' : '#F8FFFFFF').border({ width: 1, color: '#FFFFFFFF' }).borderRadius(24)
        .shadow({ radius: 18, color: '#164B5DAC', offsetY: 7 })
    } else {
      Row({ space: 18 }) {
        this.Avatar(154)
        Column({ space: 0 }) {
          Row() {
            Text('你好，我是').fontColor('#FF385AF6').fontSize(23).fontWeight(FontWeight.Bold)
            Text('CPM').fontColor('#FF8152F6').fontSize(23).fontWeight(FontWeight.Bold)
          }
          Text('尽管提问！').fontColor(this.palette().muted).fontSize(15).margin({ top: 8, bottom: 18 })
          Row({ space: 8 }) {
            this.Control($r('sys.symbol.speaker_slash'), '静音', 'mute')
            this.Control($r('sys.symbol.pause_circle'), '暂停', 'pause')
            this.Control($r('sys.symbol.arrow_counterclockwise'), '重播', 'replay')
          }.width('100%')
        }.layoutWeight(1).alignItems(HorizontalAlign.Start).justifyContent(FlexAlign.Center)
      }.width('100%').height(224).padding(18).alignItems(VerticalAlign.Center)
        .backgroundColor(this.darkMode ? '#F21B2436' : '#F8FFFFFF').border({ width: 1, color: '#FFFFFFFF' }).borderRadius(31)
        .shadow({ radius: 22, color: '#164B5DAC', offsetY: 8 })
    }
  }

  @Builder QuestionCard(question: QuickQuestion) {
    Row({ space: 10 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph(question.symbol).fontSize(22).fontColor([this.palette().primary])
      }.width(44).height(44).borderRadius(22).backgroundColor(this.palette().soft)
      Text(question.label).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Medium).lineHeight(19).layoutWeight(1)
    }.height(88).layoutWeight(1).padding(12).alignItems(VerticalAlign.Center)
      .backgroundColor(this.darkMode ? '#F21B2436' : '#F8FFFFFF').border({ width: 1, color: this.palette().line }).borderRadius(22)
      .scale({ x: this.pressedPrompt === question.prompt ? MotionSpec.scale(this.reduceMotion, 0.95) : 1, y: this.pressedPrompt === question.prompt ? MotionSpec.scale(this.reduceMotion, 0.95) : 1 })
      .onClick(() => {
        this.pressedPrompt = question.prompt;
        setTimeout(() => { this.pressedPrompt = ''; }, MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS));
        this.enterChat(question.prompt);
      })
  }

  @Builder Recommendations() {
    Column({ space: 12 }) {
      Row() {
        Text('你可以这样问').fontColor(this.palette().text).fontSize(21).fontWeight(FontWeight.Bold)
        Text('✦').fontColor(this.palette().primary).fontSize(16).margin({ left: 5, top: -5 })
        Blank()
        Row({ space: 4 }) {
          Text('换一批').fontColor(this.palette().muted).fontSize(13)
          SymbolGlyph($r('sys.symbol.arrow_clockwise')).fontSize(16).fontColor([this.palette().muted])
        }.onClick(() => { this.recommendationOffset = (this.recommendationOffset + 4) % CPM_QUESTIONS.length; })
      }.width('100%').alignItems(VerticalAlign.Center)
      Row({ space: 10 }) { this.QuestionCard(this.visibleQuestions()[0]); this.QuestionCard(this.visibleQuestions()[1]); }.width('100%')
      Row({ space: 10 }) { this.QuestionCard(this.visibleQuestions()[2]); this.QuestionCard(this.visibleQuestions()[3]); }.width('100%')
    }.width('100%').opacity(this.suggestionOpacity)
  }

  @Builder Composer() {
    Column({ space: 6 }) {
      Row({ space: 9 }) {
        TextInput({ placeholder: '✦ 输入你想聊的问题…', text: this.input })
          .layoutWeight(1).height(54).fontSize(14).fontColor(this.palette().text).placeholderColor(this.palette().muted)
          .backgroundColor(this.darkMode ? '#F21B2436' : '#F8FFFFFF').border({ width: 1, color: this.palette().line }).borderRadius(22)
          .onChange((value: string) => this.input = value).onSubmit(() => this.enterChat(this.input))
        Stack({ alignContent: Alignment.Center }) {
          if (this.sending) LoadingProgress().width(19).height(19).color('#FFFFFFFF')
          else SymbolGlyph($r('sys.symbol.paperplane_fill')).fontSize(22).fontColor(['#FFFFFFFF'])
        }.width(54).height(54).borderRadius(27).backgroundColor(this.palette().primary).onClick(() => this.enterChat(this.input))
      }.width('100%').alignItems(VerticalAlign.Center)
      Row({ space: 5 }) {
        SymbolGlyph($r('sys.symbol.shield_checkered')).fontSize(13).fontColor([this.palette().muted])
        Text('仅提供成长建议，不替代学校正式通知或专业咨询').fontColor(this.palette().muted).fontSize(10).maxLines(1)
      }.width('100%')
    }.width('100%').padding({ left: 14, right: 14, top: 11, bottom: 13 }).margin({ bottom: 88 })
      .backgroundColor(this.darkMode ? '#E61B2436' : '#E6FFFFFF').backdropBlur(24)
      .border({ width: 1, color: '#FFFFFFFF' }).borderRadius({ topLeft: 28, topRight: 28 })
  }

  build() {
    Column() {
      List({ scroller: this.scroller, space: 16 }) {
        if (!this.chatActive) {
          ListItem() { this.Header() }
        }
        ListItem() { this.DigitalHumanCard() }
        if (!this.chatActive) {
          ListItem() { this.Recommendations() }
        }
        LazyForEach(this.dataSource, (message: CpmChatMessage) => {
          ListItem() { CpmMessageRow({ message: message, darkMode: this.darkMode, sending: this.sending, onRetry: this.onRetry }) }
        }, (message: CpmChatMessage) => message.id)
        ListItem() { Row() {}.height(2) }
      }.layoutWeight(1).width('100%').padding({ left: 18, right: 18, top: 18, bottom: 14 }).scrollBar(BarState.Off)
      this.Composer()
    }.width('100%').height('100%')
      .linearGradient({ angle: 180, colors: [[this.darkMode ? '#FF101827' : '#FFFBFCFF', 0], [this.darkMode ? '#FF151C2C' : '#FFF0F2FF', 1]] })
  }
}

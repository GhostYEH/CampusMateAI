const LOGIN_INK: string = '#111A31';
const LOGIN_BLUE_DEEP: string = '#3E50D9';
const LOGIN_WARM: string = '#FFA45B';
const FORM_TEXT: string = '#F8FAFF';
const FORM_MUTED: string = '#BDEBF0FF';

@Component
export struct LoginScreen {
  @Link username: string;
  @Link password: string;
  @Prop loading: boolean = false;
  @Prop error: string = '';
  @Prop reduceMotion: boolean = false;
  onSubmit: () => void = () => {};
  onInputChanged: () => void = () => {};

  @State showPassword: boolean = false;
  @State usernameFocused: boolean = false;
  @State passwordFocused: boolean = false;
  private videoController: VideoController = new VideoController();

  aboutToDisappear(): void {
    this.videoController.stop();
  }

  @Builder
  LoginBrand() {
    Row() {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph($r('sys.symbol.school'))
          .fontSize(23)
          .fontColor(['#FFFFFFFF'])
      }
      .width(40)
      .height(40)
      .borderRadius(13)
      .backgroundColor(LOGIN_WARM)

      Column({ space: 2 }) {
        Text('CampusMate AI')
          .fontColor('#FFFFFFFF')
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
        Text('校园事务 · 温和陪伴')
          .fontColor('#B3FFFFFF')
          .fontSize(9.5)
      }
      .alignItems(HorizontalAlign.Start)
      .margin({ left: 10 })
    }
    .alignItems(VerticalAlign.Center)
  }

  @Builder
  LoginField(label: string, placeholder: string, symbol: Resource, isPassword: boolean) {
    Column({ space: 6 }) {
      Text(label)
        .fontColor(FORM_MUTED)
        .fontSize(11)
        .fontWeight(FontWeight.Medium)
        .width('100%')

      Row({ space: 11 }) {
        SymbolGlyph(symbol)
          .fontSize(18)
          .fontColor([FORM_MUTED])

        TextInput({
          placeholder: placeholder,
          text: isPassword ? this.password : this.username
        })
          .layoutWeight(1)
          .height(44)
          .fontSize(14)
          .fontColor(FORM_TEXT)
          .placeholderFont({ size: 13 })
          .placeholderColor('#75FFFFFF')
          .caretColor('#FFFFFFFF')
          .backgroundColor(Color.Transparent)
          .border({ width: 0 })
          .padding(0)
          .type(isPassword && !this.showPassword ? InputType.Password : InputType.Normal)
          .showPasswordIcon(false)
          .enterKeyType(isPassword ? EnterKeyType.Done : EnterKeyType.Next)
          .onFocus(() => {
            if (isPassword) {
              this.passwordFocused = true;
            } else {
              this.usernameFocused = true;
            }
          })
          .onBlur(() => {
            if (isPassword) {
              this.passwordFocused = false;
            } else {
              this.usernameFocused = false;
            }
          })
          .onChange((value: string) => {
            if (isPassword) {
              this.password = value;
            } else {
              this.username = value;
            }
            this.onInputChanged();
          })
          .onSubmit(() => {
            if (isPassword) {
              this.onSubmit();
            }
          })

        if (isPassword) {
          SymbolGlyph(this.showPassword ? $r('sys.symbol.eye_slash') : $r('sys.symbol.eye'))
            .fontSize(20)
            .fontColor([FORM_MUTED])
            .width(28)
            .height(44)
            .onClick(() => {
              this.showPassword = !this.showPassword;
            })
        }
      }
      .width('100%')
      .height(45)
      .alignItems(VerticalAlign.Center)

      Divider()
        .strokeWidth(1)
        .color((isPassword ? this.passwordFocused : this.usernameFocused) ? '#FFFFFFFF' : '#52FFFFFF')
    }
    .width('100%')
  }

  @Builder
  LoginContent() {
    Scroll() {
      Column() {
        Column() {
          this.LoginBrand()

          Blank().height(66)

          Text('欢迎回到校园')
            .fontColor('#FFFFFFFF')
            .fontSize(32)
            .fontWeight(FontWeight.Bold)
            .letterSpacing(-0.5)
            .lineHeight(38)
            .width('100%')
            .transition(TransitionEffect.OPACITY)

          Blank().height(8)

          Text('课程、通知与每一个重要截止，\n都替你稳稳记着。')
            .fontColor('#D1FFFFFF')
            .fontSize(13)
            .lineHeight(20)
            .width('100%')
            .transition(TransitionEffect.OPACITY)
        }
        .width('100%')
        .alignItems(HorizontalAlign.Start)
        .padding({ left: 24, top: 20, right: 24 })

        Blank().height(42)

        Column({ space: 16 }) {
          Text('登录 CampusMate')
            .fontColor(FORM_TEXT)
            .fontSize(23)
            .fontWeight(FontWeight.Bold)
            .width('100%')
            .transition(TransitionEffect.OPACITY)

          Text('使用学校统一身份账号继续。')
            .fontColor(FORM_MUTED)
            .fontSize(11.5)
            .width('100%')
            .transition(TransitionEffect.OPACITY)

          this.LoginField('账号', '学号 / 工号 / 用户名', $r('sys.symbol.person'), false)
          this.LoginField('密码', '请输入密码', $r('sys.symbol.lock'), true)

          if (this.error.length > 0) {
            Text(this.error)
              .fontColor('#FFFFC5BF')
              .fontSize(11.5)
              .width('100%')
              .padding({ left: 12, right: 12, top: 9, bottom: 9 })
              .backgroundColor('#663E171A')
              .borderRadius(10)
              .transition(TransitionEffect.OPACITY)
          }

          Row({ space: 8 }) {
            if (this.loading) {
              LoadingProgress()
                .width(18)
                .height(18)
                .color(LOGIN_BLUE_DEEP)
            } else {
              Text('进入校园空间')
                .fontColor(LOGIN_BLUE_DEEP)
                .fontSize(14)
                .fontWeight(FontWeight.Bold)
              SymbolGlyph($r('sys.symbol.arrow_right'))
                .fontSize(17)
                .fontColor([LOGIN_BLUE_DEEP])
            }
          }
          .width('100%')
          .height(51)
          .justifyContent(FlexAlign.Center)
          .alignItems(VerticalAlign.Center)
          .backgroundColor('#FFFFFFFF')
          .borderRadius(14)
          .opacity(this.loading ? 0.82 : 1.0)
          .scale({ x: 1, y: 1 })
          .animation({ duration: 200, curve: Curve.EaseInOut })
          .onClick(() => {
            if (!this.loading) {
              this.onSubmit();
            }
          })
          .gesture(
            TapGesture({ count: 1 })
              .onAction(() => {
                animateTo({ duration: 100, curve: Curve.EaseInOut }, () => {
                })
              })
          )

          Text('登录即表示你已阅读并同意校园数据使用说明')
            .fontColor('#7AFFFFFF')
            .fontSize(9.5)
            .width('100%')
            .textAlign(TextAlign.Center)
        }
        .width('100%')
        .alignItems(HorizontalAlign.Start)
        .padding({ left: 24, top: 18, right: 24, bottom: 24 })
      }
      .width('100%')
    }
    .width('100%')
    .height('100%')
    .scrollBar(BarState.Off)
  }

  build() {
    Stack() {
      Image($r('app.media.campus_login_poster'))
        .width('100%')
        .height('100%')
        .objectFit(ImageFit.Fill)

      if (!this.reduceMotion) {
        Video({
          src: $r('app.media.login_campus'),
          previewUri: $r('app.media.campus_login_poster'),
          controller: this.videoController
        })
          .width('100%')
          .height('100%')
          .objectFit(ImageFit.Fill)
          .autoPlay(true)
          .muted(true)
          .controls(false)
          .loop(true)
      }

      Column() {}
        .width('100%')
        .height('100%')
        .linearGradient({
          angle: 180,
          colors: [
            ['#5C091632', 0.0],
            ['#52091632', 0.38],
            ['#C4091632', 0.68],
            ['#F0091632', 1.0]
          ]
        })

      this.LoginContent()
    }
    .width('100%')
    .height('100%')
    .backgroundColor(LOGIN_INK)
  }
}

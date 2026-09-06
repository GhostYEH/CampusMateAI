import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { CommunityPostItem, CourseItem, NoticeItem, TaskItem } from '../../data/Models';
import { MotionDuration, MotionSpec } from '../../ui/MotionSpec';
import { AppRouteRegistry } from '../../navigation/AppRoute';

interface DashboardFeature {
  title: string;
  subtitle: string;
  route: string;
  color: string;
  symbol: Resource;
}

interface DashboardOverviewMetric {
  id: string;
  label: string;
  value: string;
  detail: string;
  color: string;
  route: string;
  symbol: Resource;
}

interface DashboardOverviewOption {
  id: string;
  label: string;
}

@Component({ freezeWhenInactive: true })
export struct DashboardPageImmersive {
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @Prop userName: string = '校园同学';
  @Prop hitokoto: string = '';
  @Prop wallpaperUrl: string = '';
  @Prop courses: CourseItem[] = [];
  @Prop tasks: TaskItem[] = [];
  @Prop notices: NoticeItem[] = [];
  @Prop hotPosts: CommunityPostItem[] = [];
  onNavigate: (route: string) => void = () => {};
  @State pressedRoute: string = '';
  @State profilePressed: boolean = false;
  @State overviewVisibleIds: string[] = ['courses', 'tasks', 'focus', 'notifications'];
  @State overviewDraftIds: string[] = [];
  @State overviewCustomizeOpen: boolean = false;

  palette(): CampusPalette {
    return this.darkMode ? darkPalette : lightPalette;
  }

  triggerAction(route: string): void {
    this.pressedRoute = route;
    setTimeout(() => { if (this.pressedRoute === route) this.pressedRoute = ''; }, MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS));
    this.onNavigate(route);
  }

  triggerProfile(): void {
    this.profilePressed = true;
    setTimeout(() => { this.profilePressed = false; }, MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS));
    this.onNavigate('profile');
  }

  openOverviewCustomization(): void {
    this.overviewDraftIds = this.overviewVisibleIds.slice();
    this.overviewCustomizeOpen = true;
  }

  toggleOverviewMetric(id: string, selected: boolean): void {
    if (!selected && this.overviewDraftIds.length <= 1) return;
    if (selected) {
      if (this.overviewDraftIds.indexOf(id) < 0) this.overviewDraftIds = [...this.overviewDraftIds, id];
    } else {
      this.overviewDraftIds = this.overviewDraftIds.filter((item: string) => item !== id);
    }
  }

  overviewMetrics(): DashboardOverviewMetric[] {
    const all: DashboardOverviewMetric[] = [
      { id: 'courses', label: '今日课程', value: `${this.courses.length}`, detail: '下一节 · 10:00', color: '#527CEF', route: 'courses', symbol: $r('sys.symbol.book') },
      { id: 'tasks', label: '近期截止', value: `${this.pendingTaskCount()}`, detail: '需要关注', color: '#7A65E8', route: 'tasks', symbol: $r('sys.symbol.clock') },
      { id: 'focus', label: '今日专注', value: '3.5', detail: '目标 5 小时', color: '#35B99A', route: 'focus', symbol: $r('sys.symbol.clock') },
      { id: 'notifications', label: '未读通知', value: `${this.unreadCount()}`, detail: '及时查看', color: '#397CEF', route: AppRouteRegistry.unreadNotificationMetricRoute(), symbol: $r('sys.symbol.bell') }
    ];
    return all.filter((metric: DashboardOverviewMetric) => this.overviewVisibleIds.indexOf(metric.id) >= 0);
  }

  overviewOptions(): DashboardOverviewOption[] {
    return [
      { id: 'courses', label: '今日课程' },
      { id: 'tasks', label: '近期截止' },
      { id: 'focus', label: '今日专注' },
      { id: 'notifications', label: '未读通知' }
    ];
  }

  @Builder
  GlassButton(symbol: Resource, route: string, badge: boolean = false) {
    Stack({ alignContent: Alignment.Center }) {
      SymbolGlyph(symbol).fontSize(22).fontColor([this.palette().text])
      if (badge) {
        Circle().width(8).height(8).fill('#FF5A54').position({ x: 17, y: -15 })
      }
    }
    .width(48).height(48).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur)
    .border({ width: 1, color: this.palette().glass.highlight }).borderRadius(16)
    .shadow({ radius: 12, color: this.palette().glass.shadow, offsetY: 4 })
    .onClick(() => this.triggerAction(route))
  }

  @Builder
  Header() {
    Stack() {
      Image($r('app.media.campus_login_poster')).width('100%').height(236).objectFit(ImageFit.Cover)
      if (this.wallpaperUrl.length > 0) {
        Image(this.wallpaperUrl).width('100%').height(236).objectFit(ImageFit.Cover)
      }
      Column() {}.width('100%').height(236).linearGradient({ angle: 180, colors: [['#B8FFFFFF', 0.0], ['#F6F8FA', 1.0]] })
      Column() {
        Row() {
          Row() {
            Image($r('app.media.profile_avatar_reference')).width(50).height(50).objectFit(ImageFit.Cover).borderRadius(25).border({ width: 2, color: '#CCFFFFFF' })
            Column({ space: 3 }) {
              Text(`上午好，${this.userName}`).fontColor(this.palette().text).fontSize(19).fontWeight(FontWeight.Bold)
              Text(this.hitokoto).fontColor(this.palette().muted).fontSize(12).maxLines(1).textOverflow({ overflow: TextOverflow.Ellipsis })
            }
            .alignItems(HorizontalAlign.Start).margin({ left: 11 })
          }
          .layoutWeight(1).alignItems(VerticalAlign.Center)
          .scale({ x: this.profilePressed ? MotionSpec.scale(this.reduceMotion, 0.97) : 1.0, y: this.profilePressed ? MotionSpec.scale(this.reduceMotion, 0.97) : 1.0 })
          .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS), curve: Curve.EaseOut })
          .onClick(() => this.triggerProfile())
          Row({ space: 9 }) {
            this.GlassButton($r('sys.symbol.bell'), 'notifications', this.unreadCount() > 0)
            this.GlassButton($r('sys.symbol.qrcode'), 'qr_scanner')
          }
        }
        .width('100%').alignItems(VerticalAlign.Center)
      }
      .width('100%').padding({ left: 18, right: 18, top: 28, bottom: 12 }).alignItems(HorizontalAlign.Start)
    }
    .width('100%').height(178).borderRadius(28).clip(true)
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 10) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), curve: Curve.EaseOut }))
  }

  @Builder
  AssistantCard() {
    Stack() {
      Column() {}.width('100%').height('100%').linearGradient({ angle: 100, colors: [['#24FFFFFF', 0.0], ['#36DDE8FF', 1.0]] })
      Row() {
        Stack({ alignContent: Alignment.Center }) {
          Circle().width(44).height(44).fill('#7D9CFFFF').shadow({ radius: 12, color: '#44749BFF' })
          Text('AI').fontColor('#FFFFFFFF').fontSize(16).fontWeight(FontWeight.Bold)
        }
        Image($r('app.media.cpm_avatar')).width(122).height(164).objectFit(ImageFit.Contain).align(Alignment.Bottom).margin({ left: -15, right: 4 })
        Column({ space: 7 }) {
          Row() {
            Text('AI 学习助手').fontColor(this.palette().text).fontSize(20).fontWeight(FontWeight.Bold)
            Text('✦').fontColor('#6B7DFFFF').fontSize(22).margin({ left: 6 })
          }
          Text('我是 CPM 数字人，可以帮你制定学习计划、解答问题和分析学习数据。').fontColor(this.palette().muted).fontSize(11.5).lineHeight(17).maxLines(3)
          Row({ space: 6 }) {
            Text('去提问').fontColor('#536EED').fontSize(12).fontWeight(FontWeight.Medium)
            SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(15).fontColor(['#536EED'])
          }
          .padding({ left: 16, right: 13, top: 7, bottom: 7 }).border({ width: 1, color: '#8097FFFF' }).borderRadius(18)
          .onClick(() => this.triggerAction('counselor'))
        }
        .layoutWeight(1).alignItems(HorizontalAlign.Start).margin({ right: 15 })
      }
      .width('100%').height('100%').alignItems(VerticalAlign.Center).padding({ left: 13, right: 10 })
    }
    .width('100%').height(184).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur)
    .border({ width: 1, color: this.palette().glass.highlight }).borderRadius(25).clip(true)
    .shadow({ radius: 18, color: this.palette().glass.shadow, offsetY: 5 })
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 12) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), delay: MotionSpec.stagger(this.reduceMotion, 1), curve: Curve.EaseOut }))
  }

  @Builder
  FeatureCard(feature: DashboardFeature) {
    Stack() {
      Column() {}.width('100%').height('100%').linearGradient({ angle: 135, colors: feature.route === 'community' ? [['#24FFF9F1', 0.0], ['#32FFE5C4', 1.0]] : [['#24F5F7FF', 0.0], ['#32DCE7FF', 1.0]] })
      Column() {
        Row() {
          SymbolGlyph(feature.symbol).fontSize(21).fontColor([feature.color])
          Column({ space: 4 }) {
            Text(feature.title).fontColor(this.palette().text).fontSize(16).fontWeight(FontWeight.Bold).maxLines(1)
            Text(feature.subtitle).fontColor(this.palette().muted).fontSize(10).maxLines(1)
          }.alignItems(HorizontalAlign.Start).margin({ left: 9 })
          Blank()
          Column({ space: 5 }) {
            Stack({ alignContent: Alignment.Center }) { SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(16).fontColor([feature.color]) }
              .width(30).height(30).backgroundColor('#AAFFFFFF').borderRadius(11)
            if (feature.route === 'community') {
              Row({ space: 3 }) {
                Circle().width(17).height(17).fill('#FFFFA43A')
                Circle().width(21).height(21).fill('#FFFFC89A')
                Circle().width(15).height(15).fill('#FFF4A3A3')
              }
            } else {
              Stack({ alignContent: Alignment.Center }) {
                SymbolGlyph($r('sys.symbol.book')).fontSize(24).fontColor(['#8AA6F2'])
                SymbolGlyph($r('sys.symbol.star_fill')).fontSize(10).fontColor(['#FFFFFFFF'])
              }.width(38).height(21)
            }
          }
        }
      }
      .width('100%').height('100%').padding({ left: 13, right: 13, top: 11, bottom: 11 }).alignItems(HorizontalAlign.Start)
    }
    .layoutWeight(1).height(110).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur)
    .border({ width: 1, color: this.palette().glass.highlight }).borderRadius(23).clip(true)
    .shadow({ radius: 15, color: this.palette().glass.shadow, offsetY: 4 })
    .scale({ x: this.pressedRoute === feature.route ? MotionSpec.scale(this.reduceMotion, 0.96) : 1.0, y: this.pressedRoute === feature.route ? MotionSpec.scale(this.reduceMotion, 0.96) : 1.0 })
    .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS), curve: Curve.EaseOut })
    .onClick(() => this.triggerAction(feature.route))
  }

  @Builder
  FeatureCards() {
    Row({ space: 10 }) {
      this.FeatureCard({ title: '校园社区', subtitle: '交流分享 · 连接同好', route: 'community', color: '#FFA43A', symbol: $r('sys.symbol.person_2') })
      this.FeatureCard({ title: '专注自习', subtitle: '沉浸专注 · 效率提升', route: 'focus', color: '#5B68F2', symbol: $r('sys.symbol.book') })
    }
    .width('100%')
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 14) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), delay: MotionSpec.stagger(this.reduceMotion, 2), curve: Curve.EaseOut }))
  }

  @Builder
  OverviewCard() {
    Column() {
      Row() {
        Text('信息总览').fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold)
        Blank()
        Text('自定义').fontColor(this.palette().muted).fontSize(11)
        SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(16).fontColor([this.palette().muted]).margin({ left: 5 })
      }.width('100%').onClick(() => this.openOverviewCustomization())
      Row({ space: 7 }) {
        ForEach(this.overviewMetrics(), (metric: DashboardOverviewMetric) => {
          this.Metric(metric.label, metric.value, metric.detail, metric.color, metric.route, metric.symbol)
        }, (metric: DashboardOverviewMetric) => metric.id)
      }
      .width('100%').margin({ top: 13 })
    }
    .width('100%').padding(16).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur)
    .border({ width: 1, color: this.palette().glass.highlight }).borderRadius(24)
    .shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 })
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 14) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), delay: MotionSpec.stagger(this.reduceMotion, 3), curve: Curve.EaseOut }))
  }

  @Builder
  Metric(label: string, metricValue: string, detail: string, color: string, route: string, symbol: Resource) {
    Column({ space: 5 }) {
      SymbolGlyph(symbol).fontSize(17).fontColor([color])
      Text(label).fontColor(this.palette().muted).fontSize(10).maxLines(1)
      Text(metricValue).fontColor(this.palette().text).fontSize(22).fontWeight(FontWeight.Bold)
      Text(detail).fontColor(this.palette().muted).fontSize(9).maxLines(1)
    }
    .layoutWeight(1).padding({ left: 7, right: 7, top: 10, bottom: 10 }).alignItems(HorizontalAlign.Start)
    .backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur)
    .border({ width: 1, color: this.palette().glass.highlight }).borderRadius(15)
    .shadow({ radius: 10, color: this.palette().glass.shadow, offsetY: 2 })
    .onClick(() => this.triggerAction(route))
  }

  @Builder
  OverviewCustomization() {
    Column({ space: 12 }) {
      Row() {
        Column({ space: 3 }) {
          Text('信息总览').fontColor(this.palette().text).fontSize(19).fontWeight(FontWeight.Bold)
          Text('选择要显示的快捷信息，至少保留一项').fontColor(this.palette().muted).fontSize(11)
        }.layoutWeight(1).alignItems(HorizontalAlign.Start)
        SymbolGlyph($r('sys.symbol.xmark')).fontSize(19).fontColor([this.palette().muted]).onClick(() => this.overviewCustomizeOpen = false)
      }.width('100%')
      ForEach(this.overviewOptions(), (option: DashboardOverviewOption) => {
        Row() {
          Column({ space: 3 }) {
            Text(option.label).fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
            Text(option.id === 'focus' ? '专注时长与目标' : '首页快捷查看').fontColor(this.palette().muted).fontSize(10)
          }.layoutWeight(1).alignItems(HorizontalAlign.Start)
          Toggle({ type: ToggleType.Checkbox, isOn: this.overviewDraftIds.indexOf(option.id) >= 0 })
            .selectedColor(this.palette().primary)
            .onChange((selected: boolean) => this.toggleOverviewMetric(option.id, selected))
        }.width('100%').padding({ left: 12, right: 8, top: 10, bottom: 10 }).backgroundColor(this.palette().background).borderRadius(14)
      }, (option: DashboardOverviewOption) => option.id)
      Row({ space: 10 }) {
        Text('取消').fontColor(this.palette().muted).fontSize(13).padding({ left: 18, right: 18, top: 9, bottom: 9 }).border({ width: 1, color: this.palette().line }).borderRadius(17).onClick(() => this.overviewCustomizeOpen = false)
        Text('应用').fontColor('#FFFFFFFF').fontSize(13).fontWeight(FontWeight.Bold).padding({ left: 21, right: 21, top: 9, bottom: 9 }).backgroundColor(this.palette().primary).borderRadius(17).onClick(() => { this.overviewVisibleIds = this.overviewDraftIds.slice(); this.overviewCustomizeOpen = false; })
      }.width('100%').justifyContent(FlexAlign.End)
    }
    .width('88%').padding(20).backgroundColor(this.palette().glass.surface).backdropBlur(28)
    .border({ width: 1, color: this.palette().glass.highlight }).borderRadius(24)
    .shadow({ radius: 24, color: this.palette().glass.shadow, offsetY: 8 })
  }

  @Builder
  CourseRow(course: CourseItem, index: number) {
    Row() {
      Column() {
        Text(index === 0 ? '10:00' : '14:00').fontColor(index === 0 ? '#527CEF' : '#7766E8').fontSize(17).fontWeight(FontWeight.Bold)
        Text(index === 0 ? '11:40' : '15:40').fontColor(this.palette().muted).fontSize(12).margin({ top: 4 })
      }
      .width(67).alignItems(HorizontalAlign.Start)
      Divider().vertical(true).color(this.palette().line).strokeWidth(1).height(42)
      Column({ space: 4 }) {
        Text(course.name).fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold)
        Text(`${course.teacher_name ?? '教师待定'} · ${course.semester ?? '本学期'}`).fontColor(this.palette().muted).fontSize(10)
      }
      .layoutWeight(1).alignItems(HorizontalAlign.Start).margin({ left: 12 })
      Text(index === 0 ? '进行中' : '未开始').fontColor(index === 0 ? '#527CEF' : '#7766E8').fontSize(10)
        .padding({ left: 8, right: 8, top: 5, bottom: 5 }).backgroundColor(index === 0 ? '#1A527CEF' : '#1A7766E8').borderRadius(12)
    }
    .width('100%').padding({ left: 13, right: 13, top: 12, bottom: 12 })
    .backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur)
    .border({ width: 1, color: this.palette().glass.highlight }).borderRadius(17)
    .shadow({ radius: 10, color: this.palette().glass.shadow, offsetY: 2 })
    .onClick(() => this.triggerAction('courses'))
  }

  @Builder
  TodayCourses() {
    Column() {
      Row() {
        Text('今日课程').fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold)
        Blank()
        Text('查看课表').fontColor(this.palette().muted).fontSize(11)
        SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(16).fontColor([this.palette().muted])
      }.onClick(() => this.triggerAction('courses'))
      if (this.courses.length > 0) {
        ForEach(this.courses.slice(0, 2), (course: CourseItem, index: number) => { this.CourseRow(course, index); }, (course: CourseItem) => course.id)
      } else {
        Text('今日暂无课程，去安排一段专注时间吧').fontColor(this.palette().muted).fontSize(12).width('100%').padding({ top: 28, bottom: 28 }).textAlign(TextAlign.Center)
      }
    }
    .width('100%').padding(16).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur)
    .border({ width: 1, color: this.palette().glass.highlight }).borderRadius(24)
    .shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 })
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 14) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), delay: MotionSpec.stagger(this.reduceMotion, 4), curve: Curve.EaseOut }))
  }

  @Builder
  CampusUpdates() {
    Column() {
      Row() {
        Text('校园动态').fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold)
        Blank()
        Text('查看更多').fontColor(this.palette().muted).fontSize(11)
        SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(16).fontColor([this.palette().muted])
      }
      ForEach(this.hotPosts.slice(0, 2), (post: CommunityPostItem) => {
        Row() {
          Circle().width(9).height(9).fill('#FFA43A').margin({ right: 10 })
          Column({ space: 3 }) {
            Text(post.title).fontColor(this.palette().text).fontSize(12).fontWeight(FontWeight.Medium).maxLines(1)
            Text(post.content).fontColor(this.palette().muted).fontSize(10).maxLines(1).textOverflow({ overflow: TextOverflow.Ellipsis })
          }
          .layoutWeight(1).alignItems(HorizontalAlign.Start)
        }
        .width('100%').padding({ left: 12, right: 12, top: 10, bottom: 10 })
        .backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur)
        .border({ width: 1, color: this.palette().glass.highlight }).borderRadius(16)
        .shadow({ radius: 10, color: this.palette().glass.shadow, offsetY: 2 })
        .margin({ top: 4, bottom: 4 })
      }, (post: CommunityPostItem) => post.id)
      if (this.hotPosts.length === 0) {
        Text('校园社区正在等你分享新鲜事').fontColor(this.palette().muted).fontSize(11).width('100%').padding({ top: 22, bottom: 22 }).textAlign(TextAlign.Center)
      }
    }
    .width('100%').padding(16).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur)
    .border({ width: 1, color: this.palette().glass.highlight }).borderRadius(24)
    .shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 })
    .onClick(() => this.triggerAction('community'))
  }

  unreadCount(): number {
    return this.notices.filter((notice: NoticeItem) => notice.unread === true).length;
  }

  pendingTaskCount(): number {
    return this.tasks.filter((task: TaskItem) => task.status !== 'completed').length;
  }

  build() {
    Stack({ alignContent: Alignment.Center }) {
      Scroll() {
        Column({ space: 14 }) {
          this.Header()
          this.AssistantCard()
          this.FeatureCards()
          this.OverviewCard()
          this.TodayCourses()
          this.CampusUpdates()
          Blank().height(112)
        }
        .width('100%').padding({ left: 16, right: 16, top: 0, bottom: 10 })
      }
      .width('100%').height('100%').scrollBar(BarState.Off).backgroundColor(this.palette().background)
      if (this.overviewCustomizeOpen) {
        Column() {}.width('100%').height('100%').backgroundColor('#66303D5F').onClick(() => this.overviewCustomizeOpen = false)
        this.OverviewCustomization()
      }
    }
    .width('100%').height('100%')
  }
}

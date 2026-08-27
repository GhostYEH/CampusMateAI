import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { CommunityPostItem, CourseItem, HomeBannerItem, NoticeItem, TaskItem } from '../../data/Models';
import { MotionDuration, MotionSpec } from '../../ui/MotionSpec';

interface DashboardAction {
  title: string;
  route: string;
  symbol: Resource;
  color: string;
}

@Component({ freezeWhenInactive: true })
export struct DashboardPage {
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @Prop userName: string = '林知夏';
  @Prop courses: CourseItem[] = [];
  @Prop tasks: TaskItem[] = [];
  @Prop notices: NoticeItem[] = [];
  @Prop banners: HomeBannerItem[] = [];
  @Prop hotPosts: CommunityPostItem[] = [];
  onNavigate: (route: string) => void = () => {};
  @State pressedRoute: string = '';
  @State heroPressed: boolean = false;
  @State profilePressed: boolean = false;
  @State heroIndex: number = 0;

  palette(): CampusPalette {
    return this.darkMode ? darkPalette : lightPalette;
  }

  triggerAction(route: string): void {
    this.pressedRoute = route;
    setTimeout(() => { if (this.pressedRoute === route) this.pressedRoute = ''; }, MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS));
    this.onNavigate(route);
  }
  bannerRoute(actionKey: string): string {
    if (actionKey === 'CPM_ASSISTANT') return 'counselor';
    if (actionKey === 'CHAOXING') return 'chaoxing';
    if (actionKey === 'EDU_SYSTEM') return 'edu_system';
    if (actionKey === 'TASKS') return 'tasks';
    if (actionKey === 'COMMUNITY') return 'community';
    return '';
  }
  triggerHero(route: string): void {
    if (route.length === 0) return;
    this.heroPressed = true;
    setTimeout(() => { this.heroPressed = false; }, MotionSpec.duration(this.reduceMotion, MotionDuration.STATE));
    this.onNavigate(route);
  }
  triggerProfile(): void {
    this.profilePressed = true;
    setTimeout(() => { this.profilePressed = false; }, MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS));
    this.onNavigate('profile');
  }

  @Builder
  SectionTitle(title: string, action: string, route: string) {
    Row() {
      Text(title)
        .fontColor(this.palette().text)
        .fontSize(18)
        .fontWeight(FontWeight.Bold)
      Blank()
      Row({ space: 2 }) {
        Text(action).fontColor(this.palette().muted).fontSize(10.5)
        SymbolGlyph($r('sys.symbol.chevron_right'))
          .fontSize(16)
          .fontColor([this.palette().muted])
      }
      .onClick(() => this.onNavigate(route))
    }
    .width('100%')
    .alignItems(VerticalAlign.Center)
  }

  @Builder
  HeaderProfile() {
    Row() {
      Image($r('app.media.profile_avatar_reference'))
        .width(42)
        .height(42)
        .objectFit(ImageFit.Cover)
        .borderRadius(21)
        .border({ width: 2, color: this.palette().surface })
      Column({ space: 2 }) {
        Text(this.userName)
          .fontColor(this.palette().text)
          .fontSize(15)
          .fontWeight(FontWeight.Bold)
        Text('点击头像进入个人中心')
          .fontColor(this.palette().muted)
          .fontSize(11)
      }
      .alignItems(HorizontalAlign.Start)
      .margin({ left: 10 })
    }
    .width('100%')
    .alignItems(VerticalAlign.Center)
    .scale({ x: this.profilePressed ? MotionSpec.scale(this.reduceMotion, 0.97) : 1.0, y: this.profilePressed ? MotionSpec.scale(this.reduceMotion, 0.97) : 1.0 })
    .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS), curve: Curve.EaseOut })
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 10) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), curve: Curve.EaseOut }))
    .onClick(() => this.triggerProfile())
  }

  @Builder
  HomeBanner() {
    Swiper() {
      ForEach(this.banners, (banner: HomeBannerItem) => {
        Stack() {
          Image(banner.image_url).width('100%').height('100%').objectFit(ImageFit.Cover)
          Column() {}
            .width('100%').height('100%')
            .linearGradient({ angle: banner.action_key === 'CPM_ASSISTANT' ? 270 : 90, colors: banner.action_key === 'CPM_ASSISTANT'
              ? [['#003449C7', 0.0], ['#985368E8', 0.52], ['#F53449C7', 1.0]]
              : [['#F53449C7', 0.0], ['#C85368E8', 0.56], ['#005368E8', 1.0]] })
          Column() {
            Text(banner.eyebrow).fontColor('#C7FFFFFF').fontSize(9).fontWeight(FontWeight.Bold)
            Text(banner.title).fontColor('#FFFFFFFF').fontSize(21).fontWeight(FontWeight.Bold).lineHeight(25).maxLines(2).margin({ top: 6 })
            Text(banner.subtitle).fontColor('#FFDCE5FF').fontSize(11).lineHeight(15).maxLines(2).textOverflow({ overflow: TextOverflow.Ellipsis }).margin({ top: 6 })
            if (this.bannerRoute(banner.action_key).length > 0) {
              Row({ space: 6 }) {
                Text(banner.cta_label).fontColor('#FFFFFFFF').fontSize(11).fontWeight(FontWeight.Medium)
                SymbolGlyph($r('sys.symbol.arrow_right')).fontSize(14).fontColor(['#FFFFFFFF'])
              }.padding({ left: 13, right: 13, top: 7, bottom: 7 }).border({ width: 1, color: '#B8FFFFFF' }).borderRadius(18).margin({ top: 11 })
            }
          }
          .width(banner.action_key === 'CPM_ASSISTANT' ? '58%' : '72%').height('100%')
          .justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Start)
          .align(banner.action_key === 'CPM_ASSISTANT' ? Alignment.End : Alignment.Start)
          .padding({ left: 22, right: 14, top: 17, bottom: 17 })
        }
        .width('100%').height('100%')
        .onClick(() => this.triggerHero(this.bannerRoute(banner.action_key)))
      }, (banner: HomeBannerItem) => banner.id)
    }
    .width('100%')
    .height(188)
    .index(this.heroIndex)
    .autoPlay(!this.reduceMotion && this.banners.length > 1)
    .interval(4500)
    .loop(this.banners.length > 1)
    .indicator(this.banners.length > 1)
    .onChange((index: number) => { this.heroIndex = index; })
    .borderRadius(26)
    .clip(true)
    .scale({ x: this.heroPressed ? MotionSpec.scale(this.reduceMotion, 0.97) : 1.0, y: this.heroPressed ? MotionSpec.scale(this.reduceMotion, 0.97) : 1.0 })
    .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.STATE), curve: Curve.EaseOut })
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 14) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), delay: MotionSpec.stagger(this.reduceMotion, 1), curve: Curve.EaseOut }))
  }

  @Builder
  QuickActions() {
    Row() {
      ForEach([
        { title: '考试安排', route: 'exams', symbol: $r('sys.symbol.calendar'), color: '#5B68F2' },
        { title: '空教室', route: 'classrooms', symbol: $r('sys.symbol.doors_and_windows_open'), color: '#397CEF' },
        { title: '校园社区', route: 'community', symbol: $r('sys.symbol.person_2'), color: '#35B99A' },
        { title: '专注自习', route: 'focus', symbol: $r('sys.symbol.timer'), color: '#FFA43A' },
        { title: '失物招领', route: 'lostfound', symbol: $r('sys.symbol.magnifyingglass'), color: '#7C6BE8' }
      ], (action: DashboardAction) => {
        Column({ space: 8 }) {
          Stack({ alignContent: Alignment.Center }) {
            SymbolGlyph(action.symbol)
              .fontSize(24)
              .fontColor(['#FFFFFFFF'])
          }
          .width(44)
          .height(44)
          .borderRadius(13)
          .backgroundColor(action.color)
          Text(action.title)
            .fontColor(this.palette().text)
            .fontSize(11)
            .maxLines(1)
        }
        .layoutWeight(1)
        .alignItems(HorizontalAlign.Center)
        .scale({ x: this.pressedRoute === action.route ? MotionSpec.scale(this.reduceMotion, 0.90) : 1.0, y: this.pressedRoute === action.route ? MotionSpec.scale(this.reduceMotion, 0.90) : 1.0 })
        .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS), curve: Curve.EaseOut })
        .onClick(() => this.triggerAction(action.route))

      })
    }
    .width('100%')
    .padding({ left: 8, right: 8, top: 16, bottom: 16 })
    .backgroundColor(this.palette().surface)
    .borderRadius(24)
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 14) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), delay: MotionSpec.stagger(this.reduceMotion, 2), curve: Curve.EaseOut }))
  }

  @Builder
  CourseMeta(symbol: Resource, text: string) {
    Row({ space: 5 }) {
      SymbolGlyph(symbol).fontSize(15).fontColor(['#E0FFFFFF'])
      Text(text).fontColor('#E6FFFFFF').fontSize(11)
    }
    .alignItems(VerticalAlign.Center)
  }

  @Builder
  TimelineRow(title: string, meta: string, state: string, upcoming: boolean) {
    Row() {
      Circle()
        .width(9)
        .height(9)
        .fill(upcoming ? '#FFFFFFFF' : '#FFFFFFFF')
        .stroke('#FF5368E8')
        .strokeWidth(1.5)
      Column({ space: 4 }) {
        Text(title)
          .fontColor(this.palette().text)
          .fontSize(12)
          .fontWeight(FontWeight.Medium)
        Text(meta).fontColor(this.palette().muted).fontSize(9.5)
      }
      .layoutWeight(1)
      .alignItems(HorizontalAlign.Start)
      .margin({ left: 9 })
      Text(state)
        .fontColor(upcoming ? '#FF5368E8' : this.palette().muted)
        .fontSize(9)
        .padding({ left: 7, right: 7, top: 5, bottom: 5 })
        .backgroundColor(this.palette().soft)
        .borderRadius(12)
    }
    .width('100%')
    .alignItems(VerticalAlign.Center)
    .padding({ top: 12, bottom: 12 })
  }

  @Builder
  TodayCourseCard() {
    Column() {
      this.SectionTitle('今日课程', '查看全部', 'courses')
      Row({ space: 10 }) {
        Column() {
          Text('下一节')
            .fontColor('#FFFFFFFF')
            .fontSize(10)
            .padding({ left: 9, right: 9, top: 4, bottom: 4 })
            .backgroundColor('#29FFFFFF')
            .borderRadius(12)
          Text(this.courses.length > 0 ? this.courses[0].name : '今日无课')
            .fontColor('#FFFFFFFF')
            .fontSize(22)
            .fontWeight(FontWeight.Bold)
            .margin({ top: 10 })
          Blank()
          this.CourseMeta($r('sys.symbol.clock'), '10:00 · 进行中')
          Blank().height(8)
          this.CourseMeta($r('sys.symbol.location_up'), this.courses.length > 0 ? `${this.courses[0].teacher_name ?? '教师待定'} · ${this.courses[0].semester ?? '本学期'}` : '今日可自由安排')
        }
        .layoutWeight(1.02)
        .height(166)
        .padding(15)
        .alignItems(HorizontalAlign.Start)
        .linearGradient({
          angle: 135,
          colors: [['#FF4259E8', 0.0], ['#FF7B78F7', 1.0]]
        })
        .borderRadius(18)
        .scale({ x: this.pressedRoute === 'courses' ? MotionSpec.scale(this.reduceMotion, 0.96) : 1.0, y: this.pressedRoute === 'courses' ? MotionSpec.scale(this.reduceMotion, 0.96) : 1.0 })
        .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS), curve: Curve.EaseOut })
        .onClick(() => this.triggerAction('courses'))

        Column() {
          this.TimelineRow(this.courses.length > 1 ? this.courses[1].name : '高等数学', this.courses.length > 1 ? (this.courses[1].teacher_name ?? '教师待定') : '08:00 · B-301', '已结束', false)
          Divider().color(this.palette().line).strokeWidth(1)
          this.TimelineRow(this.courses.length > 2 ? this.courses[2].name : '计算机网络', this.courses.length > 2 ? (this.courses[2].teacher_name ?? '教师待定') : '14:00 · A-105', '未开始', true)
        }
        .layoutWeight(0.98)
        .height(166)
        .padding({ left: 12, right: 12 })
        .justifyContent(FlexAlign.Center)
        .border({ width: 1, color: this.palette().line })
        .borderRadius(18)
      }
      .width('100%')
      .margin({ top: 13 })
    }
    .width('100%')
    .padding(16)
    .backgroundColor(this.palette().surface)
    .borderRadius(24)
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 14) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), delay: MotionSpec.stagger(this.reduceMotion, 3), curve: Curve.EaseOut }))
  }

  @Builder
  StudyOverview() {
    Column() {
      Row() {
        Text('学习总览')
          .fontColor(this.palette().text)
          .fontSize(17)
          .fontWeight(FontWeight.Bold)
        Blank()
        SymbolGlyph($r('sys.symbol.eye')).fontSize(19).fontColor([this.palette().muted])
      }
      Row() {
        Column({ space: 4 }) {
          Text('本周进度')
            .fontColor(this.palette().muted)
            .fontSize(10)
            .maxLines(1)
          Text('72%')
            .fontColor(this.palette().text)
            .fontSize(24)
            .fontWeight(FontWeight.Bold)
            .maxLines(1)
          Column({ space: 2 }) {
            Text('较上周')
              .fontColor(this.palette().success)
              .fontSize(10)
              .maxLines(1)
            Text('↑12%')
              .fontColor(this.palette().success)
              .fontSize(10)
              .maxLines(1)
          }
          .alignItems(HorizontalAlign.Start)
        }
        .layoutWeight(1)
        .constraintSize({ minWidth: 68 })
        .alignItems(HorizontalAlign.Start)
        .justifyContent(FlexAlign.Center)
        
        Stack({ alignContent: Alignment.Center }) {
          Progress({ value: 72, total: 100, type: ProgressType.Ring })
            .width(42)
            .height(42)
            .color('#FF5368E8')
            .backgroundColor(this.palette().soft)
            .style({ strokeWidth: 4.5 })
          SymbolGlyph($r('sys.symbol.histogram'))
            .fontSize(14)
            .fontColor(['#FF5368E8'])
        }
        .margin({ left: 6 })
      }
      .width('100%')
      .layoutWeight(1)
      .padding({ left: 8, right: 8, top: 10, bottom: 10 })
      .alignItems(VerticalAlign.Center)
      .backgroundColor(this.palette().background)
      .borderRadius(16)
      .margin({ top: 12 })
    }
    .layoutWeight(1)
    .height(191)
    .padding(12)
    .backgroundColor(this.palette().surface)
    .borderRadius(22)
  }

  @Builder
  DeadlineRow(title: string, due: string, urgent: boolean) {
    Row() {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph($r('sys.symbol.book'))
          .fontSize(17)
          .fontColor([urgent ? this.palette().primary : '#FFFFA43A'])
      }
      .width(28)
      .height(28)
      .borderRadius(8)
      .backgroundColor(urgent ? this.palette().soft : '#29E08A4E')
      Column({ space: 1 }) {
        Text(title).fontColor(this.palette().text).fontSize(10.5).maxLines(1)
        Text(due)
          .fontColor(urgent ? this.palette().danger : '#FFFFA43A')
          .fontSize(9.5)
          .fontWeight(FontWeight.Medium)
      }
      .layoutWeight(1)
      .alignItems(HorizontalAlign.Start)
      .margin({ left: 8 })
    }
    .width('100%')
    .padding({ left: 9, right: 9, top: 10, bottom: 10 })
    .backgroundColor(this.palette().background)
    .borderRadius(12)
  }

  @Builder
  Deadlines() {
    Column() {
      this.SectionTitle('近期截止', '更多', 'tasks')
      Blank().height(9)
      this.DeadlineRow(this.pendingTasks().length > 0 ? this.pendingTasks()[0].title : '暂无近期截止', this.pendingTasks().length > 0 ? (this.pendingTasks()[0].deadline ?? this.pendingTasks()[0].due ?? '待设置') : '可以放松一下', true)
      Blank().height(7)
      this.DeadlineRow(this.pendingTasks().length > 1 ? this.pendingTasks()[1].title : '下一项待办', this.pendingTasks().length > 1 ? (this.pendingTasks()[1].deadline ?? this.pendingTasks()[1].due ?? '暂无') : '暂无', false)
    }
    .layoutWeight(1)
    .height(191)
    .padding(15)
    .backgroundColor(this.palette().surface)
    .borderRadius(22)
  }

  pendingTasks(): TaskItem[] {
    return this.tasks.filter((task: TaskItem) => task.status !== 'completed').slice(0, 2);
  }

  @Builder
  CampusUpdate(title: string, summary: string, tint: string, symbol: Resource) {
    Column() {
      Stack({ alignContent: Alignment.Center }) {
        Image($r('app.media.campus_login_poster'))
          .width('100%')
          .height('100%')
          .objectFit(ImageFit.Cover)
        Column() {}.width('100%').height('100%').backgroundColor(tint)
        SymbolGlyph(symbol).fontSize(28).fontColor(['#FFFFFFFF'])
      }
      .width('100%')
      .height(76)
      Column({ space: 2 }) {
        Text(title)
          .fontColor(this.palette().text)
          .fontSize(12)
          .fontWeight(FontWeight.Medium)
          .maxLines(1)
        Text(summary).fontColor(this.palette().muted).fontSize(10).maxLines(1)
      }
      .width('100%')
      .padding(11)
      .alignItems(HorizontalAlign.Start)
    }
    .width(236)
    .border({ width: 1, color: this.palette().line })
    .borderRadius(16)
    .clip(true)
  }

  @Builder
  CampusUpdates() {
    Column() {
      this.SectionTitle('校园热搜', '查看更多', 'community')
      Scroll() {
        Row({ space: 10 }) {
          this.CampusUpdate(this.hotPosts.length > 0 ? this.hotPosts[0].title : '校园论坛热门讨论', this.hotPosts.length > 0 ? this.hotPosts[0].content : '前往校园论坛查看热门帖子', '#9E5368E8', $r('sys.symbol.person_2'))
          this.CampusUpdate(this.hotPosts.length > 1 ? this.hotPosts[1].title : '学习交流正在讨论', this.hotPosts.length > 1 ? this.hotPosts[1].content : '与同学一起交流学习和校园生活', '#8CFFA43A', $r('sys.symbol.person_2'))
        }
      }
      .width('100%')
      .scrollable(ScrollDirection.Horizontal)
      .scrollBar(BarState.Off)
      .margin({ top: 12 })
    }
    .width('100%')
    .padding(16)
    .backgroundColor(this.palette().surface)
    .borderRadius(24)
  }

  build() {
    Scroll() {
      Column({ space: 14 }) {
        this.HeaderProfile()
        if (this.banners.length > 0) {
          this.HomeBanner()
        }
        this.QuickActions()
        this.TodayCourseCard()
        Row({ space: 10 }) {
          this.StudyOverview()
          this.Deadlines()
        }
        .width('100%')
        this.CampusUpdates()
        Blank().height(112)
      }
      .width('100%')
      .padding({ left: 16, right: 16, top: 12, bottom: 10 })
    }
    .width('100%')
    .height('100%')
    .scrollBar(BarState.Off)
    .backgroundColor(this.palette().background)
  }
}

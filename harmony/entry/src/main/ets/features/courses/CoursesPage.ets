import { CourseContentBundle, CourseContentItem, CourseContentSummary, CourseItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { MotionDuration, MotionSpec } from '../../ui/MotionSpec';

@Component
export struct CoursesPage {
  @Prop courses: CourseItem[] = [];
  @Prop loading: boolean = false;
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @State selectedDay: number = 0;
  @State selectedType: string = '全部';
  @State selectedId: string = '';
  @State contentFilter: string = '全部';
  @State detailLoading: boolean = false;
  @State detailError: string = '';
  @State detailSummary?: CourseContentSummary = undefined;
  @State detailContent: CourseContentItem[] = [];
  onRefresh: () => void = () => {};
  onLoadContent: (courseId: string) => Promise<CourseContentBundle> = async (_: string) => ({ items: [] });
  onSyncContent: (courseId: string) => Promise<CourseContentBundle> = async (_: string) => ({ items: [] });
  onCacheContent: (courseId: string, itemId: string) => Promise<void> = async (_: string, __: string) => {};
  onBack: () => void = () => {};

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  selectedCourse(): CourseItem | undefined { return this.courses.find((item: CourseItem) => item.id === this.selectedId); }

  async openCourse(course: CourseItem): Promise<void> {
    this.selectedId = course.id;
    this.detailLoading = true;
    this.detailError = '';
    try {
      const bundle: CourseContentBundle = await this.onLoadContent(course.id);
      this.detailSummary = bundle.summary;
      this.detailContent = bundle.items;
    } catch (_) { this.detailError = '课程内容加载失败，已保留课程基本信息'; }
    finally { this.detailLoading = false; }
  }

  async syncCourse(course: CourseItem): Promise<void> {
    this.detailLoading = true;
    this.detailError = '';
    try {
      const bundle: CourseContentBundle = await this.onSyncContent(course.id);
      this.detailSummary = bundle.summary;
      this.detailContent = bundle.items;
    } catch (_) { this.detailError = '同步失败，旧数据没有被清空'; }
    finally { this.detailLoading = false; }
  }

  filteredContent(): CourseContentItem[] {
    if (this.contentFilter === '全部') return this.detailContent;
    const groups: Record<string, string[]> = {
      '章节': ['chapter'], '资料': ['document', 'video', 'audio', 'image', 'material', 'link'],
      '作业': ['assignment'], '通知': ['notice'], '考试': ['exam'], '讨论': ['discussion']
    };
    const kinds: string[] = groups[this.contentFilter] ?? [];
    return this.detailContent.filter((item: CourseContentItem) => kinds.includes(item.kind));
  }

  sectionEmptyMessage(): string {
    const names: Record<string, string> = { '章节': 'chapters', '资料': 'materials', '作业': 'assignments', '通知': 'notices', '考试': 'exams', '讨论': 'discussions' };
    const section = this.detailSummary?.sections.find((item) => item.section === names[this.contentFilter]);
    if (section?.status === 'failed') return '本次同步失败，正在保留上次数据';
    if (section?.status === 'unavailable') return '学习通当前未开放此栏目';
    if (section?.status === 'complete') return '学习通返回的列表为空';
    return '尚未同步此栏目';
  }

  @Builder Header() {
    Row() {
      Column({ space: 1 }) {
        Text('课程').fontColor(this.palette().text).fontSize(26).fontWeight(FontWeight.Bold)
        Text('把这周的学习节奏握在手里').fontColor(this.palette().muted).fontSize(12)
      }.alignItems(HorizontalAlign.Start)
      Blank()
      Text('REAL')
        .fontColor(this.palette().success).fontSize(9).fontWeight(FontWeight.Bold)
        .padding({ left: 8, right: 8, top: 5, bottom: 5 })
        .backgroundColor(this.darkMode ? '#273D614A' : '#164E8C6A').borderRadius(12)
    }.width('100%').alignItems(VerticalAlign.Top)
  }

  @Builder Hero() {
    Row() {
      Column() {
        Row({ space: 5 }) {
          Circle().width(6).height(6).fill('#FFFFC35C')
          Text('下一节课 · 10:10').fontColor('#D1FFFFFF').fontSize(10)
        }.alignItems(VerticalAlign.Center)
        Text(this.courses.length > 0 ? this.courses[0].name : '今天没有课程')
          .fontColor('#FFFFFFFF').fontSize(20).fontWeight(FontWeight.Bold).margin({ top: 5 })
        Row({ space: 3 }) {
          SymbolGlyph($r('sys.symbol.location_up')).fontSize(13).fontColor(['#C7FFFFFF'])
          Text(this.courses.length > 0 ? `${this.courses[0].teacher_name ?? '教师待定'} · 教室待定` : '去添加你的课程安排')
            .fontColor('#C7FFFFFF').fontSize(10).maxLines(1)
        }.margin({ top: 5 })
        Blank()
        Row({ space: 16 }) {
          Row({ space: 3 }) {
            SymbolGlyph($r('sys.symbol.calendar')).fontSize(11).fontColor(['#E6FFFFFF'])
            Text('课程表').fontColor('#E6FFFFFF').fontSize(9)
          }
          Row({ space: 3 }) {
            SymbolGlyph($r('sys.symbol.info_circle')).fontSize(11).fontColor(['#E6FFFFFF'])
            Text('课程详情').fontColor('#E6FFFFFF').fontSize(9)
          }
          Row({ space: 3 }) {
            SymbolGlyph($r('sys.symbol.checkmark_circle')).fontSize(11).fontColor(['#E6FFFFFF'])
            Text('待办作业').fontColor('#E6FFFFFF').fontSize(9)
          }
        }
      }.layoutWeight(1).height('100%').alignItems(HorizontalAlign.Start)
      Column() {
        Stack({ alignContent: Alignment.Center }) {
          SymbolGlyph($r('sys.symbol.graduationcap')).fontSize(24).fontColor(['#FFFFFFFF'])
        }.width(43).height(43).backgroundColor('#2EFFFFFF').borderRadius(14)
        Blank()
        Text('去查看 →').fontColor('#FF5368E8').fontSize(10).fontWeight(FontWeight.Bold)
          .padding({ left: 10, right: 10, top: 6, bottom: 6 }).backgroundColor('#E6FFFFFF').borderRadius(14)
      }.width(70).height('100%').alignItems(HorizontalAlign.Center)
    }
    .width('100%').height(164).padding({ left: 14, top: 13, right: 10, bottom: 11 })
    .linearGradient({ angle: 135, colors: [['#FF5368E8', 0.0], ['#FF7586F5', 1.0]] }).borderRadius(18)
  }

  @Builder WeekStrip() {
    Row() {
      ForEach(['一','二','三','四','五','六','日'], (day: string, index: number) => {
        Column({ space: 3 }) {
          Text(day).fontColor(this.selectedDay === index ? this.palette().primary : this.palette().muted).fontSize(9)
          Text(this.weekDateLabel(index))
            .fontColor(this.selectedDay === index ? '#FFFFFFFF' : this.palette().muted)
            .fontSize(10).fontWeight(FontWeight.Bold).textAlign(TextAlign.Center)
            .width(25).height(25).backgroundColor(this.selectedDay === index ? this.palette().primary : Color.Transparent).borderRadius(13)
          Circle().width(4).height(4).fill(index === 2 || index === 4 ? this.palette().accent : this.palette().line)
        }.layoutWeight(1).onClick(() => this.selectedDay = index)
      })
    }.width('100%').padding({ top: 8, bottom: 8 }).backgroundColor(this.palette().surface)
      .border({ width: 1, color: this.palette().line }).borderRadius(14)
  }

  weekDateLabel(index: number): string {
    const now: Date = new Date();
    const dayOfWeek: number = now.getDay() === 0 ? 7 : now.getDay();
    const monday: Date = new Date(now);
    monday.setDate(now.getDate() - (dayOfWeek - 1) + index);
    return monday.getDate().toString();
  }

  @Builder Metrics() {
    Row() {
      this.Metric(this.courses.length.toString(), '门课程', $r('sys.symbol.book'))
      this.Metric('18', '本周学时', $r('sys.symbol.clock'))
      this.Metric('26.5', '已修学分', $r('sys.symbol.checkmark_circle'))
      this.Metric('96%', '出勤率', $r('sys.symbol.calendar_badge_checkmark'))
    }.width('100%').padding({ top: 10, bottom: 10 }).backgroundColor(this.palette().surface)
      .border({ width: 1, color: this.palette().line }).borderRadius(14)
  }

  @Builder Metric(value: string, label: string, symbol: Resource) {
    Column({ space: 2 }) {
      Row({ space: 4 }) {
        SymbolGlyph(symbol).fontSize(15).fontColor([this.palette().primary])
        Text(value).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
      }.alignItems(VerticalAlign.Center)
      Text(label).fontColor(this.palette().muted).fontSize(9)
    }.layoutWeight(1).alignItems(HorizontalAlign.Center)
  }

  @Builder Filters() {
    Row({ space: 7 }) {
      ForEach(['全部','专业课','公共课'], (label: string) => {
        Text(label)
          .fontColor(this.selectedType === label ? '#FFFFFFFF' : this.palette().muted)
          .fontSize(10).fontWeight(this.selectedType === label ? FontWeight.Bold : FontWeight.Normal)
          .padding({ left: 11, right: 11, top: 7, bottom: 7 })
          .backgroundColor(this.selectedType === label ? this.palette().primary : this.palette().surface)
          .border({ width: 1, color: this.selectedType === label ? this.palette().primary : this.palette().line })
          .borderRadius(20).onClick(() => this.selectedType = label)
      })
    }.width('100%')
  }

  @Builder CourseCard(course: CourseItem, index: number) {
    Row({ space: 9 }) {
      Stack({ alignContent: Alignment.Center }) {
        Text((course.code ?? '课').substring(0, Math.min(2, (course.code ?? '课').length)))
          .fontColor(this.palette().primary).fontSize(12).fontWeight(FontWeight.Bold)
      }.width(40).height(40).backgroundColor(this.palette().soft).borderRadius(10)
      Column({ space: 3 }) {
        Text(course.name).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold).maxLines(1)
        Text(`${course.teacher_name ?? '教师待定'} · ${course.semester ?? '本学期'}`)
          .fontColor(this.palette().muted).fontSize(10).maxLines(1)
        Text(course.code ?? `COURSE-${index + 1}`).fontColor(this.palette().muted).fontSize(9)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      Text('96%').fontColor(this.palette().primary).fontSize(9).fontWeight(FontWeight.Bold)
      SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(17).fontColor([this.palette().muted])
    }.width('100%').padding({ left: 11, right: 11, top: 10, bottom: 10 })
      .backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(14)
      .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 14) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), curve: Curve.EaseOut }))
      .onClick(() => this.openCourse(course))
  }

  @Builder CourseDetail(course: CourseItem) {
    Scroll() {
      Column({ space: 13 }) {
        Stack({ alignContent: Alignment.BottomStart }) {
          Column().width('100%').height(180).linearGradient({ angle: 135, colors: [['#FF5368E8', 0.0], ['#FF7586F5', 1.0]] })
          Column({ space: 6 }) {
            Text(course.name).fontColor('#FFFFFFFF').fontSize(24).fontWeight(FontWeight.Bold).maxLines(2)
            Text(course.code ?? '课程').fontColor('#DFFFFFFF').fontSize(12)
          }.width('100%').padding({ left: 18, right: 18, bottom: 18 }).alignItems(HorizontalAlign.Start)
        }.width('100%').height(180).borderRadius(20).clip(true)
        Column() {
          this.DetailRow($r('sys.symbol.book'), '课程名称', course.name)
          Divider().color(this.palette().line)
          this.DetailRow($r('sys.symbol.person'), '授课教师', course.teacher_name ?? '教师待定')
          Divider().color(this.palette().line)
          this.DetailRow($r('sys.symbol.calendar'), '开课学期', course.semester ?? '本学期')
          Divider().color(this.palette().line)
          this.DetailRow($r('sys.symbol.info_circle'), '课程代码', course.code ?? '—')
          Divider().color(this.palette().line)
          this.DetailRow($r('sys.symbol.info_circle'), '课程状态', course.status ?? '在修')
        }.width('100%').padding({ left: 14, right: 14 }).backgroundColor(this.palette().surface).borderRadius(18)
        Button(this.detailLoading ? '同步中…' : '同步学习通课程内容')
          .width('100%').height(46).fontSize(13).fontWeight(FontWeight.Bold)
          .enabled(!this.detailLoading).onClick(() => this.syncCourse(course))
        Scroll() {
          Row({ space: 8 }) {
            ForEach(['全部','章节','资料','作业','通知','考试','讨论'], (label: string) => {
              Text(label).fontSize(11).fontColor(this.contentFilter === label ? '#FFFFFFFF' : this.palette().primary)
                .padding({ left: 12, right: 12, top: 7, bottom: 7 })
                .backgroundColor(this.contentFilter === label ? this.palette().primary : this.palette().soft)
                .borderRadius(14).onClick(() => this.contentFilter = label)
            })
          }
        }.width('100%').scrollable(ScrollDirection.Horizontal).scrollBar(BarState.Off)
        if (this.detailError.length > 0) {
          Text(this.detailError).fontColor('#FFC64A46').fontSize(12).width('100%')
        }
        if (!this.detailLoading && this.filteredContent().length === 0) {
          Text(this.sectionEmptyMessage()).fontColor(this.palette().muted).fontSize(12).padding(18).width('100%')
        }
        ForEach(this.filteredContent(), (item: CourseContentItem) => {
          Row({ space: 11 }) {
            SymbolGlyph(item.kind === 'notice' ? $r('sys.symbol.bell') : item.kind === 'assignment' ? $r('sys.symbol.checkmark_circle') : $r('sys.symbol.doc'))
              .fontSize(19).fontColor([this.palette().primary])
            Column({ space: 3 }) {
              Text(item.title).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Medium).maxLines(2)
              Text(`${item.kind} · ${item.cached ? '已缓存' : item.status ?? '可查看'}`).fontColor(this.palette().muted).fontSize(10)
            }.layoutWeight(1).alignItems(HorizontalAlign.Start)
            SymbolGlyph(item.can_download ? $r('sys.symbol.arrow_down_circle') : $r('sys.symbol.chevron_right')).fontSize(17).fontColor([this.palette().muted])
          }.width('100%').padding(13).backgroundColor(this.palette().surface).borderRadius(14)
            .onClick(async () => {
              if (item.can_download === true) {
                try { await this.onCacheContent(course.id, item.id); item.cached = true; this.detailContent = [...this.detailContent]; }
                catch (_) { this.detailError = '资料获取失败，请稍后重试'; }
              }
            })
        }, (item: CourseContentItem) => item.id)
        if ((course.description ?? '').length > 0) {
          Column({ space: 6 }) {
            Text('课程介绍').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold)
            Text(course.description ?? '').fontColor(this.palette().muted).fontSize(12).lineHeight(20)
          }.width('100%').padding(14).backgroundColor(this.palette().surface).borderRadius(16)
        }
      }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
    }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
  }

  @Builder DetailRow(symbol: Resource, label: string, value: string) {
    Row({ space: 11 }) {
      SymbolGlyph(symbol).fontSize(19).fontColor([this.palette().primary])
      Text(label).fontColor(this.palette().muted).fontSize(11).width(74)
      Text(value).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Medium).layoutWeight(1)
    }.width('100%').padding({ top: 14, bottom: 14 })
  }

  build() {
    Column() {
      if (this.selectedCourse() !== undefined) {
        SecondaryHeader({ title: '课程详情', subtitle: '查看课程基本信息', darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.selectedId = '' })
        this.CourseDetail(this.selectedCourse()!)
      } else {
      Scroll() {
        Column({ space: 10 }) {
          this.Header(); this.Hero(); this.WeekStrip(); this.Metrics(); this.Filters()
          Row() {
            Column({ space: 1 }) {
              Text('本学期课程').fontColor(this.palette().text).fontSize(16).fontWeight(FontWeight.Bold)
              Text('按课程卡片查看上课地点与资料').fontColor(this.palette().muted).fontSize(10)
            }.alignItems(HorizontalAlign.Start)
            Blank(); Text(`${this.courses.length} 门`).fontColor(this.palette().muted).fontSize(11)
          }.width('100%').alignItems(VerticalAlign.Center)
          if (this.loading && this.courses.length === 0) {
            LoadingProgress().width(36).height(36).color(this.palette().primary).margin({ top: 40 })
          } else if (this.courses.length === 0) {
            Text('暂时没有课程，点击刷新重试').fontColor(this.palette().muted).fontSize(13)
              .padding(32).onClick(() => this.onRefresh())
          } else {
            ForEach(this.courses, (course: CourseItem, index: number) => { this.CourseCard(course, index) }, (course: CourseItem) => course.id)
          }
          Blank().height(112)
        }.width('100%').padding({ left: 14, right: 14, top: 12, bottom: 10 })
      }.width('100%').height('100%').scrollBar(BarState.Off).backgroundColor(this.palette().background)
      }
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

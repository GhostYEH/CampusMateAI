import { CourseContentBundle, CourseContentItem, CourseContentSummary, CourseItem, CourseKnowledgeGraph, KnowledgePoint } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { CourseKnowledgeGraphView } from './CourseKnowledgeGraphView';

@Component
export struct CourseDetailPage {
  @Prop course: CourseItem = { id: '', name: '' };
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @State contentFilter: string = '全部';
  @State detailLoading: boolean = false;
  @State detailError: string = '';
  @State detailSummary?: CourseContentSummary = undefined;
  @State detailContent: CourseContentItem[] = [];
  @State knowledgeGraph?: CourseKnowledgeGraph = undefined;
  @State knowledgeLoading: boolean = false;
  @State knowledgeSyncing: boolean = false;
  @State knowledgeError: string = '';
  @State knowledgeExpanded: boolean = false;
  onBack: () => void = () => {};
  onLoadContent: (courseId: string) => Promise<CourseContentBundle> = async (_: string) => ({ items: [] });
  onSyncContent: (courseId: string) => Promise<CourseContentBundle> = async (_: string) => ({ items: [] });
  onCacheContent: (courseId: string, itemId: string) => Promise<void> = async (_: string, __: string) => {};
  onLoadKnowledgeGraph: (courseId: string) => Promise<CourseKnowledgeGraph> = async (_: string) => ({ course_id: '', available: false, knowledge_point_count: 0 });
  onSyncKnowledgeGraph: (courseId: string) => Promise<CourseKnowledgeGraph> = async (_: string) => ({ course_id: '', available: false, knowledge_point_count: 0 });

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  aboutToAppear(): void {
    this.loadContent(false);
    this.loadKnowledgeGraph();
  }

  async loadKnowledgeGraph(): Promise<void> {
    this.knowledgeLoading = true;
    this.knowledgeError = '';
    try {
      this.knowledgeGraph = await this.onLoadKnowledgeGraph(this.course.id);
    } catch (_) {
      this.knowledgeError = '知识点数据加载失败，请稍后重试';
    } finally {
      this.knowledgeLoading = false;
    }
  }

  async syncKnowledgeGraph(): Promise<void> {
    this.knowledgeSyncing = true;
    this.knowledgeError = '';
    try {
      this.knowledgeGraph = await this.onSyncKnowledgeGraph(this.course.id);
    } catch (_) {
      this.knowledgeError = '知识点同步失败，请稍后重试';
    } finally {
      this.knowledgeSyncing = false;
    }
  }

  async loadContent(sync: boolean): Promise<void> {
    this.detailLoading = true;
    this.detailError = '';
    try {
      const bundle: CourseContentBundle = sync ? await this.onSyncContent(this.course.id) : await this.onLoadContent(this.course.id);
      this.detailSummary = bundle.summary;
      this.detailContent = bundle.items;
    } catch (_) {
      this.detailError = sync ? '同步失败，旧数据没有被清空' : '课程内容加载失败，已保留课程基本信息';
    } finally {
      this.detailLoading = false;
    }
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

  @Builder DetailRow(symbol: Resource, label: string, value: string) {
    Row({ space: 11 }) {
      SymbolGlyph(symbol).fontSize(19).fontColor([this.palette().primary])
      Text(label).fontColor(this.palette().muted).fontSize(11).width(74)
      Text(value).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Medium).layoutWeight(1)
    }.width('100%').padding({ top: 14, bottom: 14 })
  }

  @Builder MasteryStat(label: string, value: string) {
    Column({ space: 2 }) {
      Text(value).fontColor(this.palette().text).fontSize(17).fontWeight(FontWeight.Bold)
      Text(label).fontColor(this.palette().muted).fontSize(10)
    }.alignItems(HorizontalAlign.Start)
  }

  @Builder MasteryBar(label: string, own: number, classRate: number) {
    Column({ space: 4 }) {
      Row() {
        Text(label).fontColor(this.palette().muted).fontSize(11)
        Text(CourseKnowledgeGraphView.rateText(own)).fontColor(this.palette().text).fontSize(11).fontWeight(FontWeight.Medium)
      }.width('100%').justifyContent(FlexAlign.SpaceBetween)
      Stack({ alignContent: Alignment.TopStart }) {
        Column().width('100%').height(6).borderRadius(3).backgroundColor(this.palette().soft)
        Column().width(CourseKnowledgeGraphView.barWidth(own)).height(6).borderRadius(3).backgroundColor(this.palette().primary)
      }.width('100%').height(6)
      Text(`班级平均 ${CourseKnowledgeGraphView.rateText(classRate)}`).fontColor(this.palette().muted).fontSize(10)
    }.width('100%').alignItems(HorizontalAlign.Start)
  }

  /** 知识点掌握 —— 学习通课程图谱页观测(课程级掌握率 + 班级对比 + 知识点清单)。 */
  @Builder KnowledgePanel() {
    Column({ space: 11 }) {
      Row() {
        Row({ space: 7 }) {
          SymbolGlyph($r('sys.symbol.doc')).fontSize(18).fontColor([this.palette().primary])
          Text('知识点掌握').fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
        }
        Text(CourseKnowledgeGraphView.countLabel(this.knowledgeGraph))
          .fontColor(this.palette().muted).fontSize(11)
      }.width('100%').justifyContent(FlexAlign.SpaceBetween)
      if (this.knowledgeLoading) {
        Text('知识点数据加载中…').fontColor(this.palette().muted).fontSize(12)
      } else if (this.knowledgeGraph?.available !== true) {
        Text(CourseKnowledgeGraphView.unavailableHint(this.knowledgeError))
          .fontColor(this.palette().muted).fontSize(12)
        Button(this.knowledgeSyncing ? '同步中…' : '同步知识点')
          .width('100%').height(42).fontSize(12).fontWeight(FontWeight.Bold)
          .enabled(!this.knowledgeSyncing).onClick(() => this.syncKnowledgeGraph())
      } else {
        Row() {
          this.MasteryStat('知识点', `${this.knowledgeGraph?.knowledge_point_count ?? 0}`)
          this.MasteryStat('我的掌握率', CourseKnowledgeGraphView.rateText(this.knowledgeGraph?.own_mastery_rate))
          this.MasteryStat('班级平均', CourseKnowledgeGraphView.rateText(this.knowledgeGraph?.class_mastery_rate))
          this.MasteryStat(
            CourseKnowledgeGraphView.gapLabel(this.knowledgeGraph?.mastery_gap_vs_class),
            CourseKnowledgeGraphView.gapText(this.knowledgeGraph?.mastery_gap_vs_class)
          )
        }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        this.MasteryBar('掌握率', this.knowledgeGraph?.own_mastery_rate ?? 0, this.knowledgeGraph?.class_mastery_rate ?? 0)
        this.MasteryBar('完成率', this.knowledgeGraph?.own_completion_rate ?? 0, this.knowledgeGraph?.class_completion_rate ?? 0)
        if ((this.knowledgeGraph?.tags ?? []).length > 0) {
          Text(CourseKnowledgeGraphView.tagsText(this.knowledgeGraph)).fontColor(this.palette().muted).fontSize(10)
        }
        if (CourseKnowledgeGraphView.points(this.knowledgeGraph).length > 0) {
          Text(CourseKnowledgeGraphView.pointsToggleLabel(this.knowledgeExpanded, this.knowledgeGraph))
            .fontColor(this.palette().primary).fontSize(11).fontWeight(FontWeight.Medium)
            .onClick(() => { this.knowledgeExpanded = !this.knowledgeExpanded; })
          if (this.knowledgeExpanded) {
            ForEach(CourseKnowledgeGraphView.points(this.knowledgeGraph), (point: KnowledgePoint) => {
              Row({ space: 8 }) {
                Text(`#${(point.position ?? 0) + 1}`).fontColor(this.palette().muted).fontSize(10)
                Text(point.name).fontColor(this.palette().text).fontSize(12).maxLines(1).layoutWeight(1)
              }.width('100%')
            }, (point: KnowledgePoint) => point.external_id)
          }
        }
      }
    }.width('100%').padding(14).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).borderRadius(16).alignItems(HorizontalAlign.Start)
  }

  @Builder ContentItem(item: CourseContentItem) {
    Row({ space: 11 }) {
      SymbolGlyph(item.kind === 'notice' ? $r('sys.symbol.bell') : item.kind === 'assignment' ? $r('sys.symbol.checkmark_circle') : $r('sys.symbol.doc'))
        .fontSize(19).fontColor([this.palette().primary])
      Column({ space: 3 }) {
        Text(item.title).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Medium).maxLines(2)
        Text(`${item.kind} · ${item.cached ? '已缓存' : item.status ?? '可查看'}`).fontColor(this.palette().muted).fontSize(10)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      SymbolGlyph(item.can_download ? $r('sys.symbol.arrow_down_circle') : $r('sys.symbol.chevron_right')).fontSize(17).fontColor([this.palette().muted])
    }.width('100%').padding(13).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).borderRadius(14)
      .onClick(async () => {
        if (item.can_download === true) {
          try {
            await this.onCacheContent(this.course.id, item.id);
            item.cached = true;
            this.detailContent = [...this.detailContent];
          } catch (_) {
            this.detailError = '资料获取失败，请稍后重试';
          }
        }
      })
  }

  build() {
    Column() {
      SecondaryHeader({ title: '课程详情', subtitle: '查看课程基本信息', darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 13 }) {
          Stack({ alignContent: Alignment.BottomStart }) {
            Column().width('100%').height(180).linearGradient({ angle: 135, colors: [['#FF5368E8', 0.0], ['#FF7586F5', 1.0]] })
            Column({ space: 6 }) {
              Text(this.course.name).fontColor('#FFFFFFFF').fontSize(24).fontWeight(FontWeight.Bold).maxLines(2)
              Text(this.course.code ?? '课程').fontColor('#DFFFFFFF').fontSize(12)
            }.width('100%').padding({ left: 18, right: 18, bottom: 18 }).alignItems(HorizontalAlign.Start)
          }.width('100%').height(180).borderRadius(20).clip(true)
          Column() {
            this.DetailRow($r('sys.symbol.book'), '课程名称', this.course.name)
            Divider().color(this.palette().line)
            this.DetailRow($r('sys.symbol.person'), '授课教师', this.course.teacher_name ?? '教师待定')
            Divider().color(this.palette().line)
            this.DetailRow($r('sys.symbol.calendar'), '开课学期', this.course.semester ?? '本学期')
            Divider().color(this.palette().line)
            this.DetailRow($r('sys.symbol.info_circle'), '课程代码', this.course.code ?? '—')
            Divider().color(this.palette().line)
            this.DetailRow($r('sys.symbol.info_circle'), '课程状态', this.course.status ?? '在修')
          }.width('100%').padding({ left: 14, right: 14 }).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).borderRadius(18)
          Button(this.detailLoading ? '同步中…' : '同步学习通课程内容')
            .width('100%').height(46).fontSize(13).fontWeight(FontWeight.Bold)
            .enabled(!this.detailLoading).onClick(() => this.loadContent(true))
          this.KnowledgePanel()
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
          ForEach(this.filteredContent(), (item: CourseContentItem) => this.ContentItem(item), (item: CourseContentItem) => item.id)
          if ((this.course.description ?? '').length > 0) {
            Column({ space: 6 }) {
              Text('课程介绍').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold)
              Text(this.course.description ?? '').fontColor(this.palette().muted).fontSize(12).lineHeight(20)
            }.width('100%').padding(14).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).borderRadius(16)
          }
        }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
      }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
